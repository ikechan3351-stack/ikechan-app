# 「日本の川」の和歌山の川の地図データ（social/wakayama-rivers-data.js）を作るスクリプト
#
# 元データ（どちらもこのリポジトリの中にある。もとは国土数値情報 行政区域・河川データ）：
#   social/和歌山県市町村パズル.html の MAP … 30市町村の形と、7つの水系の川（支流つき）
#   social/tanabe-rivers-data.js … 田辺市の川の本流（上流 → 河口の1本の線）
#   social/tanabe-map-data.js … 田辺市の地図の座標の式（proj）
# 使い方：python3 tools/build-wakayama-rivers.py
#
# 和歌山県の地図は、経度・緯度に比例している（田辺市の形の範囲から式を求め、上富田町で確かめた）。
# 紀の川・有田川・古座川は、水系の線から「河口からいちばん遠くまで続く流れ」を本流として取り出す。
# 会津川・富田川・日置川・日高川・熊野川は、田辺市の川データを和歌山県の地図の座標に直して使う。
import json, re, heapq, math, os
ROOT = os.path.join(os.path.dirname(__file__), '..', 'social')

def load(path, name):
    s = open(os.path.join(ROOT, path), encoding='utf-8').read()
    i = s.index('const ' + name + ' = ') + len('const ' + name + ' = ')
    return json.JSONDecoder().raw_decode(s[i:])[0]

M = load('和歌山県市町村パズル.html', 'MAP')
T = load('tanabe-map-data.js', 'TANABE_MAP')
TR = load('tanabe-rivers-data.js', 'TANABE_RIVERS')

# 経度・緯度 → 和歌山県の地図の座標
LON0, X0, KX = 135.33575, 302.3, 836.6
LAT0, Y0, KY = 34.06847, 338.8, 1008.5
def wk(lon, lat): return (X0 + (lon - LON0) * KX, Y0 + (LAT0 - lat) * KY)
TX0, TY1, TCK, TK = T['proj']
def tanabe_to_wk(x, y): return wk(x / TCK + TX0, TY1 - y / TK)

def polylines(d):
    out = []
    for sub in re.split(r'(?=M)', d):
        p = [tuple(map(float, q.split(','))) for q in re.findall(r'-?[\d.]+,-?[\d.]+', sub)]
        if len(p) >= 2: out.append(p)
    return out

def main_stem(d, mouth_key):
    # 線のはしをノードにしたグラフで、河口から最も遠いノードまでの道を本流にする
    lines = polylines(d)
    key = lambda p: (round(p[0], 1), round(p[1], 1))
    adj = {}
    for i, ln in enumerate(lines):
        a, b = key(ln[0]), key(ln[-1]); L = sum(math.dist(ln[j], ln[j + 1]) for j in range(len(ln) - 1))
        adj.setdefault(a, []).append((b, L, i, False)); adj.setdefault(b, []).append((a, L, i, True))
    mouth = min(adj, key=mouth_key)
    dist, prev, pq = {mouth: 0}, {}, [(0, mouth)]
    while pq:
        d0, n = heapq.heappop(pq)
        if d0 > dist[n]: continue
        for m, L, i, rev in adj[n]:
            if d0 + L < dist.get(m, 1e18):
                dist[m] = d0 + L; prev[m] = (n, i, rev); heapq.heappush(pq, (dist[m], m))
    far = max(dist, key=dist.get)
    pts, n = [], far
    while n in prev:  # 源流 → 河口
        p, i, rev = prev[n]
        ln = lines[i] if rev else lines[i][::-1]  # n から p へ向かう順
        pts.extend(ln if not pts else ln[1:])
        n = p
    return pts

def simplify(P, tol=0.6):
    # Douglas-Peucker で点をへらす
    if len(P) < 3: return P
    a, b = P[0], P[-1]
    def dd(p):
        if a == b: return math.dist(p, a)
        return abs((b[0] - a[0]) * (a[1] - p[1]) - (a[0] - p[0]) * (b[1] - a[1])) / math.dist(a, b)
    i = max(range(1, len(P) - 1), key=lambda k: dd(P[k]))
    if dd(P[i]) <= tol: return [a, b]
    return simplify(P[:i + 1], tol)[:-1] + simplify(P[i:], tol)

WR = {r['n']: r for r in M['rivers']}
rivers = []
rivers.append(('kinokawa', simplify(main_stem(WR['紀の川']['d'], lambda p: p[0]))))
# 有田川・古座川は、水系の線に別の川がまざっているので、おもな地点（源流 → 河口の経度・緯度）をむすぶ
WAYPOINTS = {
    'arida': [(135.60, 34.18), (135.55, 34.13), (135.50, 34.10), (135.43, 34.08), (135.37, 34.09), (135.30, 34.08), (135.24, 34.075), (135.19, 34.07), (135.13, 34.085)],
    'koza': [(135.62, 33.76), (135.66, 33.72), (135.68, 33.67), (135.70, 33.62), (135.72, 33.58), (135.75, 33.55), (135.78, 33.53), (135.80, 33.505), (135.815, 33.48)],
}
for rid, ll in WAYPOINTS.items():
    rivers.append((rid, [wk(*q) for q in ll]))
TBY = {r['id']: r for r in TR['rivers']}
for rid in ('aizu', 'tonda', 'hiki', 'hidaka', 'kumano'):
    f = TBY[rid]['pts']
    rivers.append((rid, simplify([tanabe_to_wk(f[i], f[i + 1]) for i in range(0, len(f), 2)])))

out = {
    'W': M['W'], 'H': M['H'],
    'proj': [LON0, X0, KX, LAT0, Y0, KY],
    'munis': [{'n': m['n'], 'tx': m['tx'], 'ty': m['ty'], 'd': m['d']} for m in M['munis']],
    'butsubutsu': [round(v, 1) for v in wk(135.874, 33.583)],  # ぶつぶつ川（那智勝浦町粉白）
    'rivers': [{'id': rid, 'pts': [round(v, 1) for p in pts for v in p]} for rid, pts in rivers],
}
with open(os.path.join(ROOT, 'wakayama-rivers-data.js'), 'w', encoding='utf-8') as f:
    f.write('// 「日本の川」の和歌山の川の地図データ（作り直しは tools/build-wakayama-rivers.py）\n')
    f.write('// munis：30市町村の形（和歌山県市町村パズルと同じ）、rivers：本流の線（源流 → 河口、x,y のならび）\n')
    f.write('const WAKAYAMA_RIVERS = ' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';\n')
for rid, pts in rivers:
    print(rid, len(pts), 'from', tuple(round(v) for v in pts[0]), 'to', tuple(round(v) for v in pts[-1]))
