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
import traceback

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
        # Use a strong reference to manager
        self.manager = CBPeripheralManager.alloc().initWithDelegate_queue_(self, None)
        return self

    def peripheralManagerDidUpdateState_(self, manager):
        state = manager.state()
        print(f"Bluetooth State updated: {state}")
        if state == 5: # Powered On
            print("Bluetooth is ON. Setting up services...")
            self.setup_service()
        elif state == 4:
            print("Bluetooth is OFF.")
        elif state == 3:
            print("Bluetooth is UNAUTHORIZED.")
        elif state == 2:
            print("Bluetooth is UNSUPPORTED.")

    def setup_service(self):
        try:
            print(f"Defining Service {SERVICE_UUID}...")
            service = CBMutableService.alloc().initWithType_primary_(SERVICE_UUID, True)
            
            print("Defining Characteristics...")
            char_write = CBMutableCharacteristic.alloc().initWithType_properties_value_permissions_(
                CHAR_WRITE_UUID, 0x0C, None, 0x02 # Write | WriteWithoutResponse, Writable
            )
            char_notify = CBMutableCharacteristic.alloc().initWithType_properties_value_permissions_(
                CHAR_NOTIFY_UUID, 0x12, None, 0x01 # Notify | Read, Readable
            )
            
            service.setCharacteristics_([char_write, char_notify])
            print("Adding Service to Manager...")
            self.manager.addService_(service)
        except Exception as e:
            print(f"Error in setup_service: {e}")
            traceback.print_exc()

    def peripheralManager_didAddService_error_(self, manager, service, error):
        if error:
            print(f"Error adding service: {error}")
        else:
            print("Service successfully added. Starting advertisement...")
            # Use 16-bit FEE8 for advertisement
            adv_data = {
                CBAdvertisementDataLocalNameKey: "MagicBucket_SIM",
                CBAdvertisementDataServiceUUIDsKey: [CBUUID.UUIDWithString_("FEE8")]
            }
            self.manager.startAdvertising_(adv_data)

    def peripheralManagerDidStartAdvertising_error_(self, manager, error):
        if error:
            print(f"Advertisement failed: {error}")
        else:
            print("--- SUCCESS: MagicBucket_SIM IS NOW ADVERTISING ---")
            print("Keep this process running.")

    def peripheralManager_central_didSubscribeToCharacteristic_(self, manager, central, characteristic):
        print(f"Central {central.identifier()} subscribed to {characteristic.UUID()}")

    def peripheralManager_didReceiveWriteRequests_(self, manager, requests):
        for request in requests:
            print(f"Write request received: {request.value().hex()}")
            manager.respondToRequest_withResult_(request, 0)

if __name__ == "__main__":
    try:
        peripheral = MagicBandPeripheral.alloc().init()
        print("Entering run loop...")
        run_loop = NSRunLoop.currentRunLoop()
        while True:
            run_loop.runMode_beforeDate_("NSDefaultRunLoopMode", NSDate.dateWithTimeIntervalSinceNow_(1.0))
    except Exception as e:
        print(f"Fatal error in main: {e}")
        traceback.print_exc()
    finally:
        print("Simulator exiting.")
