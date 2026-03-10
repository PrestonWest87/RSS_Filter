import re

# Pre-compile regex for extreme multiprocessing speed
REGEX_IPV4 = re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b')
REGEX_SHA256 = re.compile(r'\b[A-Fa-f0-9]{64}\b')
REGEX_MD5 = re.compile(r'\b[A-Fa-f0-9]{32}\b')
REGEX_CVE = re.compile(r'\bCVE-\d{4}-\d{4,7}\b', re.IGNORECASE)

# Common false positives to ignore
IGNORE_IPS = {'0.0.0.0', '127.0.0.1', '8.8.8.8', '1.1.1.1', '255.255.255.255'}

def is_private_ip(ip):
    """Filters out internal routing IPs."""
    parts = ip.split('.')
    if parts[0] == '10': return True
    if parts[0] == '172' and 16 <= int(parts[1]) <= 31: return True
    if parts[0] == '192' and parts[1] == '168': return True
    if parts[0] == '169' and parts[1] == '254': return True
    return False

def extract_all_iocs(text):
    """Scans raw text and returns a deduplicated list of dicts with IOCs."""
    if not text: return []
    
    iocs = []
    seen = set()

    for ip in REGEX_IPV4.findall(text):
        if ip not in IGNORE_IPS and not is_private_ip(ip) and ip not in seen:
            iocs.append({"type": "IPv4", "value": ip}); seen.add(ip)

    for sha in REGEX_SHA256.findall(text):
        if sha not in seen:
            iocs.append({"type": "SHA256", "value": sha.lower()}); seen.add(sha)

    for md5 in REGEX_MD5.findall(text):
        if md5 not in seen:
            iocs.append({"type": "MD5", "value": md5.lower()}); seen.add(md5)

    for cve in REGEX_CVE.findall(text):
        cve_upper = cve.upper()
        if cve_upper not in seen:
            iocs.append({"type": "CVE", "value": cve_upper}); seen.add(cve_upper)

    return iocs