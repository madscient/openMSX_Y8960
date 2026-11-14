"""コミットの本文の下書き（=== <段> の見出しで区切ったもの）を、隣に msg-<段>.txt として分ける。
    py split_msg.py <messages.txt>"""
import sys
from pathlib import Path

src = Path(sys.argv[1])
cur = None
parts = {}
for line in src.read_text(encoding='utf-8').splitlines():
    if line.startswith('=== '):
        cur = line[4:].strip()
        parts[cur] = []
    elif cur:
        parts[cur].append(line)
for k, lines in parts.items():
    while lines and not lines[-1].strip():
        lines.pop()
    (src.parent / f'msg-{k}.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    print(k, lines[0])
