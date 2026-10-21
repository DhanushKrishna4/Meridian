import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { Resvg } from '@resvg/resvg-js';
import sharp from 'sharp';
import { interventionStudy, equivalenceStudy, finalArtwork } from './artwork.mjs';

const here=fileURLToPath(new URL('.', import.meta.url));
const publicDir=fileURLToPath(new URL('../../web/public/', import.meta.url));
const pngOptions={compressionLevel:9, palette:false, adaptiveFiltering:true};
async function render(svg) {
 const raw=new Resvg(svg,{fitTo:{mode:'width',value:2400},font:{loadSystemFonts:false}}).render().asPng();
 return sharp(raw).resize(1200,630,{kernel:'lanczos3'}).removeAlpha().toColourspace('srgb').withIccProfile('srgb').png(pngOptions).toBuffer();
}
await mkdir(`${here}studies`,{recursive:true});
await mkdir(`${here}proofs`,{recursive:true});
for (const [name,svg] of [['study-a-intervention',interventionStudy()],['study-b-equivalence',equivalenceStudy()]]) {
 await writeFile(`${here}studies/${name}.svg`,svg);
 await writeFile(`${here}studies/${name}.png`,await render(svg));
}
const svg=finalArtwork();
const png=await render(svg);
await writeFile(`${here}meridian-og.svg`,svg);
await writeFile(`${publicDir}og-v1.png`,png);
for(const [w,h] of [[600,315],[300,158]]) {
 await sharp(png).resize(w,h,{fit:'fill',kernel:'lanczos3'}).withIccProfile('srgb').png(pngOptions).toFile(`${here}proofs/${w}x${h}.png`);
}
for(const [name,region,w,h] of [
 ['crop-16x9',{left:40,top:0,width:1120,height:630},600,338],
 ['crop-square',{left:285,top:0,width:630,height:630},315,315],
 ['crop-inset',{left:60,top:32,width:1080,height:566},600,315],
]) await sharp(png).extract(region).resize(w,h).withIccProfile('srgb').png(pngOptions).toFile(`${here}proofs/${name}.png`);
const metadata=await sharp(png).metadata();
const report={width:metadata.width,height:metadata.height,space:metadata.space,channels:metadata.channels,hasAlpha:metadata.hasAlpha,hasProfile:metadata.hasProfile,pngColorType:png[25],bytes:png.length,sha256:createHash('sha256').update(png).digest('hex')};
await writeFile(`${here}export.json`,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
