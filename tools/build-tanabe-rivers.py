# 「田辺市の川をたどろう」の川データ（social/tanabe-rivers-data.js）を作るスクリプト
#
# 元データ：国土数値情報「河川（W05、2009年）」（https://nlftp.mlit.go.jp/ksj/）
#   W05-09_30（和歌山県）→ <dl>/W05_30/、W05-09_29（奈良県）→ <dl>/W05_29/
#   W05-08_24（三重県、2008年）→ <dl>/W05_24/　※熊野川の下流（県ざかい）は三重県のデータに入っている
# 必要なもの：pip install shapely pyshp
# 使い方：python3 tools/build-tanabe-rivers.py <dl フォルダ> social/tanabe-map-data.js social/tanabe-rivers-data.js
#
# 6本の川の「本流（いちばん長い流れ）」を、上流 → 河口の1本の線にする。
# 河口の近くの点から、同じ水系・同じ名前の流路をたどり、いちばん遠い所を上流（出発点）にする。
# 線の上に、通る地区・町の順番（境をこえる位置）と、支流が合流する位置を入れる。
# 地図の座標は tanabe-map-data.js と同じ（proj を読んで合わせる）。
import shapefile, json, sys, re, heapq, math
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.prepared import prep
D, MAPJS, OUT = sys.argv[1:4]

s = open(MAPJS, encoding='utf-8').read()
M = json.loads(s[s.index('{'):s.rindex('}') + 1])
X0, Y1, CK, K = M['proj']
def P(lon, lat): return ((lon - X0) * CK, (Y1 - lat) * K)
def path_poly(d):
    g = None
    for ring in re.findall(r'M([^MZ]+)Z', d):
        pts = [tuple(map(float, p.split(','))) for p in ring.split()]
        if len(pts) < 3: continue
        p = Polygon(pts).buffer(0)
        g = p if g is None else g.symmetric_difference(p)
    return g

# 地区（5つ）ととなりの市町村の形（地図の座標）
LAND = [('area', a['id'], a['name'], prep(path_poly(a['d']).buffer(0.3))) for a in M['areas']]
LAND += [('town', n['name'], n['name'], prep(path_poly(n['d']).buffer(0.8))) for n in M['neighbors']]
PREF = {n['name']: n['pref'] for n in M['neighbors']}

# 流路を読む
segs = []
for p in (D + '/W05_30/W05-09_30-g_Stream', D + '/W05_29/W05-09_29-g_Stream', D + '/W05_24/W05-08_24-g_Stream'):
    for sr in shapefile.Reader(p, encoding='cp932').iterShapeRecords():
        r = sr.record
        segs.append(dict(sys=r[0], name=r[3], pts=[tuple(q) for q in sr.shape.points]))
key = lambda q: (round(q[0], 4), round(q[1], 4))   # 約10mより近い点は同じ点とみなす（県ざかいで線が少しずれるため）
def seglen(pts): return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))

