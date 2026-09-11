# Control center redesign — 2026-09-08

Reviewed screenshots: Scenario, Sensors, Signals (OpenDRIVE and 3D), Weather, Sessions, Connect.

## Visual decisions before implementation
- Keep the scene central: 64 px header, 68 px navigation rail, 320 px inspector, 88 px footer. Hide inspector when a larger map is needed.
- Signal markers: 8 px coloured dots rather than 12 by 30 px housings; no permanent IDs. Selection uses an outline and one small label; hover uses a tooltip. Use a 12 px picking radius for mouse and touch. Toggle markers in the toolbar. Same visual size and behavior in 2D and 3D.
- Signals inspector: compact state summary, state selector and apply button on one row, hold and resume controls, collapsed cycle editor and help.
- Scenario: selected actor actions beside actor list, creation in an expandable section, shared destination outside the creation form, advanced instructions collapsed.
- Sensors: five compact named accordion rows; expand only the sensor being edited. Keep loadout actions visible before the editor. Preserve draft values when moving between panels.
- Weather: two-column numeric fields with units, current-scene preset state, primary apply action in view.
- Sessions: readable date/time headings, compact cards and metadata, playback above the archive list.
- Connect: compact runtime summary, startup/disconnect controls grouped here, logs behind a disclosure.
- Scene layers: small one-line detail controls, custom imports behind disclosure. Keep top-down overview and latency.
- Match both themes and make the inspector accessible on narrow screens without horizontal overflow.

## Verification
Capture every revised interface. Check marker picking and visibility in both views, inspector expansion, sensor draft retention, weather values, sessions, themes, and mobile viewport. Preserve the running simulator and its clock; frontend changes require only browser reload.
