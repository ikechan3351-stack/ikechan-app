#!/usr/bin/env python3
"""なぞって えを けそう（ひらがな なぞりっこ）で、なぞっている あいだ 3びょうごとに 鳴らす
「あひるの、あ」の声を VOICEVOX（ずんだもん）で作る。

つかいかた：VOICEVOX を起動してから  python3 tools/build-hiragana-phrase-voice.py
- pics.js の 字と 絵の ことば（1字に3つ）から「ことばの、字」を作る。
  は→ワ・へ→エ と 読まれないよう、ぜんぶ カタカナにして 渡す（カタカナは 字のとおりに 読む）。
- 小さい字は「らっぱの、ちいさい つ」、ー は「カレーの、のばす ぼう」、を は「くつを はく、を」。
- japanese/hiragana/voice-phrase/<番号>.m4a と voice-phrase.js（「字|ことば」→ 番号）を作る。
- もうある ファイルは 作り直さない。読みは tools/hiragana-phrase-voice.tsv で たしかめられる。
"""
import hashlib, json, os, re, subprocess, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PICS = os.path.join(ROOT, 'japanese', 'hiragana', 'pics.js')
OUT = os.path.join(ROOT, 'japanese', 'hiragana', 'voice-phrase')
JS = os.path.join(ROOT, 'japanese', 'hiragana', 'voice-phrase.js')
TSV = os.path.join(ROOT, 'tools', 'hiragana-phrase-voice.tsv')
API = 'http://127.0.0.1:50021'
SPEAKER = 3  # ずんだもん ノーマル
SPEED = 0.9
SMALL = 'っゃゅょッャュョ'

def post(path, params, body=None):
    req = urllib.request.Request(API + path + '?' + urllib.parse.urlencode(params), data=body, method='POST',
                                 headers={'Content-Type': 'application/json'} if body else {})
    return urllib.request.urlopen(req).read()

def kata(s):
    return ''.join(chr(ord(c) + 0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)

def name(k):
    if k == 'ー': return 'のばす ぼう'
    if k in SMALL: return 'ちいさい ' + chr(ord(k) + 1)
    return {'を': 'お', 'ヲ': 'オ', 'ぢ': 'じ', 'ヂ': 'ジ', 'づ': 'ず', 'ヅ': 'ズ'}.get(k, k)

def phrase(k, w):
    if k in 'をヲ':
        return w + '、' + name(k)
    return w + 'の、' + name(k)

def make(text, out):
    q = json.loads(post('/audio_query', {'text': kata(text).replace(' ', '、'), 'speaker': SPEAKER}))
    q['speedScale'] = SPEED
    q['prePhonemeLength'] = 0.05
    wav = post('/synthesis', {'speaker': SPEAKER}, json.dumps(q).encode())
    tmp = out + '.wav'
    open(tmp, 'wb').write(wav)
    subprocess.run(['afconvert', '-f', 'm4af', '-d', 'aac', '-b', '40000', tmp, out], check=True)
    os.remove(tmp)
    return q.get('kana', '')

def main():
    try:
        urllib.request.urlopen(API + '/version', timeout=3)
    except Exception:
        sys.exit('VOICEVOX が起動していません。アプリを開いてから もう一度。')
    pics = re.findall(r'^\s*"(.)":\s*(\[.*?\])', open(PICS, encoding='utf-8').read(), re.M)
    os.makedirs(OUT, exist_ok=True)
    table, rows, made = {}, [], 0
    for k, arr in pics:
        for w in json.loads(arr):
            t = phrase(k, w)
            fid = hashlib.md5(t.encode()).hexdigest()[:8]
            table[k + '|' + w] = fid
            path = os.path.join(OUT, fid + '.m4a')
            if not os.path.exists(path):
                rows.append(f'{k}\t{w}\t{t}\t{make(t, path)}'); made += 1
    with open(JS, 'w', encoding='utf-8') as f:
        f.write('// なぞって えを けそう：なぞっている あいだの「あひるの、あ」（VOICEVOX:ずんだもん）。「字|ことば」→ voice-phrase/○○.m4a\n')
        f.write('// tools/build-hiragana-phrase-voice.py で 作る。手で なおさない\n')
        f.write('const VOICE_PHRASE = ' + json.dumps(table, ensure_ascii=False, indent=0) + ';\n')
    if rows:
        with open(TSV, 'a', encoding='utf-8') as f:
            f.write('\n'.join(rows) + '\n')
    print(f'{len(table)}こ（あたらしく {made}こ）')

main()
