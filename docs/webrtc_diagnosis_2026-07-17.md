# WebRTC blank-client diagnosis — 2026-07-17/18

## Outcome

Two independent configuration faults were confirmed:

1. Isaac Lab's livestream was launched in **private-network mode
   (`livestream=2`)** while the client was connecting over the public Internet.
   TCP signaling was reachable, but the server was not given the VM's public
   endpoint for the WebRTC media negotiation.
2. After the server was corrected, the Windows client's newest persisted
   Server value was **` 34.61.210.0` with a leading space**. During the failed
   retry the client opened no TCP or UDP socket and the VM received no WebRTC
   packet, so that attempt never reached the server.
3. A later edit changed the persisted value to `34.61.210.0:49100`. The native
   client expects a host in this field and supplies its signaling port itself;
   this value also produced no client socket. The required value is only
   `34.61.210.0`.

On fresh public-mode Run 13, the user entered the host-only address and the
transport succeeded end to end: TCP signaling established and sustained
bidirectional UDP media flowed. If the native window remains visually stale,
`View > Reload` is now the appropriate client-side refresh; no further GCP
network change is justified.

The required launch configuration for this VM is:

- Isaac Lab `livestream=1` (public-network mode), and
- environment variable `PUBLIC_IP=34.61.210.0` before constructing
  `AppLauncher`.

Keep the GCP ingress rule restricted to the current client IPv4. Do not broaden
it to a campus, ISP, or public CIDR: the stream has no application-level
authentication.

## Evidence, not assumptions

Observed on 2026-07-17/18:

| Check | Observed result | Meaning |
|---|---|---|
| Client public IPv4 after VPN disconnect | `92.209.223.203` | This is the only source address that should be allowed. |
| GCP firewall `ebim-webrtc-owner` | source `92.209.223.203/32`; TCP `49100` and legacy TCP/UDP ranges containing UDP `47998`; target tag `webrtc-stream` | Required ingress is present and remains exact-IP only. |
| VM `sim-dev-g4b` | `RUNNING`, NAT `34.61.210.0`, tag `webrtc-stream` | Firewall rule targets the correct VM. |
| Docker networking | `host` | WebRTC can bind directly on the VM; no Docker bridge/NAT problem. |
| Encoder library in the container | `libnvidia-encode.so` and `.so.1` present | NVENC runtime is exposed. |
| Windows client | file/product version `1.1.5.265` | Matches NVIDIA's WebRTC client 1.1.5 release for Isaac Sim 5.1. |
| Windows Firewall | two enabled inbound `Allow` rules for the client on `Private, Public`; active Wi-Fi profile is `Public` | The client executable is allowed on the active profile. |
| Installed Isaac Sim | `5.1.0-rc.19+release.26219...` | Use the 5.1 streaming settings, not the changed 6.0 setting names. |
| Run 11 log | `livestream=2 ... Streaming server started` | Server was explicitly launched in private mode. |
| Run 11 sockets | TCP `0.0.0.0:49100` and TCP `0.0.0.0:8011` | Signaling was listening; this alone does not prove successful ICE/media negotiation. |
| Verifier before the fix | `scripts/task3/verify_grasp_lift.py` passed `"livestream": 2 if args.livestream else -1` | Direct source of the wrong mode. |
| Installed Isaac Lab launcher | mode 1 appends `--/app/livestream/publicEndpointAddress=$PUBLIC_IP` and `--/app/livestream/port=49100`; mode 2 only enables `omni.services.livestream.nvcf` | Confirms why setting only the firewall could not repair the blank client. |
| Installed NVCF extension | media host range `47998..48020`; signaling default `49100` | Confirms the firewall includes the actual 5.1 media/signaling ports. |
| Corrected public Run 12 | log says `livestream=1` and `Streaming server started`; exactly one Kit process; TCP `0.0.0.0:49100` listening | Confirms the server-side public-mode correction took effect. |
| Client storage after the failed public Run 12 attempt | newest `server` value is ` 34.61.210.0` (leading space); no newer clean value | The address presented to the client connection code was malformed. |
| Client/server network evidence during two 45-second retry windows | client process had zero TCP/UDP endpoints; server packet capture saw zero packets on TCP `49100` or UDP `47998:48020` | The client did not attempt a WebRTC connection; this is not an ICE or GCP packet-loss failure. |
| Direct Windows-to-VM probe during public Run 12 | TCP `34.61.210.0:49100` succeeded from active Wi-Fi | Exact-IP GCP signaling ingress works from the client machine. |
| Later client edit | newest stored value became `34.61.210.0:49100`; still zero client sockets | Port must not be entered in the native client's Server field. |
| Fresh public Run 13 with host-only input | client TCP established to `34.61.210.0:49100`; server saw `10.128.0.8:49100 <-> 92.209.223.203`; packet capture collected 300 bidirectional media/feedback packets between server UDP `47998` and client UDP `4092`, including sustained 1,180/1,208-byte server packets | Signaling, ICE selection, firewall, encoder output, and media transport are working end to end. |
| Run 13 `main: thread_init: already added for thread` | one warning at client session start; TCP and UDP remained active and simulation phases continued | Benign streaming-SDK warning in this run, not a connection failure. |

