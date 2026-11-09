# Live startup and repeated-session frame rejection

The two participant attempts at 15:22:21 and 15:22:35 on 2026-11-06 did reach
the LAN server and receive protocol-2 ready. Both were then closed for
`invalid_frame: Camera frames must have increasing sequence and timestamps`.
Only two/three encoded frames reached the sending path although the native
camera emitted hundreds. The camera preview continued, resembling a connection
stall. Original server traces and device log are preserved under
artifacts/connection_v143/.

Repeated-device testing located a queued native JPEG from the previous
subscription. It arrived first in the next session at timestamp 11346.98 ms,
before that new native subscription restarted timestamps at zero. A time-only
guard prevented a disconnect but then suppressed fresh frames until they
caught up with that stale timestamp: the second of four trial sessions ran
at 0 fps. Those intermediate receipts are retained, not counted as passing.

Every native subscription now supplies a unique session token. Native workers
stamp their events with that token; Dart rejects/acknowledges old-token events
before they can establish the next session's timestamp. Existing native
generation checks still discard old worker completions before emission.
The Android CameraImage callback additionally enables analysis without sending
frames, leaving one native JPEG clock; other platforms keep Dart encoding.
A sender guard drops negative, duplicate or backward timestamps without
changing sequence numbers or fabricating time.

Startup now shows the current connection/camera stage beside its controls.
Connection plus protocol-ready share a six-second deadline, followed by bounded
cleanup. Server rejection fails immediately rather than waiting twelve seconds
for a ready message that will never arrive. Fatal live errors stop the sender
and display a disconnected state. Startup error cards are directly under the
controls instead of below the saved-video section. Existing video/history and
the preview/stable-caption behavior are preserved.

Native streaming now starts after CameraX reports that recording has started,
so preview-only frames before that transition are not sent into the new session.
The initial token-enabled device trial passed five successive starts at 25 fps,
but some sessions still recorded a gap during that rebind. Final delivery
rechecks use the post-recording subscription order.

Flutter tests cover rejected handshakes, sockets that never upgrade, upgraded
sockets that never become ready, fatal errors after ready, backpressure, stale
timestamps, four successive sessions with reset timestamps, and injection of
an old native event before a new session's first frame. Build is profile
1.4.3+8. Actual device
verification and signed APK hashes are recorded in DELIVERY_RECEIPT.json under
artifacts/connection_v143/ after testing completes. Intermediate builds and
their test receipts are not the final signed APK identity.

This fixes a verified application failure. It does not guarantee availability
when the PC is asleep, the server is stopped or the network is unreachable.

## Server outage and recovery

Deliberately stopped the identified local API process, then pressed Start on
the physical phone. The app returned to an enabled Start button and displayed
a Vietnamese connection error directly under the controls (offline-result.png).
After restarting the same local server and checking its ready health, pressing
Start again entered live at 25 fps without restarting the app or changing its
saved URL (recovery-flow.xml). This validates refusal/retry behavior; the
separate deadline tests use an unresponsive socket and a no-ready server.

## Final installed build

Final APK SHA-256 is
c2f33bf89b8bddf5e5c6d90a8b7bc0cd56ef7834e2ecbedeac7347ba5601b5be;
its bytes match the installed base.apk. Five consecutive physical-device
start/stop cycles passed, each displaying 25 fps at the sampled UI points.
All five reached session_final without invalid_frame errors or a 0-fps stall.
Final code passed all 20 Flutter tests and analyze. Source hashes and actual
connection-ready timings are retained in SOURCE_HASHES.json and
FINAL_FLOW_METRICS.json. UI observation timings include deliberate waits and
uiautomator overhead and must not be presented as connection latency.

Some repeated runs still record one short capture gap (>0.5 s) and mark the
session incomplete. The change eliminates the observed stale-session failure,
but this test does not establish uninterrupted delivery under all load/network
conditions. The gaps were not silently ignored or relabeled successful.
The final binary's outage/recovery evidence is final-offline.xml and
final-recovery/; the saved endpoint URL and app process are retained during it.
