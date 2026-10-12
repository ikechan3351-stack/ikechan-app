/* =====================================================================
   math-render.js  ―  数式を画面に美しく出すための共通ファイル
   ---------------------------------------------------------------------
   外部ライブラリ（KaTeX など）を使わずに、HTML と CSS（一部 SVG）だけで
   分数・根号・累乗・連立方程式の大かっこ・帯分数・絶対値を描きます。

   【読みこみ方】 各アプリの HTML に次の1行を書きます。
       <script src="math-render.js"></script>

   【おもな使い方】
       el.innerHTML = MathRender.html("3x^2 - 5/6 x + √2");
       MathRender.render(el, "2x+3=7", { size: "large" });
       el.innerHTML = MathRender.system(["2x+y=5", "x-y=1"]);
       el.innerHTML = MathRender.html("3x+5", { highlight: [0] });  // 1番目の項に色と下線
       const a = new Fraction(1, 2).add("1/3");   // 5/6（厳密に計算）
       MathRender.simplifySqrt(72).text           // "6√2"

   【式の書き方（入力のきまり）】
       x^2  x^{n+1}     … 累乗（上つき）。2けた以上や式は { } でかこむ
       5/6  {x+1}/2     … 分数（たて分数）。分子・分母が式なら { } か ( ) でかこむ
       5/6 x            … 「分数×文字」は、分数のあとに空白を入れる（5/6x だと 分母が 6x になる）
       2_1/3            … 帯分数（2と3分の1）
       √2  √{x+1}       … 根号。中が式なら { } か ( ) でかこむ
       |x-3|            … 絶対値
       * → ×、 <= → ≦、 >= → ≧、 != → ≠ に自動で直ります。
   ===================================================================== */
