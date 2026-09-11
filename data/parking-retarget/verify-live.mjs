import fs from 'node:fs';import assert from 'node:assert/strict';import {chromium} from '@playwright/test';
const browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
const url='http://127.0.0.1:8095';let aid;const command=async(action,data={})=>{
 const r=await page.request.post(url+'/api/command/'+action,{data,headers:{'X-Control-Client':'carla-control-center'}});assert.ok(r.ok(),await r.text());return r.json();
};
try {
 let s=await (await page.request.get(url+'/api/status')).json();assert.equal(s.recovery_operation.stage,'ready');assert.equal(s.running,false);
 const before=JSON.parse(fs.readFileSync('data/parking-retarget/before-configuration.json'));
 const config=await (await page.request.get(url+'/api/configuration')).json();
 const oldEgo=before.actors.find(a=>a.role==='ego'),newEgo=config.actors.find(a=>a.role==='ego');
 assert.equal(newEgo.model,oldEgo.model);assert.deepEqual(newEgo.sensors,oldEgo.sensors);assert.equal(Object.keys(s.managed).length,28);
 const spawn=await command('spawn',{role:'background',model:'vehicle.mini.cooper',parking_space:'P025'});aid=spawn.id;
 await page.goto(url+'/');await page.waitForFunction(()=>document.querySelector('#actor-count').textContent==='29');
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();
 await page.locator('nav button[data-panel="scenario"]').click();await page.locator('#actor-list button[data-id="'+aid+'"]').click();
 const updates=[];
 for(const option of ['68','132']){
  const response=page.waitForResponse(r=>r.url().endsWith('/api/command/destination')&&r.request().method()==='POST');
  await page.locator('#goal-select').selectOption(option);const r=await response;assert.ok(r.ok(),await r.text());const body=await r.json();updates.push(body);
  await page.waitForFunction(()=>!document.querySelector('#goal-select').disabled);
  assert.equal(body.parked,false);assert.equal(body.arrived,false);assert.equal(body.parking_trip.stage,'leaving');
 }
 assert.equal(updates[1].route_update.revision,updates[0].route_update.revision+1);
 assert.notDeepEqual(updates[0].destination,updates[1].destination);
 assert.match(await page.locator('#destination-status').textContent(),/Leaving parking/);
 s=await (await page.request.get(url+'/api/status')).json();const start=s.actors.find(a=>a.id===aid).pose;
 for(let i=0;i<12;i++)await command('step');
 s=await (await page.request.get(url+'/api/status')).json();const end=s.actors.find(a=>a.id===aid).pose;
 const distance=Math.hypot(end.x-start.x,end.y-start.y);assert.ok(distance>.02,'Parked actor did not begin moving');
 assert.equal(s.managed[aid].parking_trip.blocked,null);assert.deepEqual(errors,[]);
 await page.screenshot({path:'data/parking-retarget/deployed-interface.png',fullPage:true});
 const report={verified:true,temporary_actor:aid,paused_dropdown_changes:2,route_revisions:updates.map(u=>u.route_update.revision),stage:s.managed[aid].parking_trip.stage,distance_m:distance,ego_sensors_preserved:newEgo.sensors.length,errors};
 fs.writeFileSync('data/parking-retarget/live-verification.json',JSON.stringify(report,null,2));console.log(report);
}finally{
 if(aid!==undefined)await command('delete',{id:aid});
 await browser.close();
}
