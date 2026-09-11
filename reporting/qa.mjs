// Visual and interaction verification. Pass a local @playwright/test ESM module path.
import {pathToFileURL} from 'node:url';
import fs from 'node:fs/promises';
import path from 'node:path';
const [modulePath,reportPath]=process.argv.slice(2);
if(!modulePath||!reportPath)throw Error('Usage: node reporting/qa.mjs /path/to/@playwright/test/index.mjs /path/to/report/index.html');
const {chromium}=await import(pathToFileURL(modulePath));
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1512,height:1100}});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
const remote=[];page.on('request',r=>{if(/^https?:/.test(r.url()))remote.push(r.url())});
await page.goto(pathToFileURL(reportPath).href);
await page.locator('#outcomes tbody tr').last().waitFor();
const dir=path.resolve(path.dirname(reportPath),'../qa');await fs.mkdir(dir,{recursive:true});
await page.screenshot({path:path.join(dir,'desktop.png'),fullPage:false});
const data=JSON.parse(await fs.readFile(path.join(path.dirname(reportPath),'data.json'),'utf8'));
let checked=0;
for(const task of data.tasks){
 await page.selectOption('#task',task.id);
 for(const phase of task.id==='actual-balance-forecast'?['initial','continuation']:['initial']){
  if(task.id==='actual-balance-forecast')await page.selectOption('#phase',phase);
  if(await page.locator('#outcomes tbody tr').count()!==4)throw Error('Missing approach rows');
  for(const approach of ['prompt','plan','openspec','gennady']){
   await page.selectOption('#approach',approach);
   const r=data.runs.find(x=>x.task===task.id&&x.phase===phase&&x.approach===approach);
   if(await page.locator('#file option').count()!==r.code.length)throw Error('Code file count mismatch');
   await page.selectOption('#diff-mode','cross');
   await page.selectOption('#diff-mode','parallel');
   const details=page.locator('#dialogue-view > details').first();
   await details.locator('summary').first().click();
   if(!await details.getAttribute('open')&&await details.getAttribute('open')!== '')throw Error('Dialogue failed to open');
   await details.locator('summary').first().click();checked++;
  }
 }
}
await page.selectOption('#approach','prompt');
await page.locator('#artifact-search').fill('prompt.txt');
if(!await page.locator('#artifact-list tbody a').count())throw Error('Artifact filter empty');
const artifact=await page.locator('#artifact-list tbody a').first().getAttribute('href');
const checkPage=await browser.newPage();await checkPage.goto(new URL(artifact,page.url()).href);await checkPage.close();
await page.locator('#code').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(dir,'code.png')});
await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.scrollTo(0,0));
await page.screenshot({path:path.join(dir,'mobile.png')});
const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
if(overflow)throw Error('Mobile page overflows');
if(errors.length||remote.length)throw Error(JSON.stringify({errors,remote}));
await fs.writeFile(path.join(dir,'result.json'),JSON.stringify({passed:true,run_views_checked:checked,offline:true,console_errors:errors,remote_requests:remote,mobile_overflow:overflow},null,2));
await browser.close();console.log(JSON.stringify({passed:true,run_views_checked:checked,screenshots:dir}));
