#!/usr/bin/env python3
"""Validate release refs and generate discovery assets from final verified packages."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-((?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?')


def metadata(manifest, ref):
    version = manifest['version']
    if not VERSION.fullmatch(version):
        raise ValueError('manifest.version must be SemVer')
    tag = 'v' + version
    if ref.startswith('refs/tags/') and ref != 'refs/tags/' + tag:
        raise ValueError('Release tag must match manifest.version: ' + tag)
    return {'tag': tag, 'prerelease': '-' in version.split('+', 1)[0]}


def prepare():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    result = metadata(manifest, os.environ.get('GITHUB_REF', ''))
    for name in ('package.json', 'package-lock.json'):
        if json.loads((ROOT / name).read_text())['version'] != manifest['version']:
            raise ValueError(name + ' version must match manifest.version')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            for key, value in result.items():
                output.write(f'{key}={str(value).lower() if isinstance(value, bool) else value}\n')
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    notes = f"""{manifest['changelog']}

Steam Frame ARM64 / Framely {manifest['engines']['framely']} / runAs: steamos.

- 中文 / 日本語 / English，默认跟随 Framely。
- 安装后画面处理默认关闭；首次启用及更新渲染库后需重新启动 SteamVR，插件不会自动重启。
- 检测到独立版 BetterFrame XP 时拒绝叠加。若修改 SteamVR 补偿设置，请先恢复或在 SteamVR 运行时卸载。
- 自动检查包括后端、三语、TypeScript、ARM64 构建和 headless Vulkan；头显记录见 DEVICE-VALIDATION.md。
- 当前渲染核心已在 Steam Frame 上确认加载、实时参数与 GPU 数据；画质感受、功耗与实验功能仍需验证。
- 本 Release 包含最终安装包、release.json、图标和 SHA256SUMS；源码随包内 source.zip 提供。

Framely 通过仓库 topic `framely-plugin` 直接发现此 Release，无需 database。
"""
    (build / 'release-notes.md').write_text(notes)
    print(json.dumps(result))


def verify_release(folder, manifest):
    """Check generated package metadata and exported images before uploading."""
    descriptor = json.loads((folder / 'release.json').read_text())
    if descriptor.get('schemaVersion') != 1 or len(descriptor.get('plugins', [])) != 1:
        raise ValueError('Expected exactly one plugin in release.json')
    plugin = descriptor['plugins'][0]
    for key in ('id', 'name', 'version', 'apiVersion', 'author', 'description', 'engines'):
        if plugin.get(key) != manifest.get(key):
            raise ValueError('Release declaration mismatch: ' + key)
    expected = f"{manifest['id']}-{manifest['version']}.framely"
    if plugin.get('asset') != expected or plugin.get('runAs') != 'steamos':
        raise ValueError('Release asset or runtime identity mismatch')
    package = folder / expected
    content = package.read_bytes()
    if plugin['size'] != len(content) or plugin['sha256'] != hashlib.sha256(content).hexdigest():
        raise ValueError('Release package hash/size mismatch')
    with zipfile.ZipFile(package) as archive:
        packed = json.loads(archive.read('manifest.json'))
        for key in ('id', 'version', 'engines', 'downloadUrl'):
            if packed.get(key) != manifest.get(key):
                raise ValueError('Packaged declaration mismatch: ' + key)
        image = folder / plugin['icon']
        if image.parent != folder or image.read_bytes() != archive.read(packed['icon']):
            raise ValueError('Exported release icon mismatch')


def assemble():
    from pack import package_manifest
    manifest = package_manifest(json.loads((ROOT / 'manifest.json').read_text()),
                                os.environ.get('GITHUB_REPOSITORY', 'toorux/framely-plugin-betterframe-xp'))
    cli = os.environ.get('FRAMELY_CLI', 'framely')
    package = ROOT / 'dist' / f"{manifest['id']}-{manifest['version']}.framely"
    # Do not mix older local builds into one metadata descriptor.
    release = ROOT / 'dist/release'
    if release.exists():
        raise SystemExit('dist/release already exists; use a clean release staging directory')
    release.mkdir()
    subprocess.run([cli, 'verify', str(package)], check=True, stdout=subprocess.DEVNULL)
    shutil.copyfile(package, release / package.name)
    subprocess.run([cli, 'release-json', '--packages', str(release), '--output', str(release / 'release.json')], check=True)
    verify_release(release, manifest)
    checksums = ''.join(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n'
                        for path in sorted(release.iterdir()) if path.is_file())
    (release / 'SHA256SUMS').write_text(checksums)
    print('Verified final package, generated discovery metadata, exported icon and checksums:', release)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'assemble'))
    args = parser.parse_args()
    prepare() if args.action == 'prepare' else assemble()
