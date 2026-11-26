"""VOICEVOX が 文を 正しく 読んだかを たしかめる（build-kanji-voice.py が使う）。

文の ひらがな・カタカナの ところは 字のとおり、漢字の ところは
漢字ガンバの 音読み・訓読み・ことばの 読みの 組み合わせで 読めているかを 見る。
読めていない（知らない読みをした）漢字が あれば その文を「あやしい」として かえす。
"""
import re

KANJI = r'[㐀-鿿々〆]'
VOICED = dict(zip('カキクケコサシスセソタチツテトハヒフヘホ', 'ガギグゲゴザジズゼゾダヂヅデドバビブベボ'))
HALF = dict(zip('ハヒフヘホ', 'パピプペポ'))
VOW = {}
for row in ['アカサタナハマヤラワガザダバパァャ', 'イキシチニヒミリギジヂビピィ', 'ウクスツヌフムユルグズヅブプゥュ',
            'エケセテネヘメレゲゼデベペェ', 'オコソトノホモヨロヲゴゾドボポォョ']:
    for c in row: VOW[c] = row[0]
# 字 → VOICEVOX が つかう 字（のばす音の 書き方の ゆれ）
LOOSE = {'イ': 'イエ', 'ウ': 'ウオ', 'ヲ': 'ヲオ', 'ヂ': 'ヂジ', 'ヅ': 'ヅズ', 'ー': 'アイウエオー'}


