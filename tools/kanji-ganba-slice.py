#!/usr/bin/env python3
"""漢字ガンバ：まとめ絵（横3×たて2のマス）を1字ずつの絵に切り分ける。

使い方：
  python3 tools/kanji-ganba-slice.py <まとめ絵の画像> 春夏秋冬雪

- マスのわくを自動で見つけ、わくの内がわの まん中を正方形に切りぬく（横長のマスは 左右が少し切れる）
- 400×400、256色にへらした PNG にして japanese/kanji-ganba/img/字.png に保存する
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
if len(xs) != 3 or len(ys) != 2:
    sys.exit(f'マスが 横3×たて2 に見つかりません（横 {xs}・たて {ys}）')
# 上下の はしは、左はしの マスの「わくの たて線」から決める（白っぽい絵でも まちがえないため）。
# わくの角は丸いので、たて線は 上下に 少し みじかい。その分（RADIUS）を 足す
RADIUS = 10
lx = xs[0][0] + 3
edge = runs([ink(px[y][lx]) for y in range(h)], h // 6)
if len(edge) == 2:
    ys = [(max(0, y0 - RADIUS), min(h - 1, y1 + RADIUS)) for y0, y1 in edge]
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
    side = min(x1 - x0, y1 - y0) - INSET * 2
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    left, top = cx - side // 2, cy - side // 2
    crop = tmp / 'c.png'
    subprocess.run(['sips', '-c', str(side), str(side), '--cropOffset', str(top), str(left), str(tmp / 'a.bmp'),
                    '--out', str(crop)], check=True, capture_output=True)
    subprocess.run(['sips', '-z', str(SIZE), str(SIZE), str(crop)], check=True, capture_output=True)
    _, _, rows = read_bmp(crop, 'c.bmp')
    write_png8(out_dir / f'{k}.png', rows)
    print(f'{k}.png  （マス {x0},{y0}〜{x1},{y1}）  {(out_dir / f"{k}.png").stat().st_size // 1024}KB')
