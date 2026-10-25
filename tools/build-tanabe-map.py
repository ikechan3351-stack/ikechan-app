# 田辺市マップの地図データ（social/tanabe-map-data.js）を作るスクリプト
#
# 元データ：国土数値情報（https://nlftp.mlit.go.jp/ksj/）
#   N03-20240101_30（和歌山県 行政区域 2024年）→ dl/n24/
#   N03-001001_30  （和歌山県 行政区域 2000年＝合併前）→ dl/n00/
#   N03-20240101_29（奈良県 行政区域 2024年）→ dl/N03-20240101_29/
#   W05-09_30・W05-09_29（和歌山県・奈良県 河川）→ dl/W05_30/・dl/W05_29/
# 必要なもの：pip install shapely pyshp
# 使い方：python3 tools/build-tanabe-map.py <dl フォルダがある場所> social/tanabe-map-data.js
#
# 旧5市町村の形は、2000年の境界を今の田辺市の形で切り取ったもの。
import shapefile, json, math, sys
from shapely.geometry import shape, box, Point, MultiPolygon, Polygon, LineString, MultiLineString
from shapely.ops import unary_union, polylabel, linemerge
from shapely import affinity
S=sys.argv[1]; OUT=sys.argv[2]
def read(p,enc):
    r=shapefile.Reader(p,encoding=enc)
    return [(s.record, shape(s.shape.__geo_interface__)) for s in r.iterShapeRecords()]
n24=read(S+'/dl/n24/N03-20240101_30.shp','utf-8')
n24n=read(S+'/dl/N03-20240101_29/N03-20240101_29.shp','utf-8')
n00=read(S+'/dl/n00/N03-001001_30-g_AdministrativeBoundary.shp','cp932')
tan=unary_union([g for r,g in n24 if r[3]=='田辺市']).buffer(0)
minx,miny,maxx,maxy=tan.bounds
LAT0=(miny+maxy)/2; C=math.cos(math.radians(LAT0))
pad=0.03
X0=minx-pad; Y1=maxy+pad
K=1000/((maxx-minx+2*pad)*C)          # 1000 units across
def P(lon,lat): return ((lon-X0)*C*K,(Y1-lat)*K)
W=round((maxx-minx+2*pad)*C*K); H=round((maxy-miny+2*pad)*K)
KM=K/111.32  # units per km (approx)
def proj(g): return affinity.affine_transform(g,[C*K,0,0,-K,-X0*C*K,Y1*K])
def km2(g): return proj(g).area/KM/KM
def ring(cs):
    pts=[f"{x:.1f},{y:.1f}" for x,y in cs]
    out=[];prev=None
    for p in pts:
        if p!=prev: out.append(p)
        prev=p
    return "M"+" ".join(out[:-1] if out[0]==out[-1] else out)+"Z"
def dpoly(g,tol,minarea=0):
    g=proj(g).simplify(tol,preserve_topology=True)
    polys=[g] if isinstance(g,Polygon) else [p for p in getattr(g,'geoms',[]) if isinstance(p,Polygon)]
    s=""
    for p in polys:
        if p.area<minarea: continue
        s+=ring(p.exterior.coords)
        for i in p.interiors: s+=ring(i.coords)
    return s
def dline(g,tol):
    g=proj(g).simplify(tol)
    ls=[g] if isinstance(g,LineString) else list(getattr(g,'geoms',[]))
    s=""
    for l in ls:
        if not isinstance(l,LineString) or l.length<1: continue
        s+="M"+" ".join(f"{x:.1f},{y:.1f}" for x,y in l.coords)
    return s
def lab(g):
    g=proj(g)
    big=max(g.geoms,key=lambda p:p.area) if hasattr(g,'geoms') else g
    p=polylabel(big,0.5); return [round(p.x,1),round(p.y,1)]
AREAS=[('tanabe','旧田辺市','きゅうたなべし','田辺市','海に面した、市の中心。市役所や駅、お店が多い。'),
       ('ryujin','龍神村','りゅうじんむら','龍神村','いちばん北の山の中。日高川が流れ、龍神温泉がある。'),
       ('nakahechi','中辺路町','なかへちちょう','中辺路町','富田川ぞいの山の町。熊野古道（中辺路）が通る。'),
       ('oto','旧大塔村','きゅうおおとうむら','大塔村','日置川ぞいの山の村。百間山などの山や谷が多い。'),
       ('hongu','本宮町','ほんぐうちょう','本宮町','いちばん東。熊野本宮大社と、温泉がある熊野川ぞいの町。')]
areas=[]
for aid,name,kana,old,desc in AREAS:
    g=unary_union([gg for r,gg in n00 if r[3]==old]).buffer(0).intersection(tan)
    pg=proj(g); bx=[round(v,1) for v in pg.bounds]
    areas.append(dict(id=aid,name=name,kana=kana,desc=desc,km2=round(km2(g)),d=dpoly(g,0.25,0.5),lab=lab(g),box=bx))
    print(name, round(km2(g),1))
