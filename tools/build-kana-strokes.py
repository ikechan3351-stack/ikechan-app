#!/usr/bin/env python3
"""ひらがな なぞりっこ の書き順データ（japanese/hiragana/○○.js）を KanjiVG の SVG から作る。

使い方：
  python3 tools/build-kana-strokes.py <SVGを置いたフォルダ> <字の一覧ファイル> <できあがりの名前> <説明>
  例）python3 tools/build-kana-strokes.py kvg list.txt strokes "ひらがな46字"

- SVG は https://github.com/KanjiVG/kanjivg の kanji/0xxxx.svg（字のコードを5けたの16進数にした名前）
- 字の一覧ファイルは、字をすき間なく並べた1行のテキスト
- 濁音・小さい字・カタカナを足すときは、べつの名前（strokes-daku など）で作って HTML から読みこむ
- 1年生の教科書（縦書き）に合わせて、次の字は形を変える
  ・小さい字（っゃゅょッャュョ）… ますの右上 4分の1 に入るよう、小さくして右上へ動かす
  ・のばす ぼう（ー）… 90度まわして、上から下への たての線にする
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

SMALL = 'っゃゅょッャュョ'

def tokens(d):
    return re.findall(r'[A-Za-z]|-?\d*\.?\d+(?:e-?\d+)?', d)

def transform(d, f, lin):
    """f：点（x, y）を うつす関数、lin：ずれ（dx, dy）を うつす関数（M と c だけ たいおう）"""
    out, cmd, nums = [], None, []
    def flush():
        if cmd is None:
            return
        pairs = [(float(nums[i]), float(nums[i + 1])) for i in range(0, len(nums), 2)]
        if cmd == 'M':
            pts = [f(*q) for q in pairs]
        elif cmd == 'c':
            pts = [lin(*q) for q in pairs]
        else:
            sys.exit(f'たいおうしていない命令 {cmd}')
        out.append(cmd + ','.join(num(x) + ',' + num(y) for x, y in pts).replace(',-', '-'))
    for t in tokens(d):
        if t.isalpha():
            flush(); cmd, nums = t, []
        else:
            nums.append(t)
    flush()
    return ''.join(out)

def points(d):
    """線の上の だいたいの点（はしと 曲線の ひかえの点）"""
    pts, cur, cmd, nums = [], (0, 0), None, []
    for t in tokens(d) + ['Z']:
        if t.isalpha():
            for i in range(0, len(nums), 2):
                x, y = float(nums[i]), float(nums[i + 1])
                if cmd == 'M':
                    cur = (x, y); pts.append(cur)
                elif cmd == 'c':
                    pts.append((cur[0] + x, cur[1] + y))
                    if i % 6 == 4:
                        cur = (cur[0] + x, cur[1] + y)
            cmd, nums = t, []
        else:
            nums.append(t)
    return pts

def tate(c, paths, nums):
    """縦書きの形に なおす"""
    if c == 'ー':  # 90度 右まわり：(x, y) → (109 - y, x)
        f = lambda x, y: (109 - y, x)
        lin = lambda dx, dy: (-dy, dx)
    elif c in SMALL:  # 右上 4分の1（x 58〜100、y 9〜51）に おさめる
        ps = [q for d in paths for q in points(d)]
        x0, x1 = min(q[0] for q in ps), max(q[0] for q in ps)
        y0, y1 = min(q[1] for q in ps), max(q[1] for q in ps)
        k = min(1, 40 / (x1 - x0), 40 / (y1 - y0))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        f = lambda x, y: (79 + (x - cx) * k, 30 + (y - cy) * k)
        lin = lambda dx, dy: (dx * k, dy * k)
    else:
        return paths, nums
    paths = [transform(d, f, lin) for d in paths]
    nums = [(*f(float(x), float(y)), i) for x, y, i in nums]
    if c == 'ー':  # 番号は 線の 左がわへ
        nums = [(x - 12, y + 4, i) for x, y, i in nums]
    return paths, nums

lines = []
for c in chars:
    svg = (svg_dir / f'{ord(c):05x}.svg').read_text(encoding='utf-8')
    paths = re.findall(r'<path[^>]*?\sd="([^"]+)"', svg)
    nums = re.findall(r'<text transform="matrix\(1 0 0 1 ([\d.]+) ([\d.]+)\)">(\d+)</text>', svg)
    nums = sorted(nums, key=lambda t: int(t[2]))
    if not paths or len(paths) != len(nums):
        sys.exit(f'{c}: 線 {len(paths)} 本と番号 {len(nums)} こが合いません')
    paths, nums = tate(c, paths, nums)
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
