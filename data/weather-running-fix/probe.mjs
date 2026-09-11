import fs from 'node:fs';import assert from 'node:assert/strict';import {chromium} from '@playwright/test';
const base='http://128.175.213.232:8095',browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});
try{
 const page=await browser.newPage({viewport:{width:1500,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(base);await page.waitForFunction(()=>document.querySelector('#weather-status')?.textContent.includes('Cloud'));
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();await page.locator('nav [data-panel="weather"]').click();
 const report=[];
 for(const name of ['clear','night','rain']){
  let s=await (await page.request.get(base+'/api/status')).json();assert.equal(s.running,true);
  await page.locator('#weather-preset').selectOption(name);assert.ok(await page.locator('#apply-weather').isEnabled());
  const next=page.waitForResponse(r=>r.url().endsWith('/api/command/weather'));await page.locator('#apply-weather').click();const response=await next;assert.equal(response.status(),200);
  const weather=await response.json();s=await (await page.request.get(base+'/api/status')).json();const frame=s.frame;
  for(let i=0;i<100;i++){s=await (await page.request.get(base+'/api/status')).json();if(s.frame>=frame+30)break;await new Promise(r=>setTimeout(r,100));}
  assert.equal(s.running,true);const sensor=s.sensors.find(s=>s.name==='front_rgb');const image=await page.request.get(base+`/api/preview/${sensor.id}?width=960`);assert.equal(image.status(),200);fs.writeFileSync(`data/weather-running-fix/${name}-before-fix.jpg`,await image.body());report.push({preset:name,status:response.status(),running:s.running,frame:s.frame,weather});
 }
 fs.writeFileSync('data/weather-running-fix/running-probe.json',JSON.stringify({report,errors},null,2));console.log(JSON.stringify({report,errors},null,2));
}finally{await browser.close()}
