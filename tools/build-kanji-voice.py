#!/usr/bin/env python3
"""漢字ガンバ の 読み上げ音声を VOICEVOX（四国めたん）で作る。

つかいかた：VOICEVOX を起動してから  python3 tools/build-kanji-voice.py [--redo]
- --redo：ある ファイルも ぜんぶ 作り直す（声を かえたとき）。
- 読むことばを tools/kanji-voice-texts.js でひろい、
  japanese/kanji-ganba/voice/<番号>.m4a と japanese/kanji-ganba/voice.js を作る。
- もうあるファイルは作り直さない。作り直したいことばは、そのファイルを消してから実行する。
- 例文は、目あての ことばの 漢字を 読みに おきかえてから 読ませる（読みまちがいを ふせぐ）。
- 作ったときの読み（カタカナ）は tools/kanji-voice-kana.tsv に のこる。読みのチェックに使う。
"""
import hashlib, json, os, re, subprocess, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'japanese', '漢字ガンバ.html')
OUT = os.path.join(ROOT, 'japanese', 'kanji-ganba', 'voice')
JS = os.path.join(ROOT, 'japanese', 'kanji-ganba', 'voice.js')
LOG = os.path.join(ROOT, 'tools', 'kanji-voice-kana.tsv')
API = 'http://127.0.0.1:50021'
SPEAKER = 2  # 四国めたん ノーマル（2026-11-23 ずんだもんから かえた）
SPEED = 0.95

def post(path, params, body=None):
    req = urllib.request.Request(API + path + '?' + urllib.parse.urlencode(params), data=body, method='POST',
                                 headers={'Content-Type': 'application/json'} if body else {})
    return urllib.request.urlopen(req).read()

