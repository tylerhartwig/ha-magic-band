import objc
from CoreBluetooth import (
    CBPeripheralManager,
    CBMutableService,
    CBMutableCharacteristic,
    CBUUID,
    CBAdvertisementDataLocalNameKey,
    CBAdvertisementDataServiceUUIDsKey
)
from Foundation import NSObject, NSRunLoop, NSDate
import sys
import time

print("--- MAGIC BUCKET MAC SIMULATOR STARTING ---")

# MagicBand+ UUIDs
SERVICE_UUID = CBUUID.UUIDWithString_("FEE8")
CHAR_WRITE_UUID = CBUUID.UUIDWithString_("f04eb177-3005-43a7-ac61-a390ddf83076")
CHAR_NOTIFY_UUID = CBUUID.UUIDWithString_("2beea05b-1879-4bb4-8a2f-72641f82420b")

class MagicBandPeripheral(NSObject):
    def init(self):
        self = objc.super(MagicBandPeripheral, self).init()
        if self is None: return None
        print("Initializing CBPeripheralManager...")
        self.manager = CBPeripheralManager.alloc().initWithDelegate_queue_(self, None)
        return self

    def peripheralManagerDidUpdateState_(self, manager):
        state = manager.state()
        print(f"Peripheral Manager State Updated: {state}")
        if state == 5: # Powered On
            print("Bluetooth Powered On. Adding Service...")
            self.setup_service()
        elif state == 4:
            print("Bluetooth Powered Off.")
        elif state == 3:
            print("Bluetooth Unauthorized. Check system permissions.")
        else:
            print(f"Other state: {state}")

    def setup_service(self):
        print(f"Creating service {SERVICE_UUID}...")
        service = CBMutableService.alloc().initWithType_primary_(SERVICE_UUID, True)
        
        print("Adding characteristics...")
        char_write = CBMutableCharacteristic.alloc().initWithType_properties_value_permissions_(
            CHAR_WRITE_UUID, 0x0C, None, 0x02 # Write | WriteWithoutResponse, Writable
        )
        char_notify = CBMutableCharacteristic.alloc().initWithType_properties_value_permissions_(
            CHAR_NOTIFY_UUID, 0x12, None, 0x01 # Notify | Read, Readable
        )
        
        service.setCharacteristics_([char_write, char_notify])
        self.manager.addService_(service)

    def peripheralManager_didAddService_error_(self, manager, service, error):
        if error:
            print(f"Error adding service: {error}")
        else:
            print("Service Added. Starting Advertisement...")
            adv_data = {
                CBAdvertisementDataLocalNameKey: "MagicBucket_SIM",
                CBAdvertisementDataServiceUUIDsKey: [SERVICE_UUID]
            }
            self.manager.startAdvertising_(adv_data)

    def peripheralManagerDidStartAdvertising_error_(self, manager, error):
        if error:
            print(f"Error advertising: {error}")
        else:
            print("--- MagicBucket SIM is ADVERTISING ---")
            print("Home Assistant should discover it as 'MagicBucket_SIM'")

    def peripheralManager_central_didSubscribeToCharacteristic_(self, manager, central, characteristic):
        print(f"Central connected and subscribed: {central.identifier()}")

    def peripheralManager_central_didUnsubscribeFromCharacteristic_(self, manager, central, characteristic):
        print(f"Central unsubscribed: {central.identifier()}")

    def peripheralManager_didReceiveWriteRequests_(self, manager, requests):
        print(f"Received {len(requests)} write requests")
        for request in requests:
            data = request.value()
            print(f"\n[COMMAND RECEIVED] Hex: {data.hex()}")
            manager.respondToRequest_withResult_(request, 0)

if __name__ == "__main__":
    peripheral = MagicBandPeripheral.alloc().init()
    print("Entering Run Loop. Press Ctrl+C to stop.")
    try:
        while True:
            NSRunLoop.currentRunLoop().runMode_beforeDate_(
                "NSDefaultRunLoopMode", 
                NSDate.dateWithTimeIntervalSinceNow_(1.0)
            )
    except KeyboardInterrupt:
        print("Stopping Simulator...")
