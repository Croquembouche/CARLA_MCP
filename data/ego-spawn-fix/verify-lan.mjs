import fs from 'node:fs';import assert from 'node:assert/strict';import {chromium} from '@playwright/test';
const base='http://128.175.213.232:8095';
const browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
async function command(action,data={}){const r=await page.request.post(base+'/api/command/'+action,{data,headers:{Origin:base,'X-Control-Client':'carla-control-center'},timeout:180000});assert.ok(r.ok(),await r.text());return r.json()}
let ego,tempExternal,success=false;
try{
 const map=await (await page.request.get(base+'/api/map')).json();
 const external=await command('spawn',{role:'ego',planner:'external',model:'vehicle.lincoln.mkz_interior',spawn:map.spawn_points.find(p=>p.index===132),sensors:[]});tempExternal=external.id;
 await command('step');await command('delete',{id:tempExternal});tempExternal=undefined;
 console.log('External-planner spawn and first tick passed');
 await page.goto(base);await page.waitForFunction(()=>document.querySelector('#actor-count').textContent==='30',{},{timeout:30000});
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();
 await page.locator('nav button[data-panel="scenario"]').click();await page.locator('#actor-create > summary').click();
 await page.locator('#role').selectOption('ego');await page.locator('#model').selectOption('vehicle.lincoln.mkz_interior');await page.locator('#planner').selectOption('tm');await page.locator('#spawn-select').selectOption('131');
 const response=page.waitForResponse(r=>r.url().endsWith('/api/command/spawn')&&r.request().method()==='POST',{timeout:240000});
 await page.locator('#spawn-button').click();const r=await response;assert.ok(r.ok(),await r.text());const spawn=await r.json();ego=spawn.id;console.log('LAN EGO SPAWNED',ego);
 const request=r.request(),headers=await request.allHeaders();assert.equal(headers.origin,base);assert.equal(headers['x-control-client'],'carla-control-center');
 let s=await (await page.request.get(base+'/api/status')).json();assert.equal(s.managed[ego].role,'ego');assert.equal(s.managed[ego].planner,'tm');assert.equal(s.error,null);
 const sensors=s.sensors.filter(v=>v.parent===ego);assert.equal(sensors.length,1);assert.equal(sensors[0].name,'cabin_overview');
 for(let i=0;i<4;i++)await command('step');
 s=await (await page.request.get(base+'/api/status')).json();assert.equal(s.error,null);assert.equal(s.vehicle_lighting.status,'ready');
 // Fetch the real completed camera sample from the same network origin.
 const preview=await page.request.get(base+'/api/preview/'+sensors[0].id+'?width=640',{timeout:15000});assert.ok(preview.ok(),await preview.text());fs.writeFileSync('data/ego-spawn-fix/cabin-preview.jpg',await preview.body());
 await page.locator('nav button[data-panel="sensorview"]').click();await page.locator('#view-ego').selectOption(String(ego));
 await page.waitForFunction(()=>document.querySelector('.sensor-frame')?.textContent.startsWith('Frame '),{},{timeout:30000});
 await page.screenshot({path:'data/ego-spawn-fix/lan-ego-sensors.png',fullPage:true});assert.deepEqual(errors,[]);
 const report={verified:true,origin:base,actor:ego,model:'vehicle.lincoln.mkz_interior',planner:'tm',external_planner_spawn_verified:true,cabin_sensor:sensors[0].id,worker_count:s.worker_count,frame:s.frame,lighting:s.vehicle_lighting,errors};
 fs.writeFileSync('data/ego-spawn-fix/lan-verification.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));success=true;
}finally{
 // A successful ego is the user's requested vehicle and remains in the scene.
 if(ego!==undefined&&!success)await command('delete',{id:ego});
 if(tempExternal!==undefined)await command('delete',{id:tempExternal});
 await browser.close();
}