def kata(s):
    return ''.join(chr(ord(c) + 0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)

def key(t):
    return ''.join(t.split())

KANJI = r'[㐀-鿿々]'
VOW = {}
for row in ['アカサタナハマヤラワガザダバパァャ', 'イキシチニヒミリギジヂビピィ', 'ウクスツヌフムユルグズヅブプゥュ', 'エケセテネヘメレゲゼデベペェ', 'オコソトノホモヨロヲゴゾドボポォョ']:
    for c in row: VOW[c] = row[0]
OK_PAIRS = {('ウ', 'オ'), ('イ', 'エ'), ('ヲ', 'オ'), ('ヂ', 'ジ'), ('ヅ', 'ズ'), ('ウ', 'ア')}

def plain(kana):
    return re.sub(r"[_'/、。！？!? ]", '', kana)

def expect(text):
    out = ''
    for c in kata(key(text)):
        if c == 'ー' and out: c = VOW.get(out[-1], 'ー')
        if c in '。、！？!?「」': continue
        out += c
    return out

def same(text, kana, particles=False):
    """読みが 字のとおりか（のばす音・を・ぢ・づ の ゆれは よい）"""
    e, g = expect(text), plain(kana)
    if len(e) != len(g): return False
    ok = OK_PAIRS | ({('ハ', 'ワ'), ('ヘ', 'エ')} if particles else set())
    for x, y in zip(e, g):
        if x == y: continue
        if (x, y) == ('ウ', 'ア'): return False  # つかう→つかー は だめ
        if (x, y) not in ok: return False
    return True

# 読みまちがいの 手直し表：例文 → 読ませる文（カタカナの ところは 字のとおりに 読む）
OVERRIDES = {
    'はこの 中を 見ます。': 'ハコの なかを 見ます。',
    'はこの 中に 何が あるのかな。': 'ハコの なかに なにが あるのかな。',
    '二年一組の みんなで しゃしんを とります。': 'にねん いちくみの みんなで しゃしんを とります。',
    '新潟県は 米づくりが さかんです。': 'にいがたけんは こめづくりが さかんです。',
    '米や 麦は 穀物です。': 'コメや むぎは こくもつです。',
    'まき場に 羊が います。': 'まきばに ひつじが います。',
    '険しい 山道を 登ります。': 'けわしい やまみちを のぼります。',
    '五・七・五で 句を 作ります。': 'ご、しち、ごで くを つくります。',
    'この 計画は 可能です。': 'この けいかくは、かのうです。',
    '脳は 体に 命令を 出します。': 'ノウは、からだに めいれいを だします。',
    '千円さつです。': 'センエンサツです。',
    '秋に なると はが 赤く なります。': 'あきに なると、ハが あかく なります。',
    '食べた 物は 胃に 入ります。': 'たべた ものは、イに はいります。',
}

def query(text):
    return json.loads(post('/audio_query', {'text': text, 'speaker': SPEAKER}))

def make(q, out):
    q['speedScale'] = SPEED
    tmp = out + '.wav'
    open(tmp, 'wb').write(post('/synthesis', {'speaker': SPEAKER}, json.dumps(q).encode()))
    subprocess.run(['afconvert', '-f', 'm4af', '-d', 'aac', '-b', '40000', tmp, out], check=True)
    os.remove(tmp)

def word_query(yomi):
    """ことば（かな）を読む。ひらがなで まちがえるときは カタカナで 字のとおりに"""
    y = key(yomi)
    if len(y) == 1:
        q = query(y)
        q['accent_phrases'] = json.loads(post('/accent_phrases', {'text': kata(y) + "'", 'speaker': SPEAKER, 'is_kana': 'true'}))
        return q, False
    q = query(y)
    if same(y, q['kana']): return q, False
    return query(kata(y)), True

def sentence(d, use_kata):
    """例文の 目あての ことばの 漢字を 読みに おきかえる"""
    w, y = list(d['word']), list(d['yomi'])
    ishira = lambda c: re.match(r'[ぁ-ゖー]', c)
    while w and y and ishira(w[-1]) and w[-1] == y[-1]: w.pop(); y.pop()
    okuri = d['word'][len(''.join(w)):]
    while w and y and ishira(w[0]) and w[0] == y[0]: w.pop(0); y.pop(0)
    kp, yp = ''.join(w), ''.join(y)
    if not kp: return d['ex'], False
    if use_kata or re.search('[はへ]', yp): yp = kata(yp)  # 「は」「へ」は「わ」「え」と読まれやすい
    after = '(?=' + re.escape(okuri[0]) + ')' if len(okuri) >= 2 else '(?=[ぁ-ゖ])' if okuri else ''
    pat = '(?<!' + KANJI + ')' + re.escape(kp) + '(?!' + KANJI + ')' + after
    if not re.search(pat, d['ex']): return d['ex'], False
    return re.sub(pat, yp, d['ex']), True

def main():
    try:
        urllib.request.urlopen(API + '/version', timeout=3)
    except Exception:
        sys.exit('VOICEVOX が起動していません。アプリを開いてから もう一度。')
    data = json.loads(subprocess.check_output(['node', os.path.join(ROOT, 'tools', 'kanji-voice-texts.js'), APP]))
    os.makedirs(OUT, exist_ok=True)
    log = {}
    if os.path.exists(LOG):
        for line in open(LOG, encoding='utf-8'):
            p = line.rstrip('\n').split('\t')
            if len(p) >= 4: log[p[0]] = p
    table, made = {}, 0

    def put(text, say, q_fn, note):
        nonlocal made
        k = key(text)
        if k in table: return
        fid = hashlib.md5(k.encode()).hexdigest()[:8]
        table[k] = fid
        path = os.path.join(OUT, fid + '.m4a')
        if os.path.exists(path) and k in log and log[k][1] == key(say) and '--redo' not in sys.argv:
            return
        q = q_fn()
        make(q, path)
        log[k] = [k, key(say), q.get('kana', ''), note]
        made += 1
        if made % 100 == 0: print(made, 'こ', flush=True)

    for d in data['rows']:
        wq = {}
        def wfn(d=d):
            q, kt = word_query(d['yomi']); wq['kata'] = kt; return q
        y = key(d['yomi'])
        say_w = kata(y) if (len(y) > 1 and not same(y, query(y)['kana'])) else y
        use_kata = say_w != y
        put(d['yomi'], say_w, wfn, 'カタカナ' if use_kata else '')
        say, hit = sentence(d, use_kata)
        if d['ex'] in OVERRIDES: say, hit = OVERRIDES[d['ex']], True
        if hit and not use_kata and not re.search(KANJI, say) and not same(say, query(key(say))['kana'], particles=True):
            say = sentence(d, True)[0]  # 文の中だと まちがえるときも カタカナに
        put(d['ex'], say, lambda s=say: query(key(s)), '' if hit else 'おきかえなし')
    for t in data['extra']:
        put(t, t, lambda t=t: query(key(t)), '')
    with open(LOG, 'w', encoding='utf-8') as f:
        for k in table: f.write('\t'.join(log[k]) + '\n')
    with open(JS, 'w', encoding='utf-8') as f:
        f.write('// 漢字ガンバ の読み上げ音声（VOICEVOX:四国めたん）。ことば → voice/○○.m4a\n')
        f.write('// tools/build-kanji-voice.py で 作る。手で なおさない\n')
        f.write('const VOICE = ' + json.dumps(table, ensure_ascii=False, indent=0) + ';\n')
    print(f'{len(table)}こ（あたらしく {made}こ）')

main()
