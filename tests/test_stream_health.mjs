import assert from 'node:assert/strict';
import {streamHealth} from '../static/stream-health.js';
const live={phase:'connected',running:true,last_complete_frame:123};
assert.equal(streamHealth({...live,stream_health:{stage:'sensor',sensor:'front_rgb',elapsed_seconds:8}}).text,'Waiting for front_rgb · 8.0 s');
assert.equal(streamHealth({...live,running:false,stream_health:{stage:'sensor',elapsed_seconds:90}}).text,'Simulation paused');
assert.equal(streamHealth({...live,stream_health:{stage:'complete',elapsed_seconds:.1}}).status,'ready');
assert.equal(streamHealth(live,8).text,'Server response delayed · 8.0 s');
assert.equal(streamHealth({...live,stream_health:{stage:'world',elapsed_seconds:4}}).text,'Waiting for simulation step · 4.0 s');
console.log('Stream health: stalled sensor, world wait, network delay, recovery and pause passed');
