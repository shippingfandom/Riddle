import subprocess
import sys
import os
import shutil
import platform

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

is_windows = platform.system() == "Windows"
EXT = ".exe" if is_windows else ""
NAME = "riddle"

for p in ["build", f"{NAME}.spec", "dist"]:
    p = os.path.join(ROOT, p)
    if os.path.exists(p):
        if os.path.isdir(p):
            shutil.rmtree(p)
        else:
            os.remove(p)

EXE = os.path.join(ROOT, f"{NAME}{EXT}")
if os.path.exists(EXE):
    os.remove(EXE)

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--name", NAME,
    "--distpath", ROOT,
    "--specpath", ROOT,
    "--clean", "--noconfirm",
]

if is_windows:
    icon = os.path.join(ROOT, "icons", "rose_flower_garden_plant_nature_icon_209857.ico")
    if os.path.exists(icon):
        cmd.append(f"--icon={icon}")

cmd.append(os.path.join(ROOT, "riddle.py"))

os.chdir(ROOT)

print(f"Building {NAME}{EXT} ...")
ret = subprocess.run(cmd)
if ret.returncode != 0:
    print(f"Build failed (exit {ret.returncode})")
    sys.exit(1)

for p in ["build", f"{NAME}.spec", "dist"]:
    p = os.path.join(ROOT, p)
    if os.path.exists(p):
        if os.path.isdir(p):
            shutil.rmtree(p)
        else:
            os.remove(p)

size_before = os.path.getsize(EXE)
print(f"Before UPX: {size_before / 1024 / 1024:.1f} MB")

upx_path = shutil.which("upx")
if upx_path:
    print(f"Compressing with UPX ({upx_path}) ...")
    ret = subprocess.run(
        [upx_path, "--best", "-f", EXE],
        capture_output=True, text=True
    )
    if ret.returncode == 0:
        size_after = os.path.getsize(EXE)
        print(f"UPX done: {size_before / 1024 / 1024:.1f} MB -> {size_after / 1024 / 1024:.1f} MB ({100 - size_after * 100 / size_before:.0f}% reduction)")
    else:
        print(f"UPX failed: {ret.stderr.strip()}")
else:
    print("UPX not found — skipping compression")

size = os.path.getsize(EXE) / 1024 / 1024
print(f"Done: {EXE} ({size:.1f} MB)")
