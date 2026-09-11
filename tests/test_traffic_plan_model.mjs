import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const m=await import('data:text/javascript;base64,'+Buffer.from(await readFile(new URL('../static/traffic-plan-model.js',import.meta.url))).toString('base64'));
const members=[{id:8,opendrive_id:'left',movement_lanes:{left:{}}},{id:9,opendrive_id:'through',movement_lanes:{straight:{}}}];
const conflicts=[[[8,'left'],[9,'straight']]];
const p={phases:[{name:'Turn',duration:10,states:{8:{left:'Permissive'},9:{straight:'Protected'}}}],yellow_time:3,all_red_time:2};
assert.deepEqual(m.validatePlan(p,members,conflicts),[]);assert.equal(m.cycleDuration(p),15);
const protectedPlan=structuredClone(p);protectedPlan.phases[0].states[8].left='Protected';assert.match(m.validatePlan(protectedPlan,members,conflicts)[0],/conflicts/);
protectedPlan.phases[0].states[9].straight='Stop';assert.deepEqual(m.validatePlan(protectedPlan,members,conflicts),[]);
for(const duration of [NaN,0,601,true,'15']){const bad=structuredClone(p);bad.phases[0].duration=duration;assert.ok(m.validatePlan(bad,members).length)}
const bad=structuredClone(p);bad.phases[0].states[8].right='Protected';assert.match(m.validatePlan(bad,members)[0],/no mapped/);
const file=m.exportPlan('Town',8,members,p,'Morning');const remapped=members.map(a=>({...a,id:a.id+100}));const imported=m.importPlan(file,'Town',remapped,[[[108,'left'],[109,'straight']]]);assert.equal(imported.phases[0].states[108].left,'Permissive');assert.equal(imported.phases[0].states[109].straight,'Protected');
assert.throws(()=>m.importPlan(file,'Another map',members,conflicts),/loaded map/);
assert.throws(()=>m.importPlan(file,'Town',[{...members[0],opendrive_id:'unknown'},members[1]],conflicts),/match/);
const dense=m.normalizePlan(p,members);assert.equal(dense.phases[0].states[8].straight,'Off');assert.equal(dense.phases[0].states[9].right,'Off');
const shuffled=structuredClone(dense);shuffled.phases[0].states[8]={right:'Off',straight:'Off',left:'Permissive'};assert.equal(m.fingerprint(dense),m.fingerprint(shuffled));
assert.equal(m.blankPhase(members).states[8].left,'Stop');assert.equal(m.blankPhase(members).states[8].right,'Off');
console.log('Traffic plan tests passed: protection conflicts, numeric limits, unsupported turns, cycle duration, file remapping, normalized acknowledgments.');
