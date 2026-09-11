import assert from 'node:assert/strict';
import {shouldFetch,cabinPresets} from '../static/sensor-view.js';
const ready={active:true,visible:true,pageVisible:true,busy:false,now:100,nextAt:0,running:true,frame:10,lastFrame:9};
assert.equal(shouldFetch(ready),true);
for(const patch of [{active:false},{visible:false},{pageVisible:false},{busy:true},{nextAt:101},{running:false,frame:9}])assert.equal(shouldFetch({...ready,...patch}),false);
assert.equal(shouldFetch({...ready,running:false}),true);
assert.equal(new Set(Object.values(cabinPresets).map(c=>c.name)).size,3);
assert.ok(cabinPresets.overview.mount.z<1.5 && cabinPresets.overview.mount.yaw===134);
console.log('Sensor view visibility, pause, concurrency and cabin preset checks passed');
