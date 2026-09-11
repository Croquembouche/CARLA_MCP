const $=id=>document.getElementById(id);
export function updateGpuControls(live,busy,connected){
 const disabled=busy||!connected||live.running||!!live.recording||live.mode==='native-replay';
 $('apply-gpu-policy').disabled=disabled;
 $('benchmark-gpus').disabled=disabled||!(live.sensors||[]).some(s=>s.type.startsWith('sensor.camera.')||s.type.startsWith('sensor.lidar.')||s.type==='sensor.other.radar');
}
export function renderGpuResources(live){
 const op=live.gpu_operation;
 $('runtime-health').textContent=live.worker_health?.status==='failed'?`Worker failed: ${live.worker_health.detail}. Last complete frame ${live.worker_health.last_complete_frame}.`:`${live.running?'Running':'Paused'} · ${live.performance?.real_time_factor??'—'}× last-frame real-time factor · latest sensor frame ${live.last_complete_frame??live.frame??'—'}`;
 if(live.vehicle_lighting?.warnings?.length)$('runtime-health').textContent+=' · Lighting: '+live.vehicle_lighting.warnings.map(w=>`actor ${w.id}: ${w.detail}`).join('; ');
 $('recover-scene').hidden=live.phase!=='error'||!live.recovery_checkpoint;
 $('recovery-help').textContent=live.worker_health?.status==='failed'?'Recover the saved configuration to resume; completed recording frames are preserved':live.recovery_operation?.detail|| (live.last_sensor_delivery_wall?`Last complete sensor delivery ${Math.max(0,Date.now()/1000-live.last_sensor_delivery_wall).toFixed(1)} s ago${live.running?'':' · paused; age is expected to grow'}`:'');
 $('native-performance').textContent=(live.native_profiles||[]).map(p=>p.worker+' · '+p.age_seconds+' s old\n'+Object.entries(p.metrics).map(([k,v])=>k+': '+v.mean.toFixed(2)+' ms mean / '+v.p95.toFixed(2)+' p95').join('\n')).join('\n\n')||'Waiting for native profiling samples';
 $('signal-audit').textContent=JSON.stringify(live.signal_audit||{scope:'Step or run to observe movement entries'},null,2);

 $('gpu-operation').textContent=live.worker_health?.status==='failed'?'Worker group unavailable: '+live.worker_health.detail:op?op.detail+(['loading','warming','releasing','verifying'].includes(op.stage)?` · ${Math.floor(Date.now()/1000-op.started)} s elapsed`:''):`Active policy: ${live.gpu_profile||'—'}`;
 const benchmark=live.gpu_benchmark;
 $('gpu-benchmark-result').textContent=benchmark?.stage==='running'?benchmark.detail+'. '+(benchmark.results||[]).map(r=>`${r.workers} GPU: ${r.timings_ms.total_ms.mean.toFixed(1)} ms/frame`).join(' · '):benchmark?.stage==='complete'?`Measured selection: ${benchmark.selected_workers} GPU worker${benchmark.selected_workers===1?'':'s'}. `+benchmark.results.map(r=>`${r.workers} GPU: ${r.timings_ms.total_ms.mean.toFixed(1)} ms/frame`).join(' · '):benchmark?.stage==='failed'?'Profiling failed; inspect the error before running again.':'';
 const perf=live.performance,fields=[['total_ms','Complete frame'],['world_ms','World update'],['sensor_wait_ms','Additional sensor wait'],['control_ms','Controls / signals'],['ros_publish_ms','ROS publishing'],['signal_audit_ms','Traffic-rule observations'],['record_write_ms','Recording writes']];
 if(perf?.frames){
  $('frame-performance').replaceChildren(...fields.map(([key,label])=>{const row=document.createElement('div');if(!perf.timings_ms[key])return row;row.textContent=`${label}: ${perf.timings_ms[key].mean.toFixed(1)} ms mean · ${perf.timings_ms[key].p95.toFixed(1)} ms p95`;return row;}));
 }else $('frame-performance').textContent='Step or run to measure frame processing.';
}
