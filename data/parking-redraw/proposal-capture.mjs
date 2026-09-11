import {chromium} from '@playwright/test';import fs from 'node:fs';
const browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
try{const page=await browser.newPage({viewport:{width:2400,height:2400}});page.on('pageerror',e=>console.log(e.message));await page.goto('http://127.0.0.1:8095/parking-review.html');await page.waitForFunction(()=>window.ready,{},{timeout:120000});
const p=JSON.parse(fs.readFileSync('data/parking-redraw/proposal.json'));await page.evaluate(bays=>window.survey.draw(bays),p.validated_spaces);
for(const [name,x,y,span] of [['proposal-overview',0,40,280],['proposal-middle',0,21,100],['proposal-north',0,-51,100],['proposal-south',10,132,100],['proposal-east',95,70,150]]){await page.evaluate(([x,y,s])=>window.survey.frame(x,y,s),[x,y,span]);await page.screenshot({path:`data/parking-redraw/${name}.png`});}
console.log('CAPTURED');
}finally{await browser.close()}
