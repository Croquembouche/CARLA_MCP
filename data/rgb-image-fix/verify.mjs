import fs from 'node:fs';
import assert from 'node:assert/strict';
import {chromium} from '@playwright/test';
const base='http://128.175.213.232:8095';
const browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
try {
 const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 let state;
 for(let i=0;i<600;i++){
  state=await (await page.request.get(base+'/api/status')).json();
  assert.notEqual(state.phase,'error',state.error);
  if(state.recovery_operation?.stage==='ready')break;
  await new Promise(resolve=>setTimeout(resolve,1000));
 }
 assert.equal(state.recovery_operation.stage,'ready');
 assert.equal(state.camera_warmup.stage,'ready');assert.equal(state.camera_warmup.completed,30);
 assert.equal(state.running,false);assert.equal(state.error,null);
 const cameras=state.sensors.filter(s=>s.type==='sensor.camera.rgb');assert.equal(cameras.length,2);
 const samples=[];
 for(const camera of cameras){
  const response=await page.request.get(`${base}/api/preview/${camera.id}?format=image&width=960`);
  assert.equal(response.status(),200);
  fs.writeFileSync(`data/rgb-image-fix/${camera.name}-after.jpg`,await response.body());
  samples.push({id:camera.id,name:camera.name,frame:Number(response.headers()['x-carla-frame']),source:response.headers()['x-preview-source-size']});
 }
 assert.equal(new Set(samples.map(s=>s.frame)).size,1);
 await page.goto(base);
 await page.waitForFunction(()=>document.querySelector('#sensor-count')?.textContent==='6 ego sensors');
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();
 await page.locator('nav button[data-panel="sensorview"]').click();
 await page.waitForFunction(()=>document.querySelectorAll('.sensor-tile').length===6&&[...document.querySelectorAll('.sensor-frame')].every(v=>v.textContent.startsWith('Frame ')),{},{timeout:30000});
 // Show both RGB feeds together for visual review without advancing the scene.
 for(const sensor of state.sensors.filter(s=>s.type!=='sensor.camera.rgb'))await page.locator(`[data-sensor="${sensor.id}"]`).uncheck();
 await page.waitForFunction(()=>document.querySelectorAll('.sensor-tile').length===2&&[...document.querySelectorAll('.sensor-frame')].every(v=>v.textContent.startsWith('Frame ')),{},{timeout:30000});
 await page.screenshot({path:'data/rgb-image-fix/both-rgb-after.png',fullPage:true});
 assert.deepEqual(errors,[]);
 const final=await (await page.request.get(base+'/api/status')).json();assert.equal(final.frame,state.frame);assert.equal(final.running,false);
 fs.writeFileSync('data/rgb-image-fix/final-status.json',JSON.stringify(final,null,2));
 const report={verified:true,warmup:state.camera_warmup,samples,frames_advanced_by_verification:0,worker_count:state.worker_count,errors};
 fs.writeFileSync('data/rgb-image-fix/verification.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}finally{await browser.close()}
