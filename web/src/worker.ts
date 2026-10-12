/// <reference lib="webworker" />
import {workerErrorMessage} from './worker-error';
declare const self: DedicatedWorkerGlobalScope;
let python:any = null;
let scipyLoaded = false;
let busy = false;

self.onmessage = async ({data}) => {
  const {action,payload,run,generation,baseURL} = data;
  const progress = (value:unknown) => self.postMessage({type:'progress',run,generation,progress:value});
  if (busy) {self.postMessage({type:'error',run,generation,error:'Worker is busy.'}); return;}
  busy = true;
  try {
    if (!python) {
      progress({stage:'Starting Python',message:'Loading the bundled local Python runtime.'});
      const runtimeURL = new URL('runtime/',baseURL).href;
      const entry = runtimeURL+'pyodide.mjs';
      const {loadPyodide} = await import(/* @vite-ignore */ entry);
      python = await loadPyodide({indexURL:runtimeURL});
      progress({stage:'Loading NumPy',message:'Preparing local numerical computation.'});
      await python.loadPackage('numpy');
      const response = await fetch(new URL('python/meridian.zip',baseURL));
      if (!response.ok) throw new Error('The shared Python package could not be loaded. Rebuild static assets.');
      python.unpackArchive(await response.arrayBuffer(),'zip',{extractDir:'/home/pyodide'});
      python.runPython('import json\nfrom meridian_causal.api import Laboratory\nlab = Laboratory()');
    }
    if (action === 'discover' && payload.method === 'notears' && !scipyLoaded) {
      progress({stage:'Loading SciPy',message:'Loading the optimizer only when NOTEARS needs it.'});
      await python.loadPackage('scipy'); scipyLoaded = true;
    }
    python.globals.set('_action',action);
    python.globals.set('_payload',JSON.stringify(payload));
    python.globals.set('_progress',(encoded:string)=>progress(JSON.parse(encoded)));
    python.runPython('lab.progress = lambda event: _progress(json.dumps(event))\ntask = lab.steps(_action, json.loads(_payload))');
    for (;;) {
      const event = JSON.parse(python.runPython('json.dumps(next(task), allow_nan=False)'));
      if ('result' in event) {
        let snapshot = null;
        if (['load','discover','select','experiment','model','restore','bootstrap'].includes(action)) {
          snapshot = JSON.parse(python.runPython('json.dumps(lab.export(include_data=True), allow_nan=False)'));
        }
        self.postMessage({type:'result',run,generation,result:event.result,snapshot});
        break;
      }
      progress(event);
      await new Promise(resolve=>setTimeout(resolve,0));
    }
  } catch (error) {
    self.postMessage({type:'error',run,generation,error:workerErrorMessage(error)});
  } finally {
    if (python) python.runPython('globals().pop("task", None)\nglobals().pop("_payload", None)\nglobals().pop("_progress", None)');
    busy = false;
  }
};
