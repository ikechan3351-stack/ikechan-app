#!/usr/bin/env python3
"""index.html のアプリの表（const D=[...]）を読んで、Obsidian のノートの「教材一覧」を作り直します。

つかい方（ikechan-app フォルダの中で）:
    python3 tools/update-obsidian-note.py

ノートの ▼ここから下 〜 ▲ここまで にはさまれた部分だけを書きかえます。
frontmatter・場所とURL・決めごと・手書きのメモはそのまま残ります。
"""

import re
import sys
import urllib.parse
from pathlib import Path

BASE_URL = 'https://ikechan3351-stack.github.io/ikechan-app/'
BEGIN = '<!-- ▼ ここから下は tools/update-obsidian-note.py が index.html から自動で作ります。手で直しても次の実行で消えます -->'
END = '<!-- ▲ ここまで -->'

DATA_RE = re.compile(r'const D=\[(.*?)\n\];', re.S)
SUBJ_RE = re.compile(r"const SUBJ=\[(.*?)\];", re.S)
ROW_RE = re.compile(r"^\s*\[(.*)\],?\s*$")
VALUE_RE = re.compile(r"'((?:[^'\\]|\\.)*)'|(-?\d+)")


def values(text):
    """['m',1,2,'🍒',...] の中身を、文字列と数の並びにする。"""
    return [s if n == '' else int(n) for s, n in VALUE_RE.findall(text)]


def grade_label(g1, g2):
    """index.html の gradeLabel() と同じ表し方。"""
    gl = lambda n: f'小{n}' if n <= 6 else f'中{n - 6}'
    if g1 == 0:
        return '先生用'
    if g1 == 1 and g2 == 9:
        return '全学年'
    return gl(g1) if g1 == g2 else f'{gl(g1)}〜{gl(g2)}'


def to_url(href):
    """トップページのリンクを、公開ページのURLに直す。"""
    if href.startswith(('http://', 'https://')):
        return href
    return BASE_URL + urllib.parse.quote(href)


def build(index_html, repo):
    data, subj = DATA_RE.search(index_html), SUBJ_RE.search(index_html)
    if not data or not subj:
        sys.exit('index.html にアプリの表（const D=[...]）か教科の表（const SUBJ=[...]）が見つかりません')
    subjects = dict(zip(*[iter(values(subj.group(1)))] * 2))
    groups, warnings = {k: [] for k in subjects}, []
    for line in data.group(1).splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        row = values(m.group(1))
        if len(row) != 9:
            warnings.append(f'形がおかしい行があります: {line.strip()}')
            continue
        if row[0] not in groups:
            warnings.append(f'知らない教科の記号 {row[0]!r}: {row[4]}')
            continue
        path = row[6]
        if not path.startswith(('http://', 'https://')) and not (repo / path).exists():
            warnings.append(f'リンク先のファイルがありません: {path}')
        groups[row[0]].append(row)

    lines, total = [], 0
    for key, name in subjects.items():
        rows = groups[key]
        if not rows:
            continue
        if key == 'm':  # トップページと同じく、算数は学年の低い順
            rows = sorted(rows, key=lambda r: r[1])
        total += len(rows)
        lines.append(f'### {name}（{len(rows)}件）\n')
        lines.append('| 教材 | 学年 | 内容 |')
        lines.append('|---|---|---|')
        for _, g1, g2, ico, title, desc, path, unit, flags in rows:
            notes = [n for f, n in (('t', '先生モード・授業向け'), ('x', '起動に少し時間がかかります')) if f in flags]
            if unit:
                notes.insert(0, unit)
            if notes:
                desc = f'{desc}（{"・".join(notes)}）'
            lines.append(f'| [{ico} {title}]({to_url(path)}) | {grade_label(g1, g2)} | {desc} |')
        lines.append('')
    head = ('教材名をクリックすると公開ページが開きます。'
            f'この一覧は `index.html` から自動で作っています（ぜんぶで {total} 件）。\n')
    return head + '\n' + '\n'.join(lines).rstrip() + '\n', total, warnings


def note_candidates():
    """脳メモ（Obsidian保管庫）の置き場所の候補。上から順に探す。"""
    home = Path.home()
    rel = Path('脳メモ') / '教材開発' / 'ikechan-app.md'
    return [home / 'Documents' / rel, home / rel]


def find_note():
    for candidate in note_candidates():
        if candidate.exists():
            return candidate
    return None


def main():
    repo = Path(__file__).resolve().parent.parent
    index_path = repo / 'index.html'
    if len(sys.argv) > 1:
        note_path = Path(sys.argv[1])
    else:
        note_path = find_note()
        if note_path is None:
            sys.exit(
                '脳メモのノートが見つかりません。探した場所:\n  '
                + '\n  '.join(str(c) for c in note_candidates())
                + '\nノートのパスを引数で渡してください。'
            )

    for path in (index_path, note_path):
        if not path.exists():
            sys.exit(f'見つかりません: {path}')

    body, total, warnings = build(index_path.read_text(encoding='utf-8'), repo)
    note = note_path.read_text(encoding='utf-8')

    if BEGIN not in note or END not in note:
        sys.exit(f'ノートに ▼▲ の目印がありません: {note_path}')

    before, rest = note.split(BEGIN, 1)
    _, after = rest.split(END, 1)
    new = f'{before}{BEGIN}\n\n{body}\n{END}{after}'

    for w in warnings:
        print('⚠️ ', w)
    if new == note:
        print(f'変わりありません（{total}件）: {note_path}')
    else:
        note_path.write_text(new, encoding='utf-8')
        print(f'✅ ノートを更新しました（{total}件）: {note_path}')


if __name__ == '__main__':
    main()
