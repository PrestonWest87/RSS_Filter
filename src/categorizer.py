import re

CATEGORIES = {
    "Cyber": re.compile(r'\b(malware|cves?|ransomware|breach(?:es)?|hack(?:er|ers|ed|ing)?|exploit(?:s|ed|ing)?|zero-day|0-day|ddos|phish(?:ing)?|apts?|vulnerab(?:ility|ilities|le)|cyber(?:security|crime|attack)?|threat(?:s)?|infosec|botnet|data leak|credentials?|misconfiguration(?:s)?|backdoor|trojan|spyware|keylogger)\b', re.IGNORECASE),
    
    "Physical/Weather": re.compile(r'\b(weather|flood(?:s|ing)?|tornado(?:es)?|hurricane(?:s)?|earthquake(?:s)?|power grid|outage(?:s)?|storm(?:s)?|warning(?:s)?|hazard(?:s)?|wildfire(?:s)?|tsunami(?:s)?)\b', re.IGNORECASE),
    
    "Geopolitics/News": re.compile(r'\b(government|election(?:s)?|war|military|sanctions|policy|terrorism|kinetic|geopolitical|senate|congress|parliament)\b', re.IGNORECASE)
}

def categorize_text(text):
    """Rapidly assigns a category to an article based on root indicators."""
    if not text: return "General"
    
    for cat, pattern in CATEGORIES.items():
        if pattern.search(text):
            return cat
            
    return "General"