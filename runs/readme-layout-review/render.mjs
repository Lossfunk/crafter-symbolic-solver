// Local, disposable README layout proof; not part of the public package.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const runtime = '/Users/sushrutthorat/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const {marked} = await import(`${runtime}/marked/lib/marked.esm.js`);
const {chromium} = require(`${runtime}/playwright`);
const root = process.cwd();
const output = path.join(root, 'runs/readme-layout-review');
const label = process.argv[2];
if (!/^(before|after)(-utf8)?$/.test(label)) throw new Error('Use before or after, optionally -utf8');
const css = await fs.readFile(path.join(output, 'github-markdown.css'), 'utf8');
const markdown = await fs.readFile(label.startsWith('before') ? path.join(output, 'before.md') : path.join(root, 'README.md'), 'utf8');
const html = marked.parse(markdown, {gfm:true});
const browser = await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const report = [];
try {
  for (const width of [1100, 860, 640, 390]) {
    const page = await browser.newPage({viewport:{width,height:950},deviceScaleFactor:1});
    await page.route('http://readme.local/**', async route => {
      const local = decodeURIComponent(new URL(route.request().url()).pathname).replace(/^\//,'');
      if (local && !local.includes('..')) {
        try {
          const data = await fs.readFile(path.join(root, local));
          await route.fulfill({status:200,body:data,contentType:local.endsWith('.gif')?'image/gif':'text/plain'});
          return;
        } catch {}
      }
      await route.fulfill({status:200,contentType:'text/html; charset=utf-8',body:`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}
body{margin:0;background:#fff}.markdown-body{box-sizing:border-box;max-width:980px;margin:0 auto;padding:32px;min-width:200px}@media(max-width:767px){.markdown-body{padding:16px}}</style></head><body><article class="markdown-body">${html}</article></body></html>`});
    });
    await page.goto('http://readme.local/', {waitUntil:'networkidle'});
    const measurements = await page.locator('article img').evaluateAll(images => images.map(img => ({
      src:img.getAttribute('src'), loaded:img.complete && img.naturalWidth>0,
      natural:[img.naturalWidth,img.naturalHeight],
      width:img.getBoundingClientRect().width,height:img.getBoundingClientRect().height,
      x:img.getBoundingClientRect().x,y:img.getBoundingClientRect().y
    })));
    const overflow = await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));
    await page.screenshot({path:path.join(output,`${label}-${width}.png`),fullPage:true});
    const gallery = page.locator('article p').filter({has:page.locator('img')}).first();
    const target = label.startsWith('before') ? page.locator('article table').first() : gallery;
    await target.screenshot({path:path.join(output,`${label}-gallery-${width}.png`)});
    report.push({width,images:measurements,overflow});
    await page.close();
  }
} finally { await browser.close(); }
await fs.writeFile(path.join(output, `${label}.json`), JSON.stringify(report,null,2)+'\n', {flag:'wx'});
console.log(JSON.stringify(report,null,2));
