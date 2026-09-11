# Vehicle destinations and physical parking

Ego vehicles and all managed background vehicles, including converted map scenery, expose the
same Destination control. Choose a road point or one of the parking bays in
its dropdown. The map's Destination tool also accepts a purple bay outline.
Changing the dropdown applies immediately while running or paused. A new goal
replaces the active route from the current pose, including during a parking
maneuver; it does not wait for arrival. While paused, press Run to begin moving.
Replay remains read-only.

The low-speed controller drives leaving/entering maneuvers with CARLA vehicle
controls and physical simulation. It does not teleport vehicles. Traffic
Manager takes over for the road portion, with the existing junction-aware
route anchors, lane checks, and traffic-light/sign compliance settings. Local
parking paths must not cross a junction. Adjacent bays on the same road can
use a direct low-speed maneuver. Bay destinations now default to backing in:
Traffic Manager drives past the bay, the vehicle stops, and the local planner
executes a reverse entry. The planner can include forward setup segments, but
the final entry must be in reverse. Direction changes require the vehicle to stop. End-of-parking checks include the whole
vehicle footprint and its heading, with up to two alignment corrections.

The interface displays the road approach, stopping before reverse parking,
pulling forward to set up, backing into the named bay, changing gear, arrived,
and waiting/blocked states. A temporary vehicle/pedestrian obstruction causes
the controller to hold the brake and wait. A stalled or untrackable maneuver
stops with an explanation; clear the obstruction and apply the destination
again. A rejected destination leaves the old plan active.

A destination bay is reserved as soon as its plan is accepted. Other vehicles
cannot reserve or be placed into that bay until the reservation is released.
Deleting or retargeting a vehicle releases its reservation. Occupancy is still
checked from the live vehicle footprints. Oversized vehicles are rejected;
the metered curb bays cannot accommodate the map's large trucks and buses.

## Scope and resource use

The map's surveyed Town10 parking positions follow scene curb and paint edges;
individual divisions along continuous strips remain planning estimates. See
[the current parking survey](parking.md). The earlier inventory used meters and
OpenDRIVE shoulders. No lane geometry is changed and individual garage bays
are not invented. A bounded hybrid search checks vehicle footprints against
buildings, walls, fences, poles, guardrails, scenery vehicles and live actors.
Some authored scenery poses intersect collision geometry or have no clear
exit. Those routes are rejected or stop as blocked; this is not a guarantee
that every parked display pose is physically drivable without clearing it.

The local controller runs only during maneuvers. Road driving uses Traffic
Manager; parked vehicles disable physics after stopping. No additional GPU
renderers or camera/LiDAR sensors are created by parking. Configuration export
preserves off-road poses and parking goals, which are replanned on restore.
Native recorder and ordinary actor-state capture retain maneuver controls.

## Reverse-parking implementation and verification

Parking paths and tracking use the rear axle, with the actor origin converted
for map display and body collision checks. Wheel geometry comes from physics
control or the vehicle's wheel bones when UE5 exposes zero wheel offsets.
The local steering controller compensates for Chaos's default squared steering
input curve. Local maneuvers explicitly select first or reverse gear, including
after parked physics wakes; braking retains the current gear. Road Traffic
Manager steering is unchanged.

Native verification ran physical vehicle controls in a separate headless Town10
world: a Traffic Manager road approach followed by reverse parking in P025, then
a departure and reverse parking in P024. Both completed inside the bay with no
collision events; no pose teleporting was used during either maneuver. This
covers the tested Mini Cooper and these bays, not every vehicle/parking layout.

Test runner: `data/reverse-parking/native-test.py` (disposable server port 2100).
Evidence: `data/reverse-parking/native-verification.json`.


Destination replacement explicitly releases a parked vehicle's handbrake and
selects first or reverse gear through the same batch-control path used by the
simulation ticks. It clears any restore hold and replaces the old parking
state, reservation and route. Gear changes while moving still wait for a stop.
The browser renders the destination acknowledgement before its next status poll.

Retargeting checks and native departure evidence: `data/parking-retarget/`.

## Ego driving policy

Traffic Manager ego vehicles use the same physical reverse-entry and parking-exit
controller as background vehicles, retaining their sensors and ego role. Parking
destinations can be changed while running. External ego planners receive the
validated bay position, legal lane heading and `parking_space` ID in `destination`;
the road route is a preview, and the external planner owns the parking maneuver.
Setting that goal does not change autopilot, physics or driving policy. External
parking destinations reserve the bay until replaced, just like automatic trips.
Pedestrians cannot target parking bays. Direct parked-vehicle creation in the
Parking panel remains a background-vehicle placement operation.

Parked ego configurations retain their ego driving policy and include an explicit
`parked` flag. Recovery uses the saved off-road pose, restores the sensors, and
holds the parking brake instead of going through scenery/background conversion.
Older ego saves that used `planner: parked` are migrated to the TM ego policy.


## Open-bay policy and early handoff (11 September 2026)

All 180 surveyed Town10 bays are offered as destinations. The historical
traffic-rule filter no longer withholds bays. Occupancy/reservations, vehicle
size and swept physical clearance still apply. Open is an availability status,
not a promise that every vehicle can fit or that moving traffic leaves a clear path.

The planner tries staging distances of 7, 4, 2 and 0 metres before longer approaches,
validating each complete maneuver before choosing it. A rejected junction-crossing
candidate does not prevent trying a shorter clear candidate.
If Traffic Manager stops short, the controller can take over from the current
slow/stopped pose on the target non-junction lane, within 14 m of the bay and
12 m of the staging target. It first proves a collision-checked parking path
that does not cross a junction, then stops and executes physical reverse entry.
Failed early checks are spaced by two simulation seconds; they never override
an obstructed path or force the vehicle through another actor.

Bay fit uses the actual vehicle footprint plus 2 cm per side, replacing the
previous 5 cm per side which rejected five narrow mapped bays for the Lincoln.
Swept collision checks and final full-footprint containment remain in force.

The final longitudinal stopping tolerance also scales with remaining bay length
and the body footprint projected at the vehicle's current heading,
and the controller slows further for final alignment in short spaces. This avoids
repeatedly stopping 18 cm short in a bay with only a few centimetres of spare length.

The parking handoff accepts adjacent lanes on the same road section and in the
same travel direction. It still validates the full local path before taking
control. This avoids waiting indefinitely when Traffic Manager finishes its
custom road path one lane inward; opposing lanes do not qualify.

Live verification with the Lincoln ego completed R135, physically departed it
for the R136 road approach, and completed R136 after the adjacent-lane handoff
and heading-aware stopping fixes. R136 is 5 m long; the final measured body
projection was fully contained. The scene retained 29 managed actors, six ego
sensors and the saved weather. Evidence: `data/parking-open-fix/acceptance.json`,
`r135-completed.json`, `r136-completed.json` and the sampled physical controls.
The regression suite passed 76 tests. An empty-road geometric planning audit
found non-junction paths for 180/180 bays; that audit does not substitute for
driving every bay with live traffic and physical scenery.
