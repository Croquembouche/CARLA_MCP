import {chromium} from '@playwright/test';
import fs from 'node:fs/promises';
const browser=await chromium.launch({executablePath:'/home/william/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',headless:true,args:['--no-sandbox']});
const results=[];
for(const viewport of [{width:1500,height:1000},{width:390,height:844}]){
 const page=await browser.newPage({viewport});
 for(const name of ['mcp','mcp-tools']){
  const response=await page.goto('http://127.0.0.1:8095/'+name+'.html');
  if(response.status()!==200)throw Error('Docs not served');
  const headings=await page.locator('main h2').count();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  if(overflow)throw Error('Horizontal page overflow '+name);
  if(name==='mcp-tools'&&headings!==50)throw Error('Expected 49 tools and cabin presets');
  await page.screenshot({path:`data/mcp-docs-${name}-${viewport.width}.png`});
  results.push({page:name,width:viewport.width,headings,overflow});
 }
 await page.close();
}
await browser.close();await fs.writeFile('data/mcp-docs-verification.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results));
