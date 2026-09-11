# Replay restart feedback

**Stop replay & restart scene** restarts both the owned CARLA process group and the control service. The service connection briefly closes by design. The browser now opens a persistent status panel immediately and follows actual server phases:

1. Stopping replay / restarting the previous scene.
2. Reconnecting while the control service restarts.
3. Starting CARLA and its configured GPU workers.
4. Preparing the map, Traffic Manager and live controls.
5. Confirmed live scene ready, or a persistent error result.

The panel displays elapsed time rather than an estimated percentage, survives a page refresh using session storage, and remains visible until completion is dismissed. Capture and replay restart controls are disabled during the operation. HTTP failures are shown as errors; a dropped response is treated as unconfirmed and followed through status polling without automatically resending the command. Other open clients discover server restart/startup phases through their regular status polls.

A ready result requires a connected live server following a confirmed request or observed startup transition. The backend publishes `connected` only after map, movement controller and schedule initialization have completed. After the restart, the UI reloads map metadata and clears selection and destination drafts from the old episode. A restart creates a clean scene; it does not automatically restore actors from the native replay.

Validation: `node --experimental-default-type=module tests/test_scene_operation.mjs` tests phase transitions, connection loss, reload recovery, definitive failure, unconfirmed requests and timeout. The live acceptance run uses an existing completed recording, follows an actual service/simulator restart, checks the progress UI during startup and after page refresh, and restores the prior scenario separately for development verification.
