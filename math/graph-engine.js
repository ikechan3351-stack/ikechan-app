/* =====================================================================
   graph-engine.js  ―  座標平面とグラフを描く共通ファイル
   ---------------------------------------------------------------------
   比例・反比例・一次関数・二次関数のアプリで共通に使う「座標平面」の部品です。
   SVG で描くので、外部ライブラリはいりません（オフラインでも動きます）。
   ここを直すと、この部品を使っているアプリぜんぶに反映されます。

   【読みこみ方】 math-render.js（分数の計算）を先に読みこみます。
       <script src="math-render.js"></script>
       <script src="graph-engine.js"></script>

   【おもな使い方】
       const g = GraphEngine.create(document.getElementById('box'),
                   { xmin: -5, xmax: 5, ymin: -5, ymax: 5, grid: true, controls: true });
       g.line(2, -1);                              // 直線 y = 2x − 1
       g.line(-1, 5, { color: '#1565c0', dash: true, label: 'ℓ' });
       g.plot(x => x * x, { from: -1, to: 2, ends: ['closed', 'open'] });   // 放物線（変域つき）
       g.point(2, 3, 'A');                         // 点 A(2, 3)
       const P = g.draggable(1, 1, { label: 'P', showCoords: true });       // ドラッグできる点
       P.onChange = p => console.log(p.x.toString(), p.y.toString());      // 座標は分数（Fraction）
       g.lineThrough(P, [4, 2]);                   // P を動かすと直線もついてくる

       const l1 = GraphEngine.lineFromSlope(2, -1), l2 = GraphEngine.lineFromSlope(-1, 5);
       GraphEngine.intersect(l1, l2)               // {kind:'point', x:Fraction(2), y:Fraction(3)}

   【座標の持ち方】 点の座標は中で分数（Fraction）として持ち、描くときにだけ小数にします。
   【スタイル（見た目）の指定】 どの図形にも最後に { } で渡せます。
       color 色 / width 線の太さ / dash 点線（true か "6 4" のような形） / fill ぬりの色
       opacity すきとおり具合 / label 名前 / from・to 描くはんい（x） / ends 変域のはしの点
   ===================================================================== */
