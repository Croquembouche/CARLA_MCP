import fs from 'node:fs';import assert from 'node:assert/strict';import {chromium} from '@playwright/test';
const browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
const base='http://127.0.0.1:8095';
try {
 await page.goto(base);await page.waitForFunction(()=>['CARLA online','CARLA stopped'].includes(document.querySelector('#carla-power-status').textContent));
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();
 assert.equal(await page.locator('#start').count(),1);assert.equal(await page.locator('#stop').count(),1);
 assert.ok(await page.locator('header #start').isVisible());assert.ok(await page.locator('header #stop').isVisible());
 for(const width of [1440,1024,390]){
  await page.setViewportSize({width,height:1000});
  const boxes=await page.locator('header > *').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {id:n.id||n.className,x:r.x,y:r.y,right:r.right,bottom:r.bottom}}));
  for(const b of boxes)assert.ok(b.x>=0&&b.right<=width+1,JSON.stringify({width,b}));
  for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){
   const a=boxes[i],b=boxes[j];assert.ok(a.right<=b.x+.5||b.right<=a.x+.5||a.bottom<=b.y+.5||b.bottom<=a.y+.5,JSON.stringify({width,a,b}));
  }
  await page.screenshot({path:`data/carla-power-ui/header-${width}.png`,fullPage:width!==390});
 }
 await page.setViewportSize({width:1440,height:1000});
 const original=await (await page.request.get(base+'/api/status')).json();let state={...original,phase:'connected',mode:'live',error:null,recovery_operation:null},releaseStop;const calls=[];
 await page.route('**/api/status',r=>r.fulfill({json:state}));
 await page.route('**/api/command/shutdown',async r=>{
  calls.push('shutdown');await new Promise(resolve=>releaseStop=resolve);
  state={...state,phase:'offline',running:false,managed:{},actors:[],sensors:[],worker_count:0};await r.fulfill({json:{stopped:true}});
 });
 await page.route('**/api/command/start',async r=>{
  calls.push('start');assert.deepEqual(r.request().postDataJSON(),{gpus:'auto'});state={...state,phase:'starting'};await r.fulfill({json:{started:true}});
 });
 await page.waitForFunction(()=>!document.querySelector('#stop').disabled);await page.locator('#stop').click();await page.waitForFunction(()=>document.querySelector('#stop').textContent==='Stopping CARLA…');assert.ok(await page.locator('#stop').isDisabled());
 while(!releaseStop)await new Promise(r=>setTimeout(r,10));releaseStop();
 await page.waitForFunction(()=>document.querySelector('#carla-power-status').textContent==='CARLA stopped');assert.ok(await page.locator('#start').isEnabled());assert.ok(await page.locator('#stop').isDisabled());
 await page.locator('#start').click();await page.waitForFunction(()=>document.querySelector('#start').textContent==='Starting CARLA…'&&!document.querySelector('#stop').disabled);
 assert.ok(await page.locator('#run').isDisabled());assert.ok(await page.locator('#start').isDisabled());
 // Starting can be cancelled with the same stop control.
 releaseStop=null;await page.locator('#stop').click();while(!releaseStop)await new Promise(r=>setTimeout(r,10));releaseStop();
 await page.waitForFunction(()=>document.querySelector('#carla-power-status').textContent==='CARLA stopped');
 await page.locator('#start').click();await page.waitForFunction(()=>document.querySelector('#start').textContent==='Starting CARLA…');
 state={...original,phase:'connected',mode:'live',error:null,recovery_operation:null,running:false};await page.waitForFunction(()=>document.querySelector('#carla-power-status').textContent==='CARLA online');
 const ready=page.getByRole('button',{name:'Continue to scene',exact:true});if(await ready.isVisible())await ready.click();
 assert.ok(await page.locator('#run').isEnabled());assert.ok(await page.locator('#stop').isEnabled());assert.ok(await page.locator('#start').isDisabled());assert.deepEqual(errors,[]);
 const report={verified:true,layouts:[1440,1024,390],header_no_overlap:true,command_wiring:calls,loading_and_stopping_states:true,startup_cancellation:true,real_simulator_not_stopped:true,errors};fs.writeFileSync('data/carla-power-ui/verification.json',JSON.stringify(report,null,2));console.log(report);
}finally{await browser.close()}
