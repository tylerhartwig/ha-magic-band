---
name: ha-dev-toolkit
description: Advanced debugging and development tools for Home Assistant. Use when you need to fetch Core or Supervisor logs, inspect Home Assistant configuration, check entity states, or call services via the REST API.
---

# Home Assistant Development & Debugging Toolkit

This skill provides a suite of tools for deep debugging and rapid development of Home Assistant integrations.

## Core Workflows

### 1. Diagnostic Logging
Use this workflow to identify why an integration is failing to load or experiencing runtime errors.

- **Fetch Core Logs**: `python3 scripts/ha_logs.py --type core --tail 100`
- **Filter for Integration**: `python3 scripts/ha_logs.py --type core --filter [integration_name]`
- **Check Supervisor Issues**: `python3 scripts/ha_logs.py --type supervisor`

### 2. Configuration Inspection
Verify that components are loaded, paths are correct, and the environment is as expected.

- **Get Full Config**: `python3 scripts/ha_api.py config`
- **Check for Component**: `python3 scripts/ha_api.py config | grep -i [component_name]`

### 3. Entity & State Debugging
Inspect the current state of any entity to verify integration behavior.

- **List All Entities**: `python3 scripts/ha_api.py state`
- **Check Specific Entity**: `python3 scripts/ha_api.py state light.living_room`

### 4. Service Testing
Manually trigger Home Assistant services to test integration logic.

- **Call Service**: `python3 scripts/ha_api.py service light/turn_on --data '{"entity_id": "light.living_room", "brightness": 255}'`

## Bundled Resources

### Scripts
- `scripts/ha_logs.py`: Efficient log fetching and filtering.
- `scripts/ha_api.py`: General-purpose REST API client for config, states, and services.

### Troubleshooting
- **404 Not Found**: Ensure the URL in `.gemini/settings.json` is correct and the `api:` integration is enabled in Home Assistant.
- **401 Unauthorized**: Check if the Bearer token in `.gemini/settings.json` is still valid.
- **Connection Refused**: Verify that the Home Assistant instance is reachable from the current network.
