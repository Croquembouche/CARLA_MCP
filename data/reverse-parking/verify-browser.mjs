import fs from 'node:fs';
import assert from 'node:assert/strict';
import {chromium} from '@playwright/test';
const browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
try {
 await page.goto('http://127.0.0.1:8095/');
 await page.waitForFunction(()=>document.querySelector('#actor-count').textContent==='28');
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();
 await page.locator('nav button[data-panel="scenario"]').click();
 const status=await (await page.request.get('http://127.0.0.1:8095/api/status')).json();
 const background=Object.entries(status.managed).find(([,actor])=>actor.role==='background')[0];
 await page.locator('#actor-list button[data-id="'+background+'"]').click();
 assert.ok((await page.locator('#panel-scenario').textContent()).includes('Parking destinations use reverse entry'));
 const options=await page.locator('#goal-select option').allTextContents();
 assert.ok(options.some(x=>x.includes('P025')));
 const labels=await page.evaluate(async()=>{
  const {DestinationState}=await import('/destination-state.js?v=reverse-parking-1');
  const state=new DestinationState();
  return ['reversing','forward','changing_gear'].map(motion=>state.describe(1,{parking_trip:{stage:'entering',bay:'P025',motion}},true));
 });
 assert.equal(labels[0],'Backing into P025');
 assert.deepEqual(errors,[]);
 await page.screenshot({path:'data/reverse-parking/deployed-interface.png',fullPage:true});
 const report={verified:true,actor_count:28,parking_goal_present:true,reverse_parking_help:true,loaded_module_labels:labels,errors};
 fs.writeFileSync('data/reverse-parking/browser-verification.json',JSON.stringify(report,null,2));console.log(report);
} finally {await browser.close()}
