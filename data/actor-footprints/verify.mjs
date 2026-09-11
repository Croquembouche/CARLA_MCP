import {chromium} from '@playwright/test';import assert from 'node:assert/strict';import fs from 'node:fs';
const browser=await chromium.launch({headless:true,executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto('http://127.0.0.1:8095');await page.waitForFunction(()=>document.querySelector('#actor-count').textContent==='38');
 const dismiss=page.getByRole('button',{name:'Continue to scene',exact:true});if(await dismiss.isVisible())await dismiss.click();await page.locator('nav [data-panel="scenario"]').click();
 const result=await page.evaluate(async()=>{
  const {drawActorMarker}=await import('/actor-markers.js?v=3');
  function inspect(type,extent,yaw,scale){let path=[],fills=[],angle=0;const ctx={save(){},restore(){},translate(){},rotate(v){angle=v},beginPath(){path=[]},rect(...a){path.push(['rect',...a])},arc(...a){path.push(['arc',...a])},moveTo(...a){path.push(['move',...a])},lineTo(...a){path.push(['line',...a])},closePath(){},fill(){fills.push({path:structuredClone(path),color:this.fillStyle,angle})},stroke(){}};drawActorMarker(ctx,{type,extent,pose:{yaw}},{role:'background'},0,0,{pixelsPerMeter:scale});return fills}
  return {vehicle:inspect('vehicle.lincoln.mkz',{x:2.5,y:1},90,4),zoomed:inspect('vehicle.lincoln.mkz',{x:2.5,y:1},90,8),pedestrian:inspect('walker.pedestrian.0043',{x:.32,y:.17},-90,4),headings:[0,90,180,-90].map(y=>inspect('vehicle.car',{x:2,y:1},y,5)[1].angle),legendCanvases:document.querySelectorAll('#actor-legend canvas').length};
 });
 assert.deepEqual(result.vehicle[0].path,[['rect',-10,-4,20,8]]);assert.deepEqual(result.zoomed[0].path,[['rect',-20,-8,40,16]]);
 assert.equal(result.pedestrian[0].path[0][0],'arc');assert.equal(result.pedestrian[0].path[0][3],1.28);assert.equal(result.legendCanvases,6);
 assert.deepEqual(result.headings,[0,Math.PI/2,Math.PI,-Math.PI/2]);
 for(const {path} of [result.vehicle[1],result.zoomed[1]]){assert.equal(path.length,7);assert.ok(path[0][1]>0);}
 for(const [,x,y] of result.vehicle[1].path){assert.ok(Math.abs(x)<10&&Math.abs(y)<4,'Arrow must stay inside rectangle')}
 for(const [,x,y] of result.pedestrian[1].path){assert.ok(Math.hypot(x,y)<1.28,'Arrow must stay inside circle')}
 const box=await page.locator('#map').boundingBox();await page.mouse.move(box.x+box.width*.65,box.y+box.height*.5);await page.mouse.wheel(0,-700);await page.waitForTimeout(300);await page.screenshot({path:'data/actor-footprints/dark.png',fullPage:true});
 await page.locator('#theme-toggle').click();await page.screenshot({path:'data/actor-footprints/light.png',fullPage:true});assert.deepEqual(errors,[]);
 fs.writeFileSync('data/actor-footprints/verification.json',JSON.stringify({verified:true,result,errors},null,2));console.log('PASS: physical rectangular footprints, circular pedestrians, enclosed heading arrows, yaw rotation, proportional zoom, six matching legend symbols, light/dark rendering, no page errors.');
}finally{await browser.close()}
