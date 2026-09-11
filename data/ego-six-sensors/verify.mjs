import fs from 'node:fs';import assert from 'node:assert/strict';import {chromium} from '@playwright/test';
const expected=['cabin_overview','front_radar','front_rgb','gnss','imu','roof_lidar'].sort();
const base='http://128.175.213.232:8095';
const browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 let s=await (await page.request.get(base+'/api/status')).json();assert.equal(s.phase,'connected');assert.equal(s.recovery_operation.stage,'ready');assert.equal(s.error,null);
 const ego=Object.keys(s.managed).find(k=>s.managed[k].role==='ego');const sensors=s.sensors.filter(v=>v.parent===Number(ego));assert.deepEqual(sensors.map(v=>v.name).sort(),expected);
 const old=JSON.parse(fs.readFileSync('data/ego-six-sensors/before-configuration.json')).actors.find(a=>a.role==='ego');const cabin=sensors.find(v=>v.name==='cabin_overview');
 assert.deepEqual(cabin.mount,old.sensors.find(v=>v.name==='cabin_overview').mount);
 const catalog=await (await page.request.get(base+'/api/catalog')).json();assert.deepEqual(catalog.defaults.map(v=>v.name).sort(),expected);
 const samples=[];
 for(const sensor of sensors){
  const format=sensor.type.startsWith('sensor.lidar.')?'points':'image';
  const r=await page.request.get(base+`/api/preview/${sensor.id}?format=${format}&width=480`,{timeout:15000});assert.ok(r.ok(),await r.text());
  const body=await r.body();assert.ok(body.length>0);samples.push({name:sensor.name,id:sensor.id,frame:Number(r.headers()['x-carla-frame']),bytes:body.length,content_type:r.headers()['content-type']});
 }
 assert.equal(new Set(samples.map(v=>v.frame)).size,1);
 await page.goto(base);await page.waitForFunction(()=>document.querySelector('#sensor-count').textContent==='6 ego sensors');
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();
 await page.locator('nav button[data-panel="sensorview"]').click();await page.locator('#view-ego').selectOption(ego);
 await page.waitForFunction(()=>document.querySelectorAll('.sensor-tile').length===6&&[...document.querySelectorAll('.sensor-frame')].every(v=>v.textContent.startsWith('Frame ')),{},{timeout:30000});
 await page.screenshot({path:'data/ego-six-sensors/all-six-sensors.png',fullPage:true});
 await page.locator('nav button[data-panel="scenario"]').click();if(!await page.locator('#actor-create').evaluate(n=>n.open))await page.locator('#actor-create > summary').click();
 assert.ok((await page.locator('#vehicle-form').textContent()).includes('Ego default loadout · 6 sensors'));
 // Intercept only the extra test spawn: the existing six native sensors above
 // already validate real capture, without allocating a second full ego rig.
 let payload;await page.route('**/api/command/spawn',async r=>{payload=r.request().postDataJSON();await r.fulfill({json:{id:Number(ego),actor:s.managed[ego]}})});
 await page.locator('#role').selectOption('ego');await page.locator('#model').selectOption(old.model);await page.locator('#spawn-select').selectOption('132');
 const response=page.waitForResponse(r=>r.url().endsWith('/api/command/spawn'));await page.locator('#spawn-button').click();await response;
 assert.equal(payload.role,'ego');assert.ok(!Object.hasOwn(payload,'sensors'),'Browser must use the server default, not override it with just a cabin camera');
 assert.deepEqual(errors,[]);const report={verified:true,ego:Number(ego),model:old.model,sensors:samples,existing_cabin_mount_preserved:true,web_uses_server_defaults:true,worker_count:s.worker_count,errors};
 fs.writeFileSync('data/ego-six-sensors/verification.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}finally{await browser.close()}
