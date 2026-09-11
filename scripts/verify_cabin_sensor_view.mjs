import fs from 'node:fs';import assert from 'node:assert/strict';import {chromium} from '@playwright/test';
const out='data/sensor-view',aid=JSON.parse(fs.readFileSync(out+'/temporary-actor.json')).id;
const browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:8095/');await page.waitForFunction(()=>document.querySelector('#actor-count').textContent==='42');
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();
 await page.locator('nav button[data-panel="sensorview"]').click();await page.locator('#view-ego').selectOption(String(aid));
 await page.waitForFunction(()=>document.querySelectorAll('.sensor-tile').length===4&&[...document.querySelectorAll('.sensor-frame')].every(e=>e.textContent.startsWith('Frame ')));
 await page.screenshot({path:out+'/cabin-all-sensors.png',fullPage:true});
 await page.getByRole('button',{name:'Focus cabin_overview',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.sensor-frame')?.textContent.startsWith('Frame '));await page.screenshot({path:out+'/cabin-focus.png',fullPage:true});
 await page.getByRole('button',{name:'Configure this ego’s sensors',exact:true}).click();assert.equal(await page.locator('#sensor-ego').inputValue(),String(aid));
 await page.getByRole('button',{name:'Add to loadout',exact:true}).click();await page.waitForFunction(()=>[...document.querySelectorAll('[data-sensor-title]')].some(e=>e.textContent==='cabin_overview_2'));
 await page.locator('nav button[data-panel="sensorview"]').click();await page.getByRole('button',{name:'All sensors',exact:true}).click();await page.getByRole('button',{name:'Switch to light mode',exact:true}).click();await page.waitForFunction(()=>[...document.querySelectorAll('.sensor-frame')].every(e=>e.textContent.startsWith('Frame ')));await page.screenshot({path:out+'/cabin-light-mode.png',fullPage:true});
 assert.deepEqual(errors,[]);fs.writeFileSync(out+'/cabin-browser-verification.json',JSON.stringify({verified:true,ego:aid,simultaneous_cameras:3,lidar:1,loadout_navigation:true,cabin_preset_add:true,light_mode:true,errors},null,2));
}finally{await browser.close()}