(function () {
  'use strict';

  /* ---------------------------------------------------------------
     1. 見た目（CSS）
     最初に使われたときに1回だけ <style> を <head> に足します。
     フォントは既存の数学教材と同じものにそろえています。
     --------------------------------------------------------------- */
  const CSS = `
.mr{font-family:"Hiragino Sans","Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;
  white-space:nowrap;line-height:1.35;font-weight:normal;color:inherit}
.mr-small{font-size:24px}
.mr-normal{font-size:32px}
.mr-large{font-size:clamp(34px,7vw,60px)}
.mr-i{font-style:italic;padding-right:.03em}
.mr-o{display:inline-block}
.mr-bin{margin:0 .2em}
.mr-rel{margin:0 .32em}
.mr-un{margin-right:.03em}
.mr-comma{margin-right:.4em}
.mr-sp{display:inline-block;width:.12em}
.mr-frac{display:inline-flex;flex-direction:column;align-items:stretch;vertical-align:middle;
  text-align:center;font-size:.9em;line-height:1.2;margin:0 .1em}
.mr-frac .mr-frac{font-size:.94em}
.mr-num{border-bottom:.07em solid currentColor;padding:0 .2em .05em}
.mr-den{padding:.05em .2em 0}
.mr-mixed{white-space:nowrap}
.mr-mixed>.mr-frac{margin-left:.04em}
.mr-sup{font-size:.62em;vertical-align:.85em;margin-left:.04em;line-height:1}
.mr-sup-hi{vertical-align:1.75em}
.mr-sqrt{display:inline-flex;align-items:stretch;margin:0 .06em 0 .04em}
.mr-dl{position:relative;flex:none;align-self:stretch}
.mr-dl svg{position:absolute;left:0;top:0;width:100%;height:100%;overflow:visible}
.mr-dl path{fill:none;stroke:currentColor;stroke-width:.07em;stroke-linejoin:round;stroke-linecap:round}
.mr-rs{width:.62em}
.mr-rad{align-self:baseline;border-top:.07em solid currentColor;padding:.07em .1em 0 .04em}
.mr-pr{display:inline-flex;align-items:stretch;margin:0 .02em}
.mr-pr>.mr-dl{width:.38em}
.mr-pc{align-self:baseline;padding:.04em 0}
.mr-abs{display:inline-block;border-left:.07em solid currentColor;border-right:.07em solid currentColor;
  padding:0 .14em;margin:0 .08em}
.mr-hl{display:inline-block;border-radius:.15em;padding:0 .06em .02em;margin:0 .02em;
  border-bottom-width:.12em}
.mr-sys{display:inline-flex;align-items:stretch;vertical-align:middle}
.mr-sys>.mr-dl{width:.6em;margin-right:.12em}
.mr-lines{display:flex;flex-direction:column;justify-content:center;gap:.12em;padding:.05em 0}
.mr-line{display:block}
.mr-t{font-style:normal}
`;
  /** CSS を1回だけページに入れる */
  function injectCSS() {
    if (typeof document === 'undefined' || document.getElementById('math-render-style')) return;
    const st = document.createElement('style');
    st.id = 'math-render-style';
    st.textContent = CSS;
    (document.head || document.documentElement).appendChild(st);
  }

  /** HTML で特別な意味をもつ文字（< > & "）を安全な形に直す */
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /* ---------------------------------------------------------------
     2. 字句に分ける（トークン化）
     "3x^2+1" → [数3][文字x][^][数2][記号+][数1] のように、意味のある
     かたまりに切り分けます。
     --------------------------------------------------------------- */
  const OPS = '+-=×÷·<>≦≧≠±,:';           // 演算子・関係の記号
  const REL = '=<>≦≧≠:';                  // 関係の記号（等号・不等号）

  /** 入力の書き方のゆれを、決まった形にそろえる */
  function normalize(src) {
    return String(src)
      .replace(/²/g, '^2').replace(/³/g, '^3')
      .replace(/[−–]/g, '-').replace(/\*/g, '×')
      .replace(/<=|≤/g, '≦').replace(/>=|≥/g, '≧').replace(/!=/g, '≠')
      .replace(/\s+/g, ' ');
  }

  /** 文字列をトークンの配列にする。各トークンは {k:種類, v:中身, s:始まり, e:終わり} */
  function tokenize(src) {
    const out = [];
    let i = 0;
    while (i < src.length) {
      const c = src[i];
      const s = i;
      if (/[0-9]/.test(c) || (c === '.' && /[0-9]/.test(src[i + 1] || ''))) {
        // 数（小数もふくむ）
        while (i < src.length && /[0-9.]/.test(src[i])) i++;
        out.push({ k: 'num', v: src.slice(s, i), s, e: i });
        continue;
      }
      if (/[A-Za-z]/.test(c)) { out.push({ k: 'var', v: c, s, e: i + 1 }); i++; continue; }   // 文字は1文字ずつ
      if (c === 'π') { out.push({ k: 'const', v: c, s, e: i + 1 }); i++; continue; }
      if (c === ' ') { out.push({ k: 'sp', v: ' ', s, e: i + 1 }); i++; continue; }
      if ('√^/_(){}[]|'.includes(c)) { out.push({ k: c, v: c, s, e: i + 1 }); i++; continue; }
      if (OPS.includes(c)) { out.push({ k: 'op', v: c, s, e: i + 1 }); i++; continue; }
      // それ以外（日本語など）は、続いている間ひとまとまりの「ことば」にする
      while (i < src.length && !/[0-9A-Za-zπ .√^/_(){}\[\]|]/.test(src[i]) && !OPS.includes(src[i])) i++;
      if (i === s) i++;
      out.push({ k: 'text', v: src.slice(s, i), s, e: i });
    }
    return out;
  }

  /* ---------------------------------------------------------------
     3. 組み立てる（構文解析）
     トークンの並びから「分数」「累乗」「根号」などの木の形を作ります。
     ノードの種類:
       num 数 / var 文字 / const π / text ことば / op 記号 / sp 空白
       frac 分数 / mixed 帯分数 / sup 累乗 / sqrt 根号 / paren かっこ
       abs 絶対値 / grp { } のまとまり（見えない）
     --------------------------------------------------------------- */
  const CLOSE = { '(': ')', '[': ']', '{': '}' };

  function parse(src) {
    const tk = tokenize(src);
    let p = 0;
    const peek = () => tk[p];

    /** 今の位置から node の始まり・終わりの文字位置をつける（項の切り出しに使う） */
    function span(node, p0) {
      node.s = tk[p0] ? tk[p0].s : src.length;
      node.e = p > p0 ? tk[p - 1].e : node.s;
      return node;
    }

    /** 式の並びを読む。closers のどれかが来たら止まる */
    function seq(closers) {
      const list = [];
      while (p < tk.length) {
        const t = peek();
        if (closers.includes(t.k)) break;
        const p0 = p;
        if (t.k === 'sp') { p++; list.push(span({ t: 'sp' }, p0)); continue; }
        if (t.k === 'op') {
          p++;
          // + − ± が式の先頭や記号の直後にあれば「符号」（単項）、そうでなければ「たし算・ひき算」
          const prev = lastSolid(list);
          const unary = '+-±'.includes(t.v) && (!prev || prev.t === 'op');
          list.push(span({ t: 'op', v: t.v, unary }, p0));
          continue;
        }
        if (t.k === '/') {
          // 分数: 直前のかたまりを分子、直後のかたまりを分母にする
          p++;
          const left = popChunk(list);
          const right = chunk(closers);
          const node = { t: 'frac', n: unwrap(left), d: unwrap(right) };
          node.s = left.length ? left[0].s : t.s;
          node.e = p > 0 ? tk[p - 1].e : t.e;
          list.push(node);
          continue;
        }
        list.push(item(closers));
      }
      return list;
    }

    /** 空白をとばして、いちばん後ろのノードを返す */
    function lastSolid(list) {
      for (let i = list.length - 1; i >= 0; i--) if (list[i].t !== 'sp') return list[i];
      return null;
    }

    /** 分子にするため、後ろから「記号・空白」の手前までを取り出す */
    function popChunk(list) {
      const got = [];
      while (list.length) {
        const last = list[list.length - 1];
        if (last.t === 'op' || last.t === 'sp') break;
        got.unshift(list.pop());
      }
      return got;
    }

    /** 分母にするため、「記号・空白」が来るまでを読む */
    function chunk(closers) {
      while (peek() && peek().k === 'sp') p++;
      const got = [];
      if (peek() && peek().k === 'op' && peek().v === '-') {     // 1/-2 のような負の分母
        const p0 = p; p++;
        got.push(span({ t: 'op', v: '-', unary: true }, p0));
      }
      while (p < tk.length) {
        const t = peek();
        if (closers.includes(t.k) || t.k === 'op' || t.k === 'sp' || t.k === '/') break;
        got.push(item(closers));
      }
      return got;
    }

    /** かっこ1つだけ・{ }1つだけのときは、外側をはずして中身を返す（分子・分母・根号の中で使う） */
    function unwrap(list) {
      if (list.length === 1 && (list[0].t === 'grp' || (list[0].t === 'paren' && list[0].o === '('))) return list[0].kids;
      return list;
    }

    /** 1つの要素（数・文字・かっこ・根号など）と、そのあとの累乗を読む */
    function item(closers) {
      const t = peek();
      const p0 = p;
      let node;
      if (t.k === 'num') {
        p++;
        node = { t: 'num', v: t.v };
        // 帯分数 2_1/3
        if (peek() && peek().k === '_' && tk[p + 1] && tk[p + 1].k === 'num' && tk[p + 2] && tk[p + 2].k === '/' && tk[p + 3] && tk[p + 3].k === 'num') {
          node = { t: 'mixed', w: t.v, n: tk[p + 1].v, d: tk[p + 3].v };
          p += 4;
        }
      } else if (t.k === 'var') { p++; node = { t: 'var', v: t.v };
      } else if (t.k === 'const') { p++; node = { t: 'const', v: t.v };
      } else if (t.k === 'text') { p++; node = { t: 'text', v: t.v };
      } else if (t.k === '√') {
        p++;
        let rad = [];
        const n = peek();
        if (n && (n.k === 'num' || n.k === 'var' || n.k === 'const')) { rad = [item(closers)]; if (rad[0].t === 'sup') { /* √x^2 は √(x²) とみなす */ } }
        else if (n && (n.k === '(' || n.k === '{')) rad = unwrap([group()]);
        node = { t: 'sqrt', kids: rad };
        return span(node, p0);   // 根号のあとの ^ は根号の中で処理ずみ
      } else if (t.k === '(' || t.k === '[' || t.k === '{') {
        node = group();
      } else if (t.k === '|') {
        p++;
        const kids = seq(['|']);
        if (peek() && peek().k === '|') p++;
        node = { t: 'abs', kids };
      } else {
        // 対応しない閉じかっこなど → そのまま文字として出す
        p++;
        node = { t: 'text', v: t.v };
      }
      span(node, p0);
      // 累乗 ^ （x^2^3 のような重ねがけもできる）
      while (peek() && peek().k === '^') {
        p++;
        node = span({ t: 'sup', base: node, exp: expo() }, p0);
      }
      return node;
    }

    /** ( ) [ ] { } のまとまりを読む */
    function group() {
      const t = peek();
      const p0 = p;
      p++;
      const close = CLOSE[t.k];
      const kids = seq([close]);
      if (peek() && peek().k === close) p++;
      if (t.k === '{') return span({ t: 'grp', kids }, p0);
      return span({ t: 'paren', o: t.k, c: close, kids }, p0);
    }

    /** 指数（^ のあと）を読む: 数・文字1つ・{式}・(式)・負の数 */
    function expo() {
      const t = peek();
      if (!t) return [];
      if (t.k === '{' || t.k === '(') return unwrap([group()]);
      if (t.k === 'op' && t.v === '-') {
        const p0 = p; p++;
        const minus = span({ t: 'op', v: '-', unary: true }, p0);
        const n = peek();
        if (n && (n.k === 'num' || n.k === 'var')) { const p1 = p; p++; return [minus, span({ t: n.k, v: n.v }, p1)]; }
        return [minus];
      }
      if (t.k === 'num' || t.k === 'var' || t.k === 'const') { const p0 = p; p++; return [span({ t: t.k, v: t.v }, p0)]; }
      return [];
    }

    const tree = seq([]);
    return tree;
  }

  /* ---------------------------------------------------------------
     4. 描く（HTML にする）
     --------------------------------------------------------------- */
  // 記号の見た目（ひき算はハイフンでなく、正式なマイナス記号「−」にする）
  const SHOW = { '-': '−', '≦': '≦', '≧': '≧', '·': '·' };

  /** 分数がふくまれているか（ふくまれていれば、かっこを背の高いものにする） */
  function hasTall(list) {
    return list.some(n =>
      n.t === 'frac' || n.t === 'mixed' ||
      (n.kids && hasTall(n.kids)) || (n.t === 'sup' && hasTall([n.base])));
  }

  /** 伸びちぢみする記号（かっこ・大かっこ・根号）を SVG で描く。h は図の高さ（よこ10に対して） */
  function delim(kind, cls, h) {
    h = h || 40;
    let d;
    if (kind === '(') d = `M8.5,1 C1.5,${h * 0.3} 1.5,${h * 0.7} 8.5,${h - 1}`;
    else if (kind === ')') d = `M1.5,1 C8.5,${h * 0.3} 8.5,${h * 0.7} 1.5,${h - 1}`;
    else if (kind === '[') d = `M8,1 L3,1 L3,${h - 1} L8,${h - 1}`;
    else if (kind === ']') d = `M2,1 L7,1 L7,${h - 1} L2,${h - 1}`;
    else if (kind === '{') {
      // 連立方程式の大かっこ。上・まん中・下の曲がりの大きさは高さによらず一定にする
      const m = h / 2;
      d = `M9.5,1 C5.5,1 5.5,3 5.5,6 L5.5,${m - 5} C5.5,${m - 2} 4,${m} 0.8,${m} ` +
          `C4,${m} 5.5,${m + 2} 5.5,${m + 5} L5.5,${h - 6} C5.5,${h - 3} 5.5,${h - 1} 9.5,${h - 1}`;
    } else if (kind === 'sqrt') {
      d = `M0.5,${h * 0.62} L2.6,${h * 0.53} L5.4,${h - 0.6} L9.4,0.4 L10.2,0.4`;
    }
    return `<span class="mr-dl ${cls}" aria-hidden="true"><svg viewBox="0 0 10 ${h}" preserveAspectRatio="none">` +
      `<path vector-effect="non-scaling-stroke" d="${d}"/></svg></span>`;
  }

  /** 1つのノードを HTML にする */
  function node2html(n) {
    switch (n.t) {
      case 'num': return `<span class="mr-n">${esc(n.v)}</span>`;
      case 'var': return `<span class="mr-i">${esc(n.v)}</span>`;
      case 'const': return `<span class="mr-n">${esc(n.v)}</span>`;
      case 'text': return `<span class="mr-t">${esc(n.v)}</span>`;
      case 'op': {
        const v = SHOW[n.v] || n.v;
        let cls = 'mr-bin';
        if (n.unary) cls = 'mr-un';
        else if (REL.includes(n.v)) cls = 'mr-rel';
        else if (n.v === ',') cls = 'mr-comma';
        return `<span class="mr-o ${cls}">${esc(v)}</span>`;
      }
      case 'frac':
        return `<span class="mr-frac"><span class="mr-num">${list2html(n.n)}</span>` +
          `<span class="mr-den">${list2html(n.d)}</span></span>`;
      case 'mixed':
        return `<span class="mr-mixed"><span class="mr-n">${esc(n.w)}</span>` +
          `<span class="mr-frac"><span class="mr-num"><span class="mr-n">${esc(n.n)}</span></span>` +
          `<span class="mr-den"><span class="mr-n">${esc(n.d)}</span></span></span></span>`;
      case 'sup':
        // 分数をふくむかっこの累乗は、指数をかっこの肩まで上げる
        return node2html(n.base) + `<span class="mr-sup${hasTall([n.base]) || n.base.t === 'frac' ? ' mr-sup-hi' : ''}">${list2html(n.exp)}</span>`;
      case 'sqrt':
        return `<span class="mr-sqrt">${delim('sqrt', 'mr-rs', 20)}<span class="mr-rad">${list2html(n.kids) || '&nbsp;'}</span></span>`;
      case 'paren':
        if (hasTall(n.kids)) {
          // 中に分数があるときは、かっこを中身の高さまで伸ばす
          return `<span class="mr-pr">${delim(n.o, '', 40)}<span class="mr-pc">${list2html(n.kids)}</span>${delim(n.c, '', 40)}</span>`;
        }
        return `<span class="mr-o">${n.o}</span>${list2html(n.kids)}<span class="mr-o">${n.c}</span>`;
      case 'abs': return `<span class="mr-abs">${list2html(n.kids)}</span>`;
      case 'grp': return list2html(n.kids);
      case 'sp': return '';
    }
    return '';
  }

  /** ノードの並びを HTML にする。空白は「記号と記号の間」以外のところでだけ少しあける */
  function list2html(list) {
    let h = '';
    for (let i = 0; i < list.length; i++) {
      const n = list[i];
      if (n.t === 'sp') {
        const a = list[i - 1], b = list[i + 1];
        if (a && b && a.t !== 'op' && b.t !== 'op' && b.t !== 'sp') h += '<span class="mr-sp"></span>';
        continue;
      }
      h += node2html(n);
    }
    return h;
  }

  /* ---------------------------------------------------------------
     5. 項に分ける（色ぬり用）
     式のいちばん外側を、たし算・ひき算と「＝」のところで区切ります。
     項には符号もふくめます（3x−5 の項は 3x と −5）。
     「＝」の右側も続けて番号をつけます（2x+3=7 なら 0:2x 1:+3 2:7）。
     --------------------------------------------------------------- */
  function termIds(list) {
    const ids = new Array(list.length).fill(-1);
    let cur = -1, open = false;
    list.forEach((n, i) => {
      if (n.t === 'op' && (REL.includes(n.v) || n.v === ',')) { open = false; return; }
      if (n.t === 'op' && '+-±'.includes(n.v) && !n.unary) { cur++; open = true; ids[i] = cur; return; }
      if (n.t === 'sp') { if (open) ids[i] = cur; return; }
      if (!open) { cur++; open = true; }
      ids[i] = cur;
    });
    // 項の終わりについている空白は、項にふくめない
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i].t === 'sp' && (i === list.length - 1 || ids[i + 1] !== ids[i])) ids[i] = -1;
    }
    return ids;
  }

  // 色ぬりの色と下線の形（色だけにたよらず、線の形も変える）。共通の色のきまりに合わせた色。
  const HL = [
    { bg: '#fff3e0', line: '#e65100', style: 'solid' },    // オレンジ・実線
    { bg: '#e3f2fd', line: '#1565c0', style: 'double' },   // 青・二重線
    { bg: '#e8f5e9', line: '#2e7d32', style: 'dashed' },   // 緑・点線（長）
    { bg: '#f3e5f5', line: '#8e24aa', style: 'dotted' },   // 紫・点線（丸）
  ];

  /** いちばん外側の並びを、色ぬりつきで HTML にする */
  function top2html(list, highlight, colors) {
    if (!highlight || !highlight.length) return list2html(list);
    const pal = colors || HL;
    const ids = termIds(list);
    let h = '';
    let i = 0;
    while (i < list.length) {
      const id = ids[i];
      const k = id >= 0 ? highlight.indexOf(id) : -1;
      if (k < 0) { h += list2html([list[i]]); i++; continue; }
      let j = i;
      while (j < list.length && ids[j] === id) j++;
      const c = pal[k % pal.length];
      h += `<span class="mr-hl" data-term="${id}" style="background:${c.bg};border-bottom-style:${c.style};` +
        `border-bottom-color:${c.line};${c.style === 'double' ? 'border-bottom-width:.18em;' : ''}">${list2html(list.slice(i, j))}</span>`;
      i = j;
    }
    return h;
  }

  /** 大きさの指定を class と style にする */
  function sizeAttr(size) {
    if (typeof size === 'number') return { cls: '', style: ` style="font-size:${size}px"` };
    if (size === 'inherit') return { cls: '', style: '' };
    if (size === 'small' || size === 'large') return { cls: ' mr-' + size, style: '' };
    return { cls: ' mr-normal', style: '' };
  }

  /* ---------------------------------------------------------------
     6. 外から使う関数
     --------------------------------------------------------------- */

  /**
   * 文字列の式を HTML 文字列にする。
   * @param {string} src  式（例 "3x^2 - 5/6 x + √2"）
   * @param {object} [opt]
   *   size: "small"(24px) / "normal"(32px・ふつう) / "large"(電子黒板用) / 数(px) / "inherit"(まわりの文字と同じ)
   *   highlight: 色ぬりする項の番号の配列（0から数える）例 [0, 2]
   *   highlightColors: 色ぬりの色を変えたいとき [{bg, line, style}, ...]
   *   tidy: true にすると、先に MathRender.tidy() で教科書の書き方に整える
   */
  function html(src, opt) {
    opt = opt || {};
    injectCSS();
    let s = normalize(src);
    if (opt.tidy) s = tidy(s);
    const tree = parse(s);
    const sz = sizeAttr(opt.size);
    return `<span class="mr${sz.cls}"${sz.style} role="math" aria-label="${esc(s)}">` +
      top2html(tree, opt.highlight, opt.highlightColors) + '</span>';
  }

  /** 要素 el の中身を、式に書きかえる。 MathRender.render(el, "x^2", {size:"large"}) */
  function render(el, src, opt) {
    if (typeof el === 'string') el = document.querySelector(el);
    if (el) el.innerHTML = html(src, opt);
    return el;
  }

  /**
   * 連立方程式を、左の大かっこ付きで描く。
   * @param {string[]} lines  例 ["2x+y=5", "x-y=1"]
   * @param {object} [opt]  size・tidy は html() と同じ。
   *   highlight: 式ごとの色ぬり。例 [[0], [1]] → 1本目の0番の項、2本目の1番の項
   */
  function system(lines, opt) {
    opt = opt || {};
    injectCSS();
    const sz = sizeAttr(opt.size);
    const hl = opt.highlight || [];
    const rows = lines.map((ln, i) => {
      let s = normalize(ln);
      if (opt.tidy) s = tidy(s);
      return `<span class="mr-line">${top2html(parse(s), hl[i], opt.highlightColors)}</span>`;
    });
    const label = lines.map(normalize).join(' , ');
    return `<span class="mr${sz.cls}"${sz.style} role="math" aria-label="連立方程式 ${esc(label)}">` +
      `<span class="mr-sys">${delim('{', '', lines.length * 27)}<span class="mr-lines">${rows.join('')}</span></span></span>`;
  }

  /** 式を「項」の文字列に分ける。 "3x-5=7" → ["3x", "-5", "7"]（色ぬりの番号と同じ順） */
  function splitTerms(src) {
    const s = normalize(src);
    const tree = parse(s);
    const ids = termIds(tree);
    const out = [];
    tree.forEach((n, i) => {
      const id = ids[i];
      if (id < 0) return;
      if (!out[id]) out[id] = { s: n.s, e: n.e };
      else out[id].e = n.e;
    });
    return out.map(r => s.slice(r.s, r.e).trim());
  }

  /* ---------------------------------------------------------------
     7. 係数の見せ方（教科書の書き方に整える）
     --------------------------------------------------------------- */

  /**
   * 式の文字列を、教科書の書き方に整える。
   *   1x → x、 -1x → -x、 x^1 → x
   *   +(-3) → -3、 -(-3) → +3、 +(+3) → +3、 -(+3) → -3
   *   +- → -、 -- → +、 先頭や「＝」のあとの + は取る
   */
  function tidy(src) {
    let s = normalize(src);
    let prev;
    do {
      prev = s;
      // ＋(−3) のように、かっこの中が「符号と1つの数・文字」のときだけ外す
      s = s.replace(/([+\-])\s*\(\s*([+\-])\s*([0-9.]*[A-Za-zπ√]*[0-9.]*(?:\/[0-9]+)?)\s*\)(?!\s*\^)/g,
        (m, a, b, x) => (a === b ? '+' : '-') + x);
      s = s.replace(/\+\s*-/g, '-').replace(/-\s*\+/g, '-').replace(/-\s*-/g, '+').replace(/\+\s*\+/g, '+');
    } while (s !== prev);
    s = s.replace(/(^|[=(,≦≧<>]\s*)\+/g, '$1');                 // 先頭の + を取る
    s = s.replace(/(^|[^0-9.A-Za-z_\/])1(?=[A-Za-zπ√(])/g, '$1'); // 係数の 1 を取る
    s = s.replace(/\^1(?![0-9.])/g, '');                         // 1乗を取る
    return s.trim();
  }

  /**
   * 係数と文字から、1つの項の文字列を作る（先頭の + はつけない）。
   *   coef(1,"x")→"x"  coef(-1,"x")→"-x"  coef(3,"x")→"3x"  coef(new Fraction(5,6),"x")→"5/6 x"
   *   coef(-1,"")→"-1"（文字がないときの 1 は残す）
   */
  function coef(c, v) {
    v = v || '';
    const f = Fraction.from(c);
    if (f.n === 0) return '0';
    if (!v) return f.toString();
    if (f.n === 1 && f.d === 1) return v;
    if (f.n === -1 && f.d === 1) return '-' + v;
    if (f.d === 1) return f.n + v;
    return f.toString() + ' ' + v;           // 分数の係数は「5/6 x」の形（分母に文字が入らないよう空白）
  }

  /**
   * 係数と文字の組の並びから、式の文字列を作る。係数0の項は消し、ぜんぶ0なら "0"。
   *   terms([[3,"x^2"],[-1,"x"],[5,""]]) → "3x^2-x+5"
   */
  function terms(list) {
    let s = '';
    list.forEach(([c, v]) => {
      const t = coef(c, v);
      if (t === '0') return;
      if (!s) s = t;
      else s += t[0] === '-' ? t : '+' + t;
    });
    return s || '0';
  }

  /** 符号つきで書く。 signed(3)→"+3"  signed(-3)→"-3" */
  function signed(x) {
    const s = Fraction.from(x).toString();
    return s[0] === '-' ? s : '+' + s;
  }

  /** 負の数にだけかっこをつける（正負の数の計算を見せるとき）。 paren(-3)→"(-3)"  paren(3)→"3" */
  function paren(x) {
    const s = Fraction.from(x).toString();
    return s[0] === '-' ? '(' + s + ')' : s;
  }

  /* ---------------------------------------------------------------
     8. 分数クラス（厳密な計算用）
     小数を使わず、いつも「分子/分母」で持つので、誤差が出ません。
     作るときに自動で約分し、符号は分子につけます（分母はいつも正）。
     --------------------------------------------------------------- */

  /** 最大公約数（ユークリッドの互除法） */
  function gcd(a, b) {
    a = Math.abs(a); b = Math.abs(b);
    while (b) { const t = a % b; a = b; b = t; }
    return a;
  }
  /** 最小公倍数 */
  function lcm(a, b) { return a === 0 || b === 0 ? 0 : Math.abs(a / gcd(a, b) * b); }

  class Fraction {
    /**
     * new Fraction(3, 4) → 3/4。 new Fraction(6, 8) → 3/4（自動で約分）
     * 分子・分母は整数で渡す。小数や "3/4" などの文字列は Fraction.from() を使う。
     */
    constructor(n, d) {
      if (d === undefined) d = 1;
      if (!Number.isInteger(n) || !Number.isInteger(d)) {
        const f = Fraction.from(n).div(Fraction.from(d));
        n = f.n; d = f.d;
      }
      if (d === 0) throw new Error('分母が0の分数は作れません');
      if (!Number.isSafeInteger(n) || !Number.isSafeInteger(d)) throw new Error('数が大きすぎて正確に計算できません');
      if (d < 0) { n = -n; d = -d; }
      const g = gcd(n, d) || 1;
      this.n = n / g;   // 分子
      this.d = d / g;   // 分母
      Object.freeze(this);
    }

    /**
     * いろいろな形から分数を作る。
     *   Fraction.from(3) / Fraction.from(0.25) / Fraction.from("3/4") / Fraction.from("-2_1/3")（帯分数）
     *   Fraction.from("1.5") / Fraction.from(すでにある分数)
     */
    static from(x) {
      if (x instanceof Fraction) return x;
      if (typeof x === 'number') {
        if (Number.isInteger(x)) return new Fraction(x, 1);
        return Fraction.from(String(x));
      }
      const s = String(x).replace(/\s+/g, '').replace(/[−–]/g, '-');
      let m;
      if ((m = s.match(/^([+-]?)(\d+)_(\d+)\/(\d+)$/))) {          // 帯分数
        const sg = m[1] === '-' ? -1 : 1;
        const d = +m[4];
        return new Fraction(sg * (+m[2] * d + +m[3]), d);
      }
      if ((m = s.match(/^([+-]?[\d.]+)\/([+-]?[\d.]+)$/))) return Fraction.from(m[1]).div(Fraction.from(m[2]));
      if ((m = s.match(/^([+-]?)(\d*)\.?(\d*)$/)) && (m[2] || m[3])) { // 整数・小数
        const sg = m[1] === '-' ? -1 : 1;
        const k = m[3].length;
        return new Fraction(sg * +(m[2] + m[3] || '0'), Math.pow(10, k));
      }
      throw new Error('分数にできません: ' + x);
    }

    /** たし算  a.add(b) */
    add(b) { b = Fraction.from(b); const l = lcm(this.d, b.d); return new Fraction(this.n * (l / this.d) + b.n * (l / b.d), l); }
    /** ひき算  a.sub(b) */
    sub(b) { return this.add(Fraction.from(b).neg()); }
    /** かけ算  a.mul(b)（先にたすきがけで約分して、数が大きくなりすぎないようにする） */
    mul(b) {
      b = Fraction.from(b);
      const g1 = gcd(this.n, b.d) || 1, g2 = gcd(b.n, this.d) || 1;
      return new Fraction((this.n / g1) * (b.n / g2), (this.d / g2) * (b.d / g1));
    }
    /** わり算  a.div(b)（わる数の逆数をかける） */
    div(b) { b = Fraction.from(b); if (b.n === 0) throw new Error('0でわることはできません'); return this.mul(b.inv()); }
    /** 符号を反対にする */
    neg() { return new Fraction(-this.n, this.d); }
    /** 絶対値 */
    abs() { return new Fraction(Math.abs(this.n), this.d); }
    /** 逆数 */
    inv() { return new Fraction(this.d, this.n); }
    /** 累乗（指数は整数） a.pow(2) */
    pow(k) {
      let r = new Fraction(1), b = k < 0 ? this.inv() : this;
      for (let i = 0; i < Math.abs(k); i++) r = r.mul(b);
      return r;
    }
    /** 等しいか */
    equals(b) { b = Fraction.from(b); return this.n === b.n && this.d === b.d; }
    /** 大小くらべ: this が小さければ負、等しければ0、大きければ正 */
    cmp(b) { b = Fraction.from(b); return this.n * b.d - b.n * this.d; }
    /** 整数か */
    isInteger() { return this.d === 1; }
    /** 0か */
    isZero() { return this.n === 0; }
    /** 符号: 正なら1、0なら0、負なら-1 */
    sign() { return Math.sign(this.n); }
    /** 小数にする（見せるときだけ使う） */
    valueOf() { return this.n / this.d; }
    /** 式の文字列にする: "3/4" "-3/4" "2" */
    toString() { return this.d === 1 ? String(this.n) : this.n + '/' + this.d; }
    /** 帯分数の部品: 7/3 → {sign:1, whole:2, num:1, den:3} */
    toMixed() {
      const a = Math.abs(this.n);
      return { sign: Math.sign(this.n), whole: Math.floor(a / this.d), num: a % this.d, den: this.d };
    }
    /** 帯分数の文字列: 7/3 → "2_1/3"、 -7/3 → "-2_1/3"、 2/3 → "2/3"（真分数はそのまま） */
    toMixedString() {
      const m = this.toMixed();
      if (m.num === 0 || m.whole === 0) return this.toString();
      return (m.sign < 0 ? '-' : '') + m.whole + '_' + m.num + '/' + m.den;
    }
    /** 画面に出す HTML。 opt は MathRender.html と同じ。 opt.mixed=true で帯分数 */
    toHTML(opt) { opt = opt || {}; return html(opt.mixed ? this.toMixedString() : this.toString(), opt); }

    /** 最大公約数・最小公倍数（ほかのアプリからも使えるように） */
    static gcd(a, b) { return gcd(a, b); }
    static lcm(a, b) { return lcm(a, b); }

    /**
     * 通分する。分母をそろえた分子の並びを返す（約分しないままの形を見せるとき用）。
     *   Fraction.common("1/2", "1/3") → {den:6, nums:[3, 2], texts:["3/6", "2/6"]}
     */
    static common(...list) {
      const fs = list.flat().map(Fraction.from);
      const den = fs.reduce((l, f) => lcm(l, f.d), 1);
      const nums = fs.map(f => f.n * (den / f.d));
      return { den, nums, texts: nums.map(n => n + '/' + den) };
    }
  }

  /* ---------------------------------------------------------------
     9. 根号（√）の簡約
     --------------------------------------------------------------- */

  /** 係数と根号の中から文字列を作る。 sqrtText(6,2)→"6√2"  sqrtText(-1,3)→"-√3"  sqrtText(4,1)→"4" */
  function sqrtText(c, r) {
    if (c === 0 || r === 0) return '0';
    if (r === 1) return String(c);
    if (c === 1) return '√' + r;
    if (c === -1) return '-√' + r;
    return c + '√' + r;
  }

  /**
   * √n を a√b の形に直す（b はできるだけ小さい整数）。
   *   simplifySqrt(72) → {coef:6, rad:2, text:"6√2"}
   *   simplifySqrt(16) → {coef:4, rad:1, text:"4"}
   *   simplifySqrt(8, 3) → 3√8 = {coef:6, rad:2, text:"6√2"}（前に係数があるとき）
   * @param {number} n  根号の中（0以上の整数）
   * @param {number} [c=1] 根号の前の係数（整数）
   */
  function simplifySqrt(n, c) {
    if (c === undefined) c = 1;
    if (!Number.isInteger(n) || n < 0) throw new Error('√の中は0以上の整数にしてください: ' + n);
    if (n === 0) return { coef: 0, rad: 0, text: '0' };
    let k = Math.floor(Math.sqrt(n));
    while (n % (k * k) !== 0) k--;      // いちばん大きい「平方数の約数」を見つける
    const coef = c * k, rad = n / (k * k);
    return { coef, rad, text: sqrtText(coef, rad) };
  }

  /**
   * 分母の有理化: a/√b を、分母に√がない形にする（中3）。
   *   rationalize(1, 2) → 1/√2 = √2/2 → {num:1, rad:2, den:2, text:"{√2}/2"}
   *   rationalize(6, 3) → 6/√3 = 2√3 → {num:2, rad:3, den:1, text:"2√3"}
   * text は MathRender.html() にそのまま渡せる形。
   */
  function rationalize(a, b) {
    const s = simplifySqrt(b);               // √b = k√r
    if (s.rad === 1) { const f = new Fraction(a, s.coef); return { num: f.n, rad: 1, den: f.d, text: f.toString() }; }
    const f = new Fraction(a, s.coef * s.rad); // a/(k√r) = a√r/(k·r)
    const top = sqrtText(f.n, s.rad);
    return { num: f.n, rad: s.rad, den: f.d, text: f.d === 1 ? top : (top[0] === '-' ? '-{' + top.slice(1) + '}/' + f.d : '{' + top + '}/' + f.d) };
  }

  /* ---------------------------------------------------------------
     10. 外に出す
     --------------------------------------------------------------- */
  const MathRender = {
    html, render, system, splitTerms,
    tidy, coef, terms, signed, paren,
    simplifySqrt, sqrtText, rationalize,
    gcd, lcm, Fraction,
    parse,                 // 式の木の形（アプリで細かく調べたいとき用）
  };
  if (typeof window !== 'undefined') {
    window.MathRender = MathRender;
    window.Fraction = Fraction;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = MathRender;
})();
