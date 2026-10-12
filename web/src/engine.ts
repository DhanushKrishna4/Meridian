/** One authoritative Python worker; completed state survives worker termination. */
type Progress = {stage:string; completed?:number; total?:number; message?:string};
type Pending = {resolve:(value:any)=>void; reject:(error:Error)=>void; timer:ReturnType<typeof setTimeout>};
type EngineOptions = {workerFactory?:()=>Worker; watchdogMs?:number};
export class Engine {
  private worker: Worker | null = null;
  private generation = 0;
  private sequence = 0;
  private pending = new Map<number, Pending>();
  private snapshot: any = null;
  private needsRestore = false;
  private onProgress: (progress:Progress)=>void;
  private options:EngineOptions;
  constructor(onProgress:(progress:Progress)=>void = ()=>{}, options:EngineOptions = {}) { this.onProgress = onProgress; this.options=options; }
  private start() {
    if (this.worker) return;
    this.generation += 1;
    const generation = this.generation;
    this.worker = this.options.workerFactory?.() ?? new Worker(new URL('./worker.ts', import.meta.url), {type:'module'});
    this.worker.onmessage = ({data}) => {
      if (data.generation !== this.generation || generation !== this.generation) return;
      const job = this.pending.get(data.run);
      if (!job) return; // cancelled and superseded responses never commit
      if (data.type === 'progress') { this.onProgress(data.progress); return; }
      clearTimeout(job.timer); this.pending.delete(data.run);
      if (data.type === 'error') { job.reject(new Error(data.error)); return; }
      if (data.snapshot) this.snapshot = data.snapshot;
      job.resolve(data.result);
    };
    this.worker.onerror = (event) => { this.fail(new Error(event.message || 'Python worker failed. Retry to recover the last completed state.')); };
  }
  private fail(error:Error) {
    this.worker?.terminate(); this.worker = null; this.generation += 1; this.needsRestore = Boolean(this.snapshot);
    for (const job of this.pending.values()) { clearTimeout(job.timer); job.reject(error); }
    this.pending.clear();
  }
  private send(action:string, payload:unknown):Promise<any> {
    this.start();
    const run = ++this.sequence;
    const baseURL = new URL(import.meta.env.BASE_URL, location.href).href;
    return new Promise((resolve,reject)=> {
      const timer = setTimeout(()=>this.fail(new Error('Budget exhausted: worker watchdog stopped this operation. Last completed results are preserved.')), this.options.watchdogMs ?? 90000);
      this.pending.set(run,{resolve,reject,timer});
      this.worker!.postMessage({action,payload,run,generation:this.generation,baseURL});
    });
  }
  async run(action:string, payload:unknown = {}):Promise<any> {
    if (this.pending.size) throw new Error('A computation is already running. Cancel it before starting another.');
    if (this.needsRestore && this.snapshot) {
      this.onProgress({stage:'Recovering',message:'Restoring the last completed experiment in a fresh Python worker.'});
      await this.send('restore',{experiment:this.snapshot});
    }
    this.needsRestore = false;
    return this.send(action,payload);
  }
  cancel() { this.fail(new Error('Cancelled. Completed results are preserved; the next operation recovers them.')); }
  dispose() { this.fail(new Error('Worker closed.')); this.snapshot = null; }
}
