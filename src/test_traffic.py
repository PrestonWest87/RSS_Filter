import requests
import random
import time

# Some messy aliases that the ML will have to figure out
NODES = [
    "BENTON-DC-CORE-RTR-01", 
    "LITTLE-ROCK-BRANCH-FW", 
    "HOTSPRINGSVillageEast-EDGE-SW04", 
    "FAYETTEVILLE-WLC-01"
]

DOWN_STATES = ["DOWN", "FATAL", "CRITICAL", "TIMEOUT"]
UP_STATES = ["UP", "RESOLVED", "CLEAR", "OK", "OPERATIONAL"]

def generate_random_payload():
    node = random.choice(NODES)
    
    # 40% chance this payload is a resolution, 60% chance it's an alert
    is_resolution = random.random() > 0.6 
    
    if is_resolution:
        # Wildly formatted UP payload
        return {
            "target_device": node,
            "current_state": random.choice(UP_STATES),
            "diagnostics": "BGP Session restored. Link stable.",
            "meta_info": {"source": "SolarWinds Orchestrator", "ip": "10.0.0.1"}
        }
    else:
        # Wildly formatted DOWN payload
        return {
            "host_system": node,
            "level": random.choice(DOWN_STATES),
            "alert_issue": "Interface GigabitEthernet0/0 dropped packets",
            "ipv4": f"10.24.{random.randint(1,255)}.{random.randint(1,255)}"
        }

def start_chaos():
    print("🚀 Starting Chaos Webhook Generator...")
    print("Press Ctrl+C to stop.")
    
    while True:
        payload = generate_random_payload()
        is_up = payload.get("current_state") in UP_STATES
        
        try:
            # Assumes you are running this on the same machine hosting the Docker cluster
            r = requests.post("http://192.168.1.148:8100/webhook/solarwinds", json=payload, timeout=3)
            
            if is_up:
                print(f"🟢 Sent RESOLUTION for {payload.get('target_device')} -> HTTP {r.status_code}")
            else:
                print(f"🔴 Sent ALERT for {payload.get('host_system')} -> HTTP {r.status_code}")
                
        except Exception as e:
            print(f"❌ Failed to reach webhook listener: {e}")
            
        # Sleep for a random amount of time before firing the next webhook
        time.sleep(random.randint(5, 15))

if __name__ == "__main__":
    start_chaos()