# 川の表：id・名前・ふりがな・本流の名前・河口に近い点（経度, 緯度）・上流の名前のことわり
RIVERS = [
    ('haya', '芳養川', 'はやがわ', ['芳養川'], (135.352, 33.745), ''),
    ('aizu', '会津川', 'あいづがわ', ['右会津川', '左会津川'], (135.373, 33.727), '上流は「右会津川」とよぶ'),
    ('tonda', '富田川', 'とんだがわ', ['富田川'], (135.375, 33.637), ''),
    ('hiki', '日置川', 'ひきがわ', ['日置川'], (135.430, 33.565), ''),
    ('hidaka', '日高川', 'ひだかがわ', ['日高川'], (135.153, 33.873), ''),
    ('kumano', '熊野川', 'くまのがわ', ['熊野川'], (135.995, 33.722), '奈良県では「十津川」とよぶ'),
]
# 会津川は、右会津川を本流としてたどる（上流の出発点を右会津川の中から選ぶ）
SRC_NAME = {'aizu': '右会津川'}
# 上流の出発点を、いちばん遠い所ではなく、この点にいちばん近い所にする（日高川は護摩壇山のあたり）
SRC_NEAR = {'hidaka': (135.567, 34.055)}
# 上流が長すぎる川は、この点から始める（熊野川は奈良県の十津川村から）
CUT_FROM = {'kumano': (135.745, 33.96)}
# 支流のふりがな。ここにある支流だけ「合流したよ」と知らせる（読みが確かめられないものは入れない）
TRIB_KANA = {'左会津川': 'さあいづがわ', '稲成川': 'いなりがわ',
             '中川': 'なかがわ', '鍛冶屋川': 'かじやがわ', '岡川': 'おかがわ', '生馬川': 'いくまがわ',
             '野中川': 'のなかがわ', '安川': 'やすかわ', '前ノ川': 'まえのかわ', '将軍川': 'しょうぐんがわ',
             '丹生川': 'にゅうのかわ', '初湯川': 'うぶゆがわ',
             '音無川': 'おとなしがわ', '大塔川': 'おおとうがわ', '北山川': 'きたやまがわ', '赤木川': 'あかぎがわ'}

# 元データの名前と、地元でのよび方がちがう支流（元データの名前 → 表示する名前）
TRIB_NAME = {'丹生川': '丹生ノ川'}
# 合流点を直す支流（元データの線の端では、合流する地区がちがって出るもの）
#   ('near', 経度, 緯度)：本流の線の上で、この点にいちばん近い所で合流させる（日置川の野中川は中辺路町の近露）
#   ('town', 名前)：本流がこの町に入った所で合流させる（日置川の将軍川は白浜町＝旧日置川町の川）
TRIB_AT = {('hiki', '野中川'): ('near', 135.602, 33.807), ('hiki', '将軍川'): ('town', '白浜町')}

# 見える範囲（地図の座標）。この外の上流は切る
VIEW = box(-330, -120, 1290, 1180)
def proj_pts(pts): return [P(*q) for q in pts]

