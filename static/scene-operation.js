// A restart outlives the HTTP connection and may outlive the browser page.
export class SceneOperation {
 constructor(saved=null,now=()=>Date.now()){this.now=now;this.value=saved?.started&&now()-saved.started<3600000?saved:null}
 get pending(){return !!this.value&&!['ready','failed'].includes(this.value.stage)}
 begin(kind='restart',town=null){this.value={kind,town,started:this.now(),stage:'requesting',accepted:false,observed:false}}
 accept(){if(this.pending){this.value.accepted=true;if(this.value.stage==='requesting')this.value.stage='restarting'}}
 fail(message){if(this.value)this.value={...this.value,stage:'failed',message,ended:this.now()}}
 dismiss(){if(!this.pending)this.value=null}
 observe(s){
  const phase=s.phase;
  if(['restarting','starting','connecting'].includes(phase)&&s.requested_town&&
     (!this.pending||this.value.town!==s.requested_town)){
   this.begin('town',s.requested_town);this.value.accepted=true;
  }
  const restoring=phase==='connected'&&['restarting','restoring'].includes(s.recovery_operation?.stage);
  if(!this.pending&&restoring){this.begin('recovery');this.value.accepted=true}
  if(!this.pending&&['restarting','starting','connecting'].includes(phase)){this.begin(phase==='restarting'?'restart':'start');this.value.accepted=true}
  if(!this.pending)return false;
  const v=this.value;
  if(phase==='error'){this.fail(s.error||'The simulator reported an error.');return false}
  if(restoring){v.stage='restoring';v.kind='recovery';v.observed=true;this.checkTimeout();return false}
  if(['restarting','starting','connecting'].includes(phase)){v.stage=phase;v.observed=true;v.accepted=true;v.workers=s.worker_count}
  else if(phase==='connected'&&s.mode!=='native-replay'&&(v.accepted||v.observed)&&(!v.town||(s.map||'').replace(/^\/Game\//,'')===v.town.replace(/^\/Game\//,''))){v.stage='ready';v.ended=this.now();return true}
  else if(phase==='offline'&&v.accepted)v.stage='reconnecting';
  else if(phase==='connected'&&s.mode==='native-replay'&&!v.observed&&this.now()-v.started>20000)this.fail('The server has not begun the restart. Replay is still active; try Stop replay again.');
  this.checkTimeout();return false;
 }
 disconnected(){if(this.pending){this.value.stage=this.value.accepted?'reconnecting':'confirming';this.checkTimeout()}}
 checkTimeout(){if(this.pending&&this.now()-this.value.started>2100000)this.fail('The restart has not completed after 35 minutes. Check the simulator status and logs before retrying.')}
 display(){
  if(!this.value)return null;const v=this.value,seconds=Math.max(0,Math.floor(((v.ended||this.now())-v.started)/1000));
  const elapsed=seconds>=60?`${Math.floor(seconds/60)}m ${seconds%60}s`:`${seconds}s`;
  const stages={requesting:['Stopping replay','Sending the restart request…'],confirming:['Checking restart request','The connection closed before confirmation. Checking the server; the request will not be sent twice.'],restarting:['Restarting the scene','Stopping replay and closing the previous simulator.'],reconnecting:['Reconnecting to the server','The control service is restarting. This page will reconnect automatically.'],starting:['Starting CARLA',`Loading the scene${v.workers?` with ${v.workers} GPU worker${v.workers===1?'':'s'}`:''}. This can take several minutes.`],connecting:['Preparing the live scene','Connecting the map, Traffic Manager and simulator controls.'],restoring:['Restoring saved configuration','Restoring actors, sensor streams, weather and signal plans. Controls remain paused until verification finishes.'],ready:['Live scene ready',v.kind==='recovery'?'Saved actors, sensors, weather and signal plans are restored. The scene is paused.':'Restart complete. The scene is paused and ready.'],failed:['Scene restart needs attention',v.message]};
  if(v.kind==='town'){
   const name=v.town?.split('/').pop()||'selected town';
   stages.requesting=['Switching town',`Saving the current scene and requesting ${name}…`];
   stages.restarting=['Switching town',`Closing the previous simulator before loading ${name}.`];
   stages.starting=['Loading '+name,'Starting CARLA and its GPU workers in the selected town. Large towns can take several minutes on their first load.'];
   stages.ready=[name+' ready','The new town is loaded. The scene is paused; press Run to advance simulation time.'];
  }
  const [title,detail]=stages[v.stage]||stages.restarting;
  return {stage:v.stage,title:v.kind==='start'&&v.stage==='ready'?'CARLA ready':title,detail:v.kind==='start'&&v.stage==='ready'?'CARLA is online. The scene is paused; press Run to advance simulation time.':detail,elapsed,pending:this.pending,slow:this.pending&&seconds>90};
 }
}
