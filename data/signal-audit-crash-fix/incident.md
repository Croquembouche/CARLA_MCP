# Traffic-light audit pause, 2026-09-10

At 08:51:27 EDT, the control center stopped its run loop at frame 759 with
`AttributeError: 'NoneType' object has no attribute 'get'` in
`signal_audit.py`, while resolving an indication for a vehicle crossing an
intersection entry. Native traffic lights publish `movements: null` when
separate turn programs are inactive. The auditor assumed an existing key
always contained a dictionary.

All primary/renderer processes were alive when inspected. The kernel log
had no CARLA OOM kill or NVIDIA Xid event in the inspected two-hour window.
System memory was 71 GiB used with 52 GiB available; the simulator service
cgroup used 65.3 GiB. These are incident snapshots, not a long-run memory
profile. No recording was active.

The fix resolves a missing/null movement mapping as an empty mapping, then
uses the native signal colour. Explicit protected/permissive turn indications
retain precedence. Regression coverage includes red/yellow/green and null,
empty, or partial turn mappings, plus continuing past the entry.

The live scene configuration at frame 759 was saved before the controlled
restart. Restore preserves configuration and poses, but resets simulation
time and can assign new actor IDs. See verification.json for the subsequent
bounded live intersection-crossing and six-sensor checks.
