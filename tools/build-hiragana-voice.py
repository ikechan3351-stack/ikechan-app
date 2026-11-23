#!/usr/bin/env python3
"""ひらがな なぞりっこ の 読み上げ音声を VOICEVOX（四国めたん）で作る。

つかいかた：VOICEVOX を起動してから  python3 tools/build-hiragana-voice.py [--redo]
- --redo：ある ファイルも ぜんぶ 作り直す（声を かえたとき）。
- アプリが読むことばを tools/hiragana-voice-texts.js でひろい、
  japanese/hiragana/voice/<番号>.m4a と japanese/hiragana/voice.js を作る。
- もうあるファイルは作り直さない（ことばを足したときは、足した分だけ作られる）。
- 1文字だけのときは「は→ワ」「へ→エ」と読まれないよう、読み方を指定する。
"""
import hashlib, json, os, subprocess, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'japanese', 'ひらがななぞりっこ.html')
OUT = os.path.join(ROOT, 'japanese', 'hiragana', 'voice')
JS = os.path.join(ROOT, 'japanese', 'hiragana', 'voice.js')
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

def make(text, out):
    q = json.loads(post('/audio_query', {'text': text, 'speaker': SPEAKER}))
    if len(key(text)) == 1:  # 1文字：字のとおりに読む（を・ぢ・づ は 音どおり）
        k = {'ヲ': 'オ', 'ヂ': 'ジ', 'ヅ': 'ズ'}.get(kata(text), kata(text))
        q['accent_phrases'] = json.loads(post('/accent_phrases', {'text': k + "'", 'speaker': SPEAKER, 'is_kana': 'true'}))
    q['speedScale'] = SPEED
    wav = post('/synthesis', {'speaker': SPEAKER}, json.dumps(q).encode())
    tmp = out + '.wav'
    open(tmp, 'wb').write(wav)
    subprocess.run(['afconvert', '-f', 'm4af', '-d', 'aac', '-b', '40000', tmp, out], check=True)
    os.remove(tmp)
    return q

def main():
    try:
        post('/version', {}) if False else urllib.request.urlopen(API + '/version', timeout=3)
    except Exception:
        sys.exit('VOICEVOX が起動していません。アプリを開いてから もう一度。')
    texts = json.loads(subprocess.check_output(['node', os.path.join(ROOT, 'tools', 'hiragana-voice-texts.js'),
                                                APP, os.path.join(ROOT, 'japanese', 'hiragana', 'pics.js')]))
    os.makedirs(OUT, exist_ok=True)
    table, made = {}, 0
    for t in texts:
        fid = hashlib.md5(key(t).encode()).hexdigest()[:8]
        table[key(t)] = fid
        path = os.path.join(OUT, fid + '.m4a')
        if os.path.exists(path) and '--redo' not in sys.argv:
            continue
        q = make(t, path); made += 1
        print(t, '→', q.get('kana', ''))
    with open(JS, 'w', encoding='utf-8') as f:
        f.write('// ひらがな なぞりっこ の読み上げ音声（VOICEVOX:四国めたん）。ことば → voice/○○.m4a\n')
        f.write('// tools/build-hiragana-voice.py で 作る。手で なおさない\n')
        f.write('const VOICE = ' + json.dumps(table, ensure_ascii=False, indent=0) + ';\n')
    print(f'{len(table)}こ（あたらしく {made}こ）')

main()
