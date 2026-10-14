/* =====================================================================
   動点エンジン.js  ―  図形の辺の上を動く点と、面積の変わり方を計算する共通ファイル
   ---------------------------------------------------------------------
   中2「動く点Pと面積のグラフ」（一次関数）と、中3「二次方程式の利用・動点」（二次関数）で使います。
   図形を「頂点の座標（cm）」、点の動きを「通る頂点の順番と速さ」、面積を「どの点でできる多角形か」で書くと、
   面積を自動で計算し、点が角に着く時刻で区間を区切って、区間ごとの式（y＝ax＋b や y＝ax²＋bx＋c）を出します。
   計算はぜんぶ分数（Fraction）で行うので、式の係数も正確です。

   【読みこみ方】 math-render.js（分数の計算）を先に読みこみます。
       <script src="math-render.js"></script>
       <script src="動点エンジン.js"></script>

   【使い方】
       const m = DottenEngine.create({
         verts: { A: [0, 4], B: [0, 0], C: [6, 0], D: [6, 4] },     // 頂点の座標（cm。y は上が正）
         movers: [{ name: 'P', path: ['A', 'B', 'C', 'D'], speed: 1 }],  // 点P は A→B→C→D を毎秒 1cm
         area: ['A', 'P', 'D']                                       // △APD の面積
       });
       m.T                 // 動き終わる時刻（秒）… 14
       m.area(5)           // 5秒後の面積（Fraction）… 12
       m.pt('P', 5)        // 5秒後の点Pの座標 [Fraction, Fraction] … [1, 0]
       m.pieces()          // 区間ごとの式 [{ from, to, c: [c0, c1, c2], on: { P: 'AB' } }, …]
       m.src(piece)        // 'y=3x' のような式（MathRender にそのまま渡せる）

   【二次関数（中3）】 movers に2つの点を書くと（例：P と Q が同時に動く）、面積は x の二次式になり、
   pieces() の c[2]（x² の係数）が 0 でなくなります。
   【注意】 辺の長さが整数・分数にならない図形（√ が出る長さ）は使えません（エラーになります）。
   ===================================================================== */
