#!/usr/bin/env python3
"""Build the namespaced upstream layer; no installation or SteamVR access."""
import os
import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'vendor/upstream/layer/src'
BUILD = ROOT / 'build/native'


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    compiler = os.environ.get('CXX', 'c++')
    glslang = os.environ.get('GLSLANG_VALIDATOR', 'glslangValidator')
    if not shutil.which(glslang):
        raise SystemExit('Install glslang-tools or set GLSLANG_VALIDATOR to glslangValidator')
    # Keep vendor/upstream byte-for-byte attributable to its pinned commit.
    for path in SOURCE.iterdir():
        if path.suffix not in ('.cpp', '.hpp'):
            continue
        content = path.read_text().replace('BETTERFRAME_XP', 'FRAMELY_BETTERFRAME_XP').replace('betterframe-xp', 'framely-betterframe-xp')
        if path.name == 'frame_stats.cpp':
            content = content.replace('const double fps = frames / seconds;',
                                      'const double fps = frames / seconds;\n        std::fprintf(out, "pid = %ld\\n", static_cast<long>(::getpid()));')
            # Per-second stats remain enabled; per-frame traces are opt-in, avoiding
            # unrequested ~80 MB of tmpfs trace storage and per-frame file I/O.
            content = content.replace('constexpr size_t kTraceLimit',
                                      'const bool traceEnabled = std::getenv("FRAMELY_BETTERFRAME_XP_TRACE") != nullptr;\n        constexpr size_t kTraceLimit')
            content = content.replace('if (!gaps.empty() && gaps.back() > 10.0)', 'if (traceEnabled && !gaps.empty() && gaps.back() > 10.0)')
            content = content.replace('if (!gaps.empty())\n            records.push_back', 'if (traceEnabled && !gaps.empty())\n            records.push_back')
        (BUILD / path.name).write_text(content)
    for name in ('full_screen_triangle.vert', 'postfx.frag'):
        subprocess.run([glslang, '-V', '-x', str(SOURCE / 'shader' / (name + '.glsl')), '-o', str(BUILD / (name + '.h'))], check=True)
    payload = ROOT / 'payload'
    payload.mkdir(exist_ok=True)
    includes = ['-I' + str(BUILD)]
    if os.environ.get('VULKAN_HEADERS'):
        includes.append('-I' + os.environ['VULKAN_HEADERS'])
    output = payload / 'libframely_betterframe_xp.so'
    temporary = output.with_suffix('.so.tmp')
    subprocess.run([compiler, '-std=c++20', '-O2', '-fPIC', '-fvisibility=hidden', '-shared', '-pthread',
                    '-Wall', '-Wextra', '-Wl,-z,relro,-z,now', *includes,
                    *[str(path) for path in sorted(BUILD.glob('*.cpp'))], '-o', str(temporary)], check=True)
    temporary.replace(output)


if __name__ == '__main__':
    main()
