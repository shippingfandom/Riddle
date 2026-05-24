import glob
import difflib
import subprocess
import sys
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import init, Fore, Style as S

init(autoreset=True)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

tests_dir = os.path.join(ROOT, 'tests')
results_dir = os.path.join(tests_dir, 'results')
correct_dir = os.path.join(tests_dir, 'correct')

if '--remove-results' in sys.argv:
    sys.argv.remove('--remove-results')
    remove_results = True
else:
    remove_results = False

os.makedirs(results_dir, exist_ok=True)

CONTEXT = 2


def fmt_diff(diff):
    lines = []
    for line in diff.splitlines(True):
        if line.startswith('---') or line.startswith('+++') or line.startswith('@@'):
            lines.append(Fore.CYAN + line + S.RESET_ALL)
        elif line.startswith('-'):
            lines.append(Fore.RED + line + S.RESET_ALL)
        elif line.startswith('+'):
            lines.append(Fore.GREEN + line + S.RESET_ALL)
        else:
            lines.append(line)
    return ''.join(lines)


def run_test(f, extra_flags=None):
    extra_flags = extra_flags or []
    name = os.path.splitext(os.path.basename(f))[0]
    suffix = '_minify' if '--minify' in extra_flags else ''
    result_file = os.path.join(results_dir, name + suffix + '.gls')
    correct_file = os.path.join(correct_dir, name + suffix + '.gls')
    if suffix and not os.path.exists(correct_file):
        return (name + suffix, 'SKIP', None, None)
    my_env = os.environ.copy()
    my_env['PYTHONIOENCODING'] = 'utf-8'
    with open(result_file, 'w', encoding='utf-8') as out:
        ret = subprocess.run(
            [sys.executable or '.venv\\Scripts\\python', os.path.join(ROOT, 'riddle.py'), '--no-attribution', '--no-time'] + extra_flags + [f],
            stdout=out, stderr=subprocess.PIPE, env=my_env, cwd=ROOT
        )
    if ret.returncode != 0:
        msg = ret.stderr.decode('utf-8') if ret.stderr else ''
        return (name + suffix, 'ERROR', f'exit {ret.returncode}', msg)
    if not os.path.exists(correct_file):
        return (name + suffix, 'MISSING', 'correct', correct_file)
    with open(result_file, encoding='utf-8') as r, open(correct_file, encoding='utf-8') as c:
        rlines = r.readlines()
        clines = c.readlines()
    if rlines == clines:
        return (name + suffix, 'PASS', None, None)
    diff = ''.join(difflib.unified_diff(clines, rlines, fromfile='expected', tofile='got', n=CONTEXT))
    return (name + suffix, 'FAIL', None, diff)


def run_all(files, extra_flags=None):
    extra_flags = extra_flags or []
    results = {}
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        fut = {executor.submit(run_test, f, extra_flags): f for f in files}
        for f in as_completed(fut):
            name, status, extra, detail = f.result()
            results[name] = (status, extra, detail)
    return results


def print_results(results):
    passed = 0
    failed = []
    for name in sorted(results):
        status, extra, detail = results[name]
        if status == 'PASS':
            print(f'{Fore.GREEN}PASS{Fore.RESET}: {name}')
            passed += 1
        elif status == 'FAIL':
            print(f'{Fore.RED}FAIL{Fore.RESET}: {name}')
            if detail:
                print(fmt_diff(detail))
            failed.append(name)
        elif status == 'ERROR':
            print(f'{Fore.YELLOW}ERROR{Fore.RESET} ({extra}): {name}')
            if detail:
                for line in detail.strip().splitlines():
                    print(f'  {Fore.YELLOW}{line}{Fore.RESET}')
            failed.append(name)
        elif status == 'MISSING':
            print(f'{Fore.YELLOW}MISSING{Fore.RESET}: {name} ({extra}: {detail})')
            failed.append(name)
    return passed, failed


files = sorted(glob.glob(os.path.join(tests_dir, '*.riddle')))

results = run_all(files)
passed, failed = print_results(results)

total = len(files)
minify_files = [f for f in files if os.path.exists(os.path.join(correct_dir, os.path.splitext(os.path.basename(f))[0] + '_minify.gls'))]
if minify_files:
    minify_results = run_all(minify_files, ['--minify'])
    m_passed, m_failed = print_results(minify_results)
    passed += m_passed
    failed += m_failed
    total += len(minify_results)

print()
if all_pass := not failed:
    print(f'{Fore.GREEN}{S.BRIGHT}ALL PASS ({passed}/{total}){Fore.RESET}')
else:
    print(f'{Fore.RED}{S.BRIGHT}SOME FAILURES{Fore.RESET}')
    print(f'{Fore.RED}{passed}/{total} passed, {len(failed)} failed{Fore.RESET}')
    for name in failed:
        print(f'  {Fore.RED}x{Fore.RESET} {name}')

if remove_results and os.path.exists(results_dir):
    shutil.rmtree(results_dir)
    print(f'{Fore.CYAN}Removed {results_dir}{Fore.RESET}')

sys.exit(0 if all_pass else 1)