import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const study = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(study, '../..');
const require = createRequire(path.join(root, '.eval-cache/actual-forecast/base/package.json'));
const { chromium } = require('playwright');
const [url = 'http://127.0.0.1:43171', output = path.join(study, 'validation/browser-probe')] = process.argv.slice(2);
fs.mkdirSync(output, {recursive: true});
const browser = await chromium.launch({headless: true});
let page;
const errors = [];
try {
  const context = await browser.newContext({userAgent:'playwright', locale:'en-US', timezoneId:'UTC',
    viewport:{width:1280,height:720}});
  await context.route('**/*', route => {
    const target = new URL(route.request().url());
    return target.hostname === '127.0.0.1' || target.hostname === 'localhost' ? route.continue() : route.abort();
  });
  page = await context.newPage();
  page.on('pageerror', error => errors.push(String(error)));
  page.on('console', message => { if(message.type()==='error') errors.push(message.text()); });
  page.on('requestfailed', request => errors.push(request.url()+': '+request.failure()?.errorText));
  await page.goto(url, {waitUntil:'domcontentloaded'});
  const localOnly = page.getByRole('button', {name:"Don't use a server", exact:true});
  const createFixture = page.getByRole('button', {name:/^(Create test file|View demo)$/}).first();
  await Promise.race([
    localOnly.waitFor({timeout:60000}),
    createFixture.waitFor({timeout:60000}),
  ]);
  if(await localOnly.isVisible()) await localOnly.click();
  await createFixture.waitFor({timeout:60000});
  await createFixture.click();
  await page.getByTestId('budget-table').waitFor({timeout:60000});
  const workerClocks = [];
  for (const worker of page.workers()) {
    // The synchronous SQLite worker can remain inside Atomics.wait; do not
    // attempt a debugger evaluation there. The application backend is observable.
    if(!worker.url().includes('kcab.worker')) continue;
    let timer;
    const now = await Promise.race([
      worker.evaluate(() => Date.now()),
      new Promise(resolve => { timer=setTimeout(()=>resolve(null),5000); }),
    ]);
    clearTimeout(timer);
    workerClocks.push({url:worker.url(), now});
  }
  const result = {url:page.url(), pageNow:await page.evaluate(() => Date.now()), workerClocks, errors,
    body:await page.locator('body').innerText()};
  await page.screenshot({path:path.join(output,'budget.png'), fullPage:true});
  fs.writeFileSync(path.join(output,'result.json'), JSON.stringify(result,null,2));
  console.log(JSON.stringify({...result,body:result.body.slice(0,600)}));
} catch (error) {
  const result = {status:'error', error:String(error), errors, url:page?.url(),
    body:page ? await page.locator('body').innerText().catch(()=>'<unavailable>') : ''};
  if(page) await page.screenshot({path:path.join(output,'failure.png'),fullPage:true}).catch(()=>{});
  fs.writeFileSync(path.join(output,'result.json'), JSON.stringify(result,null,2));
  console.error(JSON.stringify(result));
  process.exitCode = 1;
} finally { await browser.close(); }
