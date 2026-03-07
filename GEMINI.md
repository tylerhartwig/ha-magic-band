# Project: Disney MagicBand+ & Popcorn Bucket HA Integration

## Current State (March 7, 2026)
We have completed the core implementation of a Home Assistant HACS integration (`ha_magic_band`). The integration supports both **Connected Mode** (individual control) and **Broadcaster Mode** (park-style "Glow with the Show" advertisements).

### Latest Version: `v1.0.2`
- **Fixed**: Version mismatch between `manifest.json` and Git tags.
- **Added**: Comprehensive diagnostic logging in `__init__.py` to capture setup failures.
- **Protocol**: Switched to **Amazon Gadgets BLE Protocol** (the underlying transport for MagicBand+).

## Technical Specifications
### BLE GATT (Connected Mode)
- **Service UUID**: `0000fee8-0000-1000-8000-00805f9b34fb` (Amazon Gadgets)
- **Write Characteristic**: `f04eb177-3005-43a7-ac61-a390ddf83076`
- **Handshake (Discovery)**: `FE 03 01 00 00`
- **Color Packet**: `FE 03 04 [Length] 01 [R] [G] [B] [Brightness]`

### Broadcaster Mode (Passive)
- **Manufacturer ID**: `0x01E5` (Disney)
- **Packet**: `0100000000000000000000000000000000000000` (Ping/Trigger)

## MCP Configuration
We have successfully connected the Home Assistant MCP server to Gemini CLI.
- **URL**: `https://redacted.ha.url/api/mcp`
- **Auth**: Bearer token is stored in `.gemini/settings.json`.
- **Status**: ✓ Connected.

## Next Steps for the Next Session
1. **Push & Update**: The user needs to run `git push origin main --tags` and update the integration to `v1.0.2` in HACS.
2. **Log Diagnosis**: Since the integration was "failing to setup," we need to check the Home Assistant logs (`Settings > System > Logs`) and search for `ha_magic_band`. The new `try-except` block in `__init__.py` will reveal the exact Python traceback.
3. **Simulators**:
    - **Python Simulator**: `magic_bucket_sim.py` has macOS GATT caching issues.
    - **Node.js Simulator**: `magic_bucket.js` is created but needs `xpc-connection` fixed for macOS.
    - **Recommendation**: Use the **nRF Connect** mobile app to simulate a peripheral with service `FEE8` for testing.

## Project Files
- `custom_components/ha_magic_band/`: Core integration.
- `debug_setup.py`: Script to mock HA environment and test initialization logic locally.
