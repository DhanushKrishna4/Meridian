import { Engine } from './engine';
const run = document.querySelector<HTMLButtonElement>('#run')!;
const save = document.querySelector<HTMLButtonElement>('#save')!;
const status = document.querySelector<HTMLElement>('#status')!;
const output = document.querySelector<HTMLElement>('#report')!;
const list = document.querySelector<HTMLOListElement>('#results')!;
type Check={name:string;passed:boolean;milliseconds:number;detail?:string};
let report:Record<string,unknown>={};
function assert(value:unknown,message:string):asserts value {if(!value)throw new Error(message)}
function close(actual:any,expected:any,tolerance=1e-8,path='root') {
  if(typeof expected==='number'){assert(typeof actual==='number' && Math.abs(actual-expected)<=tolerance*Math.max(1,Math.abs(expected)),`${path}: ${actual} != ${expected}`);}
  else if(Array.isArray(expected)){assert(Array.isArray(actual)&&actual.length===expected.length,`${path}: dimension mismatch`);expected.forEach((v,i)=>close(actual[i],v,tolerance,`${path}[${i}]`));}
  else if(expected&&typeof expected==='object'){for(const key of Object.keys(expected))close(actual[key],expected[key],tolerance,`${path}.${key}`);}
  else assert(actual===expected,`${path}: value mismatch`);
}
run.onclick=async()=>{
 run.disabled=true;save.disabled=true;list.innerHTML='';
 const checks:Check[]=[];const started=performance.now();let cancelBootstrap=false;let lastProgress='';
 const engine=new Engine(p=>{lastProgress=p.stage;status.textContent=`${p.stage}: ${p.message||''}${p.completed===undefined?'':` (${p.completed}${p.total?`/${p.total}`:''})`}`;if(cancelBootstrap&&p.stage==='Bootstrap'&&(p.completed||0)>=1){cancelBootstrap=false;engine.cancel()}});
 const check=async(name:string,task:()=>Promise<void>)=>{const start=performance.now();let c:Check;try{await task();c={name,passed:true,milliseconds:performance.now()-start}}catch(e){c={name,passed:false,milliseconds:performance.now()-start,detail:String(e)}}checks.push(c);const li=document.createElement('li');li.className=c.passed?'pass':'fail';li.textContent=`${c.passed?'PASS':'FAIL'} · ${name}${c.detail?' — '+c.detail:''}`;list.append(li);output.textContent=JSON.stringify(checks,null,2)};
 await check('Protocol rejects injected stale worker generations and stale run IDs',async()=>{
   type Envelope={run:number;generation:number;action:string;payload:unknown};
   const workers:{onmessage:((event:{data:unknown})=>void)|null;onerror:unknown;postMessage:(data:Envelope)=>void;terminate:()=>void;last?:Envelope}[]=[];
   const fake=new Engine(()=>{}, {workerFactory:()=>{const w={onmessage:null,onerror:null,last:undefined,postMessage(data:Envelope){this.last=data},terminate(){}} as typeof workers[number];workers.push(w);return w as unknown as Worker}});
   let done=false;const cancelled=fake.run('fixture').catch(()=>null);const old=workers[0],oldMessage=old.last!;fake.cancel();await cancelled;
   const latest=fake.run('fixture').then(r=>{done=true;return r});const current=workers[1],currentMessage=current.last!;
   old.onmessage!({data:{...oldMessage,type:'result',result:'stale'}});
   current.onmessage!({data:{...currentMessage,run:oldMessage.run,type:'result',result:'wrong-run'}});
   await Promise.resolve();assert(!done,'Stale response committed');
   current.onmessage!({data:{...currentMessage,type:'result',result:'current'}});assert(await latest==='current','Current response rejected');fake.dispose();
 });
 await check('Watchdog terminates an unresponsive worker and allows retry',async()=>{
   let terminated=0,created=0;
   const fake=new Engine(()=>{},{watchdogMs:20,workerFactory:()=>{
     const generation=++created;
     const worker={onmessage:null as ((event:{data:unknown})=>void)|null,onerror:null,
       postMessage(data:{run:number;generation:number}){if(generation>1)queueMicrotask(()=>worker.onmessage?.({data:{...data,type:'result',result:'retry complete'}}))},
       terminate(){terminated++}};
     return worker as unknown as Worker;
   }});
   try {
     let exhausted=false;try{await fake.run('fixture')}catch(e){exhausted=String(e).includes('Budget exhausted')}
     assert(exhausted&&terminated===1,'Watchdog failed to terminate');
     assert(await fake.run('fixture')==='retry complete','Fresh worker did not complete the retry');
     assert(created===2&&terminated===1,'Retry did not use a fresh worker');
   } finally {fake.dispose()}
 });
 const native=await fetch('./native-fixture.json').then(r=>r.json());
 let session:any,snapshot:any,query:any,csv='';
 await check('Cold Python/NumPy startup + exact native fixture parity (1e-8)',async()=>{close(await engine.run('fixture'),native.exact)});
 await check('Native experiment imports across NumPy runtimes',async()=>{session=await engine.run('restore',{experiment:native.experiment});assert(session.candidates.length===3,'Expected 3 candidate extensions');query=await engine.run('query',{interventions:{Y:1},row:0});close(query.interventional,native.query.interventional);close(query.counterfactual,native.query.counterfactual)});
 await check('Seeded load, PC-stable and real three-candidate enumeration',async()=>{await engine.run('load',{world:'equivalence',seed:7,n:800});session=await engine.run('discover',{method:'pc'});assert(session.pc.status==='complete','PC incomplete');assert(session.candidates.length===3,'Wrong candidate count');assert(session.pc.tests>0&&session.pc.trace.length>5,'Missing computed trace');snapshot=await engine.run('export',{})});
 await check('Single and simultaneous interventions + factual invariance',async()=>{const q=await engine.run('query',{interventions:{X:1,Y:0},row:0});close(q.interventional.mean.slice(0,2),[1,0]);const same=await engine.run('query',{interventions:{Y:session.data[0][1]},row:0});close(same.factual,same.counterfactual);assert(q.interventional.covariance[1][1]===0,'Clamped variance is not zero')});
 await check('Covariance-sensitive disagreement and real oracle campaign',async()=>{const r=await engine.run('rank',{values:{Y:[0]}});assert(r.rankings.some((v:any)=>v.covariance_score>0),'Missing covariance term');const choices=await engine.run('rank',{});const chosen=choices.rankings[0];session=await engine.run('experiment',{...chosen,n:100});assert(session.history.length===1,'History missing');assert(Math.max(...session.candidates.map((c:any)=>c.weight))>.9,'Experimental likelihood did not update support');snapshot=await engine.run('export',{})});
 await check('Deterministic export/restore retains fitted parameters and outcomes',async()=>{await engine.run('load',{world:'collider'});const restored=await engine.run('restore',{experiment:snapshot});close(restored.history,session.history);close(restored.candidates,session.candidates)});
 await check('Tampered outcomes and invalid schema rejected without losing state',async()=>{const bad=structuredClone(snapshot);bad.state.history[0].outcomes[0][0]+=10;let rejected=0;try{await engine.run('restore',{experiment:bad})}catch{rejected++}try{await engine.run('restore',{experiment:{schema_version:999}})}catch{rejected++}assert(rejected===2,'Invalid imports accepted');const current=await engine.run('export',{});close(current.state.history,snapshot.state.history)});
 await check('SciPy loads lazily; NOTEARS computes and exposes diagnostics',async()=>{session=await engine.run('discover',{method:'notears'});assert(session.notears.trace.length>0&&session.notears.iterations>0,'Optimizer did not run');assert(session.notears.graph_valid,'Thresholded support invalid');assert(['complete','optimizer did not converge'].includes(session.notears.status),'Unexpected status');await engine.run('select',{index:'notears'});const q=await engine.run('query',{interventions:{Y:1}});assert(q.interventional.mean.every(Number.isFinite),'Nonfinite query')});
 await check('Bootstrap real replicate progress and conditional effect intervals',async()=>{const b=await engine.run('bootstrap',{replicates:3});assert(b.replicates===3&&b.completed>0,'Bootstrap did not run');assert(b.effect_lower.length===3,'Effect intervals missing')});
 await check('Cancellation stops active worker; next query restores completed state',async()=>{const before=await engine.run('export',{});cancelBootstrap=true;let cancelled=false;try{await engine.run('bootstrap',{replicates:40})}catch(e){cancelled=String(e).includes('Cancelled')}assert(cancelled,'Expected cancellation');const recovered=await engine.run('export',{});close(recovered.state,before.state);await engine.run('query',{interventions:{Y:0}});assert(lastProgress.length>0,'Missing progress')});
 await check('Repeated real runs retain the latest completed dataset state',async()=>{for(let i=0;i<4;i++){await engine.run('load',{world:'equivalence',seed:7+i,n:300});session=await engine.run('discover',{method:'pc'});assert(session.seed===7+i,'Stale result replaced current run')}await engine.run('load',{world:'equivalence',seed:7,n:800});session=await engine.run('discover',{method:'pc'})});
 await check('CSV stays local; no fabricated outcomes; explicit model simulation',async()=>{csv='X,Y,Z\n'+session.data.map((r:number[])=>r.join(',')).join('\n');await engine.run('load',{csv});session=await engine.run('discover',{method:'pc'});let rejected=false;try{await engine.run('experiment',{variable:'Y',value:1,n:30})}catch(e){rejected=String(e).includes('oracle')}assert(rejected,'CSV fabricated oracle');session=await engine.run('experiment',{variable:'Y',value:1,n:30,simulate_model:true});assert(session.history[0].source.includes('not measured'),'Simulation not labeled')});
 await check('Malformed/missing CSV rejected clearly, current observations retained',async()=>{const before=await engine.run('export',{});let rejected=0;for(const text of ['A,B\n1,2','A,A\n1,2','A,B\n'+'1,\n'.repeat(30)]){try{await engine.run('load',{csv:text})}catch(error){assert(!String(error).includes('Traceback (most recent call last):'),'Implementation traceback exposed');assert(String(error).length>12,'Missing useful error');rejected++}}assert(rejected===3,'Invalid CSV accepted');const after=await engine.run('export',{});assert(before.dataset.id===after.dataset.id,'Bad CSV mutated state')});
 await check('Measured experimental CSV imported separately and evidence counted once',async()=>{await engine.run('restore',{experiment:snapshot});const recorded=snapshot.state.history[0];const measured='X,Y,Z\n'+recorded.outcomes.map((r:number[])=>r.join(',')).join('\n');let duplicate=false;try{await engine.run('experiment',{variable:Object.keys(recorded.plan.intervention)[0],value:Object.values(recorded.plan.intervention)[0],n:100,csv:measured})}catch(e){duplicate=String(e).includes('already')}assert(duplicate,'Duplicate evidence was accepted')});
 await check('Model building is explicit; cyclic model rejected',async()=>{const original=(await engine.run('export',{})).state.pc;const model={nodes:['X','Y','Z'],B:[[0,0,0],[.8,0,0],[0,.8,0]],intercept:[0,0,0],noise_variances:[1,.36,.36]};await engine.run('model',model);const q=await engine.run('query',{interventions:{Y:0},row:0});assert(q.model_label.includes('user-specified'),'Missing model provenance');const cyclic={...model,B:[[0,0,.2],[.8,0,0],[0,.8,0]]};let rejected=false;try{await engine.run('model',cyclic)}catch{rejected=true}assert(rejected,'Cyclic SCM accepted');close((await engine.run('export',{})).state.pc,original)});
 await check('Truth reveal does not modify discovery or support',async()=>{await engine.run('load',{world:'hidden',n:300});await engine.run('discover',{method:'pc'});const before=await engine.run('export',{});const truth=await engine.run('truth');assert(truth.assumption_violation==='causal sufficiency','Hidden world not explicit');close((await engine.run('export',{})).state,before.state)});
 engine.dispose();
 const resources=performance.getEntriesByType('resource').map(e=>e.name);
 report={timestamp:new Date().toISOString(),path:location.pathname,userAgent:navigator.userAgent,milliseconds:performance.now()-started,passed:checks.filter(c=>c.passed).length,failed:checks.filter(c=>!c.passed).length,checks,externalResourceRequests:resources.filter(url=>new URL(url).origin!==location.origin),tolerance:'1e-8 relative to max(1,abs(reference))',notes:['UI layout and keyboard checks are recorded separately.','Repeated-run test checks state cleanup behavior; browser heap memory is not instrumented.']};
 output.textContent=JSON.stringify(report,null,2);status.textContent=`Complete: ${report.passed} passed, ${report.failed} failed`;run.disabled=false;save.disabled=false;
};
save.onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='meridian-browser-report.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
