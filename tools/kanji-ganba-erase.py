#!/usr/bin/env python3
"""漢字ガンバ：絵に入ってしまった文字を、まわりの色でぬりつぶして消す。

使い方：
  python3 tools/kanji-ganba-erase.py 姉 272,343,272,288 272,300,288,296

- 字の名前のあとに、消す四角を「左,右,上,下」（400×400の中の画素）でいくつでも書く
- 四角の中で いちばん多い明るい色を「地の色」とし、それと ちがう色の画素を 地の色にする
- kanji-ganba-slice.py で作った 256色の PNG（フィルターなし）だけを あつかえる
"""
import struct
import sys
import zlib
from pathlib import Path

img = Path(__file__).resolve().parent.parent / 'japanese' / 'kanji-ganba' / 'img' / f'{sys.argv[1]}.png'
rects = [tuple(int(v) for v in r.split(',')) for r in sys.argv[2:]]

b = img.read_bytes()
i, chunks = 8, []
while i < len(b):
    n = struct.unpack('>I', b[i:i + 4])[0]
    chunks.append((b[i + 4:i + 8], b[i + 8:i + 8 + n]))
    i += 12 + n
meta = {t: v for t, v in chunks if t != b'IDAT'}
w, h = struct.unpack('>II', meta[b'IHDR'][:8])
pal = [tuple(meta[b'PLTE'][j:j + 3]) for j in range(0, len(meta[b'PLTE']), 3)]
raw = zlib.decompress(b''.join(v for t, v in chunks if t == b'IDAT'))
if any(raw[y * (w + 1)] for y in range(h)):
    sys.exit('この PNG は あつかえません（kanji-ganba-slice.py で作り直してください）')
rows = [bytearray(raw[y * (w + 1) + 1:(y + 1) * (w + 1)]) for y in range(h)]
lum = lambda c: .3 * c[0] + .59 * c[1] + .11 * c[2]
dist = lambda a, c: sum((a[k] - c[k]) ** 2 for k in range(3))

total = 0
for x0, x1, y0, y1 in rects:
    cells = [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]
    light = [pal[rows[y][x]] for x, y in cells if lum(pal[rows[y][x]]) >= 180]
    bg = tuple(sorted(c[k] for c in light)[len(light) // 2] for k in range(3))
    bi = min(range(len(pal)), key=lambda j: dist(pal[j], bg))
    for x, y in cells:
        if dist(pal[rows[y][x]], bg) > 150:
            rows[y][x] = bi
            total += 1

chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
data = zlib.compress(b''.join(b'\x00' + bytes(r) for r in rows), 9)
img.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', meta[b'IHDR']) + chunk(b'PLTE', meta[b'PLTE'])
                + chunk(b'IDAT', data) + chunk(b'IEND', b''))
print(f'{img.name}：{total} 画素を ぬりつぶしました')
