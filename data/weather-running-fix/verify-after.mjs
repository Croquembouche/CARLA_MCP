import fs from 'node:fs';import assert from 'node:assert/strict';import {chromium} from '@playwright/test';
const base='http://128.175.213.232:8095',browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const status=async()=>await(await page.request.get(base+'/api/status')).json();
 const cmd=async(name,p={})=>{const r=await page.request.post(base+'/api/command/'+name,{headers:{'X-Control-Client':'carla-control-center'},data:p,timeout:120000});assert.equal(r.status(),200,await r.text());return await r.json()};
 await page.goto(base);await page.waitForFunction(()=>document.querySelector('#sensor-count')?.textContent==='6 ego sensors');
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();
 await page.locator('nav [data-panel="weather"]').click();const report=[];
 for(const [label,preset] of [['clear-start','clear'],['rain','rain'],['clear-after-rain','clear'],['night','night']]){
  await cmd('run');await page.waitForFunction(()=>document.querySelector('#pause')?.disabled===false);
  const before=await status();assert.equal(before.running,true);
  await page.locator('#weather-preset').selectOption(preset);assert.ok(await page.locator('#apply-weather').isEnabled());
  const next=page.waitForResponse(r=>r.url().endsWith('/api/command/weather'));await page.locator('#apply-weather').click();const r=await next;assert.equal(r.status(),200);
  let s=await status();assert.equal(s.running,true);assert.equal(s.weather_application.stage,'applied');const applied=s.weather_application.frame;
  for(let i=0;i<200;i++){s=await status();if(s.frame>=applied+45)break;await new Promise(r=>setTimeout(r,100));}
  await cmd('pause');s=await status();const frames=[];
  for(const camera of s.sensors.filter(v=>v.type==='sensor.camera.rgb')){
   const image=await page.request.get(base+`/api/preview/${camera.id}?width=960`);assert.equal(image.status(),200);
   frames.push(Number(image.headers()['x-carla-frame']));fs.writeFileSync(`data/weather-running-fix/${camera.name}-${label}-after.jpg`,await image.body());
  }
  assert.equal(new Set(frames).size,1);assert.equal(frames[0],s.last_complete_frame);
  report.push({preset:label,applied_while_running:true,applied_frame:applied,captured_frame:frames[0],weather:s.weather});
 }
 const original=JSON.parse(fs.readFileSync('data/weather-running-fix/before-status.json')).weather;
 await cmd('run');await cmd('weather',original);
 let s=await status();const f=s.frame;
 for(let i=0;i<200;i++){s=await status();if(s.frame>=f+30)break;await new Promise(r=>setTimeout(r,100));}
 await cmd('pause');await page.waitForFunction(()=>document.querySelector('#pause')?.disabled===true);await page.locator('nav [data-panel="sensorview"]').click();
 await page.waitForFunction(()=>document.querySelectorAll('.sensor-tile').length===6&&[...document.querySelectorAll('.sensor-frame')].every(v=>v.textContent.startsWith('Frame ')),{},{timeout:30000});
 assert.ok((await page.locator('#sensor-scene-weather').textContent()).includes('Rain 70%'));
 await page.screenshot({path:'data/weather-running-fix/shared-weather-after.png',fullPage:true});
 assert.deepEqual(errors,[]);fs.writeFileSync('data/weather-running-fix/verification.json',JSON.stringify({verified:true,report,errors},null,2));console.log(JSON.stringify({verified:true,report,errors},null,2));
}finally{await browser.close()}
