import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base='http://127.0.0.1:8095',model='vehicle.lincoln.mkz_interior';
async function get(path){const r=await fetch(base+path);assert.ok(r.ok);return r.json()}
async function command(action,p={}){const r=await fetch(base+'/api/command/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-Control-Client':'carla-control-center'},body:JSON.stringify(p)});const data=await r.json();assert.ok(r.ok,JSON.stringify(data));return data}
const before=await get('/api/status'),map=await get('/api/map');let aid=null;
const browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(base);await page.waitForFunction(()=>document.querySelector('#model').options.length>10);
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();
 await page.locator('nav [data-panel="scenario"]').click();
 await page.waitForFunction(id=>!!document.querySelector(`#model option[value="${id}"]`),model);
 if(!await page.locator('#actor-create').evaluate(el=>el.open))await page.locator('#actor-create > summary').click();
 await page.locator('#role').selectOption('ego');await page.locator('#model').selectOption(model);await page.locator('#planner').selectOption('external');
 const label=await page.locator('#model option:checked').textContent();assert.ok(label.includes(model)&&label.includes('finished cabin'));
 if(before.running)await command('pause');
 const point=map.spawn_points.find(p=>!before.actors.some(a=>/^(vehicle\.|walker\.)/.test(a.type)&&Math.hypot(a.pose.x-p.x,a.pose.y-p.y)<12));assert.ok(point,'No clear road point');
 await page.locator('#spawn-select').selectOption(String(point.index));await page.waitForFunction(()=>!document.querySelector('#spawn-button').disabled);
 const response=page.waitForResponse(r=>r.url().endsWith('/api/command/spawn'),{timeout:240000});
 await page.locator('#spawn-button').click();const result=await response,body=await result.json();assert.ok(result.ok(),JSON.stringify(body));aid=body.id;
 const spawned=await get('/api/status');assert.equal(spawned.actors.find(a=>a.id===aid).type,model);assert.equal(spawned.managed[aid].role,'ego');
 const cameras=spawned.sensors.filter(s=>s.parent===aid);assert.equal(cameras.length,1);assert.equal(cameras[0].name,'cabin_overview');assert.equal(cameras[0].type,'sensor.camera.rgb');
 const sid=cameras[0].id,requests=[];page.on('request',r=>{if(r.url().includes('/api/preview/'+sid+'?'))requests.push(r.url())});
 await page.locator('nav [data-panel="sensorview"]').click();await page.locator('#view-ego').selectOption(String(aid));
 await page.waitForFunction(()=>document.querySelector('img[alt="cabin_overview live sensor preview"]')?.naturalWidth>0,null,{timeout:60000});
 await page.screenshot({path:'data/auto-cabin/preview.png',fullPage:true});
 const checkbox=page.locator(`[data-sensor="${sid}"]`);await checkbox.uncheck();await page.waitForTimeout(400);const n=requests.length;
 await command('step');await page.waitForTimeout(1200);assert.equal(requests.length,n,'Hidden camera downloaded a preview');assert.equal(await page.locator(`[data-sensor-id="${sid}"]`).count(),0);
 await checkbox.check();await page.waitForFunction(()=>document.querySelector('img[alt="cabin_overview live sensor preview"]')?.naturalWidth>0);assert.ok(requests.length>n);
 assert.deepEqual(errors,[]);
 fs.writeFileSync('data/auto-cabin/verification.json',JSON.stringify({spawnedActor:aid,camera:cameras[0],previewVerified:true,hideStopsDownloads:true,reenableWorks:true,errors},null,2));
 console.log(JSON.stringify({spawnedActor:aid,camera:sid,previewVerified:true,hideStopsDownloads:true,reenableWorks:true}));
}finally{
 if(aid!==null)await command('delete',{id:aid});
 if(before.running)await command('run');
 await browser.close();
 const after=await get('/api/status');assert.deepEqual(Object.keys(after.managed).sort(),Object.keys(before.managed).sort());const loadouts=s=>s.sensors.map(({id,...config})=>config).sort((a,b)=>a.parent-b.parent||a.name.localeCompare(b.name));assert.deepEqual(loadouts(after),loadouts(before));console.log(JSON.stringify({restoredActorCount:Object.keys(after.managed).length,sensors:after.sensors.length,running:after.running,error:after.error}));
}
