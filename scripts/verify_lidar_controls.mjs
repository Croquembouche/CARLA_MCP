import fs from 'node:fs';import assert from 'node:assert/strict';import {chromium} from '@playwright/test';
const out='data/lighting-lidar',browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),requests=[],errors=[];
page.on('request',r=>{if(r.url().includes('/api/preview/'))requests.push(r.url())});page.on('pageerror',e=>errors.push(e.message));
const delay=ms=>new Promise(r=>setTimeout(r,ms));
try{
 await page.goto('http://127.0.0.1:8095/');await page.waitForFunction(()=>document.querySelector('#actor-count').textContent==='41');
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();
 await page.locator('nav [data-panel="sensorview"]').click();await page.getByRole('button',{name:'Focus roof_lidar',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('.lidar-canvas canvas')&&document.querySelector('.sensor-frame').textContent.startsWith('Frame '));
 await page.getByRole('button',{name:'Freeze previews',exact:true}).click();await delay(600);
 const host=page.locator('.lidar-canvas'),canvas=host.locator('canvas'),box=await canvas.boundingBox();const orbit=async()=>JSON.parse('['+await host.getAttribute('data-orbit')+']');const distance=a=>Math.hypot(...a);let start=await orbit(),n=requests.length;
 await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.7,box.y+box.height*.6,{steps:12});await page.mouse.up();
 const rotated=await orbit();assert.notDeepEqual(rotated,start);assert.equal(await host.getAttribute('data-target'),'0,0,0');
 await page.mouse.wheel(0,400);await delay(300);const zoomed=await orbit();assert.ok(distance(zoomed)>distance(rotated));
 await page.getByRole('button',{name:'Zoom in roof_lidar',exact:true}).click();assert.ok(distance(await orbit())<distance(zoomed));
 await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.down({button:'right'});await page.mouse.move(box.x+box.width*.7,box.y+box.height*.6,{steps:8});await page.mouse.up({button:'right'});assert.equal(await host.getAttribute('data-target'),'0,0,0');
 await page.keyboard.down('Control');await page.mouse.down();await page.mouse.move(box.x+box.width*.3,box.y+box.height*.4,{steps:8});await page.mouse.up();await page.keyboard.up('Control');assert.equal(await host.getAttribute('data-target'),'0,0,0');
 await delay(500);assert.equal(requests.length,n,'Local camera interactions must not download new scans');await page.screenshot({path:out+'/lidar-rotated.png',fullPage:true});
 await page.getByRole('button',{name:'Reset view roof_lidar',exact:true}).click();assert.deepEqual(await orbit(),[70,90,70]);
 await page.getByRole('button',{name:'Resume previews',exact:true}).click();await page.locator('nav [data-panel="scenario"]').click();await delay(300);n=requests.length;
 const r=await fetch('http://127.0.0.1:8095/api/command/step',{method:'POST',headers:{'Content-Type':'application/json','X-Control-Client':'carla-control-center'},body:'{}'});assert.ok(r.ok);await delay(1500);assert.equal(requests.length,n);
 assert.deepEqual(errors,[]);fs.writeFileSync(out+'/lidar-ui-verification.json',JSON.stringify({verified:true,drag_rotates:true,wheel_zooms:true,zoom_buttons:true,pan_target:[0,0,0],right_and_ctrl_drag_cannot_pan:true,interaction_downloads:0,hidden_workspace_downloads:0,reset:true,errors},null,2));
}finally{await browser.close()}
