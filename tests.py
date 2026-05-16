import os, glob, difflib, sys

tests_dir = 'tests'
results_dir = os.path.join(tests_dir, 'results')
correct_dir = os.path.join(tests_dir, 'correct')
os.makedirs(results_dir, exist_ok=True)

all_pass = True
for f in sorted(glob.glob(os.path.join(tests_dir, '*.riddle'))):
    name = os.path.splitext(os.path.basename(f))[0]
    result_file = os.path.join(results_dir, name + '.gls')
    correct_file = os.path.join(correct_dir, name + '.gls')
    ret = os.system(f'.venv\\Scripts\\python riddle.py --no-attribution "{f}" > "{result_file}" 2>&1')
    if ret != 0:
        print(f'ERROR (exit {ret}): {name}')
        all_pass = False
        continue
    if os.path.exists(result_file) and os.path.exists(correct_file):
        with open(result_file) as r, open(correct_file) as c:
            rlines = r.readlines()
            clines = c.readlines()
            if rlines == clines:
                print(f'PASS: {name}')
            else:
                print(f'FAIL: {name}')
                for line in difflib.unified_diff(clines, rlines, fromfile='expected', tofile='got'):
                    print(line, end='')
                all_pass = False
    else:
        print(f'MISSING: {name}')
        all_pass = False

print()
print('ALL PASS' if all_pass else 'SOME FAILURES')
sys.exit(0 if all_pass else 1)
