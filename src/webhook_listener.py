import re
import json
from fastapi import FastAPI, Request, HTTPException, Depends
from datetime import datetime
from sqlalchemy.orm import Session
from src.database import SessionLocal, init_db, SolarWindsAlert, MonitoredLocation, NodeAlias, TimelineEvent
import uvicorn
from rapidfuzz import process, fuzz

init_db()
app = FastAPI(title="NOC Fusion Webhook Gateway")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def flatten_dict(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            items.append((new_key, str(v)))
        else:
            items.append((new_key, v))
    return dict(items)

def smart_extract(payload):
    flat = flatten_dict(payload)
    extracted = {
        "node_name": "Unknown",
        "ip_address": "Unknown",
        "severity": "Unknown",
        "event_type": "Unknown",
        "status": "Unknown",
        "is_resolution": False
    }
    
    # 1. IP Extraction
    for v in flat.values():
        if isinstance(v, str):
            ip_match = re.search(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', v)
            if ip_match:
                extracted["ip_address"] = ip_match.group(0)
                break
                
    # 2. Status / Resolution Sniffing
    sev_words = ['critical', 'high', 'medium', 'low', 'warning', 'fatal', 'down', 'offline']
    res_words = ['resolved', 'up', 'ok', 'clear', 'operational', 'recovered', 'restored']
    
    for k, v in flat.items():
        if isinstance(v, str):
            val_lower = v.lower()
            if val_lower in sev_words:
                if extracted["severity"] == "Unknown": extracted["severity"] = v.capitalize()
                if extracted["status"] == "Unknown": extracted["status"] = v.capitalize()
            elif val_lower in res_words:
                extracted["is_resolution"] = True
                extracted["status"] = "Resolved"
                extracted["severity"] = "Info"
            
    # 3. Fuzzy Key Matching
    def fuzzy_get(target_concepts):
        best_k, best_score = None, 0
        for k in flat.keys():
            score = max([fuzz.partial_ratio(k.lower(), c) for c in target_concepts])
            if score > best_score:
                best_score = score; best_k = k
        if best_score >= 70: return str(flat[best_k])
        return "Unknown"

    if extracted["node_name"] == "Unknown": extracted["node_name"] = fuzzy_get(['node', 'device', 'host', 'system', 'server'])
    if extracted["event_type"] == "Unknown": extracted["event_type"] = fuzzy_get(['event', 'alert', 'type', 'issue', 'description'])
    if extracted["severity"] == "Unknown" and not extracted["is_resolution"]: extracted["severity"] = fuzzy_get(['severity', 'level'])
    if extracted["status"] == "Unknown" and not extracted["is_resolution"]: extracted["status"] = fuzzy_get(['status', 'state'])
        
    return extracted

def resolve_location_mapping(node_name: str, db: Session):
    """Upgraded to capture Unknowns for the ML Matrix."""
    if not node_name or node_name == "Unknown": return "Unknown"
    clean_node = str(node_name).upper().replace("-RTR", "").replace("-SW", "").replace("-FW", "")
    
    existing_alias = db.query(NodeAlias).filter(NodeAlias.node_pattern == clean_node).first()
    if existing_alias: return existing_alias.mapped_location_name

    sites = [loc.name for loc in db.query(MonitoredLocation).all()]
    if not sites: 
        # Add to training matrix even if no sites exist yet
        db.add(NodeAlias(node_pattern=clean_node, mapped_location_name="Unknown", confidence_score=0.0, is_verified=False))
        try: db.commit()
        except: db.rollback()
        return "Unknown"

    best_match = process.extractOne(clean_node, sites, scorer=fuzz.partial_ratio)
    if best_match:
        matched_site, confidence = best_match[0], best_match[1]
        if confidence > 60.0:
            db.add(NodeAlias(node_pattern=clean_node, mapped_location_name=matched_site, confidence_score=confidence, is_verified=False))
            try: db.commit()
            except: db.rollback()
            return matched_site
        else:
            # Traps bad matches and sends them to the UI for human correction
            db.add(NodeAlias(node_pattern=clean_node, mapped_location_name="Unknown", confidence_score=confidence, is_verified=False))
            try: db.commit()
            except: db.rollback()
            return "Unknown"
            
    return "Unknown"

@app.post("/webhook/solarwinds")
async def receive_alert(request: Request, db: Session = Depends(get_db)):
    try:
        raw_payload = await request.json()
        parsed = smart_extract(raw_payload)
        mapped_site = resolve_location_mapping(parsed["node_name"], db)

        if parsed["is_resolution"]:
            active_alerts = db.query(SolarWindsAlert).filter(
                SolarWindsAlert.node_name == parsed["node_name"],
                SolarWindsAlert.status != 'Resolved'
            ).all()
            
            if active_alerts:
                for a in active_alerts:
                    a.status = 'Resolved'
                    a.resolved_at = datetime.utcnow()
                db.add(TimelineEvent(source="Webhook", event_type="Resolution", message=f"🟢 Auto-Resolved: {parsed['node_name']} is back online."))
            else:
                db.add(TimelineEvent(source="Webhook", event_type="Info", message=f"🔵 Received CLEAR for {parsed['node_name']}, but no active alert was found."))
            
            db.commit()
            return {"status": "success", "action": "auto-resolved"}

        new_alert = SolarWindsAlert(
            event_type=parsed["event_type"], severity=parsed["severity"], node_name=parsed["node_name"],
            ip_address=parsed["ip_address"], status=parsed["status"], details="Dynamic payload ingested.",
            raw_payload=raw_payload, mapped_location=mapped_site, received_at=datetime.utcnow()
        )
        db.add(new_alert)
        db.add(TimelineEvent(source="Webhook", event_type="Alert", message=f"🔴 CRITICAL: {parsed['node_name']} went offline. ({parsed['event_type']})"))
        db.commit()
        
        return {"status": "success", "action": "alert-created"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8100)