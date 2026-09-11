const $=id=>document.getElementById(id);
export function updateGpuControls(live,busy,connected){
 const disabled=busy||!connected||live.running||!!live.recording||live.mode==='native-replay';
 $('apply-gpu-policy').disabled=disabled;
 $('benchmark-gpus').disabled=disabled||!(live.sensors||[]).some(s=>s.type.startsWith('sensor.camera.')||s.type.startsWith('sensor.lidar.')||s.type==='sensor.other.radar');
}
export function renderGpuResources(live){
 const op=live.gpu_operation;
 $('gpu-operation').textContent=op?op.detail+(['loading','warming','releasing','verifying'].includes(op.stage)?` · ${Math.floor(Date.now()/1000-op.started)} s elapsed`:''):`Active policy: ${live.gpu_profile||'—'}`;
 const benchmark=live.gpu_benchmark;
 $('gpu-benchmark-result').textContent=benchmark?.stage==='running'?benchmark.detail+'. '+(benchmark.results||[]).map(r=>`${r.workers} GPU: ${r.timings_ms.total_ms.mean.toFixed(1)} ms/frame`).join(' · '):benchmark?.stage==='complete'?`Measured selection: ${benchmark.selected_workers} GPU worker${benchmark.selected_workers===1?'':'s'}. `+benchmark.results.map(r=>`${r.workers} GPU: ${r.timings_ms.total_ms.mean.toFixed(1)} ms/frame`).join(' · '):benchmark?.stage==='failed'?'Profiling failed; inspect the error before running again.':'';
 const perf=live.performance,fields=[['total_ms','Complete frame'],['world_ms','World update'],['sensor_wait_ms','Additional sensor wait'],['control_ms','Controls / signals'],['publish_record_ms','ROS / recording']];
 if(perf?.frames){
  $('frame-performance').replaceChildren(...fields.map(([key,label])=>{const row=document.createElement('div');row.textContent=`${label}: ${perf.timings_ms[key].mean.toFixed(1)} ms mean · ${perf.timings_ms[key].p95.toFixed(1)} ms p95`;return row;}));
 }else $('frame-performance').textContent='Step or run to measure frame processing.';
}
