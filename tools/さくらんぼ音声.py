#!/usr/bin/env python3
"""さくらんぼけいさん の 音声ファイルを VOICEVOX で まとめて 作ります。

つかい方（ikechan-app フォルダの中で、VOICEVOX を 起動した まま）:
    python3 tools/さくらんぼ音声.py

1. tools/sakuranbo-phrases.js で、アプリが しゃべる 文を ぜんぶ 書き出す（node が 必要）
2. まだ ファイルが ない 文だけ、VOICEVOX（四国めたん ノーマル）で 声に する
3. m4a（AAC）に して math/さくらんぼけいさん_音声/ に 入れ、一覧 list.js を 作りなおす
4. 読み方（カナ）を 読み方チェック.tsv に 書き出す（読みまちがいを さがす ため）

もう つかわない ファイルは 一覧に 出すだけで、けしません（--clean を つけると けします）。
"""

import json
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / 'math' / 'さくらんぼけいさん.html'
OUT = ROOT / 'math' / 'さくらんぼけいさん_音声'
ENGINE = 'http://127.0.0.1:50021'
SPEAKER = 2                     # 四国めたん（ノーマル）
CREDIT = 'VOICEVOX:四国めたん'
SPEED = 0.95                    # 1年生むけに すこし ゆっくり


def voice_hash(s: str) -> str:
    """FNV-1a 32bit（アプリの voiceHash と おなじ 計算）"""
    h = 0x811c9dc5
    for b in s.encode('utf-8'):
        h ^= b
        h = (h * 0x01000193) & 0xffffffff
    return f'{h:08x}'


def tts_text(s: str) -> str:
    """VOICEVOX に わたす 文。分かち書きの すきまを とり、「8こ」は「8個」に して はっこ と 読ませる"""
    t = re.sub(r'[ 　]+', '', s)
    t = re.sub(r'(\d+)こ', r'\1個', t)
    return t


def post(path: str, params: dict, body: bytes = b'', ctype: str = 'application/json') -> bytes:
    url = f'{ENGINE}{path}?{urllib.parse.urlencode(params)}'
    req = urllib.request.Request(url, data=body, method='POST', headers={'Content-Type': ctype})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def to_m4a(wav: Path, m4a: Path):
    subprocess.run(['afconvert', '-f', 'm4af', '-d', 'aac', '-b', '48000', str(wav), str(m4a)], check=True)


def main():
    try:
        urllib.request.urlopen(f'{ENGINE}/version', timeout=5).read()
    except Exception:
        sys.exit('VOICEVOX が 見つかりません。VOICEVOX を 起動してから もういちど 実行してください。')

    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        js = tmp / 'phrases.json'
        subprocess.run(['node', str(ROOT / 'tools' / 'sakuranbo-phrases.js'), str(HTML), str(js)], check=True)
        phrases = json.loads(js.read_text(encoding='utf-8'))

        # iPad で さいしょに ならす ための むおんファイル
        silence = OUT / 'silence.m4a'
        if not silence.exists():
            w = tmp / 'silence.wav'
            with wave.open(str(w), 'wb') as f:
                f.setnchannels(1); f.setsampwidth(2); f.setframerate(24000); f.writeframes(b'\0\0' * 4800)
            to_m4a(w, silence)

        rows, made = [], 0
        for i, s in enumerate(phrases, 1):
            h = voice_hash(s)
            m4a = OUT / f'{h}.m4a'
            q = json.loads(post('/audio_query', {'speaker': SPEAKER, 'text': tts_text(s)}))
            rows.append(f'{h}\t{s}\t{q.get("kana", "")}')
            if m4a.exists():
                continue
            q['speedScale'] = SPEED
            q['prePhonemeLength'] = 0.05
            q['postPhonemeLength'] = 0.1
            wav = tmp / f'{h}.wav'
            wav.write_bytes(post('/synthesis', {'speaker': SPEAKER}, json.dumps(q).encode('utf-8')))
            to_m4a(wav, m4a)
            made += 1
            print(f'[{i}/{len(phrases)}] {s}')

    hashes = sorted(voice_hash(s) for s in phrases)
    (OUT / 'list.js').write_text(
        '// tools/さくらんぼ音声.py が 作る ファイル。手で 直さない。\n'
        f'window.SAKURA_VOICE = {json.dumps({"credit": CREDIT, "files": hashes}, ensure_ascii=False)};\n',
        encoding='utf-8')
    (OUT / '読み方チェック.tsv').write_text('ハッシュ\t文\tVOICEVOX の 読み（カナ）\n' + '\n'.join(rows) + '\n', encoding='utf-8')

    keep = set(hashes) | {'silence'}
    stale = [p for p in OUT.glob('*.m4a') if p.stem not in keep]
    if stale and '--clean' in sys.argv:
        for p in stale:
            p.unlink()
        print(f'つかわない ファイルを {len(stale)}こ けしました。')
    elif stale:
        print(f'つかわない ファイルが {len(stale)}こ あります（--clean で けせます）:', ', '.join(p.name for p in stale))
    print(f'できあがり：文 {len(phrases)}こ（あたらしく 作った のは {made}こ）→ {OUT}')


if __name__ == '__main__':
    main()
