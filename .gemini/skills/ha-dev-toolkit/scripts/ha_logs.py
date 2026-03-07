import sys
import os
import requests
import json

def get_ha_config():
    """Retrieve HA URL and Token from .gemini/settings.json."""
    try:
        settings_path = os.path.join(os.getcwd(), '.gemini/settings.json')
        if not os.path.exists(settings_path):
            return None, None
            
        with open(settings_path, 'r') as f:
            settings = json.load(f)
            
        ha_settings = settings.get('mcpServers', {}).get('homeassistant', {})
        url = ha_settings.get('httpUrl', '').split('/api/mcp')[0]
        token = ha_settings.get('headers', {}).get('Authorization', '').split('Bearer ')[-1]
        
        return url, token
    except Exception:
        return None, None

def fetch_logs(log_type="core", filter_str=None, tail=100):
    url, token = get_ha_config()
    if not url or not token:
        print("Error: Could not find Home Assistant configuration in .gemini/settings.json")
        sys.exit(1)
        
    endpoint = f"{url}/api/hassio/{log_type}/logs"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(endpoint, headers=headers)
        if response.status_code != 200:
            # Fallback to /api/error_log if supervisor is unavailable
            if log_type == "core":
                endpoint = f"{url}/api/error_log"
                response = requests.get(endpoint, headers=headers)
            
        if response.status_code != 200:
            print(f"Error: HTTP {response.status_code} - {response.text}")
            sys.exit(1)
            
        logs = response.text.splitlines()
        
        if filter_str:
            logs = [line for line in logs if filter_str.lower() in line.lower()]
            
        # Tail the logs
        logs = logs[-tail:]
        
        if not logs:
            print(f"No log entries found (type: {log_type}, filter: {filter_str})")
        else:
            print("\n".join(logs))
            
    except Exception as e:
        print(f"Error fetching logs: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch Home Assistant logs")
    parser.add_argument("--type", choices=["core", "supervisor", "host", "dns", "audio"], default="core")
    parser.add_argument("--filter", help="Case-insensitive filter string")
    parser.add_argument("--tail", type=int, default=100, help="Number of lines to return")
    
    args = parser.parse_args()
    fetch_logs(args.type, args.filter, args.tail)
