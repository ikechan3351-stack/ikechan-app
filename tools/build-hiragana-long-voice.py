#!/usr/bin/env python3
"""なぞって えを けそう（ひらがな なぞりっこ）で、なぞっている あいだに 鳴らす「のばした声」を作る。

つかいかた：VOICEVOX を起動してから  python3 tools/build-hiragana-long-voice.py [のばす秒数]
- 絵のある字（pics.js）の 音を、母音を のばして（あ → あーー）ずんだもんで作る。
  カタカナは 同じ音の ひらがなの 声を つかう。っ・ッ・ー は のばせないので 作らない。
- japanese/hiragana/voice-long/<字の番号>.m4a と japanese/hiragana/voice-long.js を作る。
- 秒数を かえたときは voice-long フォルダを けしてから 実行する（ある分は 作り直さない）。
"""
import hashlib, json, os, re, subprocess, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PICS = os.path.join(ROOT, 'japanese', 'hiragana', 'pics.js')
OUT = os.path.join(ROOT, 'japanese', 'hiragana', 'voice-long')
JS = os.path.join(ROOT, 'japanese', 'hiragana', 'voice-long.js')
API = 'http://127.0.0.1:50021'
SPEAKER = 3  # ずんだもん ノーマル
LONG = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0  # 母音を のばす 秒数

def post(path, params, body=None):
    req = urllib.request.Request(API + path + '?' + urllib.parse.urlencode(params), data=body, method='POST',
                                 headers={'Content-Type': 'application/json'} if body else {})
    return urllib.request.urlopen(req).read()

def hira(c):
    return chr(ord(c) - 0x60) if 'ァ' <= c <= 'ヶ' else c

def kata(c):
    return chr(ord(c) + 0x60) if 'ぁ' <= c <= 'ゖ' else c

def make(h, out):
    k = {'ヲ': 'オ', 'ヂ': 'ジ', 'ヅ': 'ズ'}.get(kata(h), kata(h))
    k = {'ャ': 'ヤ', 'ュ': 'ユ', 'ョ': 'ヨ'}.get(k, k)  # 小さい字は ふつうの 大きさの 音で
    q = json.loads(post('/audio_query', {'text': h, 'speaker': SPEAKER}))
    q['accent_phrases'] = json.loads(post('/accent_phrases', {'text': k + "'", 'speaker': SPEAKER, 'is_kana': 'true'}))
    mora = q['accent_phrases'][0]['moras'][-1]
    mora['vowel_length'] = LONG
    q['prePhonemeLength'] = 0.03
    q['postPhonemeLength'] = 0.08
    wav = post('/synthesis', {'speaker': SPEAKER}, json.dumps(q).encode())
    tmp = out + '.wav'
    open(tmp, 'wb').write(wav)
    subprocess.run(['afconvert', '-f', 'm4af', '-d', 'aac', '-b', '40000', tmp, out], check=True)
    os.remove(tmp)

def main():
    try:
        urllib.request.urlopen(API + '/version', timeout=3)
    except Exception:
        sys.exit('VOICEVOX が起動していません。アプリを開いてから もう一度。')
    chars = re.findall(r'^\s*"(.)":', open(PICS, encoding='utf-8').read(), re.M)
    os.makedirs(OUT, exist_ok=True)
    table, made = {}, 0
    for h in dict.fromkeys(hira(c) for c in chars):
        if h in 'っー':
            continue
        fid = hashlib.md5(('long' + h).encode()).hexdigest()[:8]
        table[h] = fid
        path = os.path.join(OUT, fid + '.m4a')
        if not os.path.exists(path):
            make(h, path); made += 1
    with open(JS, 'w', encoding='utf-8') as f:
        f.write('// なぞって えを けそう：なぞっている あいだの のばした声（VOICEVOX:ずんだもん）。字 → voice-long/○○.m4a\n')
        f.write('// tools/build-hiragana-long-voice.py で 作る。手で なおさない\n')
        f.write('const VOICE_LONG = ' + json.dumps(table, ensure_ascii=False, indent=0) + ';\n')
    print(f'{len(table)}こ（あたらしく {made}こ）')

main()
