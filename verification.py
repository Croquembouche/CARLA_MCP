"""Recorded-data integrity and measured replay comparison; no simulator mutations."""
import hashlib,json,math,struct,time,sqlite3,itertools
from pathlib import Path

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()

def seal(path):
    files={str(p.relative_to(path)):{'bytes':p.stat().st_size,'sha256':digest(p)} for p in path.rglob('*')
           if p.is_file() and p.name not in ('integrity.json','verification.json','manifest.json')}
    (path/'integrity.json').write_text(json.dumps({'algorithm':'sha256','files':files},indent=2))

def verify_session(path):
    path=Path(path);manifest=json.loads((path/'manifest.json').read_text());errors=[];warnings=[]
    def error(message):
        if len(errors)<100:errors.append(message)
    integrity=path/'integrity.json'
    if integrity.exists():
        entries=json.loads(integrity.read_text()).get('files',{})
        for name,item in entries.items():
            target=(path/name).resolve()
            if not target.is_relative_to(path.resolve()) or not target.is_file():error(f'Missing or invalid file: {name}');continue
            if target.stat().st_size!=item['bytes'] or digest(target)!=item['sha256']:error(f'File integrity mismatch: {name}')
    else:entries={};warnings.append('Legacy or interrupted session: no complete integrity seal')
    expected={(a['id'],s['name']) for a in manifest.get('configuration',{}).get('actors',[]) for s in a.get('sensors',[])}
    saved_config=path/'configuration.json'
    if saved_config.exists() and json.loads(saved_config.read_text())!=manifest.get('configuration'):error('Manifest configuration differs from sealed configuration')
    count=0;last=None;offset=0;index=(path/'frames.idx').read_bytes();total_sensors=0
    if len(index)%8:error('Truncated frame index')
    with (path/'states.jsonl').open('rb') as f:
        for line in f:
            try:row=json.loads(line)
            except ValueError:error(f'Truncated/invalid state row {count}');break
            if count*8+8>len(index) or struct.unpack_from('<Q',index,count*8)[0]!=offset:error(f'Frame index mismatch at row {count}')
            if last and (row['frame']!=last['frame']+1 or abs(row['time']-last['time']-manifest.get('configuration',{}).get('fixed_delta_seconds',.05))>1e-4):error(f'Frame/time discontinuity at row {count}')
            samples=row.get('sensor_files',[]);keys=[(s['parent'],s['name']) for s in samples]
            if len(set(keys))!=len(keys) or (expected and set(keys)!=expected):error(f'Incomplete/duplicate sensor set at frame {row["frame"]}')
            for sample in samples:
                if sample['frame']!=row['frame'] or abs(sample['timestamp']-row['time'])>1e-5:error(f'Sensor timestamp mismatch: {sample["path"]}')
                target=(path/sample['path']).resolve()
                if not target.is_relative_to(path.resolve()) or not target.is_file():error(f'Missing sensor file: {sample["path"]}');continue
                if target.stat().st_size!=sample['bytes']:error(f'Sensor size mismatch: {sample["path"]}')
                if sample.get('sha256') and digest(target)!=sample['sha256']:error(f'Sensor hash mismatch: {sample["path"]}')
                if entries and sample['path'] not in entries:error(f'Unsealed sensor file: {sample["path"]}')
            if row.get('signal_audit',{}).get('violations'):warnings.append('Recorded signal-rule violations; inspect frame audit')
            total_sensors+=len(samples);count+=1;last=row;offset+=len(line)
    if count!=len(index)//8 or count!=manifest.get('frames'):error('Manifest/index/state frame counts differ')
    if not count:error('No complete frames')
    bag_counts={}
    if manifest.get('rosbag'):
        bags=list((path/'rosbag2').glob('*.db3'))
        if not bags:error('ROS bag database is missing')
        for bag in bags:
            try:
                with sqlite3.connect(f'file:{bag.resolve()}?mode=ro',uri=True) as db:
                    if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':error('ROS bag database consistency check failed')
                    for topic,n in db.execute('SELECT topics.name,count(messages.id) FROM topics LEFT JOIN messages ON topics.id=messages.topic_id GROUP BY topics.id'):
                        bag_counts[topic]=bag_counts.get(topic,0)+n
            except sqlite3.Error as exc:error(f'Cannot read ROS bag: {exc}')
        if bag_counts!=manifest.get('ros_topics',{}):error('ROS bag topic counts differ from recorded manifest')
        if count and (not bag_counts or any(n!=count for n in bag_counts.values())):error('ROS bag does not cover every recorded frame for every topic')
    if manifest.get('status')!='complete':warnings.append(f'Session status: {manifest.get("status")}')
    report={'id':path.name,'checked_at':time.time(),'status':'failed' if errors else 'verified' if entries and manifest.get('status')=='complete' else 'partial',
            'frames':count,'sensor_samples':total_sensors,'rosbag_topic_counts':bag_counts,'files_checked':len(entries),'errors':errors,'warnings':sorted(set(warnings)),
            'scope':'Stored bytes, frame index, sensor coverage and simulation timestamps; not proof of identical re-simulation'}
    (path/'verification.json').write_text(json.dumps(report,indent=2));return report