out = []
for rid, name, kana, names, mouth, note in RIVERS:
    sysid = None
    # 河口にいちばん近い区間の水系にそろえる
    best = min((sg for sg in segs if sg['name'] in names), key=lambda sg: min(math.dist(mouth, q) for q in (sg['pts'][0], sg['pts'][-1])))
    sysid = best['sys']
    mine = [sg for sg in segs if sg['sys'] == sysid and sg['name'] in names]
    # つながりの表
    adj = {}
    for i, sg in enumerate(mine):
        a, b = key(sg['pts'][0]), key(sg['pts'][-1])
        L = seglen(sg['pts'])
        adj.setdefault(a, []).append((b, L, i, False))
        adj.setdefault(b, []).append((a, L, i, True))
    start = min(adj, key=lambda n: math.dist(n, mouth))
    dist = {start: 0}; prev = {}
    pq = [(0, start)]
    while pq:
        d0, n = heapq.heappop(pq)
        if d0 > dist[n]: continue
        for m, L, i, rev in adj[n]:
            if d0 + L < dist.get(m, 1e9):
                dist[m] = d0 + L; prev[m] = (n, i, rev); heapq.heappush(pq, (dist[m], m))
    cand = [n for n in dist if (rid not in SRC_NAME or any(key(q) == n for sg in mine if sg['name'] == SRC_NAME[rid] for q in (sg['pts'][0], sg['pts'][-1])))]
    src = min(cand, key=lambda n: math.dist(n, SRC_NEAR[rid])) if rid in SRC_NEAR else max(cand, key=lambda n: dist[n])
    # 上流 → 河口の点の列
    line = []; n = src; used = set()
    while n != start:
        p, i, rev = prev[n]
        used.add(i)
        pts = mine[i]['pts']
        # 区間を n → p の向きにする
        pts = pts if key(pts[0]) == n else pts[::-1]
        line += pts if not line else pts[1:]
        n = p
    if rid in CUT_FROM:
        j = min(range(len(line)), key=lambda j: math.dist(line[j], CUT_FROM[rid]))
        line = line[j:]
    pp = proj_pts(line)
    g = LineString(pp).intersection(VIEW)
    if g.geom_type != 'LineString':
        g = max(g.geoms, key=lambda l: Point(l.coords[-1]).distance(Point(pp[-1])) * -1)   # 河口をふくむ部分
    g = g.simplify(0.35)
    # 2 単位ごとの点にする（なぞるときの点）
    L = g.length; nstep = max(2, int(L / 2))
    dense = [g.interpolate(L * k / nstep) for k in range(nstep + 1)]
    pts = [(round(q.x, 1), round(q.y, 1)) for q in dense]
    # 通る地区・町
    runs = []
    for k, (x, y) in enumerate(pts):
        pt = Point(x, y)
        hit = next(((kind, i, nm) for kind, i, nm, pg in LAND if pg.contains(pt)), ('sea', 'sea', '海'))
        if runs and runs[-1]['id'] == hit[1]: continue
        runs.append(dict(kind=hit[0], id=hit[1], name=hit[2], i=k))
    # 県ざかい・市ざかいを流れる所で、どの形にも入らない点（川の上）は、前の地区・町のつづきとする。海は河口の後だけ
    for j in range(1, len(runs) - 1):
        if runs[j]['kind'] == 'sea': runs[j] = dict(runs[j - 1], i=runs[j]['i'])
    if runs[-1]['kind'] == 'sea': runs.pop()
    # 短すぎる通過（境の線の上のゆれ）はまとめる
    clean = []
    for j, r in enumerate(runs):
        nxt = runs[j + 1]['i'] if j + 1 < len(runs) else len(pts)
        if nxt - r['i'] < 8 and 0 < j < len(runs) - 1: continue
        if clean and clean[-1]['id'] == r['id']: continue
        clean.append(r)
    for r in clean:
        if r['kind'] == 'town': r['pref'] = PREF[r['name']]
    # 支流（本流の点につながる、ほかの名前の川）
    onpath = {key(q) for q in line}
    tribs = {}
    for sg in segs:
        if sg['sys'] != sysid or sg['name'] in ('名称不明', '') : continue
        if any(sg is mine[i] for i in used): continue
        for q in (sg['pts'][0], sg['pts'][-1]):
            if key(q) in onpath:
                x, y = P(*q)
                if not VIEW.contains(Point(x, y)): continue
                k = min(range(len(pts)), key=lambda k: math.dist(pts[k], (x, y)))
                if sg['name'] == names[0] or k < 5: continue   # 本流と同じ名前のえだ・出発点のすぐそばは入れない
                if sg['name'] not in tribs or k > tribs[sg['name']]['i']:
                    tribs[sg['name']] = dict(name=sg['name'], i=k)
    # 支流の長さ（同じ水系・同じ名前の流路の合計）と形
    for t in tribs.values():
        gs = [sg['pts'] for sg in segs if sg['sys'] == sysid and sg['name'] == t['name'] and not any(sg is mine[i] for i in used)]
        t['km'] = round(sum(seglen(proj_pts(p)) for p in gs) / M['km'], 1)
        geo = unary_union([LineString(proj_pts(p)) for p in gs if len(p) > 1]).intersection(VIEW).simplify(0.5)
        ls = [geo] if geo.geom_type == 'LineString' else list(getattr(geo, 'geoms', []))
        t['d'] = ''.join('M' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in l.coords) for l in ls if l.length > 1)
    tl = sorted([t for t in tribs.values() if t['km'] >= 4 and t['name'] in TRIB_KANA], key=lambda t: -t['km'])[:4]
    for t in tl:
        fix = TRIB_AT.get((rid, t['name']))
        if fix and fix[0] == 'near':
            x, y = P(fix[1], fix[2])
            t['i'] = min(range(len(pts)), key=lambda k: math.dist(pts[k], (x, y)))
        elif fix and fix[0] == 'town':
            t['i'] = next(r['i'] for r in clean if r['name'] == fix[1])
    tl.sort(key=lambda t: t['i'])
    for t in tl: t['kana'] = TRIB_KANA.get(t['name'], '')
    for t in tl: t['name'] = TRIB_NAME.get(t['name'], t['name'])
    out.append(dict(id=rid, name=name, kana=kana, note=note,
                    km=round(g.length / M['km']), pts=[v for q in pts for v in q],
                    places=clean, tribs=tl))
    print(name, sysid, f'{g.length / M["km"]:.0f}km', len(pts), '→', ' → '.join(r['name'] for r in clean))
    print('   支流:', [(t['name'], t['km'], t['i']) for t in tl])

