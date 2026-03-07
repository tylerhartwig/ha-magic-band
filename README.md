# Disney MagicBand+ & Popcorn Bucket for Home Assistant

Control your Disney MagicBand+ and Popcorn Buckets directly from Home Assistant! This integration uses the **Amazon Gadgets BLE Protocol** to communicate with devices.

## Features
- **Connected Mode**: Full RGB color and brightness control for individual devices.
- **Broadcaster Mode**: Trigger park-style "Glow with the Show" advertisements.
- **Presence Detection**: Track device proximity (RSSI) and connection status.
- **Manual Entry**: Manually add devices by BLE address if discovery is disabled or restricted.

## Prerequisites
- **Bluetooth Hardware**: A built-in Bluetooth adapter or an **ESPHome Bluetooth Proxy**.
- **HACS**: Home Assistant Community Store installed.

## Installation
1. Add this URL to your **HACS Custom Repositories**.
2. Search for "Disney MagicBand+" and click **Download**.
3. Restart Home Assistant.
4. Go to **Settings > Devices & Services > Add Integration** and search for "Disney MagicBand+".

## Virtual Testing (MacOS Simulator)
If you don't have a physical device, you can run the native macOS simulator included in this repository:

```bash
# Install dependencies
pip install pyobjc-core pyobjc-framework-CoreBluetooth

# Run the simulator
python3 custom_components/ha_magic_band/simulators/magic_bucket_mac.py
```

The simulator will advertise as `MB_SIM`. In Home Assistant, you can add it via **Manual Address Entry** using the UUID-style address shown in your system's Bluetooth scanner (like nRF Connect).

## Protocol Details
- **Service UUID**: `FEE8` (Amazon Gadgets)
- **Write Characteristic**: `f04eb177-3005-43a7-ac61-a390ddf83076`
- **Handshake**: `FE 03 01 00 00`
- **Color Packet**: `FE 03 04 [Length] 01 [R] [G] [B] [Brightness]`
