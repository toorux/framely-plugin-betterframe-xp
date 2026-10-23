# Steam Frame verification — 2026-10-23

Target: `steamos@192.168.5.67`, Framely 0.8.3, glibc 2.39, libstdc++ 6.0.34.
All device access used SSH. Version installed: `0.1.0-preview.2`.

## Fixed failure

Preview 1 wrote `EnvironmentFile=-"/home/steamos/.../vulkan.env"`.
The device's systemd treated the quotes as literal path characters and logged
`EnvironmentFile= path is not absolute, ignoring`. SteamVR therefore never
received the layer enable variable; settings were saved but had no effect.

Preview 2 writes the single unquoted absolute path and verifies that
`systemctl --user show steamvr.service --property=EnvironmentFiles --value`
contains it. A failure is reported as a configuration error. A regression test
also verifies rejection by systemd leaves the layer neutral and removes the
incomplete integration. All 18 backend tests, 110-message language checks,
TypeScript typechecking and package verification passed for preview 2.

## Observed after an explicitly authorized SteamVR restart

- systemd lists the plugin environment file with `ignore_errors=yes`.
- Actual `vrcompositor` PID 741518 has `ENABLE_FRAMELY_BETTERFRAME_XP=1` and
  the intended parameter path in `/proc/<pid>/environ`.
- `/proc/<pid>/maps` contains the plugin's current library without `(deleted)`.
- Plugin status: `loaded=true`, `restartRequired=false`, `outdated=false`, no error.
- Fresh native statistics carry the same compositor PID, approximately 90 FPS,
  and real GPU timestamp samples. The layer log contains no warnings/errors.
- Temporarily setting sharpening to 0 changed the measured layer GPU average
  to 0.7603 ms; restoring 1.8 changed it to 1.2000 ms. This confirms live control
  reaches the rendering path. These are individual diagnostic samples, not a benchmark.
- User settings were restored: sharpen amount 1.8, CAS sharpness 0.9, edge amount
  0.3, comparison enabled, stream-only disabled, both experimental effect amounts 0.

Visual perception of sharpness and the comparison divider has not been independently
confirmed through the headset. No additional restart is pending for the installed build.
