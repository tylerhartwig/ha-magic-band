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

def ha_api_call(endpoint, method="GET", data=None):
    url, token = get_ha_config()
    if not url or not token:
        print("Error: Could not find Home Assistant configuration in .gemini/settings.json")
        sys.exit(1)
        
    full_url = f"{url}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        if method == "GET":
            response = requests.get(full_url, headers=headers)
        elif method == "POST":
            response = requests.post(full_url, headers=headers, json=data)
        else:
            print(f"Error: Unsupported method {method}")
            sys.exit(1)
            
        if response.status_code not in [200, 201]:
            print(f"Error: HTTP {response.status_code} - {response.text}")
            sys.exit(1)
            
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Home Assistant REST API Tool")
    parser.add_argument("action", choices=["config", "state", "service"])
    parser.add_argument("param", nargs='?', help="Entity ID (for state) or domain/service (for service)")
    parser.add_argument("--data", help="JSON string for service data")
    
    args = parser.parse_args()
    
    if args.action == "config":
        result = ha_api_call("/api/config")
        print(json.dumps(result, indent=2))
        
    elif args.action == "state":
        if not args.param:
            # List all states
            result = ha_api_call("/api/states")
            print(json.dumps(result, indent=2))
        else:
            result = ha_api_call(f"/api/states/{args.param}")
            print(json.dumps(result, indent=2))
            
    elif args.action == "service":
        if not args.param or "/" not in args.param:
            print("Error: Service must be in format 'domain/service'")
            sys.exit(1)
        domain, service = args.param.split("/")
        service_data = json.loads(args.data) if args.data else {}
        result = ha_api_call(f"/api/services/{domain}/{service}", method="POST", data=service_data)
        print(json.dumps(result, indent=2))
