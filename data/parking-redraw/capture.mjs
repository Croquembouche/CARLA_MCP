import {chromium} from '@playwright/test';import fs from 'node:fs';
const browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
try{const page=await browser.newPage({viewport:{width:2400,height:2400}});page.on('pageerror',e=>console.log(e.message));await page.goto('http://127.0.0.1:8095/parking-review.html');await page.waitForFunction(()=>window.ready,{},{timeout:120000});
for(const [name,x,y,span] of [['overview',0,40,280],['north',0,-51,100],['middle',0,21,100],['east',80,35,90],['south',10,132,100],['west',-95,45,100]]){await page.evaluate(([x,y,s])=>window.survey.frame(x,y,s),[x,y,span]);await page.screenshot({path:`data/parking-redraw/${name}.png`});}
const bays=JSON.parse(fs.readFileSync('data/parking/Town10HD_Opt.json')).validated_spaces;await page.evaluate(bays=>{window.survey.draw(bays);window.survey.frame(0,40,280)},bays);await page.screenshot({path:'data/parking-redraw/before-overlay.png'});console.log('CAPTURED');
}finally{await browser.close()}
