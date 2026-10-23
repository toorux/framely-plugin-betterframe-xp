#!/usr/bin/env python3
"""Embed the corresponding source, with stable ZIP metadata and no build artifacts."""
import pathlib
import stat
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
FILES = ['manifest.json', 'package.json', 'package-lock.json', 'tsconfig.json',
         'LICENSE', 'LICENSE.integration', 'THIRD_PARTY_NOTICES.md', 'README.md',
         'VALIDATION.md', 'DEVICE-VALIDATION.md', 'icon.png', '.gitignore']
paths = [ROOT / name for name in FILES]
for folder in ('src', 'scripts', 'tests', 'vendor', '.github'):
    paths += [p for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
with zipfile.ZipFile(ROOT / 'payload/source.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(paths):
        if path.is_symlink():
            raise RuntimeError('Source archive must not contain symbolic links: ' + str(path))
        info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
        info.create_system = 3
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, path.read_bytes())