An absent UDP listener in `ss -lntup` before a client handshake is not by
itself a failure: the installed streaming service selects a media port from its
configured host range as the session is negotiated. The decisive pre-fix
evidence is the private mode plus missing public endpoint argument.

## Correct launch and validation

For the existing verifier, the application must be constructed with public
mode and the VM endpoint must be in its environment. The effective launch
shape is:

```bash
PUBLIC_IP=34.61.210.0 /workspace/isaaclab/isaaclab.sh -p \
  scripts/task3/verify_grasp_lift.py --skip-navigation --livestream ...
```

The verifier's `--livestream` path must map to `AppLauncher` mode `1`, not
mode `2`. Merely setting `LIVESTREAM=1` is insufficient while the Python code
explicitly passes mode `2`, because the explicit launcher argument overrides
the environment.

Use this acceptance sequence during an actually running simulation:

1. Confirm the new log says `livestream=1`, then `Streaming server started`.
2. Confirm `0.0.0.0:49100` is listening while the simulation is still active.
3. In the Windows client, click the Server field, press `Ctrl+A`, and type
   exactly `34.61.210.0`. There must be no leading/trailing whitespace, scheme,
   port, or `/32`. Click **Connect**.
4. Only one client may connect. If an earlier attempt is stale, close the
   client completely, reopen it, and connect once. `View > Reload` is the
   documented recovery action for a stale blank view.
5. A connection attempt made after the verification process produced its
   result and began shutdown is not valid; the Kit process may retain TCP
   `49100` while no longer rendering useful frames.

Transport confirmation was completed on fresh Run 13. Visual confirmation by
the owner remains the final UI check; if the window is stale while Run 13's
media is flowing, use `View > Reload`. Run 12 had already emitted its
`GRASP_RESULT` before the malformed client value was discovered, so its
lingering Kit shutdown process was not a reliable test window.

If a clean retry on a fresh public-mode run still fails, capture simultaneous
evidence during one click of **Connect**:

- server log lines containing `livestream`, `webrtc`, `stream`, `session`,
  `candidate`, `encoder`, or `error`;
- `ss -ntup` on the VM; and
- a short, port-filtered packet capture for TCP `49100` and UDP
  `47998:48020`.

Do not start a second Kit process for this test. Use the manipulation run's
active livestream window, because the project has one GPU and the stream
supports only one client.

## Authoritative references

- NVIDIA Isaac Sim 5.1 livestream instructions:
  <https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/manual_livestream_clients.html>
  — public endpoint flag, TCP `49100`, UDP `47998`, one-client rule, and
  `View > Reload` guidance.
- NVIDIA Isaac Sim 5.1 download matrix:
  <https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/download.html>
  — WebRTC client `1.1.5` is paired with Isaac Sim 5.1.

## Security boundary

The stream should remain limited to `92.209.223.203/32`. If the owner's public
IP changes again, replace that single `/32` with the newly measured address;
do not add the old address or widen the range unless the owner explicitly
accepts the increased exposure.
