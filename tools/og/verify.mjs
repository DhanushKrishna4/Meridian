/** Verify the exported RGB image and initial static HTML. Optional --base-url
 * requests bytes over HTTP; it does not execute or automate a browser.
 */
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';
import sharp from 'sharp';
const root=fileURLToPath(new URL('../../',import.meta.url));
const args=process.argv.slice(2);
const option=name=>{const i=args.indexOf(name);return i<0?null:args[i+1];};
const canonical='https://dhanushkrishna4.github.io/Meridian/';
const imageURL=new URL('og-v1.png',canonical).href;
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
const localImage=await readFile(`${root}web/public/og-v1.png`);
const meta=await sharp(localImage).metadata();
assert.deepEqual([meta.width,meta.height],[1200,630]);
assert.equal(meta.space,'srgb');assert.equal(meta.channels,3);assert.equal(meta.hasAlpha,false);
assert.equal(meta.hasProfile,true);assert.equal(localImage[24],8);assert.equal(localImage[25],2);
assert(localImage.length<1_000_000);
assert.equal(digest(localImage),digest(await readFile(`${root}web/dist/og-v1.png`)));
const attrs=tag=>Object.fromEntries([...tag.matchAll(/([\w:-]+)\s*=\s*"([^"]*)"/g)].map(m=>[m[1],m[2]]));
function validateHTML(html) {
 const head=html.split(/<head[^>]*>/i)[1]?.split(/<\/head>/i)[0];assert(head,'Initial HTML has a head');
 const tags=[...head.matchAll(/<meta\b[^>]*>/gi)].map(m=>attrs(m[0]));
 const values={};
 for(const t of tags){const key=t.property||t.name;if(!key)continue;assert(!Object.hasOwn(values,key),`Duplicate ${key}`);values[key]=t.content;}
 for(const [key,value] of Object.entries({'og:type':'website','og:site_name':'Meridian','og:url':canonical,'og:image':imageURL,'og:image:type':'image/png','og:image:width':'1200','og:image:height':'630','twitter:card':'summary_large_image','twitter:image':imageURL})) assert.equal(values[key],value,key);
 for(const key of ['title','description','image:alt']) {assert(values[`og:${key}`]?.length>0);assert.equal(values[`og:${key}`],values[`twitter:${key}`]);}
 assert.equal(values.description,values['og:description']);
 const links=[...head.matchAll(/<link\b[^>]*>/gi)].map(m=>attrs(m[0])).filter(t=>t.rel==='canonical');
 assert.equal(links.length,1);assert.equal(links[0].href,canonical);
 assert(head.includes('<title>Meridian — a causal laboratory</title>'));
 return values;
}
validateHTML(await readFile(`${root}web/index.html`,'utf8'));
validateHTML(await readFile(`${root}web/dist/index.html`,'utf8'));
const report={checks:['1200×630, 8-bit truecolor RGB PNG','Opaque sRGB with embedded profile','Under 1 MB','Production image identical to source export','Unique static OG/Twitter tags with matching text and image','Absolute HTTPS canonical and image URLs with /Meridian/ case'],bytes:localImage.length,sha256:digest(localImage)};
const base=option('--base-url');
if(base){
 const pageResponse=await fetch(base);assert.equal(pageResponse.status,200);
 assert(pageResponse.headers.get('content-type')?.includes('text/html'));
 const pageHTML=await pageResponse.text();validateHTML(pageHTML);
 const imageResponse=await fetch(new URL('og-v1.png',base));assert.equal(imageResponse.status,200);
 assert(imageResponse.headers.get('content-type')?.includes('image/png'));
 const bytes=Buffer.from(await imageResponse.arrayBuffer());
 assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
 assert.equal(digest(bytes),digest(localImage));
 report.delivery={page:pageResponse.url,image:imageResponse.url,status:200,contentType:imageResponse.headers.get('content-type'),sha256:digest(bytes)};
 report.checks.push('HTTP initial HTML metadata verified','HTTP image/png signature and full SHA-256 match; no fallback HTML');
}
const output=JSON.stringify(report,null,2)+'\n';
if(option('--report'))await writeFile(option('--report'),output);
console.log(output);
