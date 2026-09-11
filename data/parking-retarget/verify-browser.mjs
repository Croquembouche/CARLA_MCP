import fs from 'node:fs';import assert from 'node:assert/strict';import {chromium} from '@playwright/test';
const browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],requests=[];
const state=JSON.parse(fs.readFileSync('data/parking-retarget/before-status.json'));state.running=false;state.mode='live';state.error=null;state.recovery_operation=null;
const aid=Object.keys(state.managed).find(id=>state.managed[id].role==='background'&&state.managed[id].parked);
page.on('pageerror',e=>errors.push(e.message));
// Test the real UI event handlers against controlled parked and moving snapshots.
await page.route('**/api/status',route=>route.fulfill({json:state}));
await page.route('**/api/command/destination',async route=>{
 const p=route.request().postDataJSON();requests.push(p);
 const result={destination:p.point,route:[{x:10,y:10},p.point],route_update:{revision:100+requests.length},arrived:false,parked:false,parking_space:null,planner:'tm',parking_trip:{stage:'leaving',bay:null,blocked:null,motion:'forward'}};
 await route.fulfill({json:result});
});
try {
 await page.goto('http://127.0.0.1:8095/');await page.waitForFunction(()=>document.querySelector('#actor-count').textContent==='28');
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();
 await page.locator('nav button[data-panel="scenario"]').click();await page.locator('#actor-list button[data-id="'+aid+'"]').click();
 await page.locator('#goal-select').selectOption('0');await page.waitForFunction(()=>document.querySelector('#destination-status').textContent.includes('Leaving parking'));
 assert.equal(requests.length,1);assert.equal(requests[0].id,Number(aid));
 const pausedText=await page.locator('#destination-status').textContent();assert.match(pausedText,/Press Run/);
 state.running=true;state.managed[aid]={...state.managed[aid],parked:false,arrived:false,route_update:{revision:101},parking_trip:{stage:'entering',bay:'P025',motion:'reversing'}};
 await page.waitForFunction(()=>document.querySelector('#destination-status').textContent.includes('Backing into P025'));
 await page.locator('#goal-select').selectOption('1');await page.waitForFunction(()=>document.querySelector('#destination-status').textContent.includes('Leaving parking'));
 assert.equal(requests.length,2);assert.notDeepEqual(requests[0].point,requests[1].point);
 assert.deepEqual(errors,[]);
 const result={verified:true,paused_selection_submits_without_apply:true,moving_selection_replaces_unfinished_goal:true,paused_status:pausedText,request_count:requests.length,errors};
 fs.writeFileSync('data/parking-retarget/browser-verification.json',JSON.stringify(result,null,2));console.log(result);
} finally {await browser.close()}
