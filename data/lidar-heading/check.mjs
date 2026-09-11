import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
const browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
try {
 const page=await browser.newPage({viewport:{width:1600,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('http://128.175.213.232:8095/');
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();
 await page.locator('nav [data-panel="sensorview"]').click();
 const host=page.locator('.sensor-tile').filter({has:page.locator('h3',{hasText:'roof_lidar'})}).locator('.lidar-canvas');
 await host.waitFor();await page.waitForFunction(()=>document.querySelector('.lidar-canvas')?.dataset.orbit);
 if(process.argv.includes('--before')) {await page.screenshot({path:'data/lidar-heading/before.png',fullPage:true});console.log('Before',await host.getAttribute('data-orbit'));}
 else {
  const position=async()=> (await host.getAttribute('data-orbit')).split(',').map(Number);
  assert.deepEqual(await position(),[0,90,100]);assert.equal(await host.getAttribute('data-target'),'0,0,0');
  const canvas=host.locator('canvas'),box=await canvas.boundingBox();await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.7,box.y+box.height*.55,{steps:8});await page.mouse.up();assert.notEqual((await position())[0],0);assert.equal(await host.getAttribute('data-target'),'0,0,0');
  const beforeZoom=Math.hypot(...await position());await page.getByRole('button',{name:'Zoom in roof_lidar',exact:true}).click();assert.ok(Math.hypot(...await position())<beforeZoom);
  await page.getByRole('button',{name:'Reset view roof_lidar',exact:true}).click();assert.deepEqual(await position(),[0,90,100]);
  await canvas.focus();await page.keyboard.press('ArrowLeft');assert.equal(await host.getAttribute('data-target'),'0,0,0');await page.keyboard.press('Home');assert.deepEqual(await position(),[0,90,100]);
  await page.getByRole('button',{name:'Focus roof_lidar',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.lidar-canvas')?.dataset.orbit==='0.000,90.000,100.000');
  await page.screenshot({path:'data/lidar-heading/after.png',fullPage:true});assert.deepEqual(errors,[]);console.log('PASS: vehicle-forward default, orbit, zoom, reset/Home, no pan, focus persistence and no browser errors');
 }
} finally {await browser.close()}
