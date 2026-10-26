# 田辺市の地図記号データ（social/tanabe-symbols-data.js）を作るスクリプト
#
# 元データ：
#   国土数値情報（https://nlftp.mlit.go.jp/ksj/）の和歌山県（30）の点データ → <ksj>/ 以下に解凍
#     P29-21 学校／P30-13 郵便局／P04-20 医療機関／P18-12 警察署／P17-12 消防署／
#     P27-13 文化施設／P14-21 福祉施設／P34-14 市区町村役場
#   OpenStreetMap（© OpenStreetMap contributors, ODbL）の神社・寺・温泉・博物館 → <osm>/o1.json・o2.json
#     Overpass API で bbox 33.64,135.32,34.08,135.86 の
#     o1: amenity=place_of_worship ／ o2: natural=hot_spring・name~温泉$・man_made=lighthouse・tourism=museum・amenity=library
#     （灯台は田辺市の中に見つからなかったので入れていない）
# 必要なもの：pip install shapely pyshp pykakasi
# 使い方：python3 tools/build-tanabe-symbols.py <ksj> <osm> social/tanabe-map-data.js social/tanabe-symbols-data.js <確認リスト.md>
#
# 位置は social/tanabe-map-data.js（TANABE_MAP）と同じ計算で地図の座標にし、地区（areas）の形で地区を決める。
# ふりがなは pykakasi で付け、地名の読みは下の READ で直す。先生の確認用に、地区ごとのリスト（Markdown）も書き出す。
import shapefile, json, re, sys, math
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
import pykakasi
KSJ, OSM, MAPJS, OUT, LIST = sys.argv[1:6]

s = open(MAPJS).read()
M = json.loads(s[s.index('{'):s.rindex('}') + 1])
x0, y1, kx, ky = M['proj']
def P(lon, lat): return ((lon - x0) * kx, (y1 - lat) * ky)
def polys(d):
    out = []
    for part in d.split('M')[1:]:
        pts = [tuple(map(float, p.split(','))) for p in part.rstrip('Z').split()]
        if len(pts) >= 3: out.append(Polygon(pts).buffer(0))
    return unary_union(out)
AREA = [(a['id'], polys(a['d'])) for a in M['areas']]
def area_of(x, y):
    pt = Point(x, y)
    for aid, g in AREA:
        if g.contains(pt): return aid
    aid, g = min(AREA, key=lambda a: a[1].distance(pt))
    return aid if g.distance(pt) < 1.5 else None   # 形を簡単にしたぶんの、わずかなはみ出しだけ許す

# 地名の読み（pykakasi がまちがえやすいもの）。長いものから置きかえる
READ = {'田辺': 'たなべ', '上芳養': 'かみはや', '中芳養': 'なかはや', '芳養': 'はや', '稲成': 'いなり',
        '上秋津': 'かみあきづ', '秋津川': 'あきづがわ', '秋津': 'あきづ', '中三栖': 'なかみす', '三栖': 'みす',
        '長野': 'ながの', '新庄': 'しんじょう', '会津': 'あいづ', '大坊': 'だいぼう', '東部': 'とうぶ',
        '龍神': 'りゅうじん', '中山路': 'なかさんじ', '上山路': 'かみさんじ', '下山路': 'しもさんじ',
        '鮎川': 'あゆかわ', '近野': 'ちかの', '近露': 'ちかつゆ', '三里': 'みさと', '咲楽': 'さくら',
        '本宮': 'ほんぐう', '中辺路': 'なかへち', '栗栖川': 'くりすがわ', '東陽': 'とうよう', '明洋': 'めいよう',
        '高雄': 'たかお', '衣笠': 'きぬがさ', '大塔': 'おおとう', '南部': 'なんぶ', '神島台': 'かしまだい',
        '神島': 'かしま', '南紀': 'なんき', '江川': 'えがわ', '三川': 'みかわ', '万呂': 'まろ',
        '朝日ヶ丘': 'あさひがおか', '二川': 'ふたがわ', '平瀬': 'ひらせ', '湯の峰': 'ゆのみね', '湯峰': 'ゆのみね',
        '湯峯': 'ゆのみね', '皆地': 'みなち', '請川': 'うけがわ', '萩': 'はぎ', '湊': 'みなと', '目良': 'めら',
        '宮代': 'みやしろ', '甲斐ノ川': 'かいのかわ', '殿原': 'とのはら', '大熊': 'おおくま', '柳瀬': 'やなせ',
        '広井原': 'ひろいはら', '神子浜': 'みこのはま', '駅前': 'えきまえ', '大浜': 'おおはま', '合川': 'ごうかわ',
        '伏拝': 'ふしおがみ', '西': 'にし', '湯本': 'ゆもと', '福井': 'ふくい', '渡瀬': 'わたぜ', '川湯': 'かわゆ',
        '闘鶏': 'とうけい', '南方熊楠': 'みなかたくまぐす', '顕彰館': 'けんしょうかん', '熊野': 'くまの',
        '紀南': 'きなん', '南和歌山': 'みなみわかやま', '白百合': 'しらゆり', '龍トピア': 'りゅうトピア',
        '真寿苑': 'しんじゅえん', '鮎川園': 'あゆかわえん', '田辺の郷': 'たなべのさと', '玉置': 'たまき',
        '幹部': 'かんぶ', '熊野本宮園': 'くまのほんぐうえん', '北分署': 'きたぶんしょ', '出張所': 'しゅっちょうじょ', '世界遺産': 'せかいいさん'}
