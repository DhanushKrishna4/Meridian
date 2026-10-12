/** Preserve actionable errors without exposing a Python implementation traceback. */
export function workerErrorMessage(error:unknown):string {
  const message=(error instanceof Error ? error.message : String(error)).trim();
  if (message.includes('Traceback (most recent call last):')) {
    const lines=message.split(/\r?\n/);
    for (let index=lines.length-1;index>=0;index--) {
      const exception=lines[index].match(/^([A-Za-z_][\w.]*(?:Error|Exception|Interrupt)|StopIteration|GeneratorExit)(?::[ \t]*(.*))?$/);
      if (exception) {
        const detail=[exception[2]||'',...lines.slice(index+1)].join('\n').trim();
        return exception[1]==='ValueError' && detail ? detail : `${exception[1]}${detail?`: ${detail}`:''}`;
      }
    }
    return 'Python could not complete this operation. Check the selected data and settings, then retry.';
  }
  return message || 'The worker could not complete this operation. Retry to recover the last completed state.';
}
