// A command response can arrive before an older status request finishes.
// Keep the acknowledged route visible until polling catches up to its revision.
export class DestinationState {
 constructor(){this.accepted=new Map();this.pending=new Set();this.errors=new Map()}
 begin(id){this.pending.add(String(id));this.errors.delete(String(id))}
 accept(id,result){id=String(id);this.accepted.set(id,result);this.pending.delete(id);this.errors.delete(id)}
 fail(id,error){id=String(id);this.pending.delete(id);this.errors.set(id,error.message)}
 merge(state){
  for(const [id,result] of this.accepted){
   const actor=state.managed?.[id];
   if(!actor){this.accepted.delete(id);continue}
   if((actor.route_update?.revision??0)>=(result.route_update?.revision??0)){this.accepted.delete(id);continue}
   state.managed[id]={...actor,...result};
  }
  return state;
 }
 reset(){this.accepted.clear();this.pending.clear();this.errors.clear()}
 describe(id,actor,running){
  id=String(id);
  if(this.pending.has(id))return 'Updating destination… Simulation continues.';
  if(this.errors.has(id))return `Destination not changed: ${this.errors.get(id)}. Previous route remains active.`;
  if(actor?.parked)return `${actor.parking_space?'Parked in '+actor.parking_space:'Parked scene vehicle'} · choose a road destination or another parking bay to drive there.`;
  if(actor?.parking_trip?.blocked)return 'Waiting / blocked: '+actor.parking_trip.blocked;
  if(actor?.parking_trip&&!actor.arrived){
   const trip=actor.parking_trip;
   const entry=trip.motion==='changing_gear'?'Stopping to change gear':trip.motion==='reversing'?'Backing into ':trip.motion==='forward'?'Pulling forward to set up reverse parking in ':'Preparing reverse parking in ';
   return ({leaving:'Leaving parking · low-speed maneuver, then Traffic Manager.',stopping:'Stopping before reverse parking in '+trip.bay,entering:entry+(trip.motion==='changing_gear'?'':trip.bay),driving:'Driving · Traffic Manager'+(trip.bay?' to reverse-parking approach for '+trip.bay:'.')}[trip.stage]||'Maneuver in progress')+(running?'':' Press Run to continue.');
  }
  if(!actor?.destination)return 'Choose a destination for this actor.';
  const revision=actor.route_update?.revision;
  const prefix=(revision?`Route ${revision} · `:'')+(actor.route_update?.preserved_junction?'Junction exit retained · ':'');
  if(actor.planner==='external')return prefix+(actor.destination.parking_space?`Parking goal ${actor.destination.parking_space} and heading sent to your external planner; it controls the parking maneuver.`:'Goal available to your external planner; it must follow the new route.');
  if(actor.arrived)return prefix+'Arrived. Choose another destination to continue.';
  return prefix+(running?'Active · following destination and obeying traffic signals.':'Ready · press Run to follow destination.');
 }
}
