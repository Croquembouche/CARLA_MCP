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
 await page.route('**/api/catalog',async route=>{const response=await route.fetch(),data=await response.json();data.vehicles=data.vehicles.filter(v=>v.id!==model);await route.fulfill({response,json:data})});
 await page.goto(base);await page.waitForFunction(()=>document.querySelector('#model').options.length>10);
 assert.equal(await page.locator(`#model option[value="${model}"]`).count(),0);
 await page.unroute('**/api/catalog');
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();
 await page.locator('nav [data-panel="scenario"]').click();
 await page.waitForFunction(id=>!!document.querySelector(`#model option[value="${id}"]`),model);
 if(!await page.locator('#actor-create').evaluate(el=>el.open))await page.locator('#actor-create > summary').click();
 await page.locator('#role').selectOption('ego');await page.locator('#model').selectOption(model);await page.locator('#planner').selectOption('external');
 const label=await page.locator('#model option:checked').textContent();assert.ok(label.includes(model)&&label.includes('finished cabin'));
 if(before.running)await command('pause');
 const point=map.spawn_points.find(p=>!before.actors.some(a=>/^(vehicle\.|walker\.)/.test(a.type)&&Math.hypot(a.pose.x-p.x,a.pose.y-p.y)<12));assert.ok(point,'No clear road point');
 await page.locator('#spawn-select').selectOption(String(point.index));await page.waitForFunction(()=>!document.querySelector('#spawn-button').disabled);
 const response=page.waitForResponse(r=>r.url().endsWith('/api/command/spawn'));
 await page.locator('#spawn-button').click();const result=await response,body=await result.json();assert.ok(result.ok(),JSON.stringify(body));aid=body.id;
 const spawned=await get('/api/status');assert.equal(spawned.actors.find(a=>a.id===aid).type,model);assert.equal(spawned.managed[aid].role,'ego');
 await page.screenshot({path:'data/interior-catalog/spawned.png',fullPage:true});
 assert.deepEqual(errors,[]);
 fs.writeFileSync('data/interior-catalog/verification.json',JSON.stringify({catalogRefresh:true,label,spawnedActor:aid,model,errors},null,2));
 console.log(JSON.stringify({catalogRefresh:true,label,spawnedActor:aid,model}));
}finally{
 if(aid!==null)await command('delete',{id:aid});
 if(before.running)await command('run');
 await browser.close();
 const after=await get('/api/status');assert.deepEqual(Object.keys(after.managed).sort(),Object.keys(before.managed).sort());assert.deepEqual(after.sensors.map(x=>x.id),before.sensors.map(x=>x.id));console.log(JSON.stringify({restoredActorCount:Object.keys(after.managed).length,sensors:after.sensors.length,running:after.running,error:after.error}));
}
