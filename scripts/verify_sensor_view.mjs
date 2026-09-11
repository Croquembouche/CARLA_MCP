import fs from 'node:fs';
import assert from 'node:assert/strict';
import {chromium} from '@playwright/test';
const base='http://127.0.0.1:8095',out='data/sensor-view';
const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_PATH||'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[],requests=[];
page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().includes('/api/preview/'))requests.push(r.url())});
const cmd=async(action,p={})=>{const r=await fetch(base+'/api/command/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-Control-Client':'carla-control-center'},body:JSON.stringify(p)});if(!r.ok)throw Error(await r.text());return r.json()};
const status=()=>fetch(base+'/api/status').then(r=>r.json());
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const report={};
try{
 await page.goto(base);await page.waitForFunction(()=>document.querySelector('#actor-count').textContent==='41');
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();
 await page.locator('nav button[data-panel="sensorview"]').click();
 await page.waitForFunction(()=>document.querySelectorAll('.sensor-tile').length===5 && [...document.querySelectorAll('.sensor-frame')].every(e=>e.textContent.startsWith('Frame ')));
 report.initial=await page.locator('.sensor-frame').allTextContents();assert.equal(new Set(requests.map(u=>new URL(u).pathname)).size,5);
 await page.screenshot({path:out+'/all-sensors.png',fullPage:true});
 await wait(500);let n=requests.length;await wait(1200);assert.equal(requests.length,n,'Paused frames should not be downloaded repeatedly');report.paused_repeated_requests=0;
 await page.getByRole('button',{name:'Focus front_rgb',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.sensor-frame')?.textContent.startsWith('Frame '));
 n=requests.length;await cmd('step');await wait(1200);const focused=requests.slice(n);assert.ok(focused.length>0);assert.equal(new Set(focused.map(u=>new URL(u).pathname)).size,1);report.focused_sensor_requests=focused.length;
 await page.screenshot({path:out+'/single-camera.png',fullPage:true});
 await page.getByRole('button',{name:'Freeze previews',exact:true}).click();await wait(300);n=requests.length;await cmd('step');await wait(1200);assert.equal(requests.length,n);report.frozen_requests=0;
 await page.getByRole('button',{name:'Resume previews',exact:true}).click();await wait(800);
 await page.locator('nav button[data-panel="scenario"]').click();await wait(300);n=requests.length;await cmd('step');await wait(1200);assert.equal(requests.length,n);report.hidden_workspace_requests=0;
 await page.locator('nav button[data-panel="sensorview"]').click();await page.getByRole('button',{name:'All sensors',exact:true}).click();await wait(800);
 // A short viewport makes some tiles off-screen; only visible tiles update.
 await page.setViewportSize({width:1000,height:640});await wait(400);
 const visible=await page.locator('.sensor-tile').evaluateAll(nodes=>{const r=document.querySelector('#sensor-grid').getBoundingClientRect();return nodes.filter(n=>{const b=n.getBoundingClientRect();return b.top<r.bottom-10&&b.bottom>r.top+10}).map(n=>n.dataset.sensorId)});
 n=requests.length;await cmd('step');await wait(1200);const offscreenRequests=requests.slice(n).map(u=>new URL(u).pathname.split('/').at(-1));assert.ok(offscreenRequests.every(id=>visible.includes(id)));assert.ok(visible.length<5);report.offscreen={visible:visible.length,total:5,requests:offscreenRequests.length};
 await page.setViewportSize({width:1440,height:1000});
 report.errors=errors;assert.deepEqual(errors,[]);report.verified=true;
}finally{fs.writeFileSync(out+'/browser-verification.json',JSON.stringify(report,null,2));await browser.close()}
console.log(JSON.stringify(report,null,2));
