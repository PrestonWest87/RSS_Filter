import requests
from datetime import datetime, timedelta
import uuid
from src.database import SessionLocal, RegionalHazard, MonitoredLocation

def log_print(msg):
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] [INFRA] {msg}")

def fetch_spc_outlooks(session):
    """Fetches SPC Day 1 Convective Outlook and maps risk to custom locations."""
    try:
        from shapely.geometry import shape, Point
        
        url = "https://www.spc.noaa.gov/products/outlook/day1otlk_cat.lyr.geojson"
        headers = {'User-Agent': 'Mozilla/5.0 (NOC_Fusion_Center)'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            log_print(f"❌ Failed to fetch SPC. HTTP {response.status_code}")
            return

        geojson_data = response.json()
        features = geojson_data.get('features', [])
        log_print(f"✅ Downloaded SPC GeoJSON. Found {len(features)} risk polygons.")
        
        risk_levels = {"HIGH": 6, "MDT": 5, "ENH": 4, "SLGT": 3, "MRGL": 2, "TSTM": 1, "None": 0}
        locations = session.query(MonitoredLocation).all()
        
        if not locations:
            log_print("⚠️ No tracked locations found in DB. Skipping geospatial math.")
            return

        # Pre-compile the polygons for speed
        risk_polygons = []
        for feature in features:
            props = feature.get('properties', {})
            geom = feature.get('geometry')
            label = props.get('LABEL', 'None')
            
            if geom and label in risk_levels:
                poly = shape(geom)
                risk_polygons.append((label, risk_levels[label], poly))

        # Check every location against the polygons
        updated_count = 0
        for loc in locations:
            point = Point(loc.lon, loc.lat) # Shapely uses (lon, lat) format
            max_risk_name = "None"
            max_risk_val = 0
            
            for label, r_val, poly in risk_polygons:
                if point.within(poly) and r_val > max_risk_val:
                    max_risk_val = r_val
                    max_risk_name = label
            
            if loc.current_spc_risk != max_risk_name:
                loc.current_spc_risk = max_risk_name
                updated_count += 1
            loc.last_updated = datetime.utcnow()
            
        session.commit()
        log_print(f"✅ SPC Geospatial math complete. {updated_count} locations updated risk status.")

    except Exception as e:
        log_print(f"❌ SPC Fetch Error: {e}")
        session.rollback()

def fetch_nws_warnings(session):
    """Fetches active NWS alerts for the operational region (Arkansas)."""
    try:
        url = "https://api.weather.gov/alerts/active?area=AR"
        headers = {'User-Agent': 'Mozilla/5.0 (NOC_Fusion_Center)'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200: 
            return
            
        data = response.json()
        features = data.get('features', [])
        
        # Clear out old AR alerts so they don't pile up endlessly
        session.query(RegionalHazard).delete()
        
        added = 0
        for f in features:
            props = f.get('properties', {})
            haz = RegionalHazard(
                hazard_id=props.get('id', str(uuid.uuid4())),
                hazard_type=props.get('event', 'Unknown'),
                severity=props.get('severity', 'Unknown'),
                title=props.get('headline', 'Weather Alert'),
                description=props.get('description', ''),
                location=props.get('areaDesc', 'Arkansas'),
                updated_at=datetime.utcnow()
            )
            session.add(haz)
            added += 1
            
        session.commit()
        log_print(f"✅ NWS Sync complete. Tracking {added} active regional alerts.")
    except Exception as e:
        log_print(f"❌ NWS Fetch Error: {e}")
        session.rollback()

def fetch_regional_hazards():
    """Main wrapper for infrastructure telemetry."""
    session = SessionLocal()
    try:
        fetch_nws_warnings(session)
        fetch_spc_outlooks(session)
    finally:
        session.close()