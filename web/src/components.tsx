import { useId } from 'react';
import type { Graph, Moments } from './types';

export function Icon({ name, size=18 }: { name:string; size?:number }) {
  const paths:Record<string,React.ReactNode> = {
    arrow: <><path d="M4 12h16m-6-6 6 6-6 6"/></>, play:<path d="m8 5 11 7-11 7V5Z"/>,
    spark:<><path d="m12 3 2.2 6.8L21 12l-6.8 2.2L12 21l-2.2-6.8L3 12l6.8-2.2L12 3Z"/></>,
    upload:<><path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5"/></>, download:<><path d="M12 3v13m-5-5 5 5 5-5M4 16v5h16v-5"/></>,
    chevron:<path d="m8 5 7 7-7 7"/>, close:<path d="m6 6 12 12M6 18 18 6"/>, check:<path d="m5 12 4 4L19 6"/>,
    reset:<><path d="M3 10a9 9 0 1 1 2 8M3 4v6h6"/></>, info:<><circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/></>,
    table:<><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M3 14h18M9 4v16"/></>,
    graph:<><circle cx="5" cy="6" r="2"/><circle cx="19" cy="7" r="2"/><circle cx="12" cy="19" r="2"/><path d="m7 6 10 1M6 8l5 9m7-8-5 8"/></>,
    eye:<><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></>,
    flask:<><path d="M9 3h6m-5 0v7L4 19a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2l-6-9V3M7 16h10"/></>,
    lock:<><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4"/></>,
    layers:<><path d="m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5"/></>,
    sliders:<><path d="M4 3v18M12 3v18M20 3v18M1 8h6m2 8h6m2-11h6"/></>,
    book:<><path d="M12 6C9 3 5 3 2 4v15c4-1 7-1 10 2 3-3 6-3 10-2V4c-3-1-7-1-10 2Zm0 0v15"/></>,
    stop:<rect x="6" y="6" width="12" height="12" rx="1"/>, code:<><path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.info}</svg>;
}

export function Mark() { return <svg className="brand-mark" viewBox="0 0 42 42" fill="none" aria-hidden="true"><circle cx="21" cy="21" r="16"/><ellipse cx="21" cy="21" rx="7" ry="20"/><path d="M1 21h40M21 1v40"/><circle cx="21" cy="21" r="3" fill="currentColor"/></svg> }
export const fmt=(n:unknown, digits=3) => typeof n === 'number' ? (Number.isFinite(n) ? Math.abs(n)>9999 ? n.toExponential(2) : n.toLocaleString('en-US',{maximumFractionDigits:digits}) : '—') : '—';
export const pretty=(value:unknown) => JSON.stringify(value,null,2);
export const label=(value:string) => value.replaceAll('_',' ');

export function CausalGraph({ graph, selected, onSelect, mini=false, conflicts=[] }: { graph:Graph; selected?:string; onSelect?:(kind:'node'|'edge',id:string)=>void; mini?:boolean; conflicts?:unknown[] }) {
  const markerId=`arrow-${useId().replaceAll(':','')}`;
  const n=graph.nodes.length, width=640, height=mini?250:350;
  const points=Object.fromEntries(graph.nodes.map((node,i) => {
    if(n===2) return [node,{x:190+i*260,y:height/2}];
    if(n===3) return [node,[{x:142,y:height/2+28},{x:320,y:height/2-52},{x:498,y:height/2+28}][i]];
    const a=-Math.PI/2+i*2*Math.PI/n;
    return [node,{x:320+235*Math.cos(a),y:height/2+(height/2-58)*Math.sin(a)}];
  }));
  const r=mini?25:n>9?23:34;
  const edges=[...(graph.directed||[]).map(e=>({e,directed:true})),...(graph.undirected||[]).map(e=>({e,directed:false}))];
  return <svg viewBox={`0 0 ${width} ${height}`} className={`causal-graph ${mini?'mini-graph':''}`} role={mini?'img':'group'} aria-label={`Causal graph: ${n} variables, ${graph.directed?.length||0} directed and ${graph.undirected?.length||0} unresolved edges`}>
    <defs><marker id={markerId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 1 1 L 9 5 L 1 9" fill="none" stroke="context-stroke" strokeWidth="1.7"/></marker></defs>
    {!mini&&<><ellipse cx="320" cy={height/2} rx="276" ry="138" className="graph-orbit"/><path d={`M320 12v16m0 ${height-56}v16M24 ${height/2}h16m560 0h16`} className="graph-crosshair"/></>}
    {edges.map(({e:[a,b],directed})=>{const p=points[a],q=points[b];if(!p||!q)return null;const dx=q.x-p.x,dy=q.y-p.y,l=Math.hypot(dx,dy),id=`${a}|${b}`,active=selected===id||selected===`${b}|${a}`,conflict=conflicts.some(c=>JSON.stringify(c).includes(`"${a}"`)&&JSON.stringify(c).includes(`"${b}"`));
      return <g key={id} className={`graph-edge ${directed?'directed':'unresolved'} ${active?'selected':''} ${conflict?'conflicting':''}`} onClick={()=>onSelect?.('edge',id)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect?.('edge',id)}}} tabIndex={mini?-1:0} role={mini?undefined:'button'} aria-label={`${a} ${directed?'directed to':'unresolved with'} ${b}${conflict?', orientation conflict':''}`}>
        <line className="edge-hit" x1={p.x+dx*r/l} y1={p.y+dy*r/l} x2={q.x-dx*(r+6)/l} y2={q.y-dy*(r+6)/l}/>
        <line className="edge-line" x1={p.x+dx*(r+9)/l} y1={p.y+dy*(r+9)/l} x2={q.x-dx*(r+10)/l} y2={q.y-dy*(r+10)/l} markerEnd={directed?`url(#${markerId})`:undefined}/>
        {!mini&&<text className="edge-label" x={(p.x+q.x)/2} y={(p.y+q.y)/2-13}>{conflict?'conflict':directed?'directed':'unresolved'}</text>}
      </g>;
    })}
    {graph.nodes.map((node,i)=>{const p=points[node];return <g key={node} className={`graph-node ${selected===node?'selected':''}`} transform={`translate(${p.x},${p.y})`} onClick={()=>onSelect?.('node',node)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect?.('node',node)}}} tabIndex={mini?-1:0} role={mini?undefined:'button'} aria-label={`Inspect variable ${node}`}>
      {!mini&&<circle r={r+9} className="node-halo"/>}<circle r={r} className="node-disc"/><text className="node-name" textAnchor="middle" dy=".36em" style={{fontSize:node.length>3?Math.max(11,24-node.length):undefined}}>{node.length>8?`${node.slice(0,7)}…`:node}</text>{!mini&&<text className="node-number" textAnchor="middle" y={r+32}>VARIABLE {String(i+1).padStart(2,'0')}</text>}
    </g>})}
  </svg>;
}