print('total',round(km2(tan),1))
# neighbors
ext=box(minx-0.25,miny-0.18,maxx+0.25,maxy+0.18)
nb=[]
for pref,src in (('和歌山県',n24),('奈良県',n24n),('三重県',[])):
    names={}
    for r,g in src:
        nm=r[3] or r[2]
        if nm in ('田辺市','所属未定地') or not nm: continue
        if g.intersects(ext): names.setdefault(nm,[]).append(g)
    for nm,gs in names.items():
        g=unary_union(gs).buffer(0).intersection(ext)
        if g.is_empty: continue
        lp=lab(g)
        nb.append(dict(name=nm,pref=pref,d=dpoly(g,0.8,2),lab=lp,touch=g.buffer(0.002).intersects(tan),km2=round(km2(g))))
print([ (n['name'],n['touch']) for n in nb])
# rivers
MAJOR={'日高川','日置川','富田川','熊野川','左会津川','右会津川','会津川','芳養川','大塔川','四村川','前ノ川','十津川','丹生ノ川','丹生川'}
rv={}
for p in (S+'/dl/W05_30/W05-09_30-g_Stream.shp',S+'/dl/W05_29/W05-09_29-g_Stream.shp'):
    for r,g in read(p,'cp932'):
        nm=r[3]
        if nm=='名称不明' or not nm: continue
        gi=g.intersection(ext)
        if gi.is_empty: continue
        rv.setdefault(nm,[]).append(gi)
rivers=[]
for nm,gs in rv.items():
    g=unary_union(gs)
    inT=g.intersection(tan).length*100 if g.intersects(tan) else 0
    lvl=1 if nm in MAJOR else (2 if inT>=5 else 0)
    if not lvl: continue
    gl=g.intersection(tan) if inT>1 else g   # 名前は田辺市の中の部分に書く
    m=linemerge(gl) if not isinstance(gl,LineString) else gl
    longest=max(m.geoms,key=lambda l:l.length) if hasattr(m,'geoms') else m
    pt=longest.interpolate(0.5,normalized=True)
    rivers.append(dict(name=nm,lv=lvl,d=dline(g,0.4),lab=[round(v,1) for v in P(pt.x,pt.y)]))
print(len(rivers),[r['name'] for r in rivers if r['lv']==1])
PL=[('田辺市役所','たなべしやくしょ','office',135.389191,33.729671),
    ('紀伊田辺駅','きいたなべえき','station',135.384085,33.733653),
    ('闘雞神社','とうけいじんじゃ','shrine',135.384326,33.729473),
    ('天神崎','てんじんざき','sight',135.354016,33.726296),
    ('龍神行政局','りゅうじんぎょうせいきょく','office2',135.484787,33.898338),
    ('龍神温泉','りゅうじんおんせん','onsen',135.562279,33.955776),
    ('護摩壇山','ごまだんざん','mount',135.567092,34.057382),
    ('中辺路行政局','なかへちぎょうせいきょく','office2',135.513794,33.788193),
    ('近露','ちかつゆ','sight',135.603424,33.827766),
    ('大塔行政局','おおとうぎょうせいきょく','office2',135.516617,33.730633),
    ('百間山','ひゃっけんざん','mount',135.631278,33.728035),
    ('本宮行政局','ほんぐうぎょうせいきょく','office2',135.770554,33.836956),
    ('熊野本宮大社','くまのほんぐうたいしゃ','shrine',135.7733,33.8404),
    ('湯の峰温泉','ゆのみねおんせん','onsen',135.753448,33.824535),
    ('川湯温泉','かわゆおんせん','onsen',135.775787,33.811611)]
places=[]
olds={a[0]:unary_union([gg for r,gg in n00 if r[3]==a[3]]).intersection(tan) for a in AREAS}
for nm,kana,kind,lon,lat in PL:
    a=[k for k,g in olds.items() if g.buffer(0.004).contains(Point(lon,lat))]
    x,y=P(lon,lat); places.append(dict(name=nm,kana=kana,kind=kind,x=round(x,1),y=round(y,1),area=a[0] if a else None))
    print(nm,a)
wk=unary_union([g for r,g in n24]).buffer(0); nr=unary_union([g for r,g in n24n]).buffer(0)
pl=wk.buffer(0.0005).intersection(nr.boundary).intersection(ext)
data=dict(proj=[round(X0,6),round(Y1,6),round(C*K,4),round(K,4)],prefLine=dline(pl,0.5),W=W,H=H,km=round(KM,3),outline=dpoly(tan,0.25,0.5),areas=areas,neighbors=nb,rivers=rivers,places=places,
          note='国土数値情報（行政区域 2000年・2024年、河川）を加工')
open(OUT,'w').write('// 田辺市マップの地図データ（国土数値情報 行政区域・河川データを加工して作成）\n// 田辺市マップ.html や、これから作る教材で共通に使う\nconst TANABE_MAP = '+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n')
print('W,H',W,H,'bytes',len(open(OUT).read()))
