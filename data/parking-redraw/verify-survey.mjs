import {chromium} from '@playwright/test';import assert from 'node:assert/strict';import fs from 'node:fs';
const browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
try{const page=await browser.newPage({viewport:{width:1800,height:1200}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('http://128.175.213.232:8095/parking-review.html');await page.waitForFunction(()=>window.ready,{},{timeout:120000});
assert.match(await page.locator('#status').textContent(),/46 selectable · 115 restricted/);
assert.deepEqual(await page.evaluate(()=>window.survey.scene.children.filter(g=>g.name).map(g=>g.name)),['roads','street','props']);
await page.locator('#toggle-tools').click();assert.equal(await page.locator('#tools').isVisible(),false);await page.locator('#toggle-tools').click();await page.screenshot({path:'data/parking-redraw/survey-interface.png'});
await page.locator('#region').selectOption('north');await page.screenshot({path:'data/parking-redraw/survey-north.png'});
const z=await page.evaluate(()=>window.survey.camera.zoom);await page.mouse.move(1100,600);await page.mouse.wheel(0,-350);await page.waitForTimeout(300);assert.ok(await page.evaluate(()=>window.survey.camera.zoom)>z);
const beforePan=await page.evaluate(()=>window.survey.camera.position.toArray());await page.mouse.move(1100,600);await page.mouse.down();await page.mouse.move(1200,650,{steps:5});await page.mouse.up();assert.notDeepEqual(await page.evaluate(()=>window.survey.camera.position.toArray()),beforePan);
await page.locator('#annotations').uncheck();assert.equal(await page.evaluate(()=>window.survey.overlays.visible),false);await page.locator('#annotations').check();
await page.locator('#region').selectOption('overview');await page.setViewportSize({width:2400,height:2400});await page.waitForTimeout(300);await page.locator('#tools').evaluate(e=>e.hidden=true);await page.locator('#toggle-tools').evaluate(e=>e.hidden=true);
await page.evaluate(()=>window.survey.frame(0,40,280));await page.screenshot({path:'data/parking-redraw/final-overhead.png'});
await page.evaluate(()=>{window.survey.overlays.visible=false;window.survey.frame(0,40,280)});await page.screenshot({path:'data/parking-redraw/unobstructed-overhead.png'});
assert.deepEqual(errors,[]);fs.writeFileSync('data/parking-redraw/survey-ui-verification.json',JSON.stringify({noBuildingsOrVegetation:true,selectable:46,restricted:115,panZoomControls:true,overlayToggle:true,errors},null,2));console.log('PASS survey rendered, no buildings/vegetation, 46 selectable and 115 restricted, region selection, zoom and overlay toggle');
}finally{await browser.close()}
