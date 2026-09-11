import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const root=process.cwd(), study=path.join(root,'studies/actual-balance-forecast');
const require=createRequire(path.join(root,'.eval-cache/actual-forecast/base/package.json'));
const {chromium}=require('playwright');
const output=path.resolve(process.argv[2]||path.join(study,'validation/fixture-probe'));
fs.mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({userAgent:'playwright',locale:'en-US',timezoneId:'UTC',viewport:{width:1280,height:720}});
const page=await context.newPage();page.setDefaultTimeout(20000);
const logs=[];page.on('pageerror',e=>logs.push(String(e)));
const save=async name=>{fs.writeFileSync(path.join(output,name+'.txt'),await page.locator('body').innerText());await page.screenshot({path:path.join(output,name+'.png'),fullPage:true});};
async function rpc(name,args){return page.evaluate(async ({name,args})=>{const w=await window.Actual.getServerSocket();const id=crypto.randomUUID();return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{w.removeEventListener('message',listener);reject(new Error('RPC timeout '+name))},10000);function listener(e){if(e.data.id!==id)return;clearTimeout(timer);w.removeEventListener('message',listener);if(e.data.type==='reply')resolve(e.data.result);else reject(new Error(JSON.stringify(e.data)));}w.addEventListener('message',listener);w.postMessage({id,name,args,catchErrors:false});});},{name,args});}
try {
await page.goto('http://127.0.0.1:43171');
await page.getByRole('button',{name:"Don't use a server",exact:true}).click();
await page.getByRole('button',{name:'Start fresh',exact:true}).click();
await page.getByTestId('account-name').waitFor();
await save('fresh');
const accounts=await rpc('accounts-get'); console.log('accounts',JSON.stringify(accounts));
const account=await rpc('account-create',{name:'Forecast Fixture',balance:1000});console.log('created',JSON.stringify(account));
const schedule=await rpc('schedule/create',{conditions:[{op:'is',field:'account',value:account},{op:'is',field:'amount',value:-20000},{op:'is',field:'date',value:{start:'2017-01-15',frequency:'monthly'}}]});console.log('schedule',JSON.stringify(schedule));
if(!await page.getByRole('link',{name:'Settings',exact:true}).isVisible()) await page.getByRole('button',{name:'More',exact:true}).click();
await page.getByRole('link',{name:'Settings',exact:true}).click();
await page.getByTestId('settings').waitFor();await save('settings');
await page.getByTestId('advanced-settings').click();
await page.getByTestId('experimental-settings').click();
await page.getByRole('checkbox',{name:'Balance Forecast Report'}).click();
await page.getByRole('link',{name:'Reports',exact:true}).click();
await page.getByRole('button',{name:'Add new widget'}).click();
await page.getByRole('button',{name:'Balance forecast',exact:true}).click();
const cards=page.getByTestId('reports-page').locator('.react-grid-item');
let opened=false;
for(let attempt=0;attempt<10&&!opened;attempt++){
 for(let i=await cards.count()-1;i>=0;i--){
  await cards.nth(i).scrollIntoViewIfNeeded();
  const target=cards.nth(i).getByRole('button',{name:/^Balance Forecast/i});
  if(await target.count()){await target.click();opened=true;break;}
 }
 if(!opened) await page.waitForTimeout(250);
}
console.log('opened',opened,'cards',await cards.count());
await page.getByRole('button',{name:'Monthly',exact:true}).waitFor();
await save('forecast');console.log((await page.locator('body').innerText()).slice(-5000));
} catch(e){console.error(String(e));await save('error');process.exitCode=1;}finally{fs.writeFileSync(path.join(output,'logs.json'),JSON.stringify(logs));await browser.close();}
