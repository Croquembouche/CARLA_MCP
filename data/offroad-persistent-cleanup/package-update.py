import json,shutil,hashlib,zipfile
from pathlib import Path
root=Path(__file__).resolve().parent;bundle=Path('/mnt/simulations/maps/Town10HD_Opt-cleaned')
report=json.loads((root/'live-verification.json').read_text());assert report['verified']
shutil.copy2(root/'final-configuration.json',bundle/'scenario.json')
for name in ['live-verification.json','native-runtime-verification.json']:(bundle/name).write_text(json.dumps(report,indent=2)+'\n')
files=[p for p in bundle.rglob('*') if p.is_file() and 'backup' not in p.relative_to(bundle).parts and p.name!='SHA256SUMS.json'];sums={str(p.relative_to(bundle)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)};(bundle/'SHA256SUMS.json').write_text(json.dumps(sums,indent=2)+'\n')
archive=bundle.with_suffix('.zip');temp=archive.with_suffix('.zip.tmp')
with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
 for p in files+[bundle/'SHA256SUMS.json']:z.write(p,Path(bundle.name)/p.relative_to(bundle))
with zipfile.ZipFile(temp) as z:assert z.testzip() is None
for name,digest in sums.items():assert hashlib.sha256((bundle/name).read_bytes()).hexdigest()==digest
temp.replace(archive);print('Verified portable archive:',archive)
