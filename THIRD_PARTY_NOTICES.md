# Attribution

BetterFrame XP by omuomu0909, MIT, version 0.1.2, commit
`1e5bab4afe07835b559431e6b57671b5e080807e`:
https://github.com/omuomu0909/betterframe-xp

The Vulkan layer derives from FrameColor's modified vkBasalt, under the zlib
license. The CAS shader derives from AMD FidelityFX CAS, MIT. The deband
shader is inspired by haasn's shader, MIT. Their notices and license texts
are preserved in `vendor/upstream/THIRD_PARTY.md`, `vendor/upstream/LICENSE`
and `vendor/upstream/layer/LICENSE` and included in every plugin package.

The original source is vendored without changes. `scripts/native.py` creates
a namespaced build copy, adds PID-tagged stats, and makes frame traces opt-in.
The shader algorithms are preserved. The original standalone dashboard,
installer and network updater are replaced by Framely integration.

React and React DOM 19.2.0, MIT, Meta Platforms, Inc. and affiliates.
Their license texts are included as `LICENSE.react` and `LICENSE.react-dom`.

The Framely SDK source is copied from the SDK used by sibling plugins and is
licensed AGPL-3.0-only, as is Framely itself. It is bundled into the setting
page; the combined UI is distributed under AGPL-3.0-only (`LICENSE`). The
local copy additionally translates the SDK's page error boundary into Japanese.
The independently authored integration sources are also available under the
MIT terms in `LICENSE.integration`; upstream licenses remain unchanged.

Each plugin package contains `source.zip` with the integration source, SDK,
pinned upstream layer source, build scripts, dependency lockfile and tests.
