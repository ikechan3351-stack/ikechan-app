#!/usr/bin/env python3
"""ひらがな なぞりっこ：絵のことば一覧 japanese/hiragana/pics.js を作る。

使い方：  python3 tools/build-hiragana-pics.py

- ことばは japanese/hiragana/絵のことば候補.md の表（◎おすすめ＋ほかの候補 2つ）から取る
- japanese/hiragana/img/字1.png〜字3.png が そろっている字だけを のせる（絵ができたら このコマンドを また実行する）
- （　）の中の 説明は けす
"""
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent / 'japanese' / 'hiragana'
pics = {}
for line in (root / '絵のことば候補.md').read_text().splitlines():
    m = re.match(r'^\| (\S) \| ◎([^|]+) \| ([^|]+) \|$', line)
    if not m:
        continue
    k = m[1]
    words = [m[2]] + m[3].split('／')
    words = [re.sub(r'（[^）]*）', '', w).strip() for w in words]
    if all((root / 'img' / f'{k}{i}.png').exists() for i in (1, 2, 3)):
        pics[k] = words[:3]

body = ',\n'.join(f'  {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}' for k, v in pics.items())
(root / 'pics.js').write_text(
    '// ひらがな なぞりっこ：絵のある字と その3つの ことば（img/字1〜3.png）。\n'
    '// tools/build-hiragana-pics.py で 作る。手で なおさない\n'
    f'const PICS = {{\n{body}\n}};\n')
print(f'{len(pics)}字 → {root / "pics.js"}')