def kata(s):
    return ''.join(chr(ord(c) + 0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)


def plain(kana):
    return re.sub(r"[_'/、。！？!? ]", '', kana)


def same(a, b):
    """よみ a（ふつうの 書き方）と VOICEVOX の よみ b が 同じか"""
    if len(a) != len(b): return False
    return all(x == y or y in LOOSE.get(x, '') for x, y in zip(a, b))


# 字の 読みを くみあわせても 出てこない 読み（熟字訓・人や 地名など）
SPECIAL = {
    '一人': 'ヒトリ', '二人': 'フタリ', '今日': 'キョウ', '明日': 'アシタ・アス', '昨日': 'キノウ', '大人': 'オトナ',
    '今年': 'コトシ', '今朝': 'ケサ', '上手': 'ジョウズ', '下手': 'ヘタ', '日本': 'ニホン・ニッポン', '一日': 'ツイタチ',
    '二日': 'フツカ', '三日': 'ミッカ', '四日': 'ヨッカ', '五日': 'イツカ', '六日': 'ムイカ', '七日': 'ナノカ', '八日': 'ヨウカ',
    '九日': 'ココノカ', '十日': 'トオカ', '二十日': 'ハツカ', '時計': 'トケイ', '眼鏡': 'メガネ', '景色': 'ケシキ',
    '父': 'トウ', '母': 'カア', '兄': 'ニイ', '姉': 'ネエ', '真っ赤': 'マッカ', '真っ青': 'マッサオ', '果物': 'クダモノ',
    '友達': 'トモダチ', '博士': 'ハカセ', '部屋': 'ヘヤ', '生地': 'キジ', '奈良': 'ナラ', '家康': 'イエヤス', '清水': 'シミズ',
    '来': 'キ・コ・ク', '何': 'ナン・ナニ', '今': 'イマ・コン', '行': 'イ・ユ・オコナ', '下': 'クダ・サ', '上': 'ノボ・ア',
    '迷子': 'マイゴ', '八百屋': 'ヤオヤ', '河原': 'カワラ', '川原': 'カワラ', '一つ': 'ヒトツ', '息子': 'ムスコ', '土産': 'ミヤゲ',
    '七夕': 'タナバタ', '若人': 'ワコウド', '大和': 'ヤマト', '風邪': 'カゼ', '相撲': 'スモウ', '梅雨': 'ツユ', '雪崩': 'ナダレ',
    '竹刀': 'シナイ', '素人': 'シロウト', '玄人': 'クロウト', '木綿': 'モメン', '紅葉': 'モミジ・コウヨウ', '仮名': 'カナ',
    '王様': 'オウサマ', '気持': 'キモ', '場所': 'バショ', '毎朝': 'マイアサ', '生日': 'ジョウビ', '場面': 'バメン', '味方': 'ミカタ', '家族': 'カゾク', '理科': 'リカ',
    '茨城': 'イバラキ', '栃木': 'トチギ', '埼玉': 'サイタマ', '岡山': 'オカヤマ', '香川': 'カガワ', '東京': 'トウキョウ',
    '切手': 'キッテ', '一度': 'イチド', '手伝': 'テツダ', '試合': 'シアイ', '毎月': 'マイツキ', '金曜日': 'キンヨウビ',
    '記念日': 'キネンビ', '五月': 'ゴガツ', '十円玉': 'ジュウエンダマ', '行列': 'ギョウレツ', '児童会': 'ジドウカイ',
    '役員': 'ヤクイン', '電車': 'デンシャ', '問': 'トイ・モン', '実': 'ジツ・ジッ・ミ', '先生': 'センセイ',
    '神奈川': 'カナガワ', '大阪': 'オオサカ', '岐阜': 'ギフ', '茨城': 'イバラキ', '栃木': 'トチギ', '愛媛': 'エヒメ',
    '鹿児島': 'カゴシマ', '沖縄': 'オキナワ', '宮城': 'ミヤギ', '富山': 'トヤマ', '新潟': 'ニイガタ', '大分': 'オオイタ',
}
SOKUON = {'ジュウ': ('ジュッ', 'ジッ'), 'イチ': ('イッ',), 'ハチ': ('ハッ',)}


def variants(r, first, last):
    """ことばの 中での 読みの かわり方（にごる・つまる）"""
    out = {r}
    if r[0] in VOICED:
        out.add(VOICED[r[0]] + r[1:])
        if r[0] in HALF: out.add(HALF[r[0]] + r[1:])
    if not last and r[-1] in 'ツチクキ' and len(r) >= 2:
        out |= {v[:-1] + 'ッ' for v in list(out)}
    if r in SOKUON: out |= set(SOKUON[r])
    return out


class Checker:
    def __init__(self, rows):
        self.char = {}   # 漢字1字 → 読み（カタカナ）
        self.word = {}   # 漢字の ならび → 読み（ことば）
        self.kind = {}   # (字, 読み) → 'on'（音読み）か 'kun'（訓読み）
        for d in rows:
            rs = self.char.setdefault(d['k'], set())
            for kind, field in (('on', d.get('on', '')), ('kun', d.get('kun', ''))):
                for part in re.split('[・、]', field):
                    m = re.match(r'^([^()（）]*)[(（]([^)）]*)', part)
                    got = []
                    if m and m.group(2).startswith('っ'): got.append(kata(m.group(1) + 'っ'))
                    part = re.sub(r'\(.*?\)|（.*?）|[—\-\s]', '', part)
                    if part: got.append(kata(part))
                    for r in got:
                        rs.add(r)
                        old = self.kind.get((d['k'], r))
                        self.kind[(d['k'], r)] = kind if old in (None, kind) else 'both'
            self.add_word(d['word'], d['yomi'])
        for w, y in SPECIAL.items():
            for r in y.split('・'):
                if len(w) == 1: self.char.setdefault(w, set()).add(r)
                else: self.word.setdefault(w, set()).add(r)

    def add_word(self, word, yomi):
        """「漢字＋おくりがな」の ことばから 漢字の ところの 読みを おぼえる"""
        w, y = list(word), list(kata(''.join(yomi.split())))
        w = [kata(c) for c in w]
        while w and y and not re.match(KANJI, w[-1]) and w[-1] == y[-1]: w.pop(); y.pop()
        while w and y and not re.match(KANJI, w[0]) and w[0] == y[0]: w.pop(0); y.pop(0)
        kp = ''.join(w)
        if kp and re.fullmatch(KANJI + '+', kp):
            self.word.setdefault(kp, set()).add(''.join(y))

    def run_ok(self, units, got):
        """漢字の ならび units（[(字, 読みの集合 or None)]）を got と 読めるか"""
        n = len(units)
        memo = {}

        def go(i, pos, mode=None):
            # mode：それまでの 1字ずつの 読みが 音読みか 訓読みか（ことばの 中で まぜない）
            if i == n: return pos == len(got)
            if (i, pos, mode) in memo: return memo[(i, pos, mode)]
            res = False
            cands = []
            fixed = units[i][1]
            if fixed is not None:
                cands.append((1, fixed))
            else:
                cands.append((1, self.char.get(units[i][0], set())))
                # 2字いじょうの ことば（目あての 字を ふくまないもの）
                for j in range(i + 2, n + 1):
                    if any(u[1] is not None for u in units[i:j]): break
                    ws = self.word.get(''.join(u[0] for u in units[i:j]))
                    if ws: cands.append((j - i, ws))
            # 目あての 字を ふくむ ことば（茨城 など）：ことばの 読みに こたえの 読みが 入っていれば よい
            for j in range(i + 2, n + 1):
                us = units[i:j]
                fx = [u[1] for u in us if u[1] is not None]
                if not fx: continue
                ws = self.word.get(''.join(u[0] for u in us))
                if ws:
                    ws = {w for w in ws if all(any(f in w for f in fs) for fs in fx)}
                    if ws: cands.append((j - i, ws))
            for ci, (step, rs) in enumerate(cands):
                for r in rs:
                    m2 = mode
                    if ci == 0 and fixed is None:
                        k = self.kind.get((units[i][0], r), 'both')
                        if k != 'both':
                            if mode and mode != k: continue
                            m2 = k
                    for v in variants(r, i == 0, i + step == n):
                        seg = got[pos:pos + len(v)]
                        if same(v, seg) and go(i + step, pos + len(v), m2):
                            res = True; break
                    if res: break
                if res: break
            memo[(i, pos, mode)] = res
            return res

        return go(0, 0)

    def check(self, text, kana, target=None):
        """text を VOICEVOX が kana と 読んだ。あやしい ところの リストを かえす（なければ []）。
        target=(はじまりの位置, 字数, よみ)：その 漢字は かならず この よみ で 読む"""
        got = plain(kana)
        # 文を ひらがなの ところと 漢字の ところに 分ける
        toks = []  # ('k', [(字, 読み)]) か ('h', 字, 助詞の は・へ か)
        chars = list(text)
        i = 0
        while i < len(chars):
            c = chars[i]
            if target and i == target[0]:
                unit = (text[i:i + target[1]], {kata(target[2])})
                if toks and toks[-1][0] == 'k': toks[-1][1].append(unit)
                else: toks.append(('k', [unit]))
                i += target[1]; continue
            if re.match(KANJI, c):
                if toks and toks[-1][0] == 'k': toks[-1][1].append((c, None))
                else: toks.append(('k', [(c, None)]))
            elif not re.match('[ぁ-ゖァ-ヺー]', c):
                if toks and toks[-1][0] == 'k': toks.append(('s',))  # 空白・記号で 漢字の まとまりを 切る
            elif True:
                nxt = chars[i + 1] if i + 1 < len(chars) else ' '
                toks.append(('h', kata(c), c in 'はへ' and (nxt in ' 　、。！？!?' or c + nxt == 'への')))
            i += 1
        runs = [t[1] for t in toks if t[0] == 'k']
        memo = {}
        # 漢字の よみの 長さが いろいろ あるので、合う わけ方を さがす
        def solve(ti, pos):
            if ti == len(toks): return pos == len(got)
            if (ti, pos) in memo: return memo[(ti, pos)]
            memo[(ti, pos)] = r = solve2(ti, pos)
            return r

        def solve2(ti, pos):
            t = toks[ti]
            if t[0] == 's': return solve(ti + 1, pos)
            if t[0] == 'h':
                c = t[1]
                opts = c + LOOSE.get(c, '') + (('ワ' if c == 'ハ' else 'エ') if t[2] else '')
                return pos < len(got) and got[pos] in opts and solve(ti + 1, pos + 1)
            for end in range(pos + 1, len(got) + 1):
                if self.run_ok(t[1], got[pos:end]) and solve(ti + 1, end): return True
            return False

        if solve(0, 0): return []
        return [''.join(u[0] for u in r) for r in runs] or ['かな']

