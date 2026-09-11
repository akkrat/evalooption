import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const [treeArg,url,outputArg]=process.argv.slice(2);
const tree=path.resolve(treeArg);
const study=path.dirname(new URL(import.meta.url).pathname);
const require=createRequire(path.join(tree,'package.json'));
const {chromium,expect}=require('@playwright/test');
const output=path.resolve(outputArg);
fs.mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({userAgent:'playwright',locale:'en-US',timezoneId:'UTC',viewport:{width:1280,height:720}});
const page=await context.newPage();page.setDefaultTimeout(20000);
const checks=[];const record=(id,evidence)=>checks.push({id,status:'passed',evidence});
const logs=[];page.on('pageerror',e=>logs.push(String(e)));
const save=async name=>{await page.waitForTimeout(1800);fs.writeFileSync(path.join(output,name+'.txt'),await page.locator('body').innerText());await page.screenshot({path:path.join(output,name+'.png'),fullPage:true});fs.writeFileSync(path.join(output,name+'-layout.json'),JSON.stringify(await page.getByLabel('Start date',{exact:true}).evaluate(el=>{const rows=[];for(let x=el;x;x=x.parentElement){const r=x.getBoundingClientRect(),s=getComputedStyle(x);rows.push({tag:x.tagName,rect:{top:r.top,bottom:r.bottom,height:r.height},scrollTop:x.scrollTop,clientHeight:x.clientHeight,scrollHeight:x.scrollHeight,overflow:s.overflow,flexShrink:s.flexShrink,display:s.display});}return rows;}),null,2));};
async function rpc(name,args){return page.evaluate(async ({name,args})=>{const w=await window.Actual.getServerSocket();const id=crypto.randomUUID();return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{w.removeEventListener('message',listener);reject(new Error('RPC timeout '+name))},10000);function listener(e){if(e.data.id!==id)return;clearTimeout(timer);w.removeEventListener('message',listener);if(e.data.type==='reply')resolve(e.data.result);else reject(new Error(JSON.stringify(e.data)));}w.addEventListener('message',listener);w.postMessage({id,name,args,catchErrors:false});});},{name,args});}
try {
await context.route('**/*',route=>new URL(route.request().url()).origin===new URL(url).origin?route.continue():route.abort());
await page.goto(url);
await page.getByRole('button',{name:"Don't use a server",exact:true}).click();
await page.getByRole('button',{name:'Start fresh',exact:true}).click();
await page.getByTestId('account-name').waitFor();
record('local-budget-startup','Fresh isolated IndexedDB budget, no imported reference DB');
const accounts=await rpc('accounts-get');if(accounts.length!==0)throw new Error('Fixture requires zero accounts');
const account=await rpc('account-create',{name:'Forecast Fixture',balance:1000});
const schedule=await rpc('schedule/create',{conditions:[{op:'is',field:'account',value:account},{op:'is',field:'amount',value:-20000},{op:'is',field:'date',value:{start:'2017-01-15',frequency:'monthly'}}]});
if(!await page.getByRole('link',{name:'Settings',exact:true}).isVisible()) await page.getByRole('button',{name:'More',exact:true}).click();
await page.getByRole('link',{name:'Settings',exact:true}).click();
await page.getByTestId('settings').waitFor();
await page.getByTestId('advanced-settings').click();
await page.getByTestId('experimental-settings').click();
const feature=page.getByRole('checkbox',{name:/balance.*forecast/i});
await expect(feature).not.toBeChecked();
await feature.click();await expect(feature).toBeChecked();record('experimental-opt-in','Disabled by default and can be enabled through settings');
await page.getByRole('link',{name:'Reports',exact:true}).click();
await page.getByRole('button',{name:'Add new widget'}).click();
await page.getByRole('button',{name:'Balance Forecast',exact:true}).click();
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
if(!opened)throw new Error('Forecast dashboard card could not be opened');record('dashboard-entry','Feature card added and opens report');
await page.getByRole('button',{name:'Daily',exact:true}).click();
await page.getByRole('button',{name:'Monthly',exact:true}).click();
await page.getByLabel('Start date',{exact:true}).fill('2017-01-01');
await page.getByLabel('End date',{exact:true}).fill('2017-12-31');
const report=page.locator('body');
const assertMinimum=async (amount,date)=>{
 await expect(report.getByText('Lowest projected balance',{exact:true}).locator('..').getByText(amount,{exact:true})).toBeVisible();
 const formatted={'2017-12-15':'Dec 15, 2017','2017-03-15':'Mar 15, 2017'}[date];
 await expect(report.getByText('Lowest projected balance',{exact:true}).locator('..').getByText(formatted,{exact:true})).toBeVisible();
};
await assertMinimum('-1,400.00','2017-12-15');
record('monthly-recurring-values','1000 opening balance minus twelve 200 monthly payments; minimum -1400 on December 15. Also discriminates against an unfrozen backend clock.');
await save('monthly');
await page.getByRole('button',{name:'Monthly',exact:true}).click();
await page.getByRole('button',{name:'Daily',exact:true}).click();
await assertMinimum('-1,400.00','2017-12-15');record('daily-projection','Daily granularity preserves exact lowest amount/date');await save('daily');
await page.getByLabel('End date',{exact:true}).fill('2017-03-31');
await assertMinimum('400.00','2017-03-15');record('range-projection','Three-month range includes exactly three scheduled payments');await save('three-months');
await page.getByRole('button',{name:'Save widget',exact:true}).click();
await expect(page.getByText('Dashboard widget successfully saved.',{exact:true}).first()).toBeVisible();
await page.reload();
await page.getByRole('button',{name:'Daily',exact:true}).waitFor();
await expect(page.getByLabel('Start date',{exact:true})).toHaveValue('2017-01-01');
await expect(page.getByLabel('End date',{exact:true})).toHaveValue('2017-03-31');
await assertMinimum('400.00','2017-03-15');record('persisted-widget','Saved range and daily granularity survive reload');
await rpc('transaction-add',{id:'fixture-posted-debit',account,amount:-5000,date:'2017-01-02',notes:'Fixture posted activity'});
await page.reload();await assertMinimum('350.00','2017-03-15');record('posted-activity','A posted 50 debit changes the forecast by exactly 50');await save('posted-activity');
// Additional unscored probe: all candidates default to Daily, so persist non-default Monthly too.
await page.getByRole('button',{name:'Daily',exact:true}).click();
await page.getByRole('button',{name:'Monthly',exact:true}).click();
await page.getByRole('button',{name:'Save widget',exact:true}).click();
await expect(page.getByText('Dashboard widget successfully saved.',{exact:true}).first()).toBeVisible();
await page.reload();
await page.getByRole('button',{name:'Monthly',exact:true}).waitFor();
await assertMinimum('350.00','2017-03-15');
record('additional-nondefault-granularity-persistence','Monthly is non-default and survives save/reload with unchanged 350 minimum on March 15; separate from the seven common checks.');
await save('monthly-persisted');
} catch(e){checks.push({id:'remaining-browser-flow',status:'failed',evidence:String(e)});console.error(String(e));await save('error');process.exitCode=1;}finally{fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({passed:checks.every(c=>c.status==='passed'),checks,logs,url:page.url(),clock:await page.evaluate(()=>Date.now()).catch(()=>null)},null,2));await browser.close();}
