import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'src' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


backend = module('backend')
guard = module('guard')


class Fixture(backend.Backend):
    def __init__(self, root):
        self.commands = []
        self.maps = ''
        self.pid = None
        self.system_environment = ''
        self.fail_reload = False
        self.vr = True
        self.vr_values = {key: True for key in backend.GAZE_KEYS}
        super().__init__(home=root / 'home space %test', data=root / 'data', payload=root / 'payload', runtime=root / 'run')
        self.payload.mkdir()
        (self.payload / backend.LIBRARY).write_bytes(b'ELF fixture')
        (self.payload / 'guard.py').write_bytes(b'# guard fixture\n')

    def command(self, args, timeout=3):
        self.commands.append(args)
        if '--property=Environment' in args:
            return self.system_environment
        if '--property=EnvironmentFiles' in args:
            return str(self.envfile) + ' (ignore_errors=yes)'
        if self.fail_reload and 'daemon-reload' in args:
            raise RuntimeError('runtime_command_failed')
        return ''

    def compositor(self):
        return self.pid, self.maps

    def vr_ready(self):
        return self.vr

    def gaze_read(self, key):
        if not self.vr:
            raise RuntimeError('steamvr_unavailable')
        return self.vr_values[key]

    def gaze_write(self, key, value):
        if not self.vr:
            raise RuntimeError('steamvr_unavailable')
        self.vr_values[key] = value


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.app = Fixture(self.root)
        self.arch = patch.object(backend.platform, 'machine', return_value='aarch64')
        self.arch.start()

    def tearDown(self):
        self.arch.stop()
        self.temp.cleanup()

    def params(self):
        return (self.app.cache / 'params.conf').read_text()

    def test_default_does_not_install_layer(self):
        self.app.start()
        self.assertFalse(self.app.dropin.exists())
        self.assertFalse(self.app.layer_file.exists())
        self.assertIn('enabled = 0', self.params())
        self.assertEqual([], self.app.commands)

    def test_enable_status_live_update_and_disable(self):
        self.app.pid = 123
        info = self.app.enable(True)
        self.assertTrue(info['restartRequired'])
        self.assertTrue(info['configured'])
        layer = json.loads(self.app.layer_file.read_text())['layer']
        self.assertEqual(backend.LAYER, layer['name'])
        self.assertEqual(str(self.app.cache / backend.LIBRARY), layer['library_path'])
        self.assertIn('%%test', self.app.dropin.read_text())
        self.assertIn('EnvironmentFile=-' + str(self.app.envfile).replace('%', '%%') + '\n', self.app.dropin.read_text())
        self.assertNotIn('EnvironmentFile=-"', self.app.dropin.read_text())
        self.assertIn('ENABLE_FRAMELY_BETTERFRAME_XP="1"', self.app.envfile.read_text())
        self.app.maps = str(self.app.cache / backend.LIBRARY)
        self.assertFalse(self.app.info()['restartRequired'])
        self.app.update({'sharpenAmount': 0.85, 'showSplit': True, 'language': 'ja'})
        self.assertIn('sharpenAmount = 0.85', self.params())
        self.assertIn('showSplit = 1', self.params())
        self.assertNotIn('language', self.params())
        self.app.maps += ' (deleted)'
        self.assertTrue(self.app.info()['restartRequired'])
        self.app.enable(False)
        self.assertIn('enabled = 0', self.params())
        self.assertFalse(self.app.dropin.exists())
        self.assertFalse(self.app.layer_file.exists())
        self.assertTrue(self.app.info()['restartRequired'])
        self.assertFalse(any('restart' in arg for command in self.app.commands for arg in command))

    def test_update_does_not_replace_identical_mapped_library(self):
        self.app.enable(True)
        lib = self.app.cache / backend.LIBRARY
        first = lib.stat().st_ino
        self.app.install()
        self.assertEqual(first, lib.stat().st_ino)
        (self.app.payload / backend.LIBRARY).write_bytes(b'new ELF fixture')
        self.app.install()
        self.assertNotEqual(first, lib.stat().st_ino)

    def test_invalid_values_are_atomic(self):
        before = self.app.settings.copy()
        for bad in ({'sharpenAmount': float('nan')}, {'grainAmount': float('inf')}, {'sharpness': 2}, {'enabled': 1}, {'casCross': 'yes'}, {'debandRange': -1}, {'x': 'value'}, {'language': 'fr'}, {'sharpenAmount': True}):
            with self.assertRaises(ValueError):
                self.app.update(bad)
            self.assertEqual(before, self.app.settings)

    def test_standalone_conflict_preserves_original(self):
        self.app.maps = '/home/steam/.local/share/betterframe-xp/lib/libbetterframexp.so'
        with self.assertRaisesRegex(RuntimeError, 'original_conflict'):
            self.app.enable(True)
        self.assertFalse(self.app.dropin.exists())
        self.app.maps = ''
        self.app.system_environment = 'ENABLE_BETTERFRAME_XP=1'
        with self.assertRaisesRegex(RuntimeError, 'original_conflict'):
            self.app.enable(True)
        self.assertFalse(self.app.settings['enabled'])

    def test_foreign_paths_and_symlinks_are_not_overwritten(self):
        self.app.dropin.parent.mkdir(parents=True)
        self.app.dropin.write_text('# someone else\n')
        with self.assertRaisesRegex(RuntimeError, 'path_conflict'):
            self.app.enable(True)
        self.assertEqual('# someone else\n', self.app.dropin.read_text())
        self.app.dropin.unlink()
        target = self.root / 'untouched'
        target.write_text('keep')
        self.app.dropin.symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, 'path_conflict'):
            self.app.stop()
        self.assertEqual('keep', target.read_text())

    def test_stop_is_neutral_and_idempotent_but_retains_preferences(self):
        self.app.enable(True)
        self.app.update({'sharpenAmount': 1.4})
        self.app.stop()
        self.app.stop()
        self.assertIn('enabled = 0', self.params())
        self.assertFalse(self.app.dropin.exists())
        saved = json.loads((self.app.data / 'settings.json').read_text())
        self.assertTrue(saved['enabled'])
        self.assertEqual(1.4, saved['sharpenAmount'])
        self.app.start()
        self.assertTrue(self.app.dropin.exists())
        self.assertIn('enabled = 1', self.params())

    def test_shutdown_keeps_next_boot_integration(self):
        self.app.enable(True)
        self.app.stop(preserve_boot=True)
        self.assertTrue(self.app.dropin.exists())
        self.assertIn('enabled = 0', self.params())

    def test_failed_install_keeps_layer_neutral(self):
        self.app.fail_reload = True
        with self.assertRaisesRegex(RuntimeError, 'runtime_command_failed'):
            self.app.enable(True)
        self.assertIn('enabled = 0', self.params())
        self.assertFalse(self.app.settings['enabled'])
        self.assertFalse(self.app.dropin.exists())

    def test_systemd_rejecting_environment_file_is_reported(self):
        original = self.app.command
        def command(args, timeout=3):
            if '--property=EnvironmentFiles' in args:
                return '/usr/share/deckard/mesavars.sh (ignore_errors=no)'
            return original(args, timeout)
        self.app.command = command
        with self.assertRaisesRegex(RuntimeError, 'startup_config_invalid'):
            self.app.enable(True)
        self.assertIn('enabled = 0', self.params())
        self.assertFalse(self.app.dropin.exists())

    def test_guard_is_not_undone_by_backend_restart(self):
        self.app.enable(True)
        self.app.guard_note.write_text('signal\n')
        self.app.envfile.replace(self.app.cache / 'vulkan.env.disabled')
        self.app.start()
        self.assertFalse(self.app.envfile.exists())
        self.assertIn('enabled = 0', self.params())
        self.app.update({'sharpness': 0.8})
        self.assertIn('enabled = 0', self.params())
        self.app.enable(True)
        self.assertFalse(self.app.guard_note.exists())
        self.assertTrue(self.app.envfile.exists())

    def test_import_validates_whole_file_and_preserves_enable_language(self):
        source = self.app.home / '.config/betterframe-xp/params.conf'
        source.parent.mkdir(parents=True)
        source.write_text('enabled = 1\nuiLanguage = 0\nsharpenAmount = 0.5\ncasCross = 0\n')
        self.app.update({'language': 'zh'})
        self.app.import_original()
        self.assertFalse(self.app.settings['enabled'])
        self.assertEqual('zh', self.app.settings['language'])
        self.assertEqual(0.5, self.app.settings['sharpenAmount'])
        self.assertFalse(self.app.settings['casCross'])
        before = self.app.settings.copy()
        source.write_text('sharpenAmount = 0.9\ndebandRange = nan\n')
        with self.assertRaisesRegex(ValueError, 'import_invalid'):
            self.app.import_original()
        self.assertEqual(before, self.app.settings)

    def test_stats_require_live_pid_and_freshness(self):
        self.app.enable(True)
        self.app.pid = 456
        self.app.maps = str(self.app.cache / backend.LIBRARY)
        path = self.app.runtime / 'stats'
        path.write_text('pid = 456\nfps = 144\ngpuMsAvg = 0.98\n')
        self.assertEqual(144, self.app.info()['stats']['fps'])
        self.app.pid = 999
        self.assertIsNone(self.app.info()['stats'])
        self.app.pid = 456
        os.utime(path, (time.time() - 20,) * 2)
        self.assertIsNone(self.app.info()['stats'])

    def test_gaze_backup_is_once_and_unavailable_restore_retains_backup(self):
        key = backend.GAZE_KEYS[0]
        self.app.gaze_set(key, False)
        self.app.gaze_set(key, True)
        backup = self.app.cache / 'gaze-before.json'
        self.assertEqual({key: True}, json.loads(backup.read_text()))
        self.app.vr = False
        with self.assertRaisesRegex(RuntimeError, 'steamvr_unavailable'):
            self.app.gaze_restore()
        self.assertTrue(backup.exists())
        self.app.vr = True
        self.app.gaze_restore()
        self.assertTrue(self.app.vr_values[key])
        self.assertFalse(backup.exists())

    def test_language_mapping_and_presets(self):
        for language, expected in [('zh-CN','zh'), ('ja_JP','ja'), ('en-US','en'), ('fr-FR','en')]:
            self.assertEqual(expected, self.app.handle('language.sync', {'language': language})['effectiveLanguage'])
        self.app.update({'grainAmount': 1, 'debandAmount': 1, 'language': 'ja'})
        self.app.handle('preset', {'name': 'gentle'})
        self.assertEqual(0, self.app.settings['grainAmount'])
        self.assertEqual(0, self.app.settings['debandAmount'])
        self.assertEqual('ja', self.app.settings['language'])

    def test_rpc_batched_input_errors_and_eof_cleanup(self):
        env = {**os.environ, 'HOME': str(self.root / 'rpc-home'), 'FRAMELY_DATA_DIR': str(self.root / 'rpc-data'), 'XDG_RUNTIME_DIR': str(self.root / 'run')}
        requests = [[], {'id':1,'method':'framely.lifecycle.start'}, {'id':2,'method':'settings.update','params':{'language':'ja','sharpenAmount':0.6}}, {'id':3,'method':'status'}]
        result = subprocess.run([sys.executable, str(ROOT/'src/backend.py')], env=env, input='\n'.join(json.dumps(x) for x in requests)+'\n', capture_output=True, text=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(4, len(responses))
        self.assertEqual('invalid_request', responses[0]['error'])
        self.assertEqual('ja', responses[-1]['result']['settings']['language'])
        self.assertIn('enabled = 0', (pathlib.Path(env['HOME'])/'.local/share/framely/betterframe-xp/params.conf').read_text())


class GuardTests(unittest.TestCase):
    def test_two_fast_failures_disable_but_clean_stop_resets_counter(self):
        with tempfile.TemporaryDirectory() as folder:
            cache, runtime = pathlib.Path(folder)/'cache', pathlib.Path(folder)/'run'
            cache.mkdir()
            env = cache/'vulkan.env'
            env.write_text('enable=1')
            guard.guard('start',cache,runtime,now=0)
            guard.guard('stop',cache,runtime,result='signal',now=2)
            self.assertTrue(env.exists())
            guard.guard('start',cache,runtime,now=3)
            guard.guard('stop',cache,runtime,result='success',now=4)
            guard.guard('start',cache,runtime,now=5)
            guard.guard('stop',cache,runtime,result='signal',now=6)
            self.assertTrue(env.exists())
            guard.guard('start',cache,runtime,now=7)
            guard.guard('stop',cache,runtime,result='exit-code',now=8)
            self.assertFalse(env.exists())
            self.assertTrue((cache/'guard-disabled').exists())

    def test_guard_entry_always_succeeds_even_without_runtime(self):
        env = {key:value for key,value in os.environ.items() if key!='XDG_RUNTIME_DIR'}
        result = subprocess.run([sys.executable,str(ROOT/'src/guard.py'),'start'],env=env,capture_output=True)
        self.assertEqual(0,result.returncode)


if __name__ == '__main__':
    unittest.main()
