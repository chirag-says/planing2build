# Blueprint table check: column counts per row and AQ numbering.
import re, sys, collections

SPLIT = re.compile(r'(?<!\\)\|')
aq = collections.defaultdict(list)
problems = 0
for path in sys.argv[1:]:
    lines = open(path, encoding='utf8').read().split('\n')
    in_code = False
    header_cols = None
    for n, ln in enumerate(lines, 1):
        s = ln.strip()
        if s.startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        if s.startswith('|'):
            cells = SPLIT.split(s)[1:-1]
            if header_cols is None:
                header_cols = len(cells)
                sep = lines[n].strip() if n < len(lines) else ''
                if not re.fullmatch(r'\|(\s*:?-+:?\s*\|)+', sep):
                    print(f'{path}:{n}: table header without separator row')
                    problems += 1
            elif len(cells) != header_cols and not re.fullmatch(r'\|(\s*:?-+:?\s*\|)+', s):
                print(f'{path}:{n}: {len(cells)} cells, header has {header_cols}')
                problems += 1
            m = re.match(r'AQ-(\d+)', cells[0].strip()) if cells else None
            if m:
                aq[m.group(0)].append(f'{path}:{n}')
        else:
            header_cols = None
for k in sorted(aq, key=lambda x: int(x.split('-')[1])):
    if len(aq[k]) > 1:
        print(f'{k} defined in {len(aq[k])} places: {aq[k]}')
ids = sorted(int(k.split('-')[1]) for k in aq)
missing = [i for i in range(1, max(ids) + 1) if i not in ids] if ids else []
print(f'AQ ids present: {len(ids)}, max {max(ids) if ids else 0}, missing {missing}')
print(f'table problems: {problems}')
