#!/usr/bin/env python3
"""九九・ことわざカルタ・証明パズル の 読み上げ音声を VOICEVOX で まとめて 作る。

つかいかた（VOICEVOX を 起動してから）:
    python3 tools/build-voice.py           … 3つ ぜんぶ
    python3 tools/build-voice.py kuku      … 九九（九九で あそぼう・九九マスター の きょうよう）だけ
    python3 tools/build-voice.py kotowaza  … ことわざカルタ だけ
    python3 tools/build-voice.py shomei    … 証明パズル だけ

- アプリの HTML から 読む文を ひろい、<フォルダ>/voice/<番号>.m4a と <フォルダ>/voice.js を 作る。
- もうある ファイルは 作り直さない（文を 足したときは、足した分だけ 作られる）。
- VOICEVOX の 読み（カナ）は <フォルダ>/読み方チェック.tsv に 出る。読みまちがいは OVERRIDES に 足す。
- アプリでは、文の すきま・「、」「。」「!」を とった 形で さがす（voice.js の キー）。
"""
import hashlib, json, os, re, subprocess, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = 'http://127.0.0.1:50021'
ZUNDA, METAN = 3, 2  # ずんだもん ノーマル ／ 四国めたん ノーマル

# 読みまちがいの 手直し：アプリの 文 → VOICEVOX に わたす 文（カタカナに すると 字のとおりに 読む）
OVERRIDES = {}
# 文の 一部を 置きかえる 手直し（アプリごと）。読み方チェック.tsv を 見て 足す
FIX = {
    'kotowaza': [('急がば', 'イソガバ'), ('一兎', 'イット'), ('百聞', 'ヒャクモン'), ('我を', 'ワレを')],
    'shomei': [('辺', 'ヘン'), ('その間の', 'そのあいだの'), ('底角', 'テイカク'),
               ('①、②、③より、', 'まるいち、まるに、まるさんより、')],
}

def node(js):
    return json.loads(subprocess.check_output(['node', '-e', js], cwd=ROOT))

