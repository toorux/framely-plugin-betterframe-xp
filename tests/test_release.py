import copy
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location('release_test_' + name, ROOT / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


release = load('release')
pack = load('pack')


class ReleaseTests(unittest.TestCase):
    def test_tag_must_match_semver_and_preview_flag(self):
        for version, preview in [('1.2.3', False), ('1.2.3-preview.2', True), ('1.2.3+arm64', False)]:
            result = release.metadata({'version': version}, 'refs/tags/v' + version)
            self.assertEqual({'tag': 'v' + version, 'prerelease': preview}, result)
        for version in ('1.2', '01.2.3', '1.2.3-01', '1.2.3-'):
            with self.assertRaises(ValueError):
                release.metadata({'version': version}, 'refs/heads/main')
        with self.assertRaises(ValueError):
            release.metadata({'version': '1.2.3'}, 'refs/tags/v1.2.4')

    def test_pack_resolves_fixed_release_url_without_editing_source(self):
        original = {'id': 'tooru.betterframe-xp', 'version': '1.2.3', 'downloadSha256': 'registration-only'}
        before = original.copy()
        result = pack.package_manifest(original, 'toorux/framely-plugin-betterframe-xp')
        self.assertEqual(before, original)
        self.assertNotIn('downloadSha256', result)
        self.assertEqual('https://github.com/toorux/framely-plugin-betterframe-xp/releases/download/v1.2.3/tooru.betterframe-xp-1.2.3.framely', result['downloadUrl'])
        with self.assertRaises(ValueError):
            pack.package_manifest(original, 'invalid/repository/path')

    def test_release_metadata_rejects_mutated_package_and_icon(self):
        import hashlib
        manifest = pack.package_manifest(json.loads((ROOT / 'manifest.json').read_text()), 'toorux/framely-plugin-betterframe-xp')
        with tempfile.TemporaryDirectory() as temporary:
            folder = pathlib.Path(temporary)
            name = f"{manifest['id']}-{manifest['version']}.framely"
            image = 'released-icon.png'
            icon = b'image bytes'
            with zipfile.ZipFile(folder / name, 'w') as archive:
                archive.writestr('manifest.json', json.dumps(manifest))
                archive.writestr(manifest['icon'], icon)
            content = (folder / name).read_bytes()
            plugin = {key: manifest[key] for key in ('id', 'name', 'version', 'apiVersion', 'author', 'description', 'engines')}
            plugin.update(asset=name, runAs='steamos', icon=image, size=len(content), sha256=hashlib.sha256(content).hexdigest())
            descriptor = {'schemaVersion': 1, 'plugins': [plugin]}
            (folder / image).write_bytes(icon)
            (folder / 'release.json').write_text(json.dumps(descriptor))
            release.verify_release(folder, manifest)
            (folder / image).write_bytes(b'wrong image')
            with self.assertRaisesRegex(ValueError, 'icon mismatch'):
                release.verify_release(folder, manifest)
            (folder / image).write_bytes(icon)
            (folder / name).write_bytes(content + b'mutated')
            with self.assertRaisesRegex(ValueError, 'hash/size mismatch'):
                release.verify_release(folder, manifest)
            (folder / name).write_bytes(content)
            broken = copy.deepcopy(descriptor)
            broken['plugins'][0]['runAs'] = 'root'
            (folder / 'release.json').write_text(json.dumps(broken))
            with self.assertRaisesRegex(ValueError, 'runtime identity mismatch'):
                release.verify_release(folder, manifest)

    def test_workflow_has_no_database_registration(self):
        workflow = (ROOT / '.github/workflows/release.yml').read_text()
        self.assertNotIn('DATABASE_TOKEN', workflow)
        self.assertNotIn('submit-database', workflow)
        self.assertIn('python3 scripts/release.py assemble', workflow)
        self.assertIn('dist/release/*', workflow)
        self.assertIn('contents: read', workflow)
        self.assertIn('contents: write', workflow)


if __name__ == '__main__':
    unittest.main()
