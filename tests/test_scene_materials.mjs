import assert from 'node:assert/strict';import * as THREE from 'three';import {sceneMaterial} from '../static/scene-materials.js';
const texture=new THREE.Texture();
for(const color of ['White','Yellow']){const paint=sceneMaterial({name:'MI_Road_Asphalt_B_LaneMarking'+color,blend:'OPAQUE'},'roads',null);assert(paint.isMeshBasicMaterial);assert(paint.polygonOffset&&paint.polygonOffsetFactor<0);assert(paint.depthTest&&paint.depthWrite);assert(!paint.transparent);assert(paint.color.r>.7,'paint remains legible in dim weather')}
const fence=sceneMaterial({name:'Fence',blend:'BLEND_MASKED'},'street',texture);assert.equal(fence.alphaTest,.4);assert.equal(fence.map,texture);
const glass=sceneMaterial({name:'Glass',blend:'BLEND_TRANSLUCENT'},'buildings',texture);assert(glass.transparent);assert(!glass.depthWrite);assert(glass.opacity<1);
const road=sceneMaterial({name:'Asphalt',blend:'OPAQUE'},'roads',texture);assert.equal(road.map,texture);assert(!road.polygonOffset);assert(!road.transparent);
console.log('PASS: paint contrast/depth separation, masked non-vegetation textures, translucent surfaces, textured asphalt');
