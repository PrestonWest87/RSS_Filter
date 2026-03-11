import feedparser
import requests
from datetime import datetime, timedelta
import re
from src.database import SessionLocal, CloudOutage

# Massively expanded list based on standard service-provider-status-links
CLOUD_FEEDS = {
    "AWS": "https://status.aws.amazon.com/rss/all.rss",
    "Google Cloud": "https://status.cloud.google.com/en/feed.atom",
    "Azure": "https://azurestatuscdn.azureedge.net/en-us/status/feed/",
    "Cisco Umbrella": "https://status.umbrella.com/history.rss",
    "Cisco Webex": "https://status.webex.com/history.rss",
    "Cisco Meraki": "https://status.meraki.net/history.rss",
    "Cloudflare": "https://www.cloudflarestatus.com/history.rss",
    "GitHub": "https://www.githubstatus.com/history.rss",
    "Slack": "https://status.slack.com/feed/rss",
    "Zoom": "https://status.zoom.us/history.rss",
    "Atlassian": "https://developer.status.atlassian.com/history.rss",
    "Datadog": "https://status.datadoghq.com/history.rss",
    "PagerDuty": "https://status.pagerduty.com/history.rss",
    "Twilio": "https://status.twilio.com/history.rss",
    "Okta": "https://status.okta.com/history.rss",
    "Zscaler": "https://trust.zscaler.com/feed",
    "CrowdStrike": "https://status.crowdstrike.com/history.rss",
    "Mimecast": "https://status.meraki.net/history.rss"
}

def extract_service_name(provider, title):
    """Heuristic extractor to pull the specific service name out of chaotic RSS titles."""
    clean_title = title.replace("[Investigating]", "").replace("[Resolved]", "").replace("[Update]", "").strip()
    
    # Common delimiters used by Statuspage.io and AWS
    delimiters = [' - ', ': ', ' | ']
    for delim in delimiters:
        if delim in clean_title:
            return clean_title.split(delim)[0].strip()
            
    # Fallbacks if no delimiter is found
    if provider == "AWS": return "AWS Infrastructure"
    if provider == "Google Cloud": return "Google Cloud Platform"
    if provider == "Azure": return "Microsoft Azure"
    return "General/Multiple Services"

def fetch_cloud_outages():
    print(f"☁️ [CLOUD WORKER] Fetching status feeds from {len(CLOUD_FEEDS)} providers...")
    session = SessionLocal()
    added_count = 0
    resolved_count = 0
    failed_providers = []
    
    try:
        recent_cutoff = datetime.utcnow() - timedelta(days=7)
        
        for provider, url in CLOUD_FEEDS.items():
            try:
                # Use requests with a strict timeout to prevent feedparser from hanging indefinitely
                response = requests.get(url, timeout=10)
                if response.status_code != 200:
                    raise Exception(f"HTTP {response.status_code}")
                    
                feed = feedparser.parse(response.content)
                
                for entry in feed.entries:
                    published_tuple = entry.get('published_parsed')
                    if published_tuple:
                        updated_at = datetime(*published_tuple[:6])
                    else:
                        updated_at = datetime.utcnow()
                        
                    if updated_at < recent_cutoff:
                        continue 
                    
                    title = entry.get('title', 'Unknown Alert')
                    link = entry.get('link', '')
                    description = entry.get('description', '')
                    
                    # Enhanced Resolution Logic covering multiple platform defaults
                    text_to_check = (title + " " + description).upper()
                    resolved_keywords = ["[RESOLVED]", "RESOLVED", "OPERATIONAL", "COMPLETED", "MITIGATED"]
                    is_resolved = any(kw in text_to_check for kw in resolved_keywords)
                        
                    service = extract_service_name(provider, title)
                        
                    exists = session.query(CloudOutage).filter_by(
                        provider=provider, 
                        title=title, 
                        updated_at=updated_at
                    ).first()
                    
                    if not exists:
                        new_outage = CloudOutage(
                            provider=provider,
                            service=service,
                            title=title,
                            description=description,
                            link=link,
                            is_resolved=is_resolved,
                            updated_at=updated_at
                        )
                        session.add(new_outage)
                        added_count += 1
                    else:
                        if is_resolved and not exists.is_resolved:
                            exists.is_resolved = True
                            exists.updated_at = updated_at
                            resolved_count += 1
                            
            except Exception as e:
                failed_providers.append(provider)
                print(f"⚠️ [CLOUD WORKER] Skipping {provider} due to timeout/error: {e}")
                continue # Gracefully skip to the next provider

        # Self-cleaning: Purge resolved incidents older than 3 days
        purge_cutoff = datetime.utcnow() - timedelta(days=3)
        session.query(CloudOutage).filter(CloudOutage.is_resolved == True, CloudOutage.updated_at < purge_cutoff).delete()
        
        session.commit()
        
        summary = f"✅ [CLOUD WORKER] Added {added_count} new alerts. Marked {resolved_count} resolved."
        if failed_providers:
            summary += f" (Failed to reach: {', '.join(failed_providers)})"
        print(summary)
        
    except Exception as e:
        print(f"❌ [CLOUD WORKER] Critical failure in cloud worker: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    fetch_cloud_outages()