# 名前まるごとの読み（お寺・神社など、音読み・訓読みが決まらないもの）
NAME_READ = {'勝徳寺': 'しょうとくじ', '善徳寺': 'ぜんとくじ', '妙経寺': 'みょうきょうじ', '寳乗院': 'ほうじょういん',
             '梅龍寺': 'ばいりゅうじ', '西方寺': 'さいほうじ', '本正寺': 'ほんしょうじ', '祐川寺': 'ゆうせんじ',
             '猿神社': 'さるじんじゃ', '錦水神社': 'きんすいじんじゃ', '芳養大神社': 'はやだいじんじゃ',
             '西八王子宮': 'にしはちおうじぐう', '八立稲神社': 'やたていねじんじゃ'}
kks = pykakasi.kakasi()
def kana(name):
    if name in NAME_READ: return NAME_READ[name]
    t = name
    for k in sorted(READ, key=len, reverse=True): t = t.replace(k, READ[k])
    t = re.sub(r'寺$', 'じ', t) if re.search(r'[一-鿿]寺$', name) else t
    return ''.join(x['orig'] if re.fullmatch(r'[\u30a0-\u30ffー]+', x['orig']) else x['hira'] for x in kks.convert(t))   # カタカナはそのまま

items, seen = [], []
def add(kind, name, lon, lat, src):
    name = re.sub(r'\s+', '', name)
    x, y = P(lon, lat); a = area_of(x, y)
    if not a: return
    for it in seen:   # 同じものが2つ入っていたら1つに（同じ名前が近くに／ほぼ同じ場所）
        d = math.hypot(it[2] - x, it[3] - y)
        if it[0] == kind and ((it[1] == name and d < 3) or d < 0.3): return
    it = [kind, name, x, y, a, src]; seen.append(it); items.append(it)

def rd(p):
    r = shapefile.Reader(KSJ + '/' + p, encoding='cp932')
    return [(list(sr.record), sr.shape.points[0]) for sr in r.iterShapeRecords() if sr.shape.points]
K = '国土数値情報'
for r, (lon, lat) in rd('P29-21_30_GML/P29-21_30.shp'):
    if r[0] != '30206': continue
    kind = {16001: 'school', 16002: 'school', 16004: 'highschool'}.get(r[2])
    if kind: add(kind, r[3], lon, lat, K)
for r, (lon, lat) in rd('P30-13_30/P30-13_30/P30-13_30.shp'):
    if r[0] == '30206': add('post', r[4], lon, lat, K)
for r, (lon, lat) in rd('P04-20_30_GML/P04-20_30_GML/P04-20_30.shp'):
    if r[0] == 1 and r[2].startswith('田辺市'):
        nm = r[1].split('　')[-1].replace('独立行政法人国立病院機構', '')
        add('hospital', nm, lon, lat, K)
for r, (lon, lat) in rd('P18-12_30_GML/P18-12_30_PoliceStation.shp'):
    if r[1] != '30206': continue
    if r[2] == 2: add('police', r[0], lon, lat, K)
    elif r[2] in (4, 5): add('koban', r[0].replace('田辺警察署', ''), lon, lat, K)   # 駐在所も交番の記号
for r, (lon, lat) in rd('P17-12_30_GML/P17-12_30_FireStation.shp'):
    if r[1] == '30206' and r[2] in (2, 3):
        nm = re.sub(r'^田辺市.*?消防署', '', r[0]) if r[2] == 3 else r[0].replace('田辺市', '', 1)   # 出張所・分署は短く
        add('fire', nm, lon, lat, K)
for r, (lon, lat) in rd('P27-13_30/P27-13_30/P27-13_30.shp'):
    if r[0] != '30206': continue
    kind = {'03001': 'museum', '03002': 'museum', '03003': 'library'}.get(r[2])
    if kind: add(kind, r[4].replace('田辺市立美術館分館・', ''), lon, lat, K)