# 予想の旗を立てる海の候補（経度, 緯度）。river は、そこに出る川
SEAS = [
    ('gobo', '御坊市の海', 'ごぼうしのうみ', (135.150, 33.866)),
    ('minabe', 'みなべ町の海', 'みなべちょうのうみ', (135.316, 33.762)),
    ('tanabe', '田辺市の海（田辺湾）', 'たなべしのうみ（たなべわん）', (135.355, 33.727)),
    ('tonda', '白浜町の海（富田）', 'しらはまちょうのうみ（とんだ）', (135.370, 33.633)),
    ('hiki', '白浜町の海（日置）', 'しらはまちょうのうみ（ひき）', (135.423, 33.560)),
    ('susami', 'すさみ町の海', 'すさみちょうのうみ', (135.495, 33.540)),
    ('shingu', '新宮市の海', 'しんぐうしのうみ', (135.996, 33.712)),
]
ANSWER = {'haya': 'tanabe', 'aizu': 'tanabe', 'tonda': 'tonda', 'hiki': 'hiki', 'hidaka': 'gobo', 'kumano': 'shingu'}
for r in out: r['sea'] = ANSWER[r['id']]
seas = [dict(id=i, name=n, kana=k, x=round(P(*q)[0], 1), y=round(P(*q)[1], 1)) for i, n, k, q in SEAS]
# 答えになる海の旗は、川の河口の点におく（田辺湾は会津川の河口）
MOUTH_OF = {'tanabe': 'aizu', 'tonda': 'tonda', 'hiki': 'hiki', 'gobo': 'hidaka', 'shingu': 'kumano'}
for sea in seas:
    if sea['id'] in MOUTH_OF:
        r = next(r for r in out if r['id'] == MOUTH_OF[sea['id']])
        sea['x'], sea['y'] = r['pts'][-2], r['pts'][-1]

# 三重県（熊野川の東）。行政区域データがないので、熊野川の線と海岸のだいたいの形で作る（地図のはしの小さな部分だけ）。
# 和歌山県・奈良県の市町村の形を上にかさねるので、その下からのぞく所だけが三重県として見える
# 熊野川は、北山川が合流する所から河口までが県ざかい。そこから北は、まっすぐ上へのばす
kr = out[-1]
j0 = next(t['i'] for t in kr['tribs'] if t['name'] == '北山川')
border = [(kr['pts'][2 * j], kr['pts'][2 * j + 1]) for j in range(j0, len(kr['pts']) // 2)]
mie = [(border[0][0], -120)] + border + [P(136.0, 33.715), P(136.04, 33.76), P(136.12, 33.86), (1400, -120)]
mie_d = 'M' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in mie) + 'Z'

data = dict(rivers=out, seas=seas, mie=mie_d, view=[-330, -120, 1620, 1300],
            note='国土数値情報（河川 2009年、三重県は2008年）を加工。三重県の形は、熊野川と海岸のだいたいの形')
open(OUT, 'w', encoding='utf-8').write('// 「田辺市の川をたどろう」の川データ（国土数値情報 河川データを加工して作成）\n'
    '// 作り直しは tools/build-tanabe-rivers.py。地図の座標は tanabe-map-data.js と同じ\n'
    'const TANABE_RIVERS = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n')
print('written', OUT)
