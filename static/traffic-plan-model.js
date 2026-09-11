export const directions=['left','straight','right'];
export const directionName=m=>m==='straight'?'Through':m==='left'?'Left':'Right';
export const stateName=v=>({Stop:'Stop',Protected:'Protected',Permissive:'Unprotected · yield',Off:'Off · closed',Caution:'Yellow clearance'}[v]||v);
export const configOf=p=>({phases:structuredClone(p?.phases||p?.defaults||[]),yellow_time:p?.yellow_time??3,all_red_time:p?.all_red_time??2});
export const fingerprint=p=>{const c=configOf(p);c.phases=c.phases.map(p=>({...p,states:Object.fromEntries(Object.entries(p.states||{}).sort(([a],[b])=>Number(a)-Number(b)).map(([id,m])=>[id,Object.fromEntries(directions.filter(d=>d in m).map(d=>[d,m[d]]))]))}));return JSON.stringify(c)};
export function normalizePlan(p,members){const c=configOf(p);c.phases=c.phases.map(phase=>({...phase,states:Object.fromEntries(members.map(a=>[String(a.id),Object.fromEntries(directions.map(m=>[m,phase.states[a.id]?.[m]||(a.movement_lanes?.[m]?'Stop':'Off')]))]))}));return c}
export const blankPhase=(members,name='New phase')=>({name,duration:15,states:Object.fromEntries(members.map(a=>[String(a.id),Object.fromEntries(directions.map(m=>[m,a.movement_lanes?.[m]?'Stop':'Off']))]))});
export const cycleDuration=p=>p.phases.reduce((n,x)=>n+Number(x.duration)+Number(p.yellow_time)+Number(p.all_red_time),0);
export function validatePlan(p,members,conflicts=[]){
 const errors=[];if(!p||!Array.isArray(p.phases)||p.phases.length<1||p.phases.length>16)return ['Use between 1 and 16 phases.'];
 const validNumber=(v,min,max)=>typeof v==='number'&&Number.isFinite(v)&&v>=min&&v<=max;
 for(const [k,label]of[['yellow_time','Yellow'],['all_red_time','All-red']])if(!validNumber(p[k],.5,30))errors.push(`${label} clearance must be 0.5–30 seconds.`);
 const byId=new Map(members.map(a=>[String(a.id),a]));
 for(const [i,phase]of p.phases.entries()){
  const prefix=`Phase ${i+1}`;if(!phase||typeof phase!=='object'||Array.isArray(phase)){errors.push(`${prefix} must be a phase object.`);continue}
  if(typeof phase.name!=='string'||!phase.name.trim()||phase.name.length>60)errors.push(`${prefix} needs a name of 1–60 characters.`);
  if(!validNumber(phase.duration,.5,600))errors.push(`${prefix} duration must be 0.5–600 seconds.`);
  if(!phase.states||typeof phase.states!=='object'||Array.isArray(phase.states)){errors.push(`${prefix} needs approach states.`);continue}
  for(const [id,moves]of Object.entries(phase.states)){
   const a=byId.get(id);if(!a){errors.push(`${prefix} references an approach outside this intersection.`);continue}
   if(!moves||typeof moves!=='object'||Array.isArray(moves)){errors.push(`${prefix}, approach ${id}: invalid movement states.`);continue}
   for(const [m,v]of Object.entries(moves)){
    if(!directions.includes(m)||!['Stop','Protected','Permissive','Off'].includes(v))errors.push(`${prefix}, approach ${id}: unknown movement or state.`);
    else if(!a.movement_lanes?.[m]&&v!=='Off')errors.push(`${prefix}, approach ${id}: no mapped ${directionName(m).toLowerCase()} movement.`);
    else if(m==='straight'&&v==='Permissive')errors.push(`${prefix}: unprotected operation is available for left and right turns.`);
   }
  }
  for(const [[a,am],[b,bm]]of conflicts)if(phase.states[a]?.[am]==='Protected'&&phase.states[b]?.[bm]==='Protected')errors.push(`${prefix}: approach ${a} ${directionName(am).toLowerCase()} conflicts with approach ${b} ${directionName(bm).toLowerCase()}. Use separate phases or make a turning movement unprotected.`);
 }
 return [...new Set(errors)];
}
export function exportPlan(map,group,members,config,name){return {format:'carla-traffic-plan',version:1,name,map,group_id:group,approaches:members.map(a=>({id:a.id,opendrive_id:String(a.opendrive_id??'')})),config:structuredClone(config)}}
export function importPlan(file,map,members,conflicts){
 if(file?.format!=='carla-traffic-plan'||file.version!==1||file.map!==map||!Array.isArray(file.approaches)||!file.config)throw Error('Choose a CARLA traffic-plan file for this loaded map.');
 if(file.approaches.length!==members.length)throw Error('This plan belongs to a different intersection.');
 const mapping=new Map(),used=new Set();for(const source of file.approaches){const match=members.find(a=>source.opendrive_id?String(a.opendrive_id)===String(source.opendrive_id):a.id===source.id);if(!match||used.has(match.id)||mapping.has(String(source.id)))throw Error('The plan approaches do not match this intersection.');used.add(match.id);mapping.set(String(source.id),String(match.id))}
 const p=structuredClone(file.config);if(!Array.isArray(p.phases))throw Error('The file has no phase sequence.');
 for(const phase of p.phases){if(!phase?.states||typeof phase.states!=='object')throw Error('A phase is missing its approach states.');const states={};for(const [id,v]of Object.entries(phase.states)){if(!mapping.has(id))throw Error('The file references an unknown approach.');states[mapping.get(id)]=v}phase.states=states}
 const errors=validatePlan(p,members,conflicts);if(errors.length)throw Error(errors[0]);return p;
}