def kata(s):
    return ''.join(chr(ord(c) + 0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)

def key(t):
    return re.sub(r'[\s、。!！]', '', t)

# ---------- アプリごとの 文の ひろい方 ----------
def kuku_texts():
    """九九の となえ方（ひらがな）。「は」を「わ」と 読まないよう、カタカナに して わたす"""
    js = r'''
const fs=require('fs');const h=fs.readFileSync('math/九九で あそぼう.html','utf8');
const a=h.indexOf('const YOMI = {'),b=h.indexOf('};',a)+2;eval(h.slice(a,b).replace('const ','var '));
const T=[];for(let d=1;d<=9;d++)YOMI[d].forEach(y=>{T.push(y);T.push(y.slice(0,y.lastIndexOf(' ')));});
for(let n=1;n<=9;n++){T.push(n+'のだん');T.push('かけるかず '+n);}
T.push('すごい!パーフェクト!');console.log(JSON.stringify(T));'''
    out = []
    for t in node(js):
        if re.fullmatch(r'[ぁ-ゖ ー]+', t):
            out.append((t, kata(t)))
        else:
            out.append((t, t))
    return out

def kotowaza_texts():
    js = r'''
const fs=require('fs');const h=fs.readFileSync('japanese/ことわざカルタ.html','utf8');
const a=h.indexOf('const ITEMS = ['),b=h.indexOf('}));',a)+4;eval(h.slice(a,b).replace('const ','var '));
const T=[];ITEMS.forEach(({w,m})=>{T.push(m);T.push(w+'。'+m);});console.log(JSON.stringify(T));'''
    return [(t, t) for t in node(js)]

def shomei_yomi(t):
    """証明パズル の yomi() と おなじ 置きかえ（記号 → ことば）"""
    t = t.replace('△', '三角形').replace('∠', '角').replace('≡', '、合同、').replace('＝', ' イコール ').replace('∥', ' 平行 ')
    t = t.replace('°', '度').replace('−', ' ひく ').replace('（仮定）', '、仮定').replace('（共通）', '、共通')
    return re.sub(r'([A-F])', r' \1 ', t)

def shomei_texts():
    """読み上げを 部品に わけて 作る：仮定は〜。／カードの 文／①、②、③より、／…①／よって〜が証明できた。"""
    js = r'''
const fs=require('fs');const h=fs.readFileSync('math/証明パズル.html','utf8');var location={search:'',hash:''},window={},document={querySelector:()=>null,getElementById:()=>null},localStorage={getItem:()=>null};
const a=h.lastIndexOf('<script>',h.indexOf('const PROBS = ['))+8,b=h.indexOf('\n];',h.indexOf('const PROBS = ['))+3;
eval(h.slice(a,b).replace("'use strict';",'').replace(/^(const|let) /gm,'var '));
const T=['①、②、③より、','…①','…②','…③'];
PROBS.forEach(p=>{T.push('仮定は、'+p.hyp.join('、')+'。');T.push('よって、'+p.goal.join('、')+' が証明できた。');
  p.cards.forEach(c=>T.push(c.t));});
console.log(JSON.stringify([...new Set(T)]));'''
    out = []
    for t in node(js):
        say = {'…①': 'まるいち', '…②': 'まるに', '…③': 'まるさん'}.get(t, shomei_yomi(t))
        out.append((t, say))
    return out

APPS = {
    'kuku':     dict(dir='math/kuku-voice',      var='KUKU_VOICE',     speaker=ZUNDA, name='ずんだもん', speed=0.95, texts=kuku_texts,
                     note='九九で あそぼう・九九マスター'),
    'kotowaza': dict(dir='japanese/kotowaza-voice', var='KOTOWAZA_VOICE', speaker=METAN, name='四国めたん', speed=1.0, texts=kotowaza_texts,
                     note='ことわざカルタ'),
    'shomei':   dict(dir='math/shomei-voice',    var='SHOMEI_VOICE',   speaker=METAN, name='四国めたん', speed=1.0, texts=shomei_texts,
                     note='証明パズル'),
}

def post(path, params, body=None):
    req = urllib.request.Request(API + path + '?' + urllib.parse.urlencode(params), data=body, method='POST',
                                 headers={'Content-Type': 'application/json'} if body else {})
    return urllib.request.urlopen(req).read()

def make(text, speaker, speed, out):
    q = json.loads(post('/audio_query', {'text': text, 'speaker': speaker}))
    q['speedScale'] = speed
    wav = post('/synthesis', {'speaker': speaker}, json.dumps(q).encode())
    tmp = out + '.wav'
    open(tmp, 'wb').write(wav)
    subprocess.run(['afconvert', '-f', 'm4af', '-d', 'aac', '-b', '40000', tmp, out], check=True)
    os.remove(tmp)
    return q.get('kana', '')

def build(name):
    cfg = APPS[name]
    base = os.path.join(ROOT, cfg['dir'])
    vdir = os.path.join(base, 'voice')
    os.makedirs(vdir, exist_ok=True)
    tsv_path = os.path.join(base, '読み方チェック.tsv')
    old = {}
    if os.path.exists(tsv_path):
        for line in open(tsv_path, encoding='utf-8').read().splitlines()[1:]:
            p = line.split('\t')
            if len(p) == 4: old[p[0]] = p[3]
    table, rows, made = {}, [], 0
    for text, say in cfg['texts']():
        say = OVERRIDES.get(text, say)
        for a, b in FIX.get(name, []):
            say = say.replace(a, b)
        k = key(text)
        if k in table: continue
        fid = hashlib.md5((str(cfg['speaker']) + '|' + say).encode()).hexdigest()[:8]
        table[k] = fid
        path = os.path.join(vdir, fid + '.m4a')
        if os.path.exists(path) and fid in old:
            kana = old[fid]
        else:
            kana = make(say, cfg['speaker'], cfg['speed'], path); made += 1
            print(text, '→', kana)
        rows.append(f'{fid}\t{text}\t{say}\t{kana}')
    # 使わなくなった ファイルを かたづける
    used = set(table.values())
    for f in os.listdir(vdir):
        if f.endswith('.m4a') and f[:-4] not in used:
            os.remove(os.path.join(vdir, f))
    with open(os.path.join(base, 'voice.js'), 'w', encoding='utf-8') as f:
        f.write(f"// {cfg['note']} の 読み上げ音声（VOICEVOX:{cfg['name']}）。文（すきま・、。! を とった形）→ voice/○○.m4a\n")
        f.write('// tools/build-voice.py で 作る。手で なおさない\n')
        f.write(f"var {cfg['var']} = " + json.dumps(table, ensure_ascii=False, indent=0) + ';\n')
    with open(tsv_path, 'w', encoding='utf-8') as f:
        f.write('番号\tアプリの文\tVOICEVOX に わたした文\tVOICEVOX の 読み（カナ）\n' + '\n'.join(rows) + '\n')
    print(f"{cfg['note']}：{len(table)}こ（あたらしく {made}こ）")

def main():
    try:
        urllib.request.urlopen(API + '/version', timeout=3)
    except Exception:
        sys.exit('VOICEVOX が 起動していません。アプリを 開いてから もう一度。')
    names = sys.argv[1:] or list(APPS)
    for n in names:
        if n not in APPS: sys.exit(f'{n} は ありません。えらべるのは {", ".join(APPS)}')
        build(n)

main()
