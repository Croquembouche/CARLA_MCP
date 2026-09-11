# Live destination updates

Select an ego or background vehicle in Scenario. During a live run, selecting a road point from Destination immediately submits the new goal. Alternatively, click Destination above the map, then click the desired lane. While paused, a dropdown selection remains a draft until Apply destination is pressed. Pedestrian goals follow the same live interaction.

The persistent route status shows the request in progress, the acknowledged route revision, arrival, or rejection. The command response immediately updates the route in OpenDRIVE, the overview and the 3D scene. An older status poll cannot overwrite a route revision already acknowledged by the server. Actor buttons are retained between unchanged status polls so an in-progress click is not discarded.

The controller processes destination commands between synchronized frames. It replaces the Traffic Manager path rather than appending it, clears the old arrival/approach slowdown, and re-enables a vehicle that had stopped at its previous destination. Recording continues and logs the command with its frame and simulation timestamp. Replay remains read-only. External-planner goals are published through status without taking over vehicle control.

## Junction routing

Town10 has overlapping junction connectors. Planning solely from the nearest road to the vehicle position can select a different turn connector after Traffic Manager has already committed to going straight. The old behavior displayed that unreachable turn while the vehicle continued along the retained Traffic Manager path.

The replacement route now starts on Traffic Manager's current lane. If that waypoint is inside a junction, the planner retains the current connector to its exit and calculates the remaining route from there. The UI marks this as **Junction exit retained**. A missed turn can therefore require a loop around the block; the highlighted path represents that route.

## Verification

- Ten Python routing/controller regressions, including the actual Town10 overlapping-connector case.
- Seven capture/resource lifecycle regressions.
- JavaScript checks for command acknowledgement, an older status response, rejection feedback and external-planner behavior.
- Browser test: ego moving at 2.29 m/s; selecting a new dropdown point showed Updating and submitted it without another Apply click, while Running remained active.
- Live junction test and capture evidence are saved in `data/live-junction-reroute.json` and `data/live-reroute-recording-verification.json`.
- The test recording `20260909-094713-aab86a` verified 39 frames, 195 sensor samples, 15 ROS bag topics with 39 messages each, and 205 sealed files, with no verification warnings or errors. Its destination event is at frame 284.

A background ambulance holding its completed destination blocked the test lane; it was temporarily routed farther ahead to allow the ego's arrival test to continue. Original goals are restored after verification.

Final live junction result: passed. The destination was accepted in 143 ms at frame 284 while the ego was moving at approximately 8.05 m/s. It completed the approximately 521 m legal detour, including traffic waits, and stopped 3.17 m from the goal (within the existing 3.2 m settled-arrival test tolerance). Maximum distance to the sampled planned route was 3.90 m. The simulation remained running throughout. Original ego/background goals, weather and phase plans were checked against the pre-change backup after restoration; all three actors and five ego sensors are active.
