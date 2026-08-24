#!/usr/bin/env python3
"""index.html を読んで、Obsidian のノートの「教材一覧」を作り直します。

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

SECTION_RE = re.compile(
    r'<section class="subject" id="[^"]+"[^>]*>\s*'
    r'<div class="subject-head">\s*'
    r'<span class="emoji">([^<]+)</span><h2>([^<]+)</h2><span class="count">(\d+)</span>\s*'
    r'</div>\s*<div class="grid">(.*?)</div>\s*</section>', re.S)
CARD_RE = re.compile(r'<a class="app-card(?: external)?" href="([^"]+)"[^>]*>(.*?)</a>', re.S)


def span(html, cls):
    m = re.search(r'<span class="%s">(.*?)</span>' % cls, html, re.S)
    return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''


def to_url(href):
    """トップページのリンクを、公開ページのURLに直す。"""
    if href.startswith(('http://', 'https://')):
        return href
    return BASE_URL + urllib.parse.quote(href)


def build(index_html):
    lines, total, warnings = [], 0, []
    for emoji, name, count, grid in SECTION_RE.findall(index_html):
        cards = CARD_RE.findall(grid)
        if int(count) != len(cards):
            warnings.append(f'{name}: index.html の件数表示は {count} ですが、実際のカードは {len(cards)} 枚です')
        total += len(cards)
        lines.append(f'### {name}（{len(cards)}件）\n')
        lines.append('| 教材 | 学年 | 内容 |')
        lines.append('|---|---|---|')
        for href, body in cards:
            title, grade, desc, note = (span(body, c) for c in ('title', 'grade', 'desc', 'note'))
            if note:
                desc = f'{desc}（{note}）'
            lines.append(f'| [{title}]({to_url(href)}) | {grade} | {desc} |')
        lines.append('')
    head = ('教材名をクリックすると公開ページが開きます。'
            f'この一覧は `index.html` から自動で作っています（ぜんぶで {total} 件）。\n')
    return head + '\n' + '\n'.join(lines).rstrip() + '\n', total, warnings


def main():
    repo = Path(__file__).resolve().parent.parent
    index_path = repo / 'index.html'
    note_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / '脳メモ' / '教材開発' / 'ikechan-app.md'

    for path in (index_path, note_path):
        if not path.exists():
            sys.exit(f'見つかりません: {path}')

    body, total, warnings = build(index_path.read_text(encoding='utf-8'))
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
