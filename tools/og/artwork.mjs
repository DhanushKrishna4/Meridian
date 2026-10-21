/** Editable Meridian poster layouts. Coordinates are in the 1200 × 630 canvas.
 * Typography is shaped from the bundled site fonts, then outlined for portability.
 * The diagrams are conceptual interventions on explicit DAGs, not measured fits.
 */
import * as fontkit from 'fontkit';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export const palette = {
  bg: '#0c141d', panel: '#101b26', surface: '#14222e', rule: '#293945',
  white: '#dce6ee', muted: '#95a9b8', faint: '#758c9d',
  teal: '#6ee4cf', amber: '#e4bc83', cut: '#50616b',
};
const dm = fontkit.openSync(fileURLToPath(new URL('./fonts/dm-sans-latin-wght-normal.ttf', import.meta.url)));
const mono = fontkit.openSync(fileURLToPath(new URL('./fonts/ibm-plex-mono-latin-400-normal.ttf', import.meta.url)));
const esc = s => String(s).replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;');
const n = x => Number(x.toFixed(4));

export function text(value, x, y, size, { fill=palette.white, weight=500, tracking=0, family='sans', anchor='start' }={}) {
  const font = family === 'mono' ? mono : dm.getVariation({ wght: weight });
  const run = font.layout(value);
  if (run.glyphs.some(g => g.id === 0)) throw new Error(`Missing glyph in ${value}`);
  const scale = size / font.unitsPerEm;
  const width = run.positions.reduce((sum,p) => sum+p.xAdvance*scale, 0) + tracking * (run.glyphs.length-1);
  let cursor = anchor === 'middle' ? x-width/2 : anchor === 'end' ? x-width : x;
  const paths = run.glyphs.map((glyph,i) => {
    const pos=run.positions[i];
    const path=`<path d="${glyph.path.toSVG()}" transform="translate(${n(cursor+pos.xOffset*scale)} ${n(y-pos.yOffset*scale)}) scale(${n(scale)} ${n(-scale)})"/>`;
    cursor += pos.xAdvance*scale+tracking;
    return path;
  }).join('');
  return `<g fill="${fill}" aria-label="${esc(value)}" data-text="${esc(value)}">${paths}</g>`;
}
const rect = (x,y,w,h,fill,stroke='none',sw=1,rx=0) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
const line = (x1,y1,x2,y2,color=palette.rule,width=2) => `<path d="M${x1} ${y1}L${x2} ${y2}" fill="none" stroke="${color}" stroke-width="${width}"/>`;
const arrow = (x1,y1,x2,y2,color=palette.teal,width=3,head=11) => {
  const a=Math.atan2(y2-y1,x2-x1), backX=x2-Math.cos(a)*head, backY=y2-Math.sin(a)*head;
  const dx=Math.sin(a)*head*.55,dy=-Math.cos(a)*head*.55;
  return line(x1,y1,x2,y2,color,width)+`<path d="M${n(backX+dx)} ${n(backY+dy)}L${x2} ${y2}L${n(backX-dx)} ${n(backY-dy)}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linejoin="miter"/>`;
};
const node = (name,x,y,{size=102,active=false,dim=false}={}) => {
 const color=active?palette.amber:dim?palette.muted:palette.teal;
 return rect(x-size/2,y-size/2,size,size,active?palette.amber:palette.panel,color,active?0:2,5)+text(name,x,y+size*.20,size*.58,{anchor:'middle',fill:active?palette.bg:color,weight:450});
};
const mark = (x,y,scale=1) => `<g transform="translate(${x} ${y}) scale(${scale})" fill="none" stroke="${palette.teal}" stroke-width="1.2"><circle r="16"/><ellipse rx="7" ry="20"/><path d="M-21 0H21M0-21V21"/><circle r="3" fill="${palette.teal}" stroke="none"/></g>`;
const title = (x,y,size) => text('meridian',x,y,size,{tracking:-size*.055,weight:500});
const wrapper = (body,description) => `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-labelledby="card-title card-desc"><title id="card-title">Meridian — a causal laboratory</title><desc id="card-desc">${esc(description)}</desc>${rect(0,0,1200,630,palette.bg)}${body}</svg>`;