for r, (lon, lat) in rd('P14-21_30_GML/SHP/P14-21_30.shp'):
    if r[2] == '30206' and r[6] in ('991001', '020500') and r[7].startswith('特別養護老人ホーム'):
        add('elderly', r[7].replace('特別養護老人ホーム', ''), lon, lat, K)
for r, (lon, lat) in rd('P34-14_30_GML/P34-14_30.shp'):
    if r[0] != '30206': continue
    if r[1] == '1': add('city', r[2], lon, lat, K)
    elif r[2].endswith('行政局'): add('town', r[2], lon, lat, K)   # もとの町村役場。連絡所は入れない

O = 'OpenStreetMap'
SKIP = ('念法', '鳥居', '収蔵庫', 'お堂', '宝物殿', '教会', '地蔵尊', '大師', '庵', '薬師堂', '観音')
EN = {'Jizo-ji Temple': '地蔵寺', 'Yagami-jinja Shrine': '八上神社'}
for e in json.load(open(OSM + '/o1.json'))['elements']:
    t = e['tags']; c = e.get('center', e)
    full = EN.get(t.get('name', ''), t.get('name', ''))
    nm = full.split(' ')[0]   # 「檪原神社 いちはらじんじゃ」のような読みつきは名前だけに
    rel = t.get('religion')
    if not nm or any(w in full for w in SKIP) or re.search(r'[A-Za-z]', nm): continue
    if rel == 'shinto': add('shrine', nm, c['lon'], c['lat'], O)
    elif rel == 'buddhist': add('temple', nm, c['lon'], c['lat'], O)
# 温泉は温泉地ごとに1つ（湯の峰・川湯・渡瀬・龍神）。博物館は名前で選ぶ
ONSEN = {'龍神温泉', '湯の峰温泉', '川湯温泉', '渡瀬温泉'}
MUSEUM = {'南方熊楠顕彰館', '世界遺産熊野本宮館'}
onsen = {}
for e in json.load(open(OSM + '/o2.json'))['elements']:
    t = e['tags']; c = e.get('center', e); nm = t.get('name', '')
    if nm in ONSEN: onsen.setdefault(nm, []).append((c['lon'], c['lat']))
    elif nm in MUSEUM: add('museum', nm, c['lon'], c['lat'], O)
for nm, ps in onsen.items():   # 温泉地の中ほど（いくつかの点の平均）に1つ
    add('onsen', nm, sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps), O)

items.sort(key=lambda i: ([a['id'] for a in M['areas']].index(i[4]), i[0], i[1]))
rows = [[k, n, kana(n), round(x, 1), round(y, 1), a, 1 if src == O else 0] for k, n, x, y, a, src in items]
data = dict(note='国土数値情報（学校・郵便局・医療機関・警察署・消防署・文化施設・福祉施設・市区町村役場）と OpenStreetMap（神社・寺・温泉・博物館の一部）を加工',
            cols=['kind', 'name', 'kana', 'x', 'y', 'area', 'osm'], items=rows)
open(OUT, 'w').write('// 田辺市の地図記号データ（tools/build-tanabe-symbols.py で作成）\n'
                     '// 位置は TANABE_MAP（tanabe-map-data.js）と同じ座標。osm=1 は © OpenStreetMap contributors のデータ\n'
                     'const TANABE_SYMBOLS = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n')

JA = dict(school='小・中学校', highschool='高等学校', city='市役所', town='町・村役場（行政局）', post='郵便局', koban='交番（駐在所）',
          police='警察署', fire='消防署', hospital='病院', shrine='神社', temple='寺', library='図書館', museum='博物館・美術館',
          onsen='温泉', elderly='老人ホーム')
L = ['# 田辺市で地図記号さがし：記号データの確認リスト', '',
     '地区ごと・記号ごとの一覧です。閉校・移転・抜け、ふりがなのまちがいがあれば教えてください。（＊は OpenStreetMap から）', '']
for a in M['areas']:
    sub = [r for r in rows if r[5] == a['id']]
    L += [f"## {a['name']}（{len(sub)}）", '']
    for k in JA:
        ks = [r for r in sub if r[0] == k]
        if ks: L.append(f"- **{JA[k]}**（{len(ks)}）：" + '、'.join(f"{r[1]}（{r[2]}）" + ('＊' if r[6] else '') for r in ks))
    L.append('')
open(LIST, 'w').write('\n'.join(L))
from collections import Counter
print(len(rows), Counter(r[0] for r in rows), Counter(r[5] for r in rows), 'bytes', len(open(OUT).read()))
