#!/usr/bin/env python3
"""漢字ガンバ：まとめ絵（横3×たて2のマス）を1字ずつの絵に切り分ける。

使い方：
  python3 tools/kanji-ganba-slice.py <まとめ絵の画像> 春夏秋冬雪 [--full 鳥]

- マスのわくを自動で見つけ、わくの内がわの まん中を正方形に切りぬく（横長のマスは 左右が少し切れる）
- 400×400、256色にへらした PNG にして japanese/kanji-ganba/img/字.png に保存する
- --full のあとに書いた字は 色をへらさない（うすい空のグラデーションに 四角いまだらが出るとき用。ファイルは大きくなる）
- 画像の読みこみと拡大・縮小には macOS の sips を使う（ほかのライブラリはいらない）
"""
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

SIZE = 400      # できあがりの大きさ
INSET = 16      # わくの線と角の丸みをよけるため、内がわに入る はば

src, chars = Path(sys.argv[1]), sys.argv[2]
full = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == '--full' else ''
out_dir = Path(__file__).resolve().parent.parent / 'japanese' / 'kanji-ganba' / 'img'
tmp = Path(tempfile.mkdtemp())


def read_bmp(path, name='a.bmp'):
    """sips で 24bit BMP にして読む。px[y][x] = (r, g, b)"""
    bmp = tmp / name
    subprocess.run(['sips', '-s', 'format', 'bmp', str(path), '--out', str(bmp)], check=True, capture_output=True)
    b = bmp.read_bytes()
    off = struct.unpack_from('<I', b, 10)[0]
    w, h = struct.unpack_from('<ii', b, 18)
    bp = struct.unpack_from('<H', b, 28)[0] // 8
    rs = (w * bp + 3) // 4 * 4
    H = abs(h)
    rows = []
    for y in range(H):
        yy = H - 1 - y if h > 0 else y
        r = b[off + yy * rs: off + yy * rs + w * bp]
        rows.append([(r[i + 2], r[i + 1], r[i]) for i in range(0, w * bp, bp)])
    return w, H, rows