export function interventionStudy() {
 const p=palette;
 let s='';
 s+=text('A LABORATORY FOR CAUSAL QUESTIONS',84,83,15,{family:'mono',fill:p.muted,tracking:1});
 s+=title(74,244,176);
 s+=mark(1080,160,1.85);
 s+=text('Change a cause. Follow the consequences.',84,296,28,{fill:p.muted,weight:400,tracking:-.4});
 s+=line(84,330,1116,330,p.rule,1);
 s+=text('do(Y = 1)',650,390,26,{family:'mono',fill:p.amber,anchor:'middle'});
 s+=arrow(650,402,650,423,p.amber,2,8);
 s+=node('X',220,476,{dim:true});
 s+=node('Y',650,476,{active:true});
 s+=node('Z',980,476);
 s+=line(271,476,401,476,p.cut,3);
 s+=arrow(451,476,599,476,p.cut,3,13);
 s+=line(416,495,438,457,p.amber,4);
 s+=arrow(701,476,929,476,p.teal,4,14);
 s+=text('incoming mechanism removed',430,552,16,{family:'mono',fill:p.muted,anchor:'middle'});
 s+=text('CONCEPTUAL CHAIN INTERVENTION',84,598,13,{family:'mono',fill:p.faint,tracking:.25});
 s+=text('meridian / causal inference',1116,598,13,{family:'mono',fill:p.muted,anchor:'end'});
 return wrapper(s,'Meridian. An intervention fixes Y to 1 and removes the incoming mechanism from X while retaining Y’s effect on Z. Conceptual chain model.');
}

export function equivalenceStudy() {
 const p=palette;
 let s='';
 s+=mark(86,81,1);
 s+=text('CAUSAL LABORATORY',124,87,15,{family:'mono',fill:p.muted,tracking:1});
 s+=title(76,228,142);
 s+=text('Same evidence.',84,345,48,{weight:450,tracking:-1.8});
 s+=text('Different causes.',84,404,48,{weight:450,fill:p.teal,tracking:-1.8});
 s+=text('Which experiment tells them apart?',84,461,22,{weight:400,fill:p.muted,tracking:-.35});
 s+=line(647,66,647,558,p.rule,1);
 const xs=[738,888,1038];
 const fixture=JSON.parse(readFileSync(new URL('../../examples/exact-fixture.json',import.meta.url),'utf8'));
 const means=fixture.do_y1.map(v => `(${v[0].toFixed(1)}, ${v[2].toFixed(1)})`);
 const rows=[{y:162,label:'X → Y → Z',dirs:[1,1],means:means[0]},{y:326,label:'X ← Y ← Z',dirs:[-1,-1],means:means[1]},{y:490,label:'X ← Y → Z',dirs:[-1,1],means:means[2]}];
 rows.forEach((r,i)=>{
  s+=text(`0${i+1}`,695,r.y-57,13,{family:'mono',fill:p.faint});
  xs.forEach((x,j)=>s+=node(['X','Y','Z'][j],x,r.y,{size:66,active:j===1}));
  r.dirs.forEach((d,j)=>s+=d===1?arrow(xs[j]+34,r.y,xs[j+1]-34,r.y,p.teal,2,9):arrow(xs[j+1]-34,r.y,xs[j]+34,r.y,p.teal,2,9));
  s+=text(`do(Y=1): (X,Z) = ${r.means}`,888,r.y+65,14,{family:'mono',fill:p.muted,anchor:'middle'});
 });
 s+=line(84,563,1116,563,p.rule,1);
 s+=text('EXACT THREE-MODEL FIXTURE',84,600,13,{family:'mono',fill:p.faint,tracking:.5});
 s+=text('Same observational covariance. Different intervention means.',1116,600,13,{family:'mono',fill:p.muted,anchor:'end'});
 return wrapper(s,'Meridian. Three exact, observationally equivalent causal chain and fork models predict different X and Z means after setting Y to 1.');
}

export function finalArtwork() {
 const p=palette;
 let s='';
 s+=text('A CAUSAL LABORATORY',84,76,18,{family:'mono',fill:p.muted,tracking:1.1});
 s+=text('meridian',74,242,182,{tracking:-7.2,weight:500});
 s+=mark(1075,158,1.85);
 s+=text('Change a cause. Follow the consequences.',84,298,30,{fill:p.muted,weight:400,tracking:-.5});
 s+=line(84,337,1116,337,p.rule,1);
 s+=text('do(Y = 1)',635,389,32,{family:'mono',fill:p.amber,anchor:'middle'});
 s+=arrow(635,403,635,423,p.amber,2,8);
 s+=node('X',190,485,{size:124,dim:true});
 s+=node('Y',635,485,{size:124,active:true});
 s+=node('Z',1010,485,{size:124});
 s+=line(252,485,388,485,'#455663',4);
 s+=line(445,485,573,485,'#455663',4);
 s+=line(404,507,430,463,p.amber,5);
 s+=arrow(697,485,948,485,p.teal,4,15);
 s+=text('Incoming link removed',416,589,24,{family:'mono',fill:p.muted,anchor:'middle'});
 return wrapper(s,'Meridian, a causal laboratory. An amber intervention sets Y to 1, cutting the incoming mechanism from X while preserving the effect on Z. A conceptual chain model, not a measured result.');
}
