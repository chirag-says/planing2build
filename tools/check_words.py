# Blueprint prose check: banned filler words and em dashes (global CLAUDE.md anti-slop rules).
# Usage: python tools/check_words.py SYSTEM_BLUEPRINT/**/*.md
import re, sys

# Variant of check_words.py for the architecture docs: "key" is allowed inside
# technical terms (primary key, idempotency key, API key, cache key, SSH key,
# keyset, key_id) and flagged only as a filler adjective.
banned = [r'\bdelve', r'\bensur', r'\bcrucial', r'\brobust', r'\benhanc', r'\balign(s|ed|ing)?\b', r'\bshowcas',
          r'\blandscape\b', r'\btapestry', r'\btestament', r'\bpivotal', r'\bvibrant', r'\bmeticulous', r'\bintricac',
          r'\bunderscor', r'\bfoster', r'\bbolster', r'\bgarner', r'\bserves as\b', r'\bstands as\b', r'\bboast',
          r'\bresonat', r'\bvital\b', r'\bsignificant', r'\bseamless', r'\bleverag', r'\bholistic',
          r'\bnot just\b', r'\bI hope\b',
          r'\bkey (benefit|role|factor|feature|driver|point|term|area|concept|aspect|element|component|question|'
          r'difference|takeaway|part|piece|player|insight|consideration|requirement|rule|decision|value|metric|'
          r'signal|idea|advantage|principle|risk|step|goal|outcome|reason|property|detail|concern|issue)s?\b']

total_hits = 0
total_dash = 0
for path in sys.argv[1:]:
    t = open(path, encoding='utf8').read()
    t = re.sub(r'```mermaid[\s\S]*?```', '', t)
    t = re.sub(r'```text[\s\S]*?```', '', t)
    hits = []
    dash = []
    for n, ln in enumerate(t.split('\n'), 1):
        segs = ln.split('"')
        outside = ' '.join(segs[0::2])
        for b in banned:
            for m in re.finditer(b, outside, flags=re.I):
                hits.append((n, m.group(0), outside[max(0, m.start() - 40):m.end() + 40]))
        if '—' in outside:
            dash.append((n, outside[:120]))
    if hits or dash:
        print(f'== {path}: {len(hits)} banned, {len(dash)} em dashes')
        for h in hits[:40]:
            print('   ', h)
        for d in dash[:40]:
            print('   DASH', d)
    total_hits += len(hits)
    total_dash += len(dash)
print(f'TOTAL banned={total_hits} dashes={total_dash}')
