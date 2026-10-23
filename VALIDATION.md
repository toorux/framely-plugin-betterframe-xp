# Validation — 2026-10-23

Version: `0.1.0-preview.2`. No live SteamVR or headset configuration was modified during development.

## Completed

- Native C++20 and GLSL compilation on Linux aarch64. ELF architecture and exported Vulkan entry points checked.
- 18 Python backend/guard tests: opt-in installation, live settings, rejection of invalid values, original-install
  conflicts, ownership and symlink preservation, idempotent stop, shutdown persistence, failed-install bypass,
  guard persistence, validated import, fresh PID-tagged statistics, gaze backup/restore, language resolution,
  batched JSON RPC, and unconditional guard exit success.
- TypeScript strict typecheck.
- 110 messages in each of Chinese, Japanese and English; complete key parity, locale variants,
  UI references and backend error translation coverage.
- Chrome headless interaction tests: all three languages, host events, manual override, live slider updates,
  presets, restart notice, SteamVR setting controls, import, translated error handling, performance values
  and a 430 px layout without horizontal overflow. Screenshots generated under `build/screenshots/`.
- Real Vulkan smoke test using Mesa lavapipe 25.0.7: an isolated executable named `vrcompositor` creates
  a headless surface and presents **240 frames** through the actual implicit layer. Confirms swapchain
  substitution, compiled shader execution, effect → copy → effect switching after live parameter updates,
  destruction of resources, and PID-tagged GPU statistics. Test HOME and runtime are temporary directories.
- Framely CLI package creation and verification of manifest and payload SHA-256 hashes.

## Target-device acceptance still required

Software Vulkan testing confirms that the render path runs; it cannot establish image quality, timing,
power use or compatibility on Steam Frame's Turnip/Adreno driver.

1. Install the package through Framely on a Steam Frame; confirm the default is off and select each language.
2. Enable processing, restart SteamVR at a convenient time, and confirm the loaded status plus fresh GPU metrics.
3. Stream a known scene; compare each eye's left/right halves and verify stream-only behavior when leaving the stream.
4. Change sharpening while streaming and assess 120/144 Hz timing and visual comfort.
5. Disable processing, stop/enable the plugin, restart SteamVR, and verify bypass and persistence.
6. If SteamVR correction switches were changed, restore them and verify readback before uninstalling.
7. Verify stop/uninstall leaves no plugin drop-in or layer manifest. A mapped library should remain bypassed
   until the compositor exits. Test restart after an OS reboot and after a plugin update.

Inherited experimental effects and shared uniform-buffer behavior are documented in README. No hardware
stability, color quality or frame-time improvement is claimed by these local checks.
