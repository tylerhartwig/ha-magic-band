# Project: Disney MagicBand+ & Popcorn Bucket HA Integration

## Current State (March 7, 2026)
The integration is fully functional and has been validated against both Broadcaster and Connected modes. The initial setup failures related to `ColorMode` syntax and GATT connection hangs have been resolved.

### Latest Version: `v1.1.5`
- **Resolved**: Corrected `ColorMode.ON_OFF` to `ColorMode.ONOFF` in `light.py`.
- **Feature**: Added **Manual Address Entry** to the config flow to support environments where BLE discovery is restricted.
- **Fixed**: Refactored `async_setup_entry` to consistently load/unload platforms across all modes, fixing `FAILED_UNLOAD` errors.
- **Verified**: Connected mode successfully validated using a native macOS simulator and confirmed command byte reception.

## Technical Specifications
### BLE GATT (Connected Mode)
- **Service UUID**: `FEE8` (Amazon Gadgets)
- **Write Characteristic**: `f04eb177-3005-43a7-ac61-a390ddf83076`
- **Handshake (Discovery)**: `FE 03 01 00 00`
- **Color Packet**: `FE 03 04 [Length] 01 [R] [G] [B] [Brightness]`

### Broadcaster Mode (Passive)
- **Manufacturer ID**: `0x01E5` (Disney)
- **Packet**: `0100000000000000000000000000000000000000` (Trigger/Ping)

## Tooling & Skills
- **Skill: `ha-dev-toolkit`**: Installed in `.gemini/skills/`. Provides generic Home Assistant debugging tools (logs, states, services) that dynamically use local credentials from `.gemini/settings.json`.
- **Simulator**: `magic_bucket_mac.py` provides a stable, native macOS BLE peripheral simulation using `PyObjC`.

## Repository Hygiene
- **History Purged**: All historical Home Assistant URLs and sensitive Long-Lived Access Tokens have been purged from the git history.
- **Gitignore**: Configured to exclude `.gemini/`, development scripts, and temporary logs while preserving integration metadata.

## Future Work
1. **RSSI Smoothing**: The current RSSI sensor reports raw values; consider adding a moving average filter.
2. **Battery Monitoring**: Investigate GATT characteristics for battery level reporting.
3. **Handshake Verification**: Add logic to verify the device's identification response during the handshake.
