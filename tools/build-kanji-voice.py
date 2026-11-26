#!/usr/bin/env python3
"""漢字ガンバ の 読み上げ音声を VOICEVOX（四国めたん）で作る。

つかいかた：VOICEVOX を起動してから  python3 tools/build-kanji-voice.py [--redo]
- --redo：ある ファイルも ぜんぶ 作り直す（声を かえたとき）。
- 読むことばを tools/kanji-voice-texts.js でひろい、
  japanese/kanji-ganba/voice/<番号>.m4a と japanese/kanji-ganba/voice.js を作る。
- もうあるファイルは作り直さない。作り直したいことばは、そのファイルを消してから実行する。
- 例文は、目あての ことばの 漢字を 読みに おきかえてから 読ませる（読みまちがいを ふせぐ）。
- 単元テストの問題文（kanji-ganba/test.js）も 作る。読みは tools/kanji_yomi_check.py で 自動で たしかめ、
  あやしい 文は 最後に 一覧で 出る（TEST_OVERRIDES に 手直しを 足す）。
- 作ったときの読み（カタカナ）は tools/kanji-voice-kana.tsv に のこる。読みのチェックに使う。
"""
import hashlib, json, os, re, subprocess, sys, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kanji_yomi_check import Checker

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

# 単元テストの文の 手直し表：こたえを 入れた 文（空白なし）→ 読ませる文
# （まぜ書きの ことばは 音声だけ 漢字で 書くと 正しく 読む：やさい・ふしぎ など）
TEST_OVERRIDES = {
    'はたけで野さいを作ります。': '畑で 野菜を 作ります。',
    '学きゅうい員になりました。': '学級委員に なりました。',
    'ほうちょうで野さいを切ります。': 'ほうちょうで 野菜を 切ります。',
    '書きじゅんに気をつけます。': 'かきじゅんに 気を つけます。',
    '大さかふに住んでいます。': '大阪府に 住んで います。',
    'さんかん日に家族が来ます。': '参観日に 家族が 来ます。',
    'それはふ思ぎな話です。': 'それは 不思議な 話です。',
    'はっ表を聞くたい度が良いです。': '発表を 聞く 態度が 良いです。',
    'こん虫にきょう味があります。': '昆虫に 興味が あります。',
    'お店でしょく場体験をします。': 'お店で 職場体験を します。',
    '地図のしゅくしゃくを確かめます。': '地図の 縮尺を 確かめます。',
    '一すんぼうしの話を読みます。': 'いっすんぼうしの 話を 読みます。',
    'せんたく物をほします。': '洗濯物を 干します。',
    '児童会の役員に立こうほします。': '児童会の 役員に 立候補します。',
    'せんしゅう雨がふりました。': '先週 雨が ふりました。',
}

TEST_DONE = {}  # 前に 作ったときの 読ませた文と メモ（tsv から）


def test_say(d):
    """テストの文を どう 読ませるか きめる。(読ませる文, メモ)"""
    k = key(d['pre'] + d['yomi'] + d['post'])
    if k in TEST_OVERRIDES: return TEST_OVERRIDES[k], 'テスト・手直し'
    # 助詞では ない「は」「へ」（はが・へびの など）は「わ」「え」と 読まれることが あるので、だめなら カタカナで
    fix = lambda t: re.sub(r'(?:^|(?<=[ 　、。]))[はへ][ぁ-ゖー]+', lambda m: kata(m.group()), t)
    y = kata(d['yomi']) if re.search('[はへ]', d['yomi']) else d['yomi']
    tgt = (len(d['pre']), len(d['kj']), d['yomi'])
    tries = []
    for f in (lambda t: t, fix):
        pre, post = f(d['pre']), f(d['post'])
        # 1. 漢字の まま（しぜんに 読める）。目あての 字が こたえの 読みに なっているか たしかめる
        tries.append((pre + d['kj'] + post, tgt, 'テスト'))
        # 2. 目あての 字を 読みがなに おきかえる（は・へ は カタカナで）
        tries.append((pre + y + post, None, 'テスト・かな'))
        tries.append((pre + kata(d['yomi']) + post, None, 'テスト・カタカナ'))
    bad = None
    for text, t, note in tries:
        r = CHECK.check(text, query(key(text))['kana'], t)
        if not r: return text, note
        if bad is None: bad = r
    return tries[1][0], 'あやしい：' + '・'.join(bad)


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
    global CHECK
    data = json.loads(subprocess.check_output(['node', os.path.join(ROOT, 'tools', 'kanji-voice-texts.js'), APP]))
    CHECK = Checker(data['rows'])
    os.makedirs(OUT, exist_ok=True)
    log = {}
    if os.path.exists(LOG):
        for line in open(LOG, encoding='utf-8'):
            p = line.rstrip('\n').split('\t')
            if len(p) >= 4:
                log[p[0]] = p
                if p[3].startswith(('テスト', 'あやしい')): TEST_DONE[p[0]] = (p[1], p[3])
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
    # 単元テストの問題文（こたえを 出したあとに 読む文）
    sus = []
    for d in data['tests']:
        text = d['pre'] + d['yomi'] + d['post']
        k = key(text)
        if k in table: continue
        if k in log and k in TEST_DONE and '--redo' not in sys.argv:
            say, note = TEST_DONE[k]
        else:
            say, note = test_say(d)
        if note.startswith('あやしい'): sus.append(f"{text}\t{say}\t{note}")
        put(text, say, lambda s=say: query(key(s)), note)
    for t in data['extra']:
        put(t, t, lambda t=t: query(key(t)), '')
    if sus:
        print('▼ 読みが あやしい テストの文（tools/kanji-voice-kana.tsv で たしかめて、TEST_OVERRIDES に 手直しを 足す）')
        for x in sus: print('  ' + x)
    with open(LOG, 'w', encoding='utf-8') as f:
        for k in table: f.write('\t'.join(log[k]) + '\n')
    with open(JS, 'w', encoding='utf-8') as f:
        f.write('// 漢字ガンバ の読み上げ音声（VOICEVOX:四国めたん）。ことば → voice/○○.m4a\n')
        f.write('// tools/build-kanji-voice.py で 作る。手で なおさない\n')
        f.write('const VOICE = ' + json.dumps(table, ensure_ascii=False, indent=0) + ';\n')
    print(f'{len(table)}こ（あたらしく {made}こ）')

main()