(function (global) {
  'use strict';

  function Fr() {
    if (!global.Fraction) throw new Error('動点エンジン.js より先に math-render.js を読みこんでください');
    return global.Fraction;
  }
  const F = (v) => Fr().from(v);

  /** 分数の平方根（分子・分母がどちらも平方数のときだけ）。ならなければ null */
  function sqrtF(f) {
    f = F(f);
    if (f.sign() < 0) return null;
    const n = Math.round(Math.sqrt(f.n)), d = Math.round(Math.sqrt(f.d));
    return n * n === f.n && d * d === f.d ? new (Fr())(n, d) : null;
  }

  /**
   * 動点のようすを作る。
   * @param {object} def
   *   verts  … 頂点の座標 { 名前: [x, y] }（cm）
   *   movers … 動く点 [{ name, path: [頂点の名前…], speed（cm/秒）, start（動き出す時刻。書かなければ 0）}]
   *   area   … 面積を求める多角形の点の名前の順番（頂点の名前と、動く点の名前がまざってよい）
   *   T      … 見る時間の長さ（書かなければ、いちばん遅く動き終わる時刻）
   */
  function create(def) {
    const V = {};
    Object.keys(def.verts).forEach(k => { V[k] = def.verts[k].map(F); });
    // 動く点ごとに、辺ごとの区間（どの時刻からどの時刻まで、どの辺の上か）を作る
    const movers = def.movers.map(m => {
      const speed = F(m.speed || 1), segs = [];
      let t = F(m.start || 0);
      for (let i = 0; i + 1 < m.path.length; i++) {
        const p0 = V[m.path[i]], p1 = V[m.path[i + 1]];
        const len = sqrtF(p1[0].sub(p0[0]).pow(2).add(p1[1].sub(p0[1]).pow(2)));
        if (!len) throw new Error('辺 ' + m.path[i] + m.path[i + 1] + ' の長さが整数・分数にならない');
        const t1 = t.add(len.div(speed));
        segs.push({ from: m.path[i], to: m.path[i + 1], edge: m.path[i] + m.path[i + 1], t0: t, t1, p0, p1, len });
        t = t1;
      }
      return { name: m.name, speed, segs, start: F(m.start || 0), end: t };
    });
    const T = def.T != null ? F(def.T) : movers.reduce((a, m) => (m.end.cmp(a) > 0 ? m.end : a), F(0));

    /** 動く点の、時刻 t の区間（辺）。動き出す前は最初の辺、動き終わったあとは最後の辺 */
    function segAt(name, t) {
      const m = movers.find(q => q.name === name);
      t = F(t);
      return m.segs.find(s => t.cmp(s.t1) <= 0) || m.segs[m.segs.length - 1];
    }
    /** 点の座標（頂点ならそのまま、動く点なら時刻 t の位置） */
    function pt(name, t) {
      if (V[name]) return V[name];
      const m = movers.find(q => q.name === name);
      if (!m) throw new Error('点 ' + name + ' がない');
      t = F(t);
      if (t.cmp(m.start) <= 0) return m.segs[0].p0;
      if (t.cmp(m.end) >= 0) return m.segs[m.segs.length - 1].p1;
      const s = segAt(name, t), k = t.sub(s.t0).div(s.t1.sub(s.t0));
      return [s.p0[0].add(s.p1[0].sub(s.p0[0]).mul(k)), s.p0[1].add(s.p1[1].sub(s.p0[1]).mul(k))];
    }
    /** 多角形の面積（符号つき。くつひもの公式） */
    function signedArea(names, t) {
      const ps = names.map(n => pt(n, t));
      let s = F(0);
      ps.forEach((p, i) => { const q = ps[(i + 1) % ps.length]; s = s.add(p[0].mul(q[1]).sub(q[0].mul(p[1]))); });
      return s.div(2);
    }
    const areaNames = def.area;
    function area(t, names) { return signedArea(names || areaNames, t).abs(); }

    /** 区間の切れ目（0・T と、どれかの点が角に着く時刻） */
    function breaks() {
      const set = [F(0), T];
      movers.forEach(m => { set.push(m.start); m.segs.forEach(s => set.push(s.t1)); });
      const ok = set.filter(t => t.sign() >= 0 && t.cmp(T) <= 0).sort((a, b) => a.cmp(b));
      return ok.filter((t, i) => i === 0 || !t.equals(ok[i - 1]));
    }
    /**
     * 区間ごとの式。面積は区間の中では x の多項式（動く点が1つなら一次式、2つなら二次式まで）。
     * 区間の両はしと まん中の3点の値から、二次式 c2 x² ＋ c1 x ＋ c0 を正確に求める。
     */
    function pieces(names) {
      names = names || areaNames;
      const bs = breaks(), out = [];
      for (let i = 0; i + 1 < bs.length; i++) {
        const a = bs[i], b = bs[i + 1], m = a.add(b).div(2);
        // 区間の中で面積の符号は変わらないので、まん中の符号で絶対値をとる
        const sm = signedArea(names, m), sg = sm.sign() < 0 ? -1 : 1;
        const va = signedArea(names, a).mul(sg), vm = sm.mul(sg), vb = signedArea(names, b).mul(sg);
        const d1 = vm.sub(va).div(m.sub(a)), d2 = vb.sub(vm).div(b.sub(m));
        const c2 = d2.sub(d1).div(b.sub(a));
        const c1 = d1.sub(c2.mul(a.add(m)));
        const c0 = va.sub(d1.mul(a)).add(c2.mul(a).mul(m));
        const on = {};
        movers.forEach(mv => { const s = segAt(mv.name, m); on[mv.name] = m.cmp(mv.start) < 0 ? null : (m.cmp(mv.end) > 0 ? null : s.edge); });
        out.push({ from: a, to: b, c: [c0, c1, c2], on });
      }
      return out;
    }
    /** 区間の式の値 */
    const valOf = (pc, x) => { x = F(x); return pc.c[0].add(pc.c[1].mul(x)).add(pc.c[2].mul(x).mul(x)); };
    /** 区間の式の文字列 'y=3x' 'y=-3x+42' 'y=12' 'y=x^2'（MathRender の書き方） */
    function src(pc, v) {
      v = v || 'x';
      const MR = global.MathRender;
      const body = MR ? MR.terms([[pc.c[2], v + '^2'], [pc.c[1], v], [pc.c[0], '']]) : pc.c.join(',');
      return 'y=' + body;
    }
    /** 点 P から、2点 base[0]・base[1] を通る直線へおろした垂線の足（三角形の高さを見せるとき） */
    function foot(name, base, t) {
      const p = pt(name, t), a = pt(base[0], t), b = pt(base[1], t);
      const dx = b[0].sub(a[0]), dy = b[1].sub(a[1]);
      const k = p[0].sub(a[0]).mul(dx).add(p[1].sub(a[1]).mul(dy)).div(dx.mul(dx).add(dy.mul(dy)));
      return [a[0].add(dx.mul(k)), a[1].add(dy.mul(k))];
    }
    /** 辺の長さ（頂点の名前2つ） */
    function len(a, b) { return sqrtF(V[b][0].sub(V[a][0]).pow(2).add(V[b][1].sub(V[a][1]).pow(2))); }

    return { def, V, movers, T, segAt, pt, signedArea, area, breaks, pieces, valOf, src, foot, len };
  }

  const DottenEngine = { create, sqrtF };
  global.DottenEngine = DottenEngine;
  if (typeof module !== 'undefined' && module.exports) module.exports = DottenEngine;
})(typeof window !== 'undefined' ? window : globalThis);
