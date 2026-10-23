#!/usr/bin/env python3
"""Runs in a temporary HOME/runtime; never contacts SteamVR or systemd."""
import json
import os
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='betterframe-vulkan-') as folder:
    base = pathlib.Path(folder)
    binary = base / 'vrcompositor'
    include = ['-I' + os.environ['VULKAN_HEADERS']] if os.environ.get('VULKAN_HEADERS') else []
    subprocess.run([os.environ.get('CXX','c++'),'-std=c++20',*include,str(ROOT/'tests/vulkan_smoke.cpp'),'-Wl,-l:libvulkan.so.1','-o',str(binary)],check=True)
    layers = base/'layers'
    layers.mkdir()
    manifest = {'file_format_version':'1.0.0','layer':{'name':'VK_LAYER_FRAMELY_BETTERFRAME_XP','type':'GLOBAL','library_path':str(ROOT/'payload/libframely_betterframe_xp.so'),'api_version':'1.3.223','implementation_version':'1','description':'Isolated test','functions':{'vkGetInstanceProcAddr':'vkBasalt_GetInstanceProcAddr','vkGetDeviceProcAddr':'vkBasalt_GetDeviceProcAddr'},'enable_environment':{'ENABLE_FRAMELY_BETTERFRAME_XP':'1'},'disable_environment':{'DISABLE_FRAMELY_BETTERFRAME_XP':'1'}}}
    (layers/'layer.json').write_text(json.dumps(manifest))
    log = base/'layer.log'
    env={**os.environ,'HOME':str(base),'XDG_RUNTIME_DIR':str(base),'VK_ADD_IMPLICIT_LAYER_PATH':str(layers),
         'ENABLE_FRAMELY_BETTERFRAME_XP':'1','FRAMELY_BETTERFRAME_XP_PARAMS':str(base/'params.conf'),
         'FRAMELY_BETTERFRAME_XP_LOG_LEVEL':'info','FRAMELY_BETTERFRAME_XP_LOG_FILE':str(log)}
    if os.path.exists('/usr/share/vulkan/icd.d/lvp_icd.json'):
        env['VK_ICD_FILENAMES']='/usr/share/vulkan/icd.d/lvp_icd.json'
    result=subprocess.run([str(binary)],env=env,timeout=40)
    if result.returncode:
        if log.exists(): print(log.read_text())
        raise SystemExit(result.returncode)
    text=log.read_text()
    assert 'effect ready' in text,text
    assert 'present path: plain copy' in text,text
    assert 'present path: effect pass' in text,text
    stats=(base/'framely-betterframe-xp/stats').read_text()
    assert 'pid = ' in stats,stats
    assert 'gpuMsAvg = ' in stats,stats
    print('Real Vulkan layer load, swapchain substitution, shader execution, live bypass, and PID-tagged GPU stats passed.')
