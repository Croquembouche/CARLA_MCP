#!/usr/bin/env python3
"""Fit a profile from paired reference-target CSV, then evaluate held-out captures.

CSV columns: capture_id, channel, true_range_m, measured_range_m, signal_photons,
response, detected, saturated, split (train or validation). Missing detections
must be rows with detected=0; response is the known target's angular return
fraction. This tool requires signal expressed in detected-photon units, not
arbitrary vendor intensity counts. It never labels a profile hardware validated.
"""
import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
import numpy as np


def read_csv(path):
    rows=list(csv.DictReader(Path(path).open()))
    required={'capture_id','channel','true_range_m','measured_range_m','signal_photons','response','detected','saturated','split'}
    if not rows or not required.issubset(rows[0]):raise ValueError('CSV requires columns: '+', '.join(sorted(required)))
    parsed=[];groups={}
    for r in rows:
        split=r['split'];group=r['capture_id']
        if split not in ('train','validation') or not group:raise ValueError('Each row needs a capture ID and train/validation split')
        if group in groups and groups[group]!=split:raise ValueError('A capture cannot appear in training and validation')
        groups[group]=split
        channel=int(r['channel']);detected=int(r['detected']);saturated=int(r['saturated'])
        distance=float(r['true_range_m']);response=float(r['response'])
        measured=float(r['measured_range_m']) if detected else np.nan
        signal=float(r['signal_photons']) if detected else np.nan
        if channel<0 or channel>4095 or detected not in (0,1) or saturated not in (0,1):raise ValueError('Invalid channel or detection flag')
        if not np.isfinite([distance,response]).all() or distance<=0 or not 0<response<=1:raise ValueError('Reference range/response must be finite and positive; response <= 1')
        if detected and (not np.isfinite([measured,signal]).all() or measured<=0 or signal<0):raise ValueError('Detected rows require valid measured range and photon signal')
        parsed.append(dict(split=split,channel=channel,true_range=distance,range=measured,signal=signal,response=response,detected=detected,saturated=saturated))
    if set(groups.values())!={'train','validation'}:raise ValueError('Both training and held-out validation captures are required')
    return parsed


def evaluate(rows,profile):
    result=[];receiver=profile.get('receiver',{});bias=receiver.get('range_bias_m',0)
    for channel in sorted({r['channel'] for r in rows}):
        points=[r for r in rows if r['channel']==channel]
        bins=[]
        for lo,hi in [(0,10),(10,25),(25,50),(50,100),(100,1000)]:
            selected=[r for r in points if lo<=r['true_range']<hi]
            if not selected:continue
            errors=[r['range']-r['true_range']-bias-profile['channel_range_bias_m'][channel] for r in selected if r['detected'] and not r['saturated']]
            bins.append(dict(range_m=[lo,hi],emitted=len(selected),detected=sum(r['detected'] for r in selected),
                detection_probability=sum(r['detected'] for r in selected)/len(selected),
                residual_bias_m=float(np.median(errors)) if errors else None,
                residual_rmse_m=float(np.sqrt(np.mean(np.square(errors)))) if errors else None,
                residual_p95_abs_m=float(np.quantile(np.abs(errors),.95)) if errors else None))
        result.append(dict(channel=channel,bins=bins))
    return result


def fit(rows,base,evidence_sha256):
    profile=copy.deepcopy(base);receiver=profile.setdefault('receiver',{})
    channels=max(r['channel'] for r in rows)+1
    if set(r['channel'] for r in rows)!=set(range(channels)):raise ValueError('Provide contiguous channel numbers starting at zero')
    gain=receiver.get('pulse_energy_nj',40)*1e-9*receiver.get('wavelength_nm',905)*1e-9/(6.62607015e-34*299792458)*receiver.get('aperture_diameter_m',.015)**2*.25*receiver.get('efficiency',.1)
    overlap=receiver.get('overlap_distance_m',.5);bias=receiver.get('range_bias_m',0)
    profile['channel_range_bias_m']=[];profile['channel_gain']=[]
    for c in range(channels):
        train=[r for r in rows if r['channel']==c and r['split']=='train' and r['detected'] and not r['saturated']]
        validation=[r for r in rows if r['channel']==c and r['split']=='validation']
        if len(train)<20 or len(validation)<10:raise ValueError(f'Channel {c} requires 20 usable training returns and 10 held-out emitted shots')
        correction=float(np.median([r['range']-r['true_range']-bias for r in train]))
        scale=float(np.median([r['signal']*(r['true_range']**2+overlap**2)/(gain*r['response']) for r in train]))
        if not -10<=correction<=10 or not .001<=scale<=1000:raise ValueError('Fitted correction is outside native profile bounds; check units')
        profile['channel_range_bias_m'].append(correction);profile['channel_gain'].append(scale)
    profile['calibration']={'status':'fitted','evidence_sha256':evidence_sha256,'method':'reference-range-and-photon-gain-v1'}
    validation=evaluate([r for r in rows if r['split']=='validation'],profile)
    report={'status':'fitted','evidence_sha256':evidence_sha256,'rows':len(rows),'channels':channels,'validation':validation,
        'scope':'Fits channel range offsets and photon gain using known response targets. Held-out residuals describe this dataset, not a general hardware fidelity guarantee.',
        'requires_separate_validation':['firing pattern and motion','beam footprint and edge mixtures','receiver detection thresholds and false alarms','spectral materials','weather and cover contamination','saturation and multipath','clock and packet timing']}
    return profile,report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv',type=Path);parser.add_argument('--base-profile',required=True,type=Path)
    parser.add_argument('--output-profile',required=True,type=Path);parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args()
    if args.output_profile.resolve()==args.base_profile.resolve():parser.error('Write a separate candidate profile before deployment')
    digest=hashlib.sha256(args.csv.read_bytes()).hexdigest()
    profile,report=fit(read_csv(args.csv),json.loads(args.base_profile.read_text()),digest)
    args.output_profile.write_text(json.dumps(profile,indent=2,allow_nan=False)+'\n')
    args.report.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':'fitted','profile':str(args.output_profile),'report':str(args.report),'channels':report['channels']}))

if __name__=='__main__':main()