def runs(flags, min_len):
    out, start = [], None
    for i, f in enumerate(flags + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            if i - start >= min_len:
                out.append((start, i - 1))
            start = None
    return out


w, h, px = read_bmp(src)
ink = lambda p: min(p) < 235
# マスのある列・行：白くない画素が多い はんいを さがす
col = [sum(ink(px[y][x]) for y in range(0, h, 4)) > h // 40 for x in range(w)]
row = [sum(ink(px[y][x]) for x in range(0, w, 4)) > w // 40 for y in range(h)]
xs, ys = runs(col, w // 6), runs(row, h // 4)
# わくの線が細く、わくの内がわに白いすき間がある絵では、上で見つかるのは 絵の部分だけ。
# 外がわ40画素以内（となりのマスとの まん中まで）に「たてに長い線（わく）」があれば、そこまで広げる
tall = lambda x: sum(ink(px[y][x]) for y in range(0, h, 2)) > h // 2 * 0.6
def widen(i):
    x0, x1 = xs[i]
    lo = (xs[i - 1][1] + x0) // 2 + 1 if i > 0 else 0
    hi = (x1 + xs[i + 1][0]) // 2 - 1 if i < len(xs) - 1 else w - 1
    left = [x for x in range(max(lo, x0 - 40), x0) if tall(x)]
    right = [x for x in range(x1 + 1, min(hi, x1 + 40) + 1) if tall(x)]
    return (left[0] if left else x0, right[-1] if right else x1)
xs = [widen(i) for i in range(len(xs))] if len(xs) == 3 else xs
# 白い地のマス（わくの線だけが たてに長い）なら、わくの線を 直接さがす。
# 上下2段をつらぬく たて線が ちょうど6本なら、2本ずつが 1つのマスの 左右の はし
# （木のみきや塔のような はばの広いものは のぞく。空白のマスの わくは みじかいので、長さは 画面の35%以上でよい）
cols = [sum(ink(px[y][x]) for y in range(0, h, 2)) for x in range(w)]
lines = []
tl = []
for r in runs([c > h // 2 * 0.35 for c in cols], 1):
    # わくの線と 色でうまった絵の あいだの 小さな すき間（8画素以下）は つなげる
    if tl and r[0] - tl[-1][1] <= 8:
        tl[-1] = (tl[-1][0], r[1])
    else:
        tl.append(r)
for r in tl:
    if r[1] - r[0] <= 16:
        lines.append(r)
    elif r[1] - r[0] > w // 4:
        # 色でうまった マス（わくと絵が つながって 1本の太い線に見える）は、その左右の はしを わくとする
        lines += [(r[0], r[0]), (r[1], r[1])]
# 絵の中の 細いたて線（矢など）が まじって 6本より多いときは、
# 「3つのマスの はばが そろい、マスの間の すき間も そろう」6本の組を えらぶ
from itertools import combinations
best = None
for c in combinations(lines, 6):
    ws = [c[i + 1][1] - c[i][0] for i in (0, 2, 4)]
    gs = [c[2][0] - c[1][1], c[4][0] - c[3][1]]
    if min(ws) <= w // 5 or min(gs) < 0:
        continue
    score = max(ws) - min(ws) + abs(gs[0] - gs[1])
    if best is None or score < best[0]:
        best = (score, c)
if best and best[0] <= 30:
    lines = best[1]
    xs = [(lines[i][0], lines[i + 1][1]) for i in (0, 2, 4)]
# 絵が小さいマスがあると 上の方法では3つそろわないことがある。わくの線で見つかれば それでよい
# 白っぽい絵のマスは 見つからないことがある。左の2列が見つかって 右に場所があれば、同じ はば・同じ すき間で 3列目を足す
if len(xs) == 2 and xs[1][0] - xs[0][1] > 0:
    step = xs[1][0] - xs[0][0]
    third = (xs[1][0] + step, xs[1][1] + step)
    if third[1] < w:
        xs = xs + [third]
if len(xs) != 3 or len(ys) != 2:
    sys.exit(f'マスが 横3×たて2 に見つかりません（横 {xs}・たて {ys}）')
if '--dry' in sys.argv:
    print('横', xs)
# 上下の はしは、左はしの マスの「わくの たて線」から決める（白っぽい絵でも まちがえないため）。
# わくの角は丸いので、たて線は 上下に 少し みじかい。その分（RADIUS）を 足す
RADIUS = 10
lx = xs[0][0] + 3
inset = INSET
edge = runs([ink(px[y][lx]) for y in range(h)], h // 6)
if len(edge) == 2:
    ys = [(max(0, y0 - RADIUS), min(h - 1, y1 + RADIUS)) for y0, y1 in edge]
    # 角の丸みが大きい絵では RADIUS では足りない。たて線のはしから 外へ50画素以内で、
    # マスの はばの6割以上が線になっている「わくの横線」があれば、そこを上下の はしにする
    fx0, fx1 = xs[0]
    hline = lambda y: sum(ink(px[y][x]) for x in range(fx0 + 40, fx1 - 40, 2)) > (fx1 - fx0 - 80) // 2 * 0.6
    # 上の段の下と 下の段の上は、2段の あいだの まん中より 先は さがさない（となりの段の わくを まちがえないため）
    mid = (edge[0][1] + edge[1][0]) // 2
    def outer(y0, y1, lo, hi):
        top = [y for y in range(max(lo, y0 - 50), y0) if hline(y)]
        bot = [y for y in range(y1 + 1, min(hi, y1 + 51)) if hline(y)]
        return (top[0] if top else max(0, y0 - RADIUS), bot[-1] if bot else min(h - 1, y1 + RADIUS))
    ys = [outer(*edge[0], 0, mid), outer(*edge[1], mid + 1, h)]
    if "--dry" in sys.argv: print("edge", edge, "ys", ys)
    # 角の丸みが大きいほど、切りぬく正方形の角に わくの丸い線が 入りやすい。丸みに合わせて 内がわへ 入る
    corner = max(edge[0][0] - ys[0][0], ys[0][1] - edge[0][1])
    inset = max(INSET, int(corner * 0.4) + 10)
boxes = [(x, y) for y in ys for x in xs]


def median_cut(colors, n):
    """colors: {(r,g,b): 数}。n色の パレットを返す"""
    boxes = [list(colors.items())]
    while len(boxes) < n:
        boxes.sort(key=lambda b: max(max(c[0][i] for c in b) - min(c[0][i] for c in b) for i in range(3)) if len(b) > 1 else -1)
        b = boxes.pop()
        if len(b) < 2:
            boxes.append(b)
            break
        ch = max(range(3), key=lambda i: max(c[0][i] for c in b) - min(c[0][i] for c in b))
        b.sort(key=lambda c: c[0][ch])
        total, acc = sum(c[1] for c in b), 0
        for i, c in enumerate(b):
            acc += c[1]
            if acc >= total / 2:
                break
        i = max(1, min(i, len(b) - 1))
        boxes += [b[:i], b[i:]]
    pal = []
    for b in boxes:
        t = sum(c[1] for c in b)
        pal.append(tuple(round(sum(c[0][i] * c[1] for c in b) / t) for i in range(3)))
    return pal


def write_png8(path, rows):
    hist = {}
    for r in rows:
        for p in r:
            k = (p[0] >> 2 << 2, p[1] >> 2 << 2, p[2] >> 2 << 2)
            hist[k] = hist.get(k, 0) + 1
    pal = median_cut(hist, 256)
    cache = {}

    def idx(p):
        k = (p[0] >> 2, p[1] >> 2, p[2] >> 2)
        if k not in cache:
            cache[k] = min(range(len(pal)), key=lambda i: (pal[i][0] - p[0]) ** 2 * 3 + (pal[i][1] - p[1]) ** 2 * 4 + (pal[i][2] - p[2]) ** 2 * 2)
        return cache[k]

    raw = b''.join(b'\x00' + bytes(idx(p) for p in r) for r in rows)
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', len(rows[0]), len(rows), 8, 3, 0, 0, 0))
           + chunk(b'PLTE', b''.join(bytes(c) for c in pal)) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
    path.write_bytes(png)


for k, ((x0, x1), (y0, y1)) in zip(chars, boxes):
    if '--dry' in sys.argv:
        print(k, x0, y0, x1, y1)
        continue
    side = min(x1 - x0, y1 - y0) - inset * 2
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    left, top = cx - side // 2, cy - side // 2
    crop = tmp / 'c.png'
    subprocess.run(['sips', '-c', str(side), str(side), '--cropOffset', str(top), str(left), str(tmp / 'a.bmp'),
                    '--out', str(crop)], check=True, capture_output=True)
    subprocess.run(['sips', '-z', str(SIZE), str(SIZE), str(crop)], check=True, capture_output=True)
    if k in full:
        subprocess.run(['sips', '-s', 'format', 'png', str(crop), '--out', str(out_dir / f'{k}.png')], check=True, capture_output=True)
    else:
        _, _, rows = read_bmp(crop, 'c.bmp')
        write_png8(out_dir / f'{k}.png', rows)
    print(f'{k}.png  （マス {x0},{y0}〜{x1},{y1}）  {(out_dir / f"{k}.png").stat().st_size // 1024}KB')
