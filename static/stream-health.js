export function streamHealth(state,replyAge=0){
 if(replyAge>5)return {status:'waiting',text:`Server response delayed · ${replyAge.toFixed(1)} s`};
 if(state.phase!=='connected')return {status:'idle',text:state.phase==='error'?'Simulation needs attention':'Waiting for simulator'};
 if(!state.running)return {status:'idle',text:'Simulation paused'};
 const h=state.stream_health||{},age=Number(h.elapsed_seconds)||0;
 if(h.stage!=='complete'&&age>2){const task=h.stage==='sensor'?`Waiting for ${h.sensor||'sensor data'}`:h.stage==='world'?'Waiting for simulation step':h.stage==='publish'?'Publishing completed frame':'Updating scene controls';return {status:'waiting',text:`${task} · ${age.toFixed(1)} s`};}
 return {status:'ready',text:`Data live · frame ${state.last_complete_frame??state.frame??'—'}`};
}
