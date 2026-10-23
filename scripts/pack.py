#!/usr/bin/env python3
"""Package and validate using Framely's own manifest and archive validators."""
import hashlib
import json
import os
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
REQUIRED = {'backend.py', 'guard.py', 'page.js', 'icon.png', 'libframely_betterframe_xp.so',
            'LICENSE', 'LICENSE.integration', 'LICENSE.react', 'LICENSE.react-dom',
            'LICENSE.upstream', 'LICENSE.vkbasalt', 'THIRD_PARTY.upstream.md',
            'THIRD_PARTY_NOTICES.md', 'UPSTREAM.json', 'source.zip'}


def package_manifest(manifest, repository):
    """Resolve immutable Release URL without modifying the source manifest."""
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Invalid GitHub repository')
    result = dict(manifest)
    result.pop('downloadSha256', None)
    result.setdefault('downloadUrl', f"https://github.com/{repository}/releases/download/v{result['version']}/{result['id']}-{result['version']}.framely")
    return result


def pack():
    cli = os.environ.get('FRAMELY_CLI', 'framely')
    manifest = package_manifest(json.loads((ROOT / 'manifest.json').read_text()),
                                os.environ.get('GITHUB_REPOSITORY', 'toorux/framely-plugin-betterframe-xp'))
    payload = ROOT / 'payload'
    if {path.name for path in payload.iterdir()} != REQUIRED:
        raise SystemExit('Unexpected or missing payload files. Rebuild a clean payload.')
    for path in payload.iterdir():
        if path.is_symlink() or not path.is_file():
            raise SystemExit('Payload files must be regular files: ' + path.name)
    library = (payload / 'libframely_betterframe_xp.so').read_bytes()
    if library[:5] != b'\x7fELF\x02' or int.from_bytes(library[18:20], 'little') != 183:
        raise SystemExit('Build the native layer for Linux ARM64 before packaging.')
    temporary_manifest = ROOT / 'build/package-manifest.json'
    temporary_manifest.parent.mkdir(exist_ok=True)
    temporary_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    output = dist / f"{manifest['id']}-{manifest['version']}.framely"
    subprocess.run([cli, 'pack', '--manifest', str(temporary_manifest), '--payload', str(payload), '--output', str(output)], check=True)
    result = subprocess.run([cli, 'verify', str(output)], check=True, capture_output=True, text=True)
    (dist / 'verification.json').write_text(result.stdout)
    (dist / 'SHA256SUMS').write_text(hashlib.sha256(output.read_bytes()).hexdigest() + '  ' + output.name + '\n')
    print(output)
    return output


if __name__ == '__main__':
    pack()
