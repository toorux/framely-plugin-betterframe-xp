#!/usr/bin/python3
"""Framely JSON-line backend. User-owned Vulkan integration; no runtime restarts."""
import hashlib
import json
import math
import os
import pathlib
import platform
import select
import shlex
import signal
import subprocess
import sys
import tempfile
import time

PLUGIN = 'tooru.betterframe-xp'
MARKER = '# Managed by ' + PLUGIN + '\n'
LIBRARY = 'libframely_betterframe_xp.so'
LAYER = 'VK_LAYER_FRAMELY_BETTERFRAME_XP'
ENV_ENABLE = 'ENABLE_FRAMELY_BETTERFRAME_XP'
DEFAULT = {
    'enabled': False, 'language': 'auto', 'streamOnly': True, 'showSplit': False,
    'sharpenAmount': 1.2, 'sharpness': 0.7, 'centerRadius': 0.55, 'edgeAmount': 0.4,
    'debandAmount': 0.0, 'debandRange': 12.0, 'debandThreshold': 2.5,
    'detailBoost': 0.0, 'grainAmount': 0.0, 'grainSize': 1.0, 'grainAnimate': True,
    'casCross': True, 'casLuma': True, 'cornerSkip': 1.15, 'splitEyes': True,
}
RANGES = {
    'sharpenAmount': (0, 2), 'sharpness': (0, 1), 'centerRadius': (0, 1),
    'edgeAmount': (0, 1), 'debandAmount': (0, 1), 'debandRange': (1, 32),
    'debandThreshold': (0.5, 8), 'detailBoost': (0, 1), 'grainAmount': (0, 1),
    'grainSize': (1, 4), 'cornerSkip': (0, 2),
}
PRESETS = {
    'gentle': {'sharpenAmount': 0.6, 'sharpness': 0.5, 'centerRadius': 0.55, 'edgeAmount': 0.3},
    'balanced': {'sharpenAmount': 1.2, 'sharpness': 0.7, 'centerRadius': 0.55, 'edgeAmount': 0.4},
    'strong': {'sharpenAmount': 1.6, 'sharpness': 0.8, 'centerRadius': 0.65, 'edgeAmount': 0.5},
}
GAZE_KEYS = ('gazeDepReprojectEnable', 'gazeDepEyeToHeadEnable')


def validate(patch):
    if not isinstance(patch, dict) or set(patch) - DEFAULT.keys():
        raise ValueError('invalid_settings')
    for key, value in patch.items():
        if key == 'language':
            if value not in ('auto', 'zh', 'ja', 'en'):
                raise ValueError('invalid_language')
        elif isinstance(DEFAULT[key], bool):
            if not isinstance(value, bool):
                raise ValueError('invalid_settings')
        elif isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not RANGES[key][0] <= value <= RANGES[key][1]:
            raise ValueError('invalid_settings')
    return patch


def atomic(path, data, mode=0o600):
    path = pathlib.Path(path)
    if path.is_symlink():
        raise RuntimeError('path_conflict')
    fd, temporary = tempfile.mkstemp(prefix='.betterframe-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        pathlib.Path(temporary).unlink(missing_ok=True)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n').encode()


def private_dir(path):
    if path.is_symlink():
        raise RuntimeError('path_conflict')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_uid != os.getuid():
        raise RuntimeError('path_conflict')
    path.chmod(0o700)


def quote(value):
    if any(char in str(value) for char in '\n\r\0'):
        raise RuntimeError('path_conflict')
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


