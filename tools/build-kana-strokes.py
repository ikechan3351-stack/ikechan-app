#!/usr/bin/env python3
"""ひらがな なぞりっこ の書き順データ（japanese/hiragana/○○.js）を KanjiVG の SVG から作る。

使い方：
  python3 tools/build-kana-strokes.py <SVGを置いたフォルダ> <字の一覧ファイル> <できあがりの名前> <説明>
  例）python3 tools/build-kana-strokes.py kvg list.txt strokes "ひらがな46字"

- SVG は https://github.com/KanjiVG/kanjivg の kanji/0xxxx.svg（字のコードを5けたの16進数にした名前）
- 字の一覧ファイルは、字をすき間なく並べた1行のテキスト
- 濁音・小さい字・カタカナを足すときは、べつの名前（strokes-daku など）で作って HTML から読みこむ
"""
import re
import sys
from pathlib import Path

svg_dir, list_file, name, label = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
chars = list_file.read_text(encoding='utf-8').strip()
out = Path(__file__).resolve().parent.parent / 'japanese' / 'hiragana' / f'{name}.js'
out.parent.mkdir(exist_ok=True)

def num(v):
    return format(round(float(v), 1), 'g')

lines = []
for c in chars:
    svg = (svg_dir / f'{ord(c):05x}.svg').read_text(encoding='utf-8')
    paths = re.findall(r'<path[^>]*?\sd="([^"]+)"', svg)
    nums = re.findall(r'<text transform="matrix\(1 0 0 1 ([\d.]+) ([\d.]+)\)">(\d+)</text>', svg)
    nums = sorted(nums, key=lambda t: int(t[2]))
    if not paths or len(paths) != len(nums):
        sys.exit(f'{c}: 線 {len(paths)} 本と番号 {len(nums)} こが合いません')
    s = ','.join('"' + p.replace('"', '') + '"' for p in paths)
    n = ','.join(f'[{num(x)},{num(y)}]' for x, y, _ in nums)
    lines.append(f'"{c}":{{"s":[{s}],"n":[{n}]}}')

head = f'''// ひらがな なぞりっこ 書き順データ（{label}）
// もとのデータ：KanjiVG（https://kanjivg.tagaini.net/）
// Copyright (C) 2009/2010/2011 Ulrich Apel. CC BY-SA 3.0 (https://creativecommons.org/licenses/by-sa/3.0/)
// このファイルは KanjiVG から筆画の線（path の d）だけを取り出したもので、同じ CC BY-SA 3.0 で公開します。
// 座標は 109×109 の中。s＝筆画の線（順番が書き順）、n＝書き順の番号を置く位置。
// tools/build-kana-strokes.py で作成。
window.KANA_STROKES = Object.assign(window.KANA_STROKES || {{}}, {{
'''
out.write_text(head + ',\n'.join(lines) + '\n});\n', encoding='utf-8')
print(f'{out.name}：{len(lines)}字')
