const bleno = require('bleno');

const SERVICE_UUID = 'fee8'; // Amazon Gadget Service
const CHAR_WRITE_UUID = 'f04eb177300543a7ac61a390ddf83076';
const CHAR_NOTIFY_UUID = '2beea05b18794bb48a2f72641f82420b';

console.log('--- Disney MagicBand+ / Popcorn Bucket SIM (macOS) ---');

bleno.on('stateChange', function(state) {
  console.log('on -> stateChange: ' + state);
  if (state === 'poweredOn') {
    bleno.startAdvertising('MagicBucket_SIM', [SERVICE_UUID]);
  } else {
    bleno.stopAdvertising();
  }
});

bleno.on('advertisingStart', function(error) {
  console.log('on -> advertisingStart: ' + (error ? 'error ' + error : 'success'));
  if (!error) {
    bleno.setServices([
      new bleno.PrimaryService({
        uuid: SERVICE_UUID,
        characteristics: [
          new bleno.Characteristic({
            uuid: CHAR_WRITE_UUID,
            properties: ['write', 'writeWithoutResponse'],
            onWriteRequest: function(data, offset, withoutResponse, callback) {
              console.log('\n--- [COMMAND RECEIVED] ---');
              console.log('Hex: ' + data.toString('hex'));
              console.log('Bytes: ' + JSON.stringify(Array.from(data)));
              console.log('--------------------------');
              callback(this.RESULT_SUCCESS);
            }
          }),
          new bleno.Characteristic({
            uuid: CHAR_NOTIFY_UUID,
            properties: ['notify', 'read'],
            value: Buffer.from([0x00])
          })
        ]
      })
    ]);
  }
});

bleno.on('accept', function(clientAddress) {
  console.log('Home Assistant connected! (Address: ' + clientAddress + ')');
});

bleno.on('disconnect', function(clientAddress) {
  console.log('Home Assistant disconnected.');
});