class Backend:
    def __init__(self, home=None, data=None, payload=None, runtime=None):
        self.home = pathlib.Path(home or os.environ['HOME'])
        self.data = pathlib.Path(data or os.environ['FRAMELY_DATA_DIR'])
        self.payload = pathlib.Path(payload or pathlib.Path(__file__).resolve().parent)
        self.runtime = pathlib.Path(runtime or os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')) / 'framely-betterframe-xp'
        self.cache = self.home / '.local/share/framely/betterframe-xp'
        self.dropin = self.home / '.config/systemd/user/steamvr.service.d/92-framely-betterframe-xp.conf'
        self.layer_file = self.home / '.local/share/vulkan/implicit_layer.d/framely-betterframe-xp.json'
        self.envfile = self.cache / 'vulkan.env'
        self.guard_note = self.cache / 'guard-disabled'
        self.settings = DEFAULT.copy()
        self.error = ''
        self.host_language = 'en'
        self.stopped = False
        self.gaze = None
        private_dir(self.data)
        try:
            self.settings.update(validate(json.loads((self.data / 'settings.json').read_text())))
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError):
            self.error = 'saved_settings_invalid'
        self.env = {**os.environ, 'XDG_RUNTIME_DIR': str(self.runtime.parent),
                    'DBUS_SESSION_BUS_ADDRESS': f'unix:path={self.runtime.parent}/bus'}

    def command(self, args, timeout=3):
        try:
            process = subprocess.run(args, env=self.env, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            print(f'command failed: {args[0]}: {error}', file=sys.stderr)
            raise RuntimeError('runtime_command_failed') from error
        if process.returncode:
            print(process.stderr[-1500:], file=sys.stderr)
            raise RuntimeError('runtime_command_failed')
        return process.stdout

    def save(self):
        atomic(self.data / 'settings.json', encoded(self.settings))

    def params(self, active=None):
        private_dir(self.cache)
        values = {key: value for key, value in self.settings.items() if key != 'language'}
        values['enabled'] = self.settings['enabled'] if active is None else active
        text = MARKER + ''.join(f'{key} = {int(value) if isinstance(value, bool) else value}\n' for key, value in values.items())
        atomic(self.cache / 'params.conf', text.encode())

    def compositor(self):
        for proc in pathlib.Path('/proc').iterdir():
            if not proc.name.isdigit():
                continue
            try:
                if proc.stat().st_uid == os.getuid() and (proc / 'comm').read_text().strip() == 'vrcompositor':
                    return int(proc.name), (proc / 'maps').read_text()
            except (OSError, ValueError):
                continue
        return None, ''

    def original_conflict(self, maps=''):
        # Never change the standalone installation or load both post-processing layers.
        dropin = self.home / '.config/systemd/user/steamvr.service.d/91-betterframe-xp.conf'
        original_env = self.home / '.config/betterframe-xp/vulkan.env'
        return 'libbetterframexp.so' in maps or (dropin.exists() and original_env.exists())

    def verify_owned(self):
        if self.dropin.is_symlink() or self.layer_file.is_symlink():
            raise RuntimeError('path_conflict')
        if self.dropin.exists() and not self.dropin.read_text().startswith(MARKER):
            raise RuntimeError('path_conflict')
        if self.layer_file.exists() and json.loads(self.layer_file.read_text()).get('layer', {}).get('name') != LAYER:
            raise RuntimeError('path_conflict')

    def install(self):
        if platform.machine() not in ('aarch64', 'arm64') or os.getuid() == 0:
            raise RuntimeError('unsupported_platform')
        _, maps = self.compositor()
        if self.original_conflict(maps):
            raise RuntimeError('original_conflict')
        self.verify_owned()
        private_dir(self.cache)
        private_dir(self.runtime)
        # Catch enablement through other service drop-ins without overwriting them.
        environment = shlex.split(self.command(['systemctl', '--user', 'show', 'steamvr.service', '--property=Environment', '--value']))
        if 'ENABLE_BETTERFRAME_XP=1' in environment:
            raise RuntimeError('original_conflict')
        for name in (LIBRARY, 'guard.py'):
            source, target = self.payload / name, self.cache / name
            content = source.read_bytes()
            if target.is_symlink():
                raise RuntimeError('path_conflict')
            if not target.exists() or hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(content).digest():
                atomic(target, content, 0o700)
        manifest = {'file_format_version': '1.0.0', 'layer': {
            'name': LAYER, 'type': 'GLOBAL', 'library_path': str(self.cache / LIBRARY),
            'api_version': '1.3.223', 'implementation_version': '1',
            'description': 'Framely BetterFrame XP post-processing',
            'functions': {'vkGetInstanceProcAddr': 'vkBasalt_GetInstanceProcAddr', 'vkGetDeviceProcAddr': 'vkBasalt_GetDeviceProcAddr'},
            'enable_environment': {ENV_ENABLE: '1'}, 'disable_environment': {'DISABLE_FRAMELY_BETTERFRAME_XP': '1'}}}
        self.layer_file.parent.mkdir(parents=True, exist_ok=True)
        atomic(self.layer_file, encoded(manifest))
        environment = {
            ENV_ENABLE: '1', 'FRAMELY_BETTERFRAME_XP_PARAMS': str(self.cache / 'params.conf'),
            'FRAMELY_BETTERFRAME_XP_LOG_LEVEL': 'warn', 'FRAMELY_BETTERFRAME_XP_LOG_FILE': str(self.runtime / 'layer.log'),
        }
        atomic(self.envfile, ''.join(f'{key}={quote(value)}\n' for key, value in environment.items()).encode())
        self.dropin.parent.mkdir(parents=True, exist_ok=True)
        # EnvironmentFile= is one path, not an ExecStart-style quoted word.
        # Quotes after the optional '-' become literal filename characters and
        # systemd rejects the resulting non-absolute path. Spaces are literal.
        quote(self.envfile)  # Reject line breaks / NUL before writing the unit.
        env_path = str(self.envfile).replace('%', '%%')
        guard_path = quote(self.cache / 'guard.py').replace('%', '%%')
        atomic(self.dropin, (MARKER + f'[Service]\nEnvironmentFile=-{env_path}\nExecCondition=-/usr/bin/python3 {guard_path} start\nExecStopPost=-/usr/bin/python3 {guard_path} stop\n').encode())
        self.command(['systemctl', '--user', 'daemon-reload'])
        registered = self.command(['systemctl', '--user', 'show', 'steamvr.service', '--property=EnvironmentFiles', '--value'])
        if str(self.envfile) not in registered:
            raise RuntimeError('startup_config_invalid')

    def remove_integration(self):
        self.verify_owned()
        changed = self.dropin.exists()
        self.dropin.unlink(missing_ok=True)
        self.layer_file.unlink(missing_ok=True)
        self.envfile.unlink(missing_ok=True)
        (self.cache / 'vulkan.env.disabled').unlink(missing_ok=True)
        if changed:
            self.command(['systemctl', '--user', 'daemon-reload'])

    def start(self):
        self.stopped = False
        try:
            if self.settings['enabled'] and not self.guard_note.exists():
                self.params(active=False)
                self.install()
                self.params()
            else:
                self.params(active=False)
        except Exception as error:
            self.error = str(error)
            self.params(active=False)
        return {'ready': True}

    def enable(self, enabled):
        if not isinstance(enabled, bool):
            raise ValueError('invalid_settings')
        if enabled:
            self.params(active=False)
            try:
                self.install()
            except Exception:
                # Keep the running layer neutral if setup fails part way through.
                self.params(active=False)
                try:
                    self.remove_integration()
                except Exception:
                    pass
                raise
            self.guard_note.unlink(missing_ok=True)
            self.settings['enabled'] = True
            self.params()
        else:
            self.params(active=False)
            self.remove_integration()
            self.settings['enabled'] = False
        self.save()
        self.error = ''
        return self.info()

    def update(self, patch):
        validate(patch)
        if 'enabled' in patch:
            raise ValueError('use_enable')
        self.settings.update(patch)
        self.save()
        if self.error == 'saved_settings_invalid':
            self.error = ''
        self.params(active=False if self.guard_note.exists() or self.error else None)
        return self.info()

    def import_original(self):
        path = self.home / '.config/betterframe-xp/params.conf'
        if not path.is_file() or path.stat().st_size > 65536:
            raise RuntimeError('import_unavailable')
        patch = {}
        try:
            for line in path.read_text().splitlines():
                key, separator, value = line.split('#', 1)[0].partition('=')
                key = key.strip()
                if not separator or key in ('enabled', 'language') or key not in DEFAULT:
                    continue
                number = float(value.strip())
                if isinstance(DEFAULT[key], bool):
                    if number not in (0, 1):
                        raise ValueError('invalid_settings')
                    patch[key] = bool(number)
                else:
                    patch[key] = number
            validate(patch)
        except (OSError, ValueError):
            raise ValueError('import_invalid')
        return self.update(patch)

    def stats(self, pid):
        path = self.runtime / 'stats'
        try:
            if time.time() - path.stat().st_mtime > 5 or path.stat().st_size > 16384:
                return None
            stats = {}
            for line in path.read_text().splitlines():
                key, _, value = line.partition('=')
                value = float(value.strip())
                if math.isfinite(value):
                    stats[key.strip()] = value
            return stats if stats.get('pid') == pid else None
        except (OSError, ValueError):
            return None

    def info(self):
        pid, maps = self.compositor()
        entries = [line for line in maps.splitlines() if str(self.cache / LIBRARY) in line]
        loaded = bool(entries)
        outdated = any('(deleted)' in line for line in entries)
        guarded = self.guard_note.exists()
        configured = self.dropin.exists() and self.envfile.exists() and not guarded
        locale = self.settings['language']
        if locale == 'auto':
            locale = self.host_language
        return {'settings': self.settings.copy(), 'effectiveLanguage': locale,
                'loaded': loaded, 'configured': configured, 'guardDisabled': guarded,
                'restartRequired': bool(pid and (configured != loaded or outdated)),
                'running': bool(pid), 'outdated': outdated, 'conflict': self.original_conflict(maps),
                'stats': self.stats(pid) if loaded else None, 'error': self.error,
                'gaze': self.gaze, 'gazeModified': (self.cache / 'gaze-before.json').exists()}

    def vr_ready(self):
        return any(self.server_pids())

    def server_pids(self):
        for proc in pathlib.Path('/proc').iterdir():
            if proc.name.isdigit():
                try:
                    if proc.stat().st_uid == os.getuid() and (proc / 'comm').read_text().strip() == 'vrserver':
                        yield proc.name
                except OSError:
                    pass

    def gaze_read(self, key):
        if not self.vr_ready():
            raise RuntimeError('steamvr_unavailable')
        output = self.command(['/opt/steamvr/bin/linuxarm64/vrcmd', '--settings-bool', 'steamvr.' + key], timeout=2)
        value = output.strip().splitlines()[-1].rpartition('=')[2].strip()
        if value not in ('true', 'false'):
            raise RuntimeError('gaze_read_failed')
        return value == 'true'

    def gaze_write(self, key, value):
        if not self.vr_ready():
            raise RuntimeError('steamvr_unavailable')
        self.command(['/opt/steamvr/bin/linuxarm64/vrcmd', '--set-settings-bool', 'steamvr.' + key, str(int(value))], timeout=2)

    def gaze_set(self, key, value):
        if key not in GAZE_KEYS or not isinstance(value, bool):
            raise ValueError('invalid_settings')
        previous = self.gaze_read(key)
        private_dir(self.cache)
        path = self.cache / 'gaze-before.json'
        backup = json.loads(path.read_text()) if path.exists() else {}
        if key not in backup:
            backup[key] = previous
            atomic(path, encoded(backup))
        self.gaze_write(key, value)
        actual = self.gaze_read(key)
        if actual != value:
            raise RuntimeError('gaze_write_failed')
        self.gaze = {**(self.gaze or {}), key: actual}
        return self.info()

    def gaze_restore(self):
        path = self.cache / 'gaze-before.json'
        if path.exists():
            values = json.loads(path.read_text())
            for key, value in values.items():
                if key not in GAZE_KEYS or not isinstance(value, bool):
                    raise ValueError('invalid_settings')
                self.gaze_write(key, value)
                if self.gaze_read(key) != value:
                    raise RuntimeError('gaze_write_failed')
            path.unlink()
            self.gaze = values
        return self.info()

    def stop(self, preserve_boot=False):
        if self.stopped:
            return {'stopped': True}
        self.params(active=False)
        if not preserve_boot:
            self.remove_integration()
        self.stopped = True
        return {'stopped': True}

    def handle(self, method, params):
        if not isinstance(params, dict):
            raise ValueError('invalid_settings')
        if method == 'framely.lifecycle.start':
            return self.start()
        if method == 'framely.lifecycle.stop':
            # Only preserve next-boot loading when the OS is actually shutting down.
            try:
                shutdown = subprocess.run(['systemctl', 'is-system-running'], capture_output=True, text=True, timeout=1).stdout.strip() == 'stopping'
            except (OSError, subprocess.TimeoutExpired):
                shutdown = False
            return self.stop(preserve_boot=shutdown)
        if method == 'status':
            return self.info()
        if method == 'enable':
            return self.enable(params.get('enabled'))
        if method == 'settings.update':
            return self.update(params)
        if method == 'language.sync':
            language = str(params.get('language', '')).lower().replace('_', '-').split('-')[0]
            self.host_language = language if language in ('zh', 'ja') else 'en'
            return self.info()
        if method == 'preset':
            name = params.get('name')
            if name not in PRESETS:
                raise ValueError('invalid_settings')
            return self.update({**{key: DEFAULT[key] for key in ('debandAmount', 'detailBoost', 'grainAmount', 'casCross', 'casLuma', 'cornerSkip')}, **PRESETS[name]})
        if method == 'reset':
            return self.update({key: value for key, value in DEFAULT.items() if key not in ('enabled', 'language')})
        if method == 'settings.importOriginal':
            return self.import_original()
        if method == 'gaze.get':
            self.gaze = {key: self.gaze_read(key) for key in GAZE_KEYS}
            return self.info()
        if method == 'gaze.set':
            return self.gaze_set(params.get('key'), params.get('value'))
        if method == 'gaze.restore':
            return self.gaze_restore()
        raise ValueError('unknown_method')


def main():
    backend = Backend()
    if sys.argv[1:] in (['--cleanup'], ['--uninstall']):
        backend.stop()
        if sys.argv[1:] == ['--uninstall']:
            # Retain the backup and report failure if SteamVR is unavailable for restoration.
            backend.gaze_restore()
            for name in (LIBRARY, 'guard.py', 'guard-disabled'):
                (backend.cache / name).unlink(missing_ok=True)
            # Keep only neutral params for a layer still mapped in a running compositor.
        return
    stopping = False

    def stop_signal(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop_signal)
    signal.signal(signal.SIGINT, stop_signal)
    # Raw nonblocking reads avoid TextIO buffering starving a second queued RPC.
    buffer = b''
    try:
        while not stopping:
            if not select.select([sys.stdin.buffer], [], [], 0.25)[0]:
                continue
            chunk = os.read(sys.stdin.fileno(), 65536)
            if not chunk:
                break
            buffer += chunk
            if len(buffer) > 131072:
                raise ValueError('request_too_large')
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                request = {}
                try:
                    if len(line) > 65536:
                        raise ValueError('request_too_large')
                    request = json.loads(line)
                    if not isinstance(request, dict):
                        raise ValueError('invalid_request')
                    result = backend.handle(request['method'], request.get('params', {}))
                    response = {'id': request.get('id'), 'result': result}
                except Exception as error:
                    print(str(error), file=sys.stderr)
                    response = {'id': request.get('id') if isinstance(request, dict) else None, 'error': str(error)}
                print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)
    finally:
        backend.stop()


if __name__ == '__main__':
    main()