def compare_sessions(reference,candidate,position_tolerance=.05):
    integrity={str(p.name):verify_session(p)['status'] for p in (reference,candidate)}
    def load(path):
        manifest=json.loads((path/'manifest.json').read_text())
        def rows():
            with (path/'states.jsonl').open() as stream:
                for line in stream:yield json.loads(line)
        # Configuration order and role identify scenario actors across fresh actor IDs.
        actors={a['id']:(a['role'],i,a['model']) for i,a in enumerate(manifest.get('configuration',{}).get('actors',[]))}
        return manifest,rows(),actors
    ma,a,ka=load(reference);mb,b,kb=load(candidate)
    if ma['map']!=mb['map'] or set(ka.values())!=set(kb.values()):raise ValueError('Compare recordings of the same map and ordered actor configuration')
    errors=[f'Recording integrity is {status}: {name}' for name,status in integrity.items() if status!='verified'];square_sum=0.;square_max=0.;position_samples=0;yaw_max=0.;speed_max=0.;time_max=0.;signal_mismatches=0;sensor_differences=0;sensor_compared=0
    first_times=None;counts=[0,0];frames_compared=0
    for index,(ra,rb) in enumerate(itertools.zip_longest(a,b)):
        counts[0]+=ra is not None;counts[1]+=rb is not None
        if ra is None or rb is None:continue
        frames_compared+=1
        if first_times is None:first_times=(ra['time'],rb['time'])
        time_max=max(time_max,abs((ra['time']-first_times[0])-(rb['time']-first_times[1])))
        pa={ka[x['id']]:x for x in ra['actors'] if x['id'] in ka};pb={kb[x['id']]:x for x in rb['actors'] if x['id'] in kb}
        if set(pa)!=set(pb) and len(errors)<100:errors.append(f'Actor coverage differs at row {index}')
        for key in pa.keys()&pb.keys():
            x,y=pa[key]['pose'],pb[key]['pose'];square=sum((x[k]-y[k])**2 for k in ('x','y','z'));square_sum+=square;square_max=max(square_max,square);position_samples+=1;yaw_max=max(yaw_max,abs((x['yaw']-y['yaw']+180)%360-180))
        for key in pa.keys()&pb.keys():
            if 'velocity' in pa[key] and 'velocity' in pb[key]:speed_max=max(speed_max,math.sqrt(sum((pa[key]['velocity'][k]-pb[key]['velocity'][k])**2 for k in ('x','y','z'))))
        lights=lambda row:{str(x.get('opendrive_id',x['id'])):(x.get('state'),x.get('movement_word')) for x in row['actors'] if x['type']=='traffic.traffic_light'}
        signal_mismatches+=lights(ra)!=lights(rb)
        sa={(ka.get(s['parent']),s['name']):s.get('sha256') for s in ra.get('sensor_files',[])};sb={(kb.get(s['parent']),s['name']):s.get('sha256') for s in rb.get('sensor_files',[])}
        for key in sa.keys()&sb.keys():
            if sa[key] and sb[key]:sensor_compared+=1;sensor_differences+=sa[key]!=sb[key]
    maximum=math.sqrt(square_max);frames_equal=counts[0]==counts[1]
    return {'integrity':integrity,'reference':reference.name,'candidate':candidate.name,'frames_compared':frames_compared,'frame_counts_equal':frames_equal,
            'position_max_m':maximum,'position_rms_m':math.sqrt(square_sum/position_samples) if position_samples else None,'yaw_max_deg':yaw_max,
            'time_alignment_max_s':time_max,'velocity_max_error_mps':speed_max,'signal_mismatch_frames':signal_mismatches,'sensor_payloads_compared':sensor_compared,'sensor_payload_differences':sensor_differences,
            'position_tolerance_m':position_tolerance,'trajectory_pass':bool(position_samples) and frames_equal and not errors and maximum<=position_tolerance and yaw_max<=.5 and signal_mismatches==0 and time_max<1e-5 and speed_max<=.05,
            'errors':errors[:100],'scope':'Aligns by recording-relative frame and configured actor order; regenerated sensor bytes may differ'}
