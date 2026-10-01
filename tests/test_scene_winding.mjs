import assert from 'node:assert/strict';import {orientTriangles} from '../static/scene-winding.js';
const p=new Float32Array([0,0,0,0,0,1,1,0,0]),n=new Float32Array([0,1,0,0,1,0,0,1,0]);
const wrong=new Uint32Array([0,2,1]);assert.equal(orientTriangles(p,n,wrong),1);assert.deepEqual([...wrong],[0,1,2]);assert.equal(orientTriangles(p,n,wrong),0);
const missing=new Uint32Array([0,2,1]);assert.equal(orientTriangles(p,new Float32Array(9),missing),0);
console.log('PASS: reversed roof faces corrected, valid faces preserved, correction idempotent');