export function Histogram({ values, variable }: { values:number[]; variable:string }) {
  if(!values.length) return <div className="empty-small">Select a dataset to inspect its distribution.</div>;
  const min=Math.min(...values),max=Math.max(...values),span=max-min||1,bins=new Array(22).fill(0);
  values.forEach(v=>bins[Math.min(21,Math.floor((v-min)/span*22))]++);
  const highest=Math.max(...bins);
  return <div className="histogram"><svg viewBox="0 0 280 80" role="img" aria-label={`Histogram of ${variable}, ${values.length} preview observations`}><path d="M0 70h280" className="chart-axis"/>{bins.map((count,i)=><rect key={i} x={i*12.6+1} y={70-count/highest*62} width="10" height={count/highest*62} rx="1"/>)}</svg><div className="chart-range"><span>{fmt(min,2)}</span><span>{fmt(max,2)}</span></div></div>;
}

export function DistributionChart({ observational, interventional, index }: { observational:Moments; interventional:Moments; index:number }) {
  const a=observational.mean[index],b=interventional.mean[index],sa=Math.sqrt(Math.max(0,observational.covariance[index][index])),sb=Math.sqrt(Math.max(0,interventional.covariance[index][index]));
  const lo=Math.min(a-3*sa,b-3*sb)-.2,hi=Math.max(a+3*sa,b+3*sb)+.2,span=hi-lo||1;
  const density=(x:number,m:number,s:number)=>Math.exp(-.5*((x-m)/s)**2)/s;
  const distributions=[{m:a,s:sa},{m:b,s:sb}];
  const series=distributions.map(({m,s})=>s<1e-10?[]:Array.from({length:140},(_,i)=>({x:i*280/139,y:density(lo+i*span/139,m,s)})));
  const peak=Math.max(1e-10,...series.flat().map(p=>p.y));
  return <svg className="distribution-chart" viewBox="0 0 280 95" role="img" aria-label={`Conditional mean ${fmt(a)}, variance ${fmt(sa*sa)}; intervention mean ${fmt(b)}, variance ${fmt(sb*sb)}. A vertical dashed line denotes a fixed value with zero variance.`}><path d="M0 80h280" className="chart-axis"/>{series.map((pts,i)=>pts.length?<path key={i} className={i?'curve-do':'curve-observe'} d={`M0 80 ${pts.map(p=>`L${p.x.toFixed(1)} ${(80-p.y/peak*65).toFixed(1)}`).join(' ')} L280 80Z`}/>:<g key={i}><path className={`${i?'curve-do':'curve-observe'} point-mass`} d={`M${(distributions[i].m-lo)/span*280} 80 V15`}/><circle cx={(distributions[i].m-lo)/span*280} cy={15} r="3" className={i?'curve-do':'curve-observe'}/></g>)}<text x="0" y="94">{fmt(lo,1)}</text><text x="280" y="94" textAnchor="end">{fmt(hi,1)}</text></svg>;
}

export function JsonDetails({ title, value, open=false }: {title:string;value:unknown;open?:boolean}) {return <details className="json-details" open={open}><summary>{title}<Icon name="chevron" size={13}/></summary><pre>{pretty(value)}</pre></details>}
