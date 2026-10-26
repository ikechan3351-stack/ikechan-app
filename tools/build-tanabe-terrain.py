# 田辺市の地形（標高の色分け）データ（social/tanabe-terrain-data.js）を作るスクリプト
#
# 元データ：国土数値情報「標高・傾斜度4次メッシュ（G04-c、2011年）」（https://nlftp.mlit.go.jp/ksj/）
#   G04-c-11_5035-jgd_GML.zip・G04-c-11_5135-jgd_GML.zip を1つのフォルダに展開しておく
# 必要なもの：pip install shapely pyshp
# 使い方：python3 tools/build-tanabe-terrain.py <展開したフォルダ> social/tanabe-map-data.js social/tanabe-terrain-data.js
#
# 地図の座標は tanabe-map-data.js と同じ（proj を読んで合わせる）。
# 標高の段ごとに「その高さ以上の土地」の形を作り、田辺市の形で切り取る（下の段から重ねてかく）。
import shapefile, json, sys, glob, re
from shapely.geometry import box, Polygon
from shapely.ops import unary_union
SRC, MAPJS, OUT = sys.argv[1:4]

s = open(MAPJS, encoding='utf-8').read()
M = json.loads(s[s.index('{'):s.rindex('}') + 1])
X0, Y1, CK, K = M['proj']
def P(lon, lat): return ((lon - X0) * CK, (Y1 - lat) * K)

# 地区の形（"M x,y x,y ...Z" のくり返し、evenodd）→ shapely
def path_poly(d):
    g = None
    for ring in re.findall(r'M([^MZ]+)Z', d):
        pts = [tuple(map(float, p.split(','))) for p in ring.split()]
        if len(pts) < 3: continue
        p = Polygon(pts).buffer(0)
        g = p if g is None else g.symmetric_difference(p)
    return g
AREAS = {a['id']: path_poly(a['d']) for a in M['areas']}
TAN = unary_union(list(AREAS.values())).buffer(0)

# 標高のメッシュ（500mごと）
cells = []
for f in glob.glob(SRC + '/G04-c-11_*_ElevationAndSlopeAngleFourthMesh.shp'):
    r = shapefile.Reader(f, encoding='cp932')
    for sr in r.iterShapeRecords():
        h = sr.record[1]
        if h == 'unknown': continue
        x0, y0, x1, y1 = sr.shape.bbox
        a, b = P(x0, y1)
        c, d = P(x1, y0)
        cb = box(a, b, c, d)
        if not cb.intersects(TAN): continue
        cells.append((float(h), cb))
print('メッシュ', len(cells))

# 段（m）。いちばん下の段（0〜100m）は地区の形そのもの
BANDS = [100, 300, 600, 1000]
SM = 8   # なめらかにする強さ（地図の単位。メッシュ1つは約11×9）
layers = []
for t in BANDS:
    g = unary_union([cb for h, cb in cells if h >= t])
    g = g.buffer(SM, join_style=1).buffer(-SM * 1.6, join_style=1).buffer(SM * 0.6, join_style=1)
    g = g.intersection(TAN).simplify(1.8).buffer(0)
    polys = [g] if g.geom_type == 'Polygon' else list(g.geoms)
    polys = [p for p in polys if p.geom_type == 'Polygon' and p.area > 30]
    def ring(cs):
        pts = [f'{x:.1f},{y:.1f}' for x, y in list(cs)[:-1]]
        return 'M' + ' '.join(pts) + 'Z'
    d = ''.join(ring(p.exterior.coords) + ''.join(ring(i.coords) for i in p.interiors) for p in polys)
    layers.append({'min': t, 'd': d})
    print(t, 'm 以上', len(polys), 'こ', len(d), '文字')

# 地区ごとの標高（先生モードと、地区のようすの説明に使う）
stats = {}
for aid, ag in AREAS.items():
    hs = []
    for h, cb in cells:
        w = cb.intersection(ag).area
        if w > 0: hs.append((h, w))
    tot = sum(w for h, w in hs)
    stats[aid] = {
        'mean': round(sum(h * w for h, w in hs) / tot),
        'max': round(max(h for h, w in hs)),
        'low': round(100 * sum(w for h, w in hs if h < 100) / tot),     # 100m より低い土地の割合（%）
        'high': round(100 * sum(w for h, w in hs if h >= 600) / tot)     # 600m 以上の割合（%）
    }
    print(aid, stats[aid])

out = {'bands': [0] + BANDS, 'layers': layers, 'stats': stats,
       'note': '国土数値情報（標高・傾斜度4次メッシュ 2011年）を加工'}
with open(OUT, 'w', encoding='utf-8') as f:
    f.write('// 田辺市の地形（標高の色分け）データ（国土数値情報 標高・傾斜度4次メッシュを加工して作成）\n')
    f.write('// 田辺市の特産マップ.html などで、tanabe-map-data.js といっしょに使う\n')
    f.write('const TANABE_TERRAIN = ' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';\n')
print('書き出し', OUT)
