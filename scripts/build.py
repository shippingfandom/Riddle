import subprocess
import sys
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ICON = os.path.join(ROOT, 'icons', 'rose_flower_garden_plant_nature_icon_209857.ico')
NAME = 'riddle'

for p in ['build', f'{NAME}.spec', 'dist']:
    p = os.path.join(ROOT, p)
    if os.path.exists(p):
        if os.path.isdir(p):
            shutil.rmtree(p)
        else:
            os.remove(p)

EXE = os.path.join(ROOT, f'{NAME}.exe')
if os.path.exists(EXE):
    os.remove(EXE)

cmd = [
    sys.executable, '-m', 'PyInstaller',
    '--onefile',
    '--name', NAME,
    '--distpath', ROOT,
    '--specpath', ROOT,
    '--clean', '--noconfirm',
    f'--icon={ICON}',
    os.path.join(ROOT, 'riddle.py'),
]

os.chdir(ROOT)

print(f'Building {NAME}.exe ...')
ret = subprocess.run(cmd)
if ret.returncode != 0:
    print(f'Build failed (exit {ret.returncode})')
    sys.exit(1)

for p in ['build', f'{NAME}.spec', 'dist']:
    p = os.path.join(ROOT, p)
    if os.path.exists(p):
        if os.path.isdir(p):
            shutil.rmtree(p)
        else:
            os.remove(p)

size = os.path.getsize(EXE) / 1024 / 1024
print(f'Done: {EXE} ({size:.1f} MB)')