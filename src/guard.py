#!/usr/bin/python3
"""SteamVR start guard. ExecCondition must never prevent SteamVR from starting."""
import json
import os
import pathlib
import sys
import time


def guard(phase, cache, runtime, result=None, now=None):
    cache, runtime = pathlib.Path(cache), pathlib.Path(runtime)
    env = cache / 'vulkan.env'
    state = runtime / 'guard.json'
    now = time.monotonic() if now is None else now
    previous = {}
    try:
        previous = json.loads(state.read_text())
    except (OSError, ValueError):
        pass
    if phase == 'start':
        if env.exists():
            runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
            state.write_text(json.dumps({'started': now, 'failures': previous.get('failures', 0)}))
        else:
            state.unlink(missing_ok=True)
    elif phase == 'stop' and env.exists():
        elapsed = now - previous.get('started', -100000)
        failures = previous.get('failures', 0) + 1 if result and result != 'success' and 0 <= elapsed < 10 else 0
        if failures >= 2:
            env.replace(cache / 'vulkan.env.disabled')
            (cache / 'guard-disabled').write_text(result + '\n')
            state.unlink(missing_ok=True)
        else:
            state.write_text(json.dumps({'failures': failures}))


if __name__ == '__main__':
    try:
        guard(sys.argv[1], pathlib.Path(__file__).resolve().parent,
              pathlib.Path(os.environ['XDG_RUNTIME_DIR']) / 'framely-betterframe-xp',
              os.environ.get('SERVICE_RESULT'))
    except Exception as error:
        print('BetterFrame XP guard: ' + str(error), file=sys.stderr)
    # Missing files, corruption, or a failed write must never skip SteamVR.
    sys.exit(0)
