import time
import schedule
import feedparser
import sys
import asyncio
import aiohttp
import concurrent.futures
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from src.database import SessionLocal, Article, FeedSource, RegionalHazard, CloudOutage, ExtractedIOC, engine, init_db
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.cve_worker import fetch_cisa_kev
from src.infra_worker import fetch_regional_hazards
from src.cloud_worker import fetch_cloud_outages
from src.telemetry_worker import run_telemetry_sync

init_db()

def log(message, source="SYSTEM"):
    local_time = datetime.now(ZoneInfo("America/Chicago")).strftime('%H:%M:%S')
    print(f"[{local_time}] [{source.upper()}] {message}")
    sys.stdout.flush()

async def fetch_single_feed(session, f_name, f_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        async with session.get(f_url, headers=headers, timeout=15) as response:
            response.raise_for_status()
            content = await response.text()
            return f_name, content
    except Exception as e:
        log(f"⚠️ Async Fetch Error on {f_name}: {e}", "WORKER")
        return f_name, None

async def fetch_all_feeds(feed_data):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_single_feed(session, f_name, f_url) for _, f_name, f_url in feed_data]
        return await asyncio.gather(*tasks)

_process_scorer = None
def init_process():
    global _process_scorer
    from src.logic import get_scorer
    _process_scorer = get_scorer()

def parse_and_score_feed(f_name, content, known_links):
    from src.config import ALERT_THRESHOLD
    from src.threat_hunter import extract_all_iocs
    from src.categorizer import categorize_text
    
    if not content: return f_name, []
    
    feed = feedparser.parse(content)
    new_articles_data = []
    seen_in_batch = set()

    for entry in feed.entries:
        link = entry.get('link', '')
        if not link or link in known_links or link in seen_in_batch: 
            continue
            
        seen_in_batch.add(link)
        title = entry.get('title', '')
        summary = entry.get('summary', '')
        full_text = f"{title} {summary}"
        
        score, reasons = _process_scorer.score(full_text)
        category = categorize_text(full_text)
        
        extracted_iocs = []
        if score >= 50.0 and category == "Cyber":
            extracted_iocs = extract_all_iocs(full_text)
            
        new_articles_data.append({
            "title": title, "link": link, "summary": summary, "source": f_name,
            "score": float(score), "category": category, "keywords_found": reasons,
            "is_bubbled": (score >= ALERT_THRESHOLD),
            "iocs": extracted_iocs
        })
    return f_name, new_articles_data

def bulk_save_to_db(db_session, arts_data):
    if not arts_data: return 0
    added = 0
    for d in arts_data:
        art = Article(
            title=d["title"], link=d["link"], summary=d["summary"], source=d["source"],
            published_date=datetime.utcnow(), score=d["score"], category=d["category"],
            keywords_found=d["keywords_found"], is_bubbled=d["is_bubbled"]
        )
        db_session.add(art)
        try:
            db_session.flush() # Locks in the ID for the IOC foreign key
            if d.get("iocs"):
                ioc_objs = [
                    ExtractedIOC(
                        article_id=art.id, indicator_type=ioc["type"], indicator_value=ioc["value"]
                    ) for ioc in d["iocs"]
                ]
                db_session.add_all(ioc_objs)
            db_session.commit()
            added += 1
        except IntegrityError:
            db_session.rollback()
    return added

def fetch_feeds(source="Scheduled"):
    log("🚀 Starting ASYNC & MULTIPROCESS feed fetch cycle...", source)
    
    main_session = SessionLocal()
    sources = main_session.query(FeedSource).filter(FeedSource.is_active == True).all()
    feed_data = [(s.id, s.name, s.url) for s in sources]
    
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    known_links_query = main_session.query(Article.link).filter(Article.published_date >= seven_days_ago).all()
    known_links = {link[0] for link in known_links_query}
    
    if not feed_data:
        main_session.close(); return

    results = asyncio.run(fetch_all_feeds(feed_data))
    total_added = 0
    
    with concurrent.futures.ProcessPoolExecutor(initializer=init_process) as executor:
        futures = [executor.submit(parse_and_score_feed, f_name, content, known_links) for f_name, content in results]
        for future in concurrent.futures.as_completed(futures):
            try:
                f_name, extracted_arts = future.result()
                if extracted_arts:
                    added = bulk_save_to_db(main_session, extracted_arts)
                    if added > 0: log(f"✅ {f_name}: Saved {added} new articles.", "WORKER")
                    total_added += added
            except Exception as e:
                log(f"💥 Process cluster crash: {e}", "WORKER")

    log(f"🏁 Cycle complete. Added {total_added} items.", source)
    main_session.close()
        
def run_database_maintenance():
    log("🧹 Running Master Database Maintenance...", "SYSTEM")
    session = SessionLocal()
    try:
        now = datetime.utcnow()
        one_day_ago = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)
        thirty_days_ago = now - timedelta(days=30)
        
        session.query(Article).filter(Article.score <= 0.0).delete()
        session.query(Article).filter(Article.published_date < thirty_days_ago, Article.is_pinned == False).delete()
        session.query(RegionalHazard).filter(RegionalHazard.updated_at < two_days_ago).delete()
        session.query(CloudOutage).filter(CloudOutage.updated_at < one_day_ago).delete()
        
        # Clean up orphaned IOCs
        session.execute(text("DELETE FROM extracted_iocs WHERE article_id NOT IN (SELECT id FROM articles);"))
        session.commit()
    except Exception as e:
        session.rollback()
    finally:
        session.close()
        
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("VACUUM ANALYZE articles;"))
            conn.execute(text("VACUUM ANALYZE extracted_iocs;"))
    except Exception: pass

def job_cisa(): fetch_cisa_kev()
def job_regional(): fetch_regional_hazards()
def job_cloud(): fetch_cloud_outages()

if __name__ == "__main__":
    import threading
    from src.report_worker import start_report_scheduler
    
    threading.Thread(target=start_report_scheduler, daemon=True).start()
    schedule.every(60).minutes.do(run_database_maintenance)
    schedule.every(15).minutes.do(fetch_feeds)
    schedule.every(5).minutes.do(job_regional)
    schedule.every(5).minutes.do(job_cloud)
    schedule.every(5).minutes.do(run_telemetry_sync)
    schedule.every(6).hours.do(job_cisa)
    
    fetch_feeds(source="Worker Boot")
    job_cisa()
    job_regional()
    job_cloud()
    
    log("🚀 Master Scheduler Service Started.", "SYSTEM")
    while True:
        schedule.run_pending()
        time.sleep(1)