(function (global) {
  'use strict';

  const NS = 'http://www.w3.org/2000/svg';
  const FONT = '"Hiragino Sans","Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif';
  // 線の色の順番（共通の色のきまりに合わせた、色覚のちがいでも区別しやすい色）
  const PALETTE = ['#e65100', '#1565c0', '#2e7d32', '#8e24aa', '#00838f'];
  const DRAG_COLOR = '#00897b';

  /** 分数クラス（math-render.js の Fraction）を取り出す */
  function Fr() {
    if (!global.Fraction) throw new Error('graph-engine.js より先に math-render.js を読みこんでください');
    return global.Fraction;
  }
  /** いろいろな値を分数にする（数・"3/4"・分数） */
  function toF(v) { return Fr().from(v); }
  /** 分数や数を、描くための小数にする */
  function toN(v) { return typeof v === 'number' ? v : (v && v.n !== undefined ? v.n / v.d : +v); }
  /** 小数を「step きざみ」の分数にする（ドラッグの位置から座標を決めるとき） */
  function roundF(v, step) {
    const F = Fr();
    const s = F.from(step);
    return s.mul(Math.round(v / toN(s)));
  }
  /** 表示用の数の文字列（マイナスは「−」） */
  function fmtNum(v, digits) {
    let s = (+v.toFixed(digits)).toString();
    if (s === '-0') s = '0';
    return s.replace('-', '−');
  }
  /** 分数を表示用の文字列にする。整数ならそのまま、分母が小さければ分数、それ以外は小数 */
  function fmtF(f, mode) {
    if (f.d === 1) return String(f.n).replace('-', '−');
    if (mode === 'decimal' || (mode !== 'fraction' && f.d > 12)) return fmtNum(f.n / f.d, 2);
    return f.toString().replace('-', '−');
  }
  /** SVG の文字に使う &, < をにがす */
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  /** きりのよい目もりの幅（1, 2, 5 × 10ⁿ）で、v 以上のいちばん小さいもの */
  function nice(v) {
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    for (const m of [1, 2, 5, 10]) if (m * p >= v - 1e-12) return m * p;
    return 10 * p;
  }
  /** 小数点以下のけた数（目もりの数字のずれ 0.30000004 などを防ぐ） */
  function decimalsOf(step) {
    const s = String(step);
    return s.includes('.') ? s.split('.')[1].length : 0;
  }

  /* ---------------------------------------------------------------
     1. 直線の計算（分数で厳密に）
     直線は { a: 傾き, b: 切片 }（y = ax + b）か、たての直線 { x: k }（x = k）で表します。
     --------------------------------------------------------------- */

  /** 傾き a と切片 b から直線を作る */
  function lineFromSlope(a, b) { return { a: toF(a), b: toF(b) }; }

  /** 2点を通る直線を作る。同じ点なら null。x がそろっていれば たての直線 {x} */
  function lineFromPoints(p1, p2) {
    const [x1, y1] = ptF(p1), [x2, y2] = ptF(p2);
    if (x1.equals(x2)) return y1.equals(y2) ? null : { x: x1 };
    const a = y2.sub(y1).div(x2.sub(x1));      // 傾き ＝ yの増加量 ÷ xの増加量
    return { a, b: y1.sub(a.mul(x1)) };        // 切片 ＝ y1 − a×x1
  }

  /** 直線の上で、x のときの y を求める */
  function evalLine(l, x) { return l.a.mul(x).add(l.b); }

  /**
   * 2本の直線の交点を求める（連立方程式を解くのと同じ）。
   * 戻り値: {kind:'point', x, y}（交わる）/ {kind:'parallel'}（平行で交わらない）/ {kind:'same'}（重なる）
   */
  function intersect(l1, l2) {
    l1 = normLine(l1); l2 = normLine(l2);
    if (l1.x !== undefined && l2.x !== undefined) return { kind: l1.x.equals(l2.x) ? 'same' : 'parallel' };
    if (l1.x !== undefined) return { kind: 'point', x: l1.x, y: evalLine(l2, l1.x) };
    if (l2.x !== undefined) return { kind: 'point', x: l2.x, y: evalLine(l1, l2.x) };
    if (l1.a.equals(l2.a)) return { kind: l1.b.equals(l2.b) ? 'same' : 'parallel' };
    const x = l2.b.sub(l1.b).div(l1.a.sub(l2.a));   // ax + b = cx + d → x = (d − b) ÷ (a − c)
    return { kind: 'point', x, y: evalLine(l1, x) };
  }

  /** 直線の式の文字列。 {a:2,b:-1} → "y=2x-1"、 {x:3} → "x=3"（MathRender.html にそのまま渡せる） */
  function lineText(l) {
    l = normLine(l);
    if (l.x !== undefined) return 'x=' + l.x.toString();
    if (global.MathRender) return 'y=' + global.MathRender.terms([[l.a, 'x'], [l.b, '']]);
    return 'y=' + l.a + 'x+' + l.b;
  }

  /** 直線の中身を分数にそろえる */
  function normLine(l) { return l.x !== undefined ? { x: toF(l.x) } : { a: toF(l.a), b: toF(l.b) }; }

  /** 点を [分数x, 分数y] にする。点は [x,y]・{x,y}・ドラッグ点・関数（() => [x,y]）のどれでもよい */
  function ptF(p) {
    if (typeof p === 'function') p = p();
    if (Array.isArray(p)) return [toF(p[0]), toF(p[1])];
    return [toF(p.x), toF(p.y)];
  }
  /** 値が関数なら呼び出して中身を取り出す（ドラッグ点と連動させるため） */
  function val(v) { return typeof v === 'function' ? v() : v; }

  /* ---------------------------------------------------------------
     2. 座標平面を作る
     --------------------------------------------------------------- */

  /**
   * 座標平面を作る。
   * @param {HTMLElement} el  入れ物の要素（中身は書きかえられる）
   * @param {object} [o]
   *   xmin, xmax, ymin, ymax … 見えるはんい（ふつう −5〜5）
   *   grid: true    … 方眼を引く
   *   step          … 目もりの幅（書かなければ、画面の大きさから自動で決める）
   *   equalScale: true … x と y の1目もりを同じ長さにする（高さは幅から決まる）
   *   height        … 高さ(px)を決めたいとき（equalScale より優先）
   *   snap: true    … ドラッグ点を整数にすいつかせる（数を書くと、そのきざみ。例 0.5）
   *   coords: true  … マウスを重ねると (x, y) を表示
   *   controls: true… ＋−・もとにもどす・すいつく・画像保存のボタンをつける
   *   pan: true     … 何もないところをドラッグすると、中心が動く（controls:true のとき初めから true）
   *   axisLabels: ['x','y'] … 軸の名前
   */
  function create(el, o) {
    Fr();   // math-render.js があるか確かめる
    o = Object.assign({
      xmin: -5, xmax: 5, ymin: -5, ymax: 5, grid: true, step: null, equalScale: true, height: null,
      snap: true, coords: true, controls: false, pan: null, axisLabels: ['x', 'y'],
    }, o || {});
    if (o.pan === null) o.pan = !!o.controls;

    const home = { xmin: o.xmin, xmax: o.xmax, ymin: o.ymin, ymax: o.ymax };   // 「もとにもどす」用
    const view = Object.assign({}, home);
    let W = 600, H = 600;
    let snapOn = o.snap !== false;
    const snapStep = typeof o.snap === 'number' ? o.snap : 1;

    // ---- 部品の組み立て ----
    el.innerHTML = '';
    const wrap = document.createElement('div');
    wrap.style.cssText = 'position:relative;width:100%;user-select:none;-webkit-user-select:none';
    el.appendChild(wrap);
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('xmlns', NS);
    svg.style.cssText = 'display:block;width:100%;background:#fff;border-radius:12px;touch-action:none;font-family:' + FONT;
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', '座標平面');
    wrap.appendChild(svg);
    const layer = name => { const gEl = document.createElementNS(NS, 'g'); gEl.setAttribute('data-layer', name); svg.appendChild(gEl); return gEl; };
    const gBack = layer('back');      // 方眼・軸・目もり
    const gShape = layer('shape');    // 直線・グラフ・点など
    const gDrag = layer('drag');      // ドラッグできる点
    const gRead = layer('read');      // マウス位置の座標表示（画像保存には入れない）

    const shapes = [];                // 描く図形の一覧
    const handles = [];               // ドラッグ点の一覧
    const listeners = [];             // onChange（どれかの点が動いたとき）
    let colorNo = 0;

    // ---- 座標の変換（数学の座標 ⇔ 画面の位置） ----
    const X = x => (x - view.xmin) / (view.xmax - view.xmin) * W;
    const Y = y => H - (y - view.ymin) / (view.ymax - view.ymin) * H;
    const unitX = () => W / (view.xmax - view.xmin);   // 1 あたりの画面の長さ
    const unitY = () => H / (view.ymax - view.ymin);
    /** マウス・指の位置（画面）を、数学の座標（小数）にする */
    function clientToData(e) {
      const r = svg.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width * W, py = (e.clientY - r.top) / r.height * H;
      return { x: view.xmin + px / W * (view.xmax - view.xmin), y: view.ymin + (H - py) / H * (view.ymax - view.ymin) };
    }

    // ---- 大きさを入れ物に合わせる ----
    function measure() {
      W = Math.max(200, Math.round(wrap.clientWidth || 600));
      if (o.height) H = o.height;
      else if (o.equalScale) H = Math.round(W * (home.ymax - home.ymin) / (home.xmax - home.xmin));
      else H = Math.round(W * 0.75);
      svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
      svg.setAttribute('width', W);
      svg.setAttribute('height', H);
      svg.style.height = 'auto';
    }

    /* ---- 方眼・軸・目もり・矢印・x y O の文字 ---- */
    function drawBack() {
      const ux = unitX(), uy = unitY();
      // 目もりの幅: 指定があればそれ（せますぎるときは広げる）。なければ、1目もりが28〜90pxのあいだは 1 きざみ、
      // それより大きくしたら細かく、小さくしたら 2・5・10… きざみにする
      const auto = u => (u >= 28 && u < 90 ? 1 : nice(28 / u));
      const sx = o.step && o.step * ux >= 14 ? o.step : auto(ux);
      const sy = o.step && o.step * uy >= 14 ? o.step : auto(uy);
      // 数字を書く間かく（数字どうしが重ならないように。小数の数字は長いので広めにとる）
      const lx = sx * Math.max(1, Math.ceil((sx % 1 ? 52 : 34) / (sx * ux)));
      const ly = sy * Math.max(1, Math.ceil((sy % 1 ? 34 : 26) / (sy * uy)));
      const dx = decimalsOf(lx), dy = decimalsOf(ly);
      let h = '';
      if (o.grid) {
        let p = '';
        for (let k = Math.ceil(view.xmin / sx); k * sx <= view.xmax + 1e-9; k++) { const x = X(k * sx); p += `M${x.toFixed(1)},0V${H}`; }
        for (let k = Math.ceil(view.ymin / sy); k * sy <= view.ymax + 1e-9; k++) { const y = Y(k * sy); p += `M0,${y.toFixed(1)}H${W}`; }
        h += `<path d="${p}" stroke="#cfd8dc" stroke-width="1" fill="none"/>`;
      }
      // 軸の位置（原点が見えないときは、画面のはしに寄せる）
      const X0 = Math.min(Math.max(X(0), 0), W), Y0 = Math.min(Math.max(Y(0), 0), H);
      h += `<path d="M0,${Y0}H${W - 2}M${X0},${H}V2" stroke="#37474f" stroke-width="2" fill="none"/>`;
      // 矢印（x軸は右、y軸は上）
      h += `<path d="M${W},${Y0} l-14,-6 v12 z M${X0},0 l-6,14 h12 z" fill="#37474f"/>`;
      // 目もりの数字（白いふちどりで方眼の上でも読みやすく）
      const T = 'font-size="17" fill="#37474f" stroke="#fff" stroke-width="4" paint-order="stroke" stroke-linejoin="round"';
      const below = Y0 + 22 <= H - 4;
      for (let k = Math.ceil(view.xmin / lx); k * lx <= view.xmax + 1e-9; k++) {
        const v = k * lx; if (Math.abs(v) < 1e-9) continue;
        const x = X(v); if (x < 10 || x > W - 22) continue;
        h += `<path d="M${x},${Y0 - 5}V${Y0 + 5}" stroke="#37474f" stroke-width="2"/>`;
        h += `<text x="${x}" y="${below ? Y0 + 22 : Y0 - 9}" text-anchor="middle" ${T}>${fmtNum(v, dx)}</text>`;
      }
      const left = X0 - 9 >= 30;
      for (let k = Math.ceil(view.ymin / ly); k * ly <= view.ymax + 1e-9; k++) {
        const v = k * ly; if (Math.abs(v) < 1e-9) continue;
        const y = Y(v); if (y < 24 || y > H - 8) continue;
        h += `<path d="M${X0 - 5},${y}H${X0 + 5}" stroke="#37474f" stroke-width="2"/>`;
        h += `<text x="${left ? X0 - 9 : X0 + 9}" y="${y + 6}" text-anchor="${left ? 'end' : 'start'}" ${T}>${fmtNum(v, dy)}</text>`;
      }
      // x・y・O の文字
      const L = 'font-size="24" font-style="italic" font-weight="bold" fill="#263238" stroke="#fff" stroke-width="5" paint-order="stroke"';
      h += `<text x="${W - 10}" y="${below ? Y0 + 26 : Y0 - 12}" text-anchor="end" ${L}>${esc(o.axisLabels[0])}</text>`;
      h += `<text x="${X0 + 12}" y="22" ${L}>${esc(o.axisLabels[1])}</text>`;
      if (X(0) >= 0 && X(0) <= W && Y(0) >= 0 && Y(0) <= H) {
        h += `<text x="${X0 - 7}" y="${Y0 + 22}" text-anchor="end" ${L.replace('italic', 'normal')}>O</text>`;
      }
      gBack.innerHTML = h;
    }

    /* ---- 図形を描く ---- */
    // 線のスタイル（色・太さ・点線）を SVG の属性にする
    function strokeAttr(s) {
      const dash = s.dash === true ? '9 7' : (s.dash || '');
      return `stroke="${s.color}" stroke-width="${s.width}" fill="none" stroke-linecap="round" stroke-linejoin="round"` +
        (dash ? ` stroke-dasharray="${dash}"` : '') + (s.opacity != null ? ` stroke-opacity="${s.opacity}"` : '');
    }
    // 名前（ラベル）の文字
    function labelSVG(x, y, text, color, anchor) {
      return `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" text-anchor="${anchor || 'start'}" font-size="22" font-weight="bold" ` +
        `fill="${color}" stroke="#fff" stroke-width="5" paint-order="stroke" stroke-linejoin="round">${esc(text)}</text>`;
    }
    // 変域のはしの点（closed＝●ふくむ、open＝○ふくまない）
    function endSVG(x, y, kind, color) {
      if (!kind || !isFinite(y)) return '';
      return `<circle cx="${X(x).toFixed(1)}" cy="${Y(y).toFixed(1)}" r="6.5" stroke="${color}" stroke-width="3" fill="${kind === 'open' ? '#fff' : color}"/>`;
    }
    // 線の名前を置く。右はしで切れるときは、線の左がわに出す
    function lineLabel(p, text, color) {
      if (!p) return '';
      const x = X(p[0]), y = Y(p[1]);
      const w = String(text).length * 14;
      return x + 8 + w > W - 4 ? labelSVG(x - 8, y - 10, text, color, 'end') : labelSVG(x + 8, y - 10, text, color);
    }
    // ラベルを置く場所: 画面の右のほうで、線が見えているところ
    function labelPlace(f, x0, x1) {
      for (let i = 0; i <= 40; i++) {
        const x = x1 - (x1 - x0) * (0.06 + i / 48);
        const y = f(x);
        if (isFinite(y) && y > view.ymin + (view.ymax - view.ymin) * 0.08 && y < view.ymax - (view.ymax - view.ymin) * 0.08) return [x, y];
      }
      return null;
    }

    // 図形の種類ごとの描き方（s は図形1つ分のデータ、st はスタイル）
    const DRAW = {
      // 直線 y = ax + b（たての直線 x = k もふくむ）
      line(s, st) {
        const l = normLine(val(s.l));
        if (l.x !== undefined) {
          const x = X(toN(l.x));
          return `<path d="M${x},${H}V0" ${strokeAttr(st)}/>` + (st.label ? labelSVG(x + 8, 30, st.label, st.color) : '');
        }
        const a = toN(l.a), b = toN(l.b);
        const x0 = st.from != null ? toN(val(st.from)) : view.xmin, x1 = st.to != null ? toN(val(st.to)) : view.xmax;
        let h = `<path d="M${X(x0).toFixed(1)},${Y(a * x0 + b).toFixed(1)}L${X(x1).toFixed(1)},${Y(a * x1 + b).toFixed(1)}" ${strokeAttr(st)}/>`;
        if (st.ends) h += endSVG(x0, a * x0 + b, st.ends[0], st.color) + endSVG(x1, a * x1 + b, st.ends[1], st.color);
        if (st.label) h += lineLabel(labelPlace(x => a * x + b, x0, x1), st.label, st.color);
        return h;
      },
      // 関数のグラフ y = f(x)。とびとびのところ（反比例の x=0 など）では線を切る
      plot(s, st) {
        const f = s.f;
        const x0 = Math.max(st.from != null ? toN(val(st.from)) : view.xmin, view.xmin - 1);
        const x1 = Math.min(st.to != null ? toN(val(st.to)) : view.xmax, view.xmax + 1);
        const n = Math.max(60, Math.round(W / 2));
        const span = view.ymax - view.ymin, lim = span * 4;
        let d = '', pen = false, prev = null;
        for (let i = 0; i <= n; i++) {
          const x = x0 + (x1 - x0) * i / n;
          let y = f(x);
          if (typeof y !== 'number') y = toN(y);
          const ok = isFinite(y) && y > view.ymin - lim && y < view.ymax + lim;
          // となりの点と大きくはなれていたら（グラフがとぶところ）線をつなげない
          if (ok && prev !== null && Math.abs(y - prev) > span * 2 && Math.sign(y) !== Math.sign(prev)) pen = false;
          if (ok) { d += (pen ? 'L' : 'M') + X(x).toFixed(1) + ',' + Y(y).toFixed(1); pen = true; prev = y; }
          else { pen = false; prev = null; }
        }
        let h = `<path d="${d}" ${strokeAttr(st)}/>`;
        if (st.ends) h += endSVG(x0, toN(f(x0)), st.ends[0], st.color) + endSVG(x1, toN(f(x1)), st.ends[1], st.color);
        if (st.label) h += lineLabel(labelPlace(x => toN(f(x)), x0, x1), st.label, st.color);
        return h;
      },
      // 点（動かない点）
      point(s, st) {
        const [fx, fy] = ptF(s.p);
        const x = X(toN(fx)), y = Y(toN(fy));
        let text = st.label || '';
        if (st.showCoords) text += `(${fmtF(fx, st.format)}, ${fmtF(fy, st.format)})`;
        return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${st.r || 6}" fill="${st.open ? '#fff' : st.color}" stroke="${st.color}" stroke-width="2.5"/>` +
          (text ? labelSVG(x + 10, y - 10, text, st.color) : '');
      },
      // 線分
      segment(s, st) {
        const [a, b] = [ptF(s.p1), ptF(s.p2)];
        return `<path d="M${X(toN(a[0])).toFixed(1)},${Y(toN(a[1])).toFixed(1)}L${X(toN(b[0])).toFixed(1)},${Y(toN(b[1])).toFixed(1)}" ${strokeAttr(st)}/>`;
      },
      // 多角形（点の並び）
      polygon(s, st) {
        const pts = val(s.pts).map(ptF).map(([x, y]) => X(toN(x)).toFixed(1) + ',' + Y(toN(y)).toFixed(1)).join(' ');
        return `<polygon points="${pts}" ${strokeAttr(st).replace('fill="none"', `fill="${st.fill || 'none'}" fill-opacity="${st.fillOpacity != null ? st.fillOpacity : 0.25}"`)}/>`;
      },
      // ぬり（2つのグラフの間。下のグラフを書かなければ x軸との間）
      area(s, st) {
        const f = s.f, g = s.g || (() => 0);
        const x0 = toN(val(st.from != null ? st.from : view.xmin)), x1 = toN(val(st.to != null ? st.to : view.xmax));
        const n = 120, top = [], bot = [];
        for (let i = 0; i <= n; i++) {
          const x = x0 + (x1 - x0) * i / n;
          top.push(X(x).toFixed(1) + ',' + Y(toN(f(x))).toFixed(1));
          bot.unshift(X(x).toFixed(1) + ',' + Y(toN(g(x))).toFixed(1));
        }
        return `<polygon points="${top.concat(bot).join(' ')}" fill="${st.fill || st.color}" fill-opacity="${st.fillOpacity != null ? st.fillOpacity : 0.25}" stroke="none"/>`;
      },
      // 文字
      text(s, st) {
        const [fx, fy] = ptF(s.p);
        return labelSVG(X(toN(fx)), Y(toN(fy)), val(s.text), st.color, st.anchor);
      },
    };

    function drawShapes() {
      let h = '';
      for (const s of shapes) {
        if (s.style.hidden) continue;
        try { h += DRAW[s.kind](s, s.style); } catch (e) { /* 描けない図形（分母0など）はとばす */ }
      }
      gShape.innerHTML = h;
    }

    /** 図形を一覧に足す（あとで .remove()・.set() できる物を返す） */
    function add(kind, data, style, isLine) {
      style = Object.assign({}, style || {});
      if (!style.color) style.color = isLine === false ? '#263238' : PALETTE[colorNo++ % PALETTE.length];
      if (style.width == null) style.width = 3.5;
      const s = Object.assign({ kind, style }, data);
      s.remove = () => { const i = shapes.indexOf(s); if (i >= 0) shapes.splice(i, 1); redraw(); };
      s.set = (newData, newStyle) => { Object.assign(s, newData || {}); Object.assign(s.style, newStyle || {}); redraw(); return s; };
      shapes.push(s);
      redraw();
      return s;
    }

    /* ---- ドラッグできる点 ---- */
    function draggable(x, y, opt) {
      opt = Object.assign({ color: DRAG_COLOR, label: '', showCoords: false, snap: null, constrain: null, format: null }, opt || {});
      const gp = document.createElementNS(NS, 'g');
      gp.innerHTML = `<circle r="24" fill="${opt.color}" fill-opacity="0.12" data-hit="1" style="cursor:grab"/>` +
        `<circle r="9" fill="${opt.color}" stroke="#fff" stroke-width="3" pointer-events="none"/>` +
        `<text pointer-events="none" font-size="22" font-weight="bold" fill="${opt.color}" stroke="#fff" stroke-width="5" paint-order="stroke" stroke-linejoin="round"></text>`;
      gp.setAttribute('tabindex', '0');
      gp.setAttribute('role', 'slider');
      gp.style.outline = 'none';
      gDrag.appendChild(gp);
      const hit = gp.children[0], txt = gp.children[2];

      const h = {
        x: toF(x), y: toF(y), opt, onChange: opt.onChange || null, onEnd: opt.onEnd || null,
        /** 座標を決める（コードから動かすとき）。silent:true なら onChange を呼ばない */
        set(nx, ny, silent) {
          let fx = toF(nx), fy = toF(ny);
          if (opt.constrain) { const r = opt.constrain(fx, fy); fx = toF(r[0]); fy = toF(r[1]); }
          if (fx.equals(h.x) && fy.equals(h.y)) return h;
          h.x = fx; h.y = fy;
          redraw();
          if (!silent) fire(h);
          return h;
        },
        /** [x, y] の形で返す（ほかの図形の点として渡せる） */
        get pt() { return [h.x, h.y]; },
        remove() { gp.remove(); handles.splice(handles.indexOf(h), 1); redraw(); },
        el: gp,
      };
      /** すいつきの幅（この点だけの指定 → 平面全体の指定） */
      const stepOf = () => {
        const sn = opt.snap !== null ? opt.snap : (snapOn ? snapStep : false);
        return sn === false ? 0.01 : (sn === true ? 1 : sn);
      };
      /** 画面の位置から座標を決めて動かす */
      function moveTo(px, py) {
        const st = stepOf();
        const cx = Math.min(Math.max(px, view.xmin), view.xmax), cy = Math.min(Math.max(py, view.ymin), view.ymax);
        h.set(roundF(cx, st), roundF(cy, st));
      }
      h.draw = () => {
        gp.setAttribute('transform', `translate(${X(toN(h.x)).toFixed(1)},${Y(toN(h.y)).toFixed(1)})`);
        const fm = opt.format || (stepOf() === 0.01 ? 'decimal' : 'auto');
        let t = opt.label || '';
        if (opt.showCoords) t += `(${fmtF(h.x, fm)}, ${fmtF(h.y, fm)})`;
        txt.textContent = t;
        // 右上にはみ出すときは、文字を左下に出す
        const right = X(toN(h.x)) > W - 150, top = Y(toN(h.y)) < 40;
        txt.setAttribute('x', right ? -14 : 14);
        txt.setAttribute('y', top ? 34 : -14);
        txt.setAttribute('text-anchor', right ? 'end' : 'start');
        gp.setAttribute('aria-label', `${opt.label || '点'} x=${h.x} y=${h.y}`);
      };

      // マウス・タッチでドラッグ（pointer events）
      let dragging = false;
      hit.addEventListener('pointerdown', e => {
        e.preventDefault(); e.stopPropagation();
        dragging = true; hit.setPointerCapture(e.pointerId); hit.style.cursor = 'grabbing';
        gp.focus({ preventScroll: true });
      });
      hit.addEventListener('pointermove', e => {
        if (!dragging) return;
        const p = clientToData(e);
        moveTo(p.x, p.y);
        showRead(p, true);
      });
      const end = e => {
        if (!dragging) return;
        dragging = false; hit.style.cursor = 'grab';
        try { hit.releasePointerCapture(e.pointerId); } catch (_) { /* すでにはなれている */ }
        hideRead();
        if (h.onEnd) h.onEnd(h);
      };
      hit.addEventListener('pointerup', end);
      hit.addEventListener('pointercancel', end);
      // キーボードの矢印でも動かせる
      gp.addEventListener('keydown', e => {
        const st = Fr().from(stepOf() === 0.01 ? 0.1 : stepOf());
        const mv = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }[e.key];
        if (!mv) return;
        e.preventDefault();
        h.set(h.x.add(st.mul(mv[0])), h.y.add(st.mul(mv[1])));
      });
      handles.push(h);
      h.draw();
      redraw();
      return h;
    }

    /** どれかの点が動いたことを知らせる */
    function fire(h) {
      if (h.onChange) h.onChange(h);
      listeners.forEach(fn => fn(h, api));
    }

    /* ---- マウス位置の座標表示 ---- */
    function showRead(p, onPoint) {
      if (!o.coords && !onPoint) return;
      const dg = unitX() >= 100 ? 2 : (unitX() >= 12 ? 1 : 0);
      const t = `(${fmtNum(p.x, dg)}, ${fmtNum(p.y, dg)})`;
      const px = X(p.x), py = Y(p.y);
      const right = px > W - 140, top = py < 50;
      gRead.innerHTML = (onPoint ? '' : `<circle cx="${px}" cy="${py}" r="4" fill="#263238"/>`) +
        `<text x="${right ? px - 14 : px + 14}" y="${top ? py + 36 : py - 26}" text-anchor="${right ? 'end' : 'start'}" ` +
        `font-size="18" fill="#263238" stroke="#fffde7" stroke-width="7" paint-order="stroke" stroke-linejoin="round">${t}</text>`;
    }
    function hideRead() { gRead.innerHTML = ''; }

    // 何もないところの操作: マウスを重ねる → 座標表示、ドラッグ → 中心を動かす
    let panFrom = null;
    svg.addEventListener('pointermove', e => {
      if (panFrom) {
        const r = svg.getBoundingClientRect();
        const dx = (e.clientX - panFrom.cx) / r.width * (view.xmax - view.xmin);
        const dy = (e.clientY - panFrom.cy) / r.height * (view.ymax - view.ymin);
        setView({ xmin: panFrom.v.xmin - dx, xmax: panFrom.v.xmax - dx, ymin: panFrom.v.ymin + dy, ymax: panFrom.v.ymax + dy });
        return;
      }
      if (e.target.getAttribute('data-hit')) return;
      if (e.pointerType === 'mouse') showRead(clientToData(e));
    });
    svg.addEventListener('pointerleave', () => { if (!panFrom) hideRead(); });
    svg.addEventListener('pointerdown', e => {
      if (!o.pan || e.target.getAttribute('data-hit')) return;
      panFrom = { cx: e.clientX, cy: e.clientY, v: Object.assign({}, view) };
      svg.setPointerCapture(e.pointerId);
      hideRead();
    });
    const panEnd = () => { panFrom = null; };
    svg.addEventListener('pointerup', panEnd);
    svg.addEventListener('pointercancel', panEnd);

    /* ---- 見えるはんい（ズーム・中心の移動） ---- */
    function setView(v) { Object.assign(view, v); redraw(true); return api; }
    /** ズーム。 factor が 2 なら2倍に大きく（はんいは半分）、0.5 なら小さく。中心 (cx, cy) は書かなければ今の中心 */
    function zoom(factor, cx, cy) {
      if (cx == null) cx = (view.xmin + view.xmax) / 2;
      if (cy == null) cy = (view.ymin + view.ymax) / 2;
      const hw = (view.xmax - view.xmin) / 2 / factor, hh = (view.ymax - view.ymin) / 2 / factor;
      if (hw < 0.25 || hw > 500) return api;   // 大きくしすぎ・小さくしすぎをふせぐ
      return setView({ xmin: cx - hw, xmax: cx + hw, ymin: cy - hh, ymax: cy + hh });
    }
    /** 中心を (cx, cy) に動かす（はんいの広さはそのまま） */
    function center(cx, cy) {
      const hw = (view.xmax - view.xmin) / 2, hh = (view.ymax - view.ymin) / 2;
      return setView({ xmin: cx - hw, xmax: cx + hw, ymin: cy - hh, ymax: cy + hh });
    }
    /** 中心をずらす（dx, dy は数学の座標の長さ） */
    function pan(dx, dy) { return setView({ xmin: view.xmin + dx, xmax: view.xmax + dx, ymin: view.ymin + dy, ymax: view.ymax + dy }); }
    /** 最初のはんいにもどす */
    function resetView() { return setView(Object.assign({}, home)); }

    /* ---- 描きなおし（まとめて1回にする） ---- */
    let queued = false, backDirty = true;
    function redraw(back) {
      if (back) backDirty = true;
      if (queued) return;
      queued = true;
      const run = () => { queued = false; drawNow(); };
      if (global.requestAnimationFrame) requestAnimationFrame(run); else run();
    }
    function drawNow() {
      if (backDirty) { drawBack(); backDirty = false; }
      drawShapes();
      handles.forEach(h => h.draw());
    }

    /* ---- 画像（PNG）にして保存 ---- */
    /** PNG の data URL を作る（Promise）。scale は画質（2 なら2倍の細かさ） */
    function toPNG(scale) {
      scale = scale || 2;
      drawNow();
      const clone = svg.cloneNode(true);
      clone.querySelector('[data-layer="read"]').innerHTML = '';
      clone.querySelectorAll('[data-hit]').forEach(c => c.remove());
      const bg = document.createElementNS(NS, 'rect');
      bg.setAttribute('width', W); bg.setAttribute('height', H); bg.setAttribute('fill', '#fff');
      clone.insertBefore(bg, clone.firstChild);
      clone.setAttribute('font-family', FONT);
      const data = new XMLSerializer().serializeToString(clone);
      return new Promise((ok, ng) => {
        const img = new Image();
        img.onload = () => {
          const cv = document.createElement('canvas');
          cv.width = W * scale; cv.height = H * scale;
          const cx = cv.getContext('2d');
          cx.scale(scale, scale);
          cx.drawImage(img, 0, 0, W, H);
          ok(cv.toDataURL('image/png'));
        };
        img.onerror = ng;
        img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(data);
      });
    }
    /** PNG をダウンロードする */
    function savePNG(name) {
      return toPNG(2).then(url => {
        const a = document.createElement('a');
        a.href = url; a.download = name || 'グラフ.png';
        document.body.appendChild(a); a.click(); a.remove();
        return url;
      });
    }

    /* ---- ボタン（＋ − もどす すいつく 画像） ---- */
    let snapBtn = null;
    if (o.controls) {
      const bar = document.createElement('div');
      // ボタンは座標平面の上の段に置く（グラフや x・y の文字に重ならないように）
      bar.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;padding:6px 6px 0';
      const mk = (text, title, fn) => {
        const b = document.createElement('button');
        b.type = 'button'; b.textContent = text; b.title = title; b.setAttribute('aria-label', title);
        b.style.cssText = 'min-width:44px;min-height:44px;padding:2px 10px;border:2px solid #b2dfdb;background:rgba(255,255,255,.92);' +
          'border-radius:12px;font:bold 18px ' + FONT + ';color:#00695c;cursor:pointer;touch-action:manipulation';
        b.addEventListener('click', fn);
        bar.appendChild(b);
        return b;
      };
      mk('＋', '大きくする（ズーム）', () => zoom(1.5));
      mk('－', '小さくする（広く見る）', () => zoom(1 / 1.5));
      mk('⟲', 'もとの大きさにもどす', () => resetView());
      snapBtn = mk('', '点を整数にすいつかせる／すいつかせない', () => setSnap(!snapOn));
      mk('📷', 'グラフを画像で保存', () => savePNG());
      wrap.insertBefore(bar, svg);
    }
    /** ドラッグ点を整数（すいつきの幅）にすいつかせるか */
    function setSnap(on) {
      snapOn = !!on;
      if (snapBtn) { snapBtn.textContent = snapOn ? '✔すいつく' : 'すいつかない'; snapBtn.setAttribute('aria-pressed', snapOn); }
      handles.forEach(h => { if (snapOn && h.opt.snap === null) h.set(roundF(toN(h.x), snapStep), roundF(toN(h.y), snapStep)); });
      redraw();
      return api;
    }

    // 画面の大きさがかわったら描きなおす
    measure();
    if (global.ResizeObserver) {
      new ResizeObserver(() => { const w = Math.round(wrap.clientWidth); if (w && w !== W) { measure(); backDirty = true; drawNow(); } }).observe(wrap);
    }

    /* ---- 外から使う関数 ---- */
    const api = {
      /** 直線。 line(2, -1) で y=2x−1。 line({a,b}) や line({x:3})（たての直線）、line(() => 直線) でもよい */
      line(a, b, style) {
        if (typeof a === 'object' && !(a instanceof Fr()) || typeof a === 'function') return add('line', { l: a }, b);
        return add('line', { l: lineFromSlope(a, b) }, style);
      },
      /** 2点を通る直線（点にドラッグ点を渡すと、いっしょに動く） */
      lineThrough(p1, p2, style) { return add('line', { l: () => lineFromPoints(p1, p2) || { x: ptF(p1)[0] } }, style); },
      /** 関数のグラフ。 plot(x => x*x) */
      plot(f, style) { return add('plot', { f }, style); },
      /** 点。 point(2, 3, 'A')。 x に [x,y] やドラッグ点を渡してもよい： point(P, null, 'P') */
      point(x, y, label, style) {
        const p = (typeof x === 'object' || typeof x === 'function') && !(x instanceof Fr()) ? x : [x, y];
        return add('point', { p }, Object.assign({ label }, style), true);
      },
      /** 線分 */
      segment(p1, p2, style) { return add('segment', { p1, p2 }, style); },
      /** 多角形。 polygon([[0,0],[3,0],[0,2]], {fill:'#ffcc80'}) */
      polygon(pts, style) { return add('polygon', { pts }, style); },
      /** ぬり（2つのグラフの間）。 area(x => x*x, null, {from:0, to:2}) は放物線と x軸の間 */
      area(f, g, style) { return add('area', { f, g }, style); },
      /** 文字。 text(1, 2, 'A') */
      text(x, y, str, style) { return add('text', { p: [x, y], text: str }, style, false); },
      draggable, setSnap,
      /** どれかのドラッグ点が動いたときに呼ばれる関数を登録する。 fn(動いた点, 座標平面) */
      onChange(fn) { listeners.push(fn); return api; },
      /** 図形とドラッグ点を全部消す（軸と方眼は残る） */
      clear() { shapes.length = 0; handles.slice().forEach(h => h.remove()); colorNo = 0; redraw(); return api; },
      zoom, center, pan, setView, resetView,
      /** 今の見えるはんい */
      get view() { return Object.assign({}, view); },
      get snap() { return snapOn; },
      redraw: () => { backDirty = true; drawNow(); return api; },
      toPNG, savePNG,
      /** 画面の位置(clientX, clientY)を数学の座標にする */
      toData: (cx, cy) => clientToData({ clientX: cx, clientY: cy }),
      svg, shapes, handles,
    };
    if (snapBtn) setSnap(snapOn);   // ボタンの文字を今の状態にする
    drawNow();
    return api;
  }

  const GraphEngine = { create, lineFromSlope, lineFromPoints, intersect, evalLine, lineText, PALETTE };
  global.GraphEngine = GraphEngine;
  if (typeof module !== 'undefined' && module.exports) module.exports = GraphEngine;
})(typeof window !== 'undefined' ? window : globalThis);
