# Parking spaces and parked background vehicles

In Scenario, expand Parking. Select a purple parking position in OpenDRIVE or
choose its ID in the dropdown. Pause to place a parked background vehicle. A
road or parking destination can then be assigned while the simulation is running.
The vehicle uses the physical parking controller for entry/exit and Traffic
Manager for the road portion. Occupancy, vehicle dimensions and obstruction
checks still apply. See [physical parking](parking-driving.md).

## Town10 curb survey — 10 September 2026

The inventory now contains **180 surveyed parking-position candidates**:
41 existing IDs with corrected geometry and 139 new roadside positions R001–R139.
**All 180 positions are open unless occupied.** As requested on 11 September,
the simulation no longer withholds mapped bays based on the historical traffic-rule audit.
Vehicle dimensions, occupancy and physical maneuver clearance are still checked.

The survey renders the exported Town10 road, curb, painted-edge and street
geometry from directly overhead, omitting buildings and vegetation. The review
page also hides static parked-car models to make the edges visible. It is a
static geometry view; it does not display live occupancy. The 19 gap-fill positions added in the individual-space review retain all prior IDs and are checked against the same pavement and restriction evidence. Open **Open unobstructed
Town10 curb survey** in the Parking panel to inspect it, choose a road region,
pan/zoom or turn the annotations off.

Both the OpenDRIVE view and the 3D scene use the same parking geometry:

- Every mapped position is a solid rectangle with a **P**, including all previously withheld
  positions. Continuous curb bands and dotted survey boundaries are not drawn.
- Purple means open; grey means occupied (including a bay claimed by an approaching vehicle).
- Click any position in OpenDRIVE or the survey to inspect it. All mapped positions
  are offered for placement and destinations; physical feasibility is checked per vehicle.
- The survey includes an optional overlay of 42 authored parking-meter locations.
  Meter presence is evidence of parking infrastructure, not blanket permission.

Most roadside strips have no painted divisions between individual vehicles.
Their lateral edges are measured from scene geometry, while the divisions along
the curb remain planning positions. Gap positions are 5–6 m long; the initial
roadside additions are 6 m long. Existing IDs retain their prior length where
the complete footprint fits. Residual curb fragments too short for a complete
5 m footprint are not offered as vehicle placements. These annotations
do not modify road lanes or assert that the rectangles are painted stalls.

## Geometry and restriction evidence

`diagnostics/redraw_parking.py` builds a proposal in `data/parking-redraw` from
the saved pre-survey annotations, OpenDRIVE and exported native mesh triangles.
It requires Shapely 2.1.2 in the control-center Python environment. It does not
deploy its proposal automatically.

The survey uses road asphalt/gutter surfaces, white/yellow paint and curb/sidewalk
material geometry. A 0.06 m closing radius joins small export seams between
asphalt and gutters; actual sidewalk/curb and painted-line surfaces are then
subtracted. A complete footprint must fit the resulting pavement, with no bay
intersection. OpenDRIVE provides lane identity and traffic heading, not the final
lateral parking boundaries. Curb-strip linework is simplified within 0.02 m.

The historical provisional restriction audit remains on disk for reference but is
not enforced in this simulation. No bay is withheld for sign coverage, hydrants,
crossings, bus stops or approach-control policy. This changes simulated availability;
it does not alter map geometry. OpenDRIVE and exported geometry revision checks
still protect against loading annotations from a different scene.

Projected Unreal decals are not reproduced by the browser mesh renderer. The
separate exported decal inventory was inspected; access-road decals are not
interpreted as individual parking stalls. Garage interiors and unconnected lots
are not automatically populated with parking positions.

The map-specific saved annotations are in `data/parking/Town10HD_Opt.json`.
Runtime loading checks OpenDRIVE, scene metadata and geometry digests to reject
stale surveys. After a reviewed annotation update, the `reload-parking` command
reloads the map overlay and destination/placement catalogue between ticks without
restarting CARLA. It is disabled during recording and replay. Refresh the browser
to fetch the revised map. The pre-survey inventory, overhead images, proposal and full
footprint verification are retained in `data/parking-redraw`.

## Recording and restoration

Parked vehicles remain normal physical CARLA actors, with autopilot disabled and
the handbrake applied until assigned a destination. They are captured in actor
states and native recording. Scenario exports retain parking IDs and poses.
An annotation update does not automatically delete or relocate existing actors.
