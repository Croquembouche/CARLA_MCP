import assert from 'node:assert/strict';import {repairUV} from '../static/scene-attributes.js';
const p=new Float32Array([2,3,4,5,6,7]),uv=new Float32Array([NaN,Infinity,.25,.75]);assert.equal(repairUV(p,uv),2);assert.deepEqual([...uv],[2,4,.25,.75]);assert.equal(repairUV(p,uv),0);console.log('PASS: undefined UVs get a finite planar fallback while valid coordinates stay exact');
