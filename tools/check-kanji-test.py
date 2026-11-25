#!/usr/bin/env python3
"""漢字ガンバの単元テストの問題文（japanese/kanji-ganba/test.js）をたしかめる。

しらべること
- 単元の字に、テストの文がそろっているか（ぬけ・だぶり・よけいな字）
- [漢字]{よみ} の形になっているか、[ ] の中に その字が入っているか
- 文の中の ほかの漢字が、その単元より 前の単元（または 下の学年）で 習った字か
  （同じ単元の字が出ると、紙のテストで 答えが 見えてしまう）
- よみの問題と かきの問題が 同じ文になっていないか

つかいかた：python3 tools/check-kanji-test.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / 'japanese' / '漢字ガンバ.html'
TEST = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'japanese' / 'kanji-ganba' / 'test.js'

html = HTML.read_text(encoding='utf-8')
test = TEST.read_text(encoding='utf-8')

# 学年ごとの字（RAW・RAW2〜RAW6）
grade_of = {}
for g, name in enumerate(['RAW', 'RAW2', 'RAW3', 'RAW4', 'RAW5', 'RAW6'], start=1):
    m = re.search(r'const ' + name + r' = `(.*?)`;', html, re.S)
    for line in m.group(1).strip().split('\n'):
        grade_of[line.split('|')[0]] = g

# 光村の単元（UNITS_BY.mitsu）。11字以上は ①② に分ける（アプリの unitList() と同じ）
m = re.search(r'const UNITS_BY = \{ mitsu: \{(.*?)\n\} \};', html, re.S)
units = {}
for gm in re.finditer(r'(\d):\s*\[(.*?)\]\],?\s*(?=\n\s*\d:|\Z)', m.group(1), re.S):
    g = int(gm.group(1))
    lst = []
    for name, ks in re.findall(r"\['[^']*',\s*'([^']*)',\s*'([^']*)'\]", gm.group(2) + ']'):
        ks = list(ks)
        if len(ks) <= 10:
            lst.append((name, ks))
        else:
            h = (len(ks) + 1) // 2
            lst += [(name + ' ①', ks[:h]), (name + ' ②', ks[h:])]
    units[g] = lst

KANJI = re.compile(r'[一-鿿々]')
PAT = re.compile(r'^(.*)\[(.+?)\]\{(.+?)\}(.*)$')

warn = 0
def w(msg):
    global warn
    warn += 1
    print('⚠️ ', msg)

for gm in re.finditer(r'^(\d): `(.*?)`', test, re.S | re.M):
    g = int(gm.group(1))
    rows = {}
    for line in gm.group(2).strip().split('\n'):
        p = line.split('|')
        if len(p) != 3:
            w(f'{g}年 形がおかしい行：{line}')
            continue
        if p[0] in rows:
            w(f'{g}年 {p[0]} が 2回あります')
        rows[p[0]] = p[1:]

    if g not in units:
        print(f'{g}年：単元のデータがないので、文の形だけ しらべます')
    learned = {k for k, gg in grade_of.items() if gg < g}  # 下の学年の字
    order = units.get(g, [(f'{g}年', list(rows))])
    in_units = {k for _, ks in order for k in ks}
    for k in rows:
        if k not in in_units:
            w(f'{g}年 {k} は 単元に入っていません')
    for name, ks in order:
        for k in ks:
            if k not in rows:
                w(f'{g}年「{name}」 {k} の テストの文が ありません')
                continue
            r, wr = rows[k]
            if r == wr:
                w(f'{g}年 {k} よみと かきが 同じ文です')
            for kind, s in (('よみ', r), ('かき', wr)):
                mm = PAT.match(s)
                if not mm:
                    w(f'{g}年 {k} {kind}：[漢字]{{よみ}} が ありません：{s}')
                    continue
                pre, kj, yomi, post = mm.groups()
                if k not in kj:
                    w(f'{g}年 {k} {kind}：[ ] の中に {k} がありません：{s}')
                if KANJI.search(yomi) or not yomi:
                    w(f'{g}年 {k} {kind}：よみが おかしい：{s}')
                others = [c for c in pre + kj.replace(k, '', 1) + post if KANJI.match(c)]
                for c in others:
                    if c not in learned:
                        where = '同じ単元の字' if c in ks else ('まだ習っていない字' if grade_of.get(c, 9) <= g else '小学校で このあとに習う字')
                        w(f'{g}年「{name}」 {k} {kind}：{c} は {where}です：{s}')
        learned |= set(ks)
    print(f'{g}年：{len(rows)}字 しらべました')

print('ぜんぶ OK' if not warn else f'けいこく {warn}こ')
sys.exit(1 if warn else 0)
