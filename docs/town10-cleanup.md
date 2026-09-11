# Persistent Town10 vehicle cleanup

The 2026-09-09 cleanup removes ten native scenery actors from
`Carla/Maps/Town10HD_Opt.umap`. Seven previously failed the parking planner's
starting-position clearance check; three failed its non-junction exit requirement.
The exact names, native mesh assets, poses and reasons are recorded in
`map-revisions/Town10HD_Opt.json`.

The read/validate/delete/save/reload editor script and portable map update live at
`/mnt/simulations/maps/Town10HD_Opt-cleaned/`. The editor verified that the actor
name set changed by exactly these ten entries (2,932 to 2,922). The original map
is backed up under that folder's `backup/Carla/Maps/`. The ZIP excludes this backup.

The live scene already lacked two targets when cleanup started. The other eight
were deleted through the normal controller endpoint, leaving 41 managed actors.
`data/town10-cleanup/` contains the before/after configurations, live removal audit,
editor inventory and runtime verification. The simulator is restarted from the
cleaned configuration to load the saved native map on primary and GPU workers.

On the cleaned native map, SceneVehicles recognises the approved missing source
keys. It filters them from older hidden-source configurations and the controller
skips their saved replacement actors. Unrelated missing source identities still
raise an error. The web renderer also suppresses these deleted instances in older
static scene exports, while live source totals count only the remaining 38.

Validation: 33 focused scene-vehicle, parking and parking-driving tests passed;
JavaScript syntax check passed. Native editor save/reload and live runtime checks
are recorded separately from these unit tests.

Fresh native runtime verification found all 19 removed body/glass components absent
and all 38 retained sources present. Live verification restored 41 actors, five ego
sensors and two automatic GPU workers, paused without errors. Weather and sensor
configurations match the saved scenario; destination reprojection differed by at
most 7.5 mm. Reports are in `data/town10-cleanup/`.

## Permanent removal of the three remote trucks — 10 September 2026

Earlier scenario-only removal of `BP_Carlacola_Parked_C_7`,
`BP_Carlacola_Parked_C_9`, and `BP_EuropeanHGV_Parked_C_8` did not change the
native map. They could therefore be converted again when Town10 was started
without that particular scenario. They were observed again as actors 25–27,
30.7–44.1 m from the road network.

The native map revision now removes these three source actors as well: 13 total
permanent removals. The incremental save/reload audit changed exactly 2,922 to
2,919 actors. The cumulative manifest accepts the original map, the previous
complete ten-removal revision, or the fully cleaned map; other partial states
fail validation. Restore migration skips these source identities in old scenarios.

The reusable map and scenario are updated under
`/mnt/simulations/maps/Town10HD_Opt-cleaned/`; evidence and the previous portable
archive are retained in `data/offroad-persistent-cleanup/`. The replacement
scenario retains the current 28 actors and six ego sensors, including the cabin
camera. Parking annotations, weather and user destinations are preserved.
