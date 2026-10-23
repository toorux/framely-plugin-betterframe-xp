#!/usr/bin/env python3
"""Package and validate using Framely's own manifest and archive validators."""
import hashlib
import json
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
cli = os.environ.get('FRAMELY_CLI', 'framely')
manifest = json.loads((ROOT / 'manifest.json').read_text())
required = {'backend.py', 'guard.py', 'page.js', 'icon.png', 'libframely_betterframe_xp.so',
            'LICENSE', 'LICENSE.integration', 'LICENSE.react', 'LICENSE.react-dom',
            'LICENSE.upstream', 'LICENSE.vkbasalt', 'THIRD_PARTY.upstream.md',
            'THIRD_PARTY_NOTICES.md', 'UPSTREAM.json', 'source.zip'}
payload = ROOT / 'payload'
if {path.name for path in payload.iterdir()} != required:
    raise SystemExit('Unexpected or missing payload files. Rebuild a clean payload.')
for path in payload.iterdir():
    if path.is_symlink() or not path.is_file():
        raise SystemExit('Payload files must be regular files: ' + path.name)
library = (payload / 'libframely_betterframe_xp.so').read_bytes()
if library[:5] != b'\x7fELF\x02' or int.from_bytes(library[18:20], 'little') != 183:
    raise SystemExit('Build the native layer for Linux ARM64 before packaging.')
dist = ROOT / 'dist'
dist.mkdir(exist_ok=True)
output = dist / f"{manifest['id']}-{manifest['version']}.framely"
subprocess.run([cli, 'pack', '--manifest', str(ROOT / 'manifest.json'), '--payload', str(ROOT / 'payload'), '--output', str(output)], check=True)
result = subprocess.run([cli, 'verify', str(output)], check=True, capture_output=True, text=True)
(dist / 'verification.json').write_text(result.stdout)
(dist / 'SHA256SUMS').write_text(hashlib.sha256(output.read_bytes()).hexdigest() + '  ' + output.name + '\n')
print(result.stdout)
print(output)
