"""Evidence-based exclusions for estimated parking bays.

Geometry validation and traffic restrictions are separate checks. Distances are
measured from the complete footprint, never just the centre. A rule profile is
scenario policy; this is not a certification of all local parking requirements.
"""
import math

def point_in_polygon(p, polygon):
    inside=False
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        if (a[1]>p[1])!=(b[1]>p[1]) and p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:inside=not inside
    return inside

def segment_distance(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    t=max(0.,min(1.,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy or 1.)))
    return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)

def point_distance(p,polygon):
    return 0. if point_in_polygon(p,polygon) else min(segment_distance(p,a,b) for a,b in zip(polygon,polygon[1:]+polygon[:1]))

def polygon_distance(a,b):
    # Edge intersections also matter when neither polygon contains a vertex.
    def cross(p,q,r):return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    for p,q in zip(a,a[1:]+a[:1]):
        for r,s in zip(b,b[1:]+b[:1]):
            if cross(p,q,r)*cross(p,q,s)<0 and cross(r,s,p)*cross(r,s,q)<0:return 0.
    return min(min(point_distance(p,b) for p in a),min(point_distance(p,a) for p in b))

def screen_spaces(spaces,rules):
    """Keep only unrestricted candidates; retain rejected geometry and evidence."""
    allowed=[];excluded=[]
    for bay in spaces:
        reasons=[]
        for zone in rules.get('zones',[]):
            if zone.get('bay_ids') is not None:
                hit=bay['id'] in zone['bay_ids'];distance=None
            else:
                distance=polygon_distance(bay['polygon'],zone['polygon']) if 'polygon' in zone else point_distance(zone['point'],bay['polygon'])
                hit=distance<=zone.get('clearance_m',0.)+1e-7
            if hit:
                reason={k:zone[k] for k in ('id','kind','reason','evidence') if k in zone}
                if distance is not None:reason.update(distance_m=round(distance,3),clearance_m=zone.get('clearance_m',0.))
                reasons.append(reason)
        if reasons:excluded.append(dict(bay,restriction_reasons=reasons))
        else:allowed.append(bay)
    return allowed,excluded
