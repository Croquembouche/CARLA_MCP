import {chromium} from '@playwright/test';import assert from 'node:assert/strict';import fs from 'node:fs';
const ego=JSON.parse(fs.readFileSync('data/ego-lincoln-replacement/new-ego.json')).id;
const browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:8095');await page.waitForFunction(()=>document.querySelector('#actor-count').textContent==='28');
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();
 await page.locator('nav [data-panel="sensorview"]').click();await page.locator('#view-ego').selectOption(String(ego));await page.waitForFunction(()=>[...document.querySelectorAll('#view-focus option')].some(o=>o.textContent==='cabin_overview'),null,{timeout:180000});
 await page.getByRole('button',{name:'Focus cabin_overview',exact:true}).click();await page.waitForFunction(()=>document.querySelector('img[alt="cabin_overview live sensor preview"]')?.naturalWidth>0,null,{timeout:60000});
 await page.screenshot({path:'data/ego-lincoln-replacement/cabin-ui.png',fullPage:true});assert.deepEqual(errors,[]);fs.writeFileSync('data/ego-lincoln-replacement/ui-verification.json',JSON.stringify({ego,camera:'cabin_overview',imageLoaded:true,errors},null,2));console.log('Verified cabin_overview is visible with a live image on the new Lincoln ego.');
}finally{await browser.close()}
