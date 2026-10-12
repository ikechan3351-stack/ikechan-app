/* =====================================================================
   circuit-engine.js — 理科シミュレーション共通「回路のつながりの判定」部品
   ---------------------------------------------------------------------
   かん電池・豆電球・スイッチ・どう線などが「どうつながっているか」から、
     ・それぞれの部品に流れる電流（大きさと向き）
     ・豆電球の明るさ
     ・ショート回路（豆電球を通らずに電池の＋と−がつながる）かどうか
     ・つかないとき、どこが原因か（ヒント用）
   を計算します。画面の絵とは切りはなしてあるので、どの教材からも使えます。
   （3年「電気の通り道」・4年「電流のはたらき」・6年「電気の利用」で使用）
   外部ライブラリは使っていません（オフラインでも動きます）。

   【考え方】
     ・部品のはし（たんし）を「点」、部品とどう線を「点と点をむすぶ線」と考えます。
     ・オームの法則（電流 ＝ 電圧 ÷ 電気の通りにくさ）を、すべての点について
       連立方程式にして解きます（science/回路シミュレーター.html と同じ計算方法）。
     ・電気を通さない物・切れたスイッチは「線がない」として計算します。

   【使い方】
     <script src="circuit-engine.js"></script>
     <script>
       // 部品1つ＝ { id, type, a, b }。a と b は、たんしの名前（同じ名前どうしはつながっている）。
       // かん電池は a＝−極、b＝＋極。どう線も type:'wire' の部品として書きます。
       const circuit = { elements: [
         { id: 'B1', type: 'battery', a: 'B1-', b: 'B1+' },
         { id: 'L1', type: 'bulb',    a: 'L1a', b: 'L1b' },
         { id: 'S1', type: 'switch',  a: 'S1a', b: 'S1b', on: true },
         { id: 'w1', type: 'wire',    a: 'B1+', b: 'L1a' },
         { id: 'w2', type: 'wire',    a: 'L1b', b: 'S1a' },
         { id: 'w3', type: 'wire',    a: 'S1b', b: 'B1-' }
       ]};
       const sim = CircuitEngine.solve(circuit);
       sim.current.get('L1')     // a→b の向きに流れる電流（A）。マイナスなら b→a の向き
       sim.brightness.get('L1')  // 豆電球の明るさ（電池1こ・豆電球1このときを 1 とする）
       sim.lit / sim.short       // どれか1つでも点灯しているか／ショートしているか

       const d = CircuitEngine.diagnose(circuit);   // つかない理由をしらべる（下の diagnose を参照）
     </script>

   【部品の種類をふやすとき】（6年の電熱線・発電機など。モーター・けん流計は下の TYPES に入っています）
     CircuitEngine.defineType('heater', { R: 4, load: true, pNom: 0.3 });
       R    … 電気の通りにくさ（Ω）
       emf  … 電池のように電気をおし出すはたらき（V）。書くと「電源」になる
       load … true なら、豆電球やモーターのように電気を使う部品（明るさ・回る速さを計算する）
       pNom … 「ふつうの強さ」とする電力（W）。brightness はこれとのくらべ
       openWhen(el) … true を返すと、そのときは電気を通さない（スイッチの「切」など）
     部品ごとに el.R や el.emf を書けば、その部品だけ値を変えられます（手回し発電機の速さなど）。
   ===================================================================== */
(function (global) {
  'use strict';

  // ===== 電気の計算に使う数値 =====
  const EMF = 1.5;        // かん電池1この電圧（V）
  const R_BATT = 0.1;     // かん電池の中の、電気の通りにくさ（Ω）
  const R_BULB = 5;       // 豆電球の、電気の通りにくさ（Ω）
  const R_WIRE = 0.01;    // どう線（ほとんど0）
  const R_MOTOR = 4;      // モーターの、電気の通りにくさ（Ω）。電池1こで約0.37A流れる
  const SHORT_I = 2;      // 電池にこれより大きい電流（A）が流れたらショート。ふつうは約0.3A
  const LIT = 0.05;       // 明るさがこれより大きければ「ついた」
  const LOW_R = 0.05;     // これより通りやすい部品は「どう線と同じ」（同じ点）とみなす

  // ===== 部品の種類 =====
  const TYPES = {
    wire:    { R: R_WIRE },
    battery: { R: R_BATT, emf: EMF },
    bulb:    { R: R_BULB, load: true, pNom: Math.pow(EMF / (R_BATT + R_BULB), 2) * R_BULB },
    motor:   { R: R_MOTOR, load: true, pNom: Math.pow(EMF / (R_BATT + R_MOTOR), 2) * R_MOTOR }, // モーター（4年）
    meter:   { R: R_WIRE },                                    // けん流計（電流の大きさと向きをはかる。4年）
    switch:  { R: R_WIRE, openWhen: el => !el.on },            // スイッチ：on が false なら切れている
    gap:     { R: 0.02, openWhen: el => !el.conductor }        // 物をはさむ所：電気を通す物のときだけつながる
  };

  function defineType(name, def) { TYPES[name] = def; }
  function typeOf(el) {
    const t = TYPES[el.type];
    if (!t) throw new Error('circuit-engine: 知らない部品の種類 ' + el.type);
    return t;
  }
  // 部品の「電気の通りにくさ」と「おし出すはたらき」。電気を通さないときは null
  function model(el) {
    const t = typeOf(el);
    if (!el.forceClosed && t.openWhen && t.openWhen(el)) return null;
    return { R: el.R != null ? el.R : t.R, emf: el.emf != null ? el.emf : (t.emf || 0) };
  }
  const isSource = el => !!(el.emf != null ? el.emf : typeOf(el).emf);
  const isLoad = el => !!typeOf(el).load;

  // つながりのグループ分け（ユニオン・ファインド）
  function makeUF(n) {
    const parent = Array.from({ length: n }, (_, i) => i);
    const find = i => { while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i]; } return i; };
    const union = (a, b) => { const ra = find(a), rb = find(b); if (ra !== rb) parent[ra] = rb; };
    return { find, union };
  }

  // たんしの名前に番号をつけ、部品の一覧を作る
  function prepare(circuit) {
    const index = new Map();
    const nid = k => { if (!index.has(k)) index.set(k, index.size); return index.get(k); };
    const list = circuit.elements.map(el => ({ el, a: nid(el.a), b: nid(el.b), m: model(el) }));
    return { index, list, n: index.size };
  }

  // ===== 回路を計算する =====
  function solve(circuit) {
    const { index, list, n } = prepare(circuit);
    const current = new Map(), brightness = new Map();
    const res = { current, brightness, lit: false, short: false, shortIds: [], voltage: new Map() };
    if (n === 0) return res;

    // 電気が通る部品でつながっているまとまり
    const uf = makeUF(n);
    list.forEach(it => { if (it.m) uf.union(it.a, it.b); });

    // 連立方程式（点ごとに「入る電流＝出る電流」）の表を作る
    const G = Array.from({ length: n }, () => new Array(n).fill(0));
    const rhs = new Array(n).fill(0);
    list.forEach(it => {
      if (!it.m) return;
      const g = 1 / it.m.R;
      it.g = g;
      G[it.a][it.a] += g; G[it.b][it.b] += g;
      G[it.a][it.b] -= g; G[it.b][it.a] -= g;
      // 電池は、中で a（−）から b（＋）へ電流をおし出す
      it.J = it.m.emf * g;
      rhs[it.b] += it.J; rhs[it.a] -= it.J;
    });
    // まとまりごとに1点を「基準（0V）」にする
    const grounded = new Set();
    for (let i = 0; i < n; i++) {
      const r = uf.find(i);
      if (grounded.has(r)) continue;
      grounded.add(r);
      G[i].fill(0); G[i][i] = 1; rhs[i] = 0;
    }
    // ガウスの消去法でとく
    for (let i = 0; i < n; i++) {
      let p = i;
      for (let r = i + 1; r < n; r++) if (Math.abs(G[r][i]) > Math.abs(G[p][i])) p = r;
      if (Math.abs(G[p][i]) < 1e-12) continue;
      [G[i], G[p]] = [G[p], G[i]]; [rhs[i], rhs[p]] = [rhs[p], rhs[i]];
      for (let r = i + 1; r < n; r++) {
        const f = G[r][i] / G[i][i];
        if (!f) continue;
        for (let c = i; c < n; c++) G[r][c] -= f * G[i][c];
        rhs[r] -= f * rhs[i];
      }
    }
    const V = new Array(n).fill(0);
    for (let i = n - 1; i >= 0; i--) {
      if (Math.abs(G[i][i]) < 1e-12) continue;
      let s = rhs[i];
      for (let c = i + 1; c < n; c++) s -= G[i][c] * V[c];
      V[i] = s / G[i][i];
    }
    index.forEach((i, k) => res.voltage.set(k, V[i]));

    // 部品ごとの電流と明るさ
    list.forEach(it => {
      const id = it.el.id;
      const I = it.m ? (V[it.a] - V[it.b]) * it.g + it.J : 0;   // a→b の向きがプラス
      current.set(id, Math.abs(I) < 1e-9 ? 0 : I);
      const t = typeOf(it.el);
      if (t.load) {
        const R = it.m ? it.m.R : t.R;
        const b = it.m ? I * I * R / (t.pNom || 1) : 0;
        brightness.set(id, b);
        if (b > LIT) res.lit = true;
      }
      if (isSource(it.el) && Math.abs(I) > SHORT_I) { res.short = true; res.shortIds.push(id); }
    });
    return res;
  }

  // ===== つかないとき、どこが原因かをしらべる =====
  // 返す値 { kind, ids, terminals, sim }
  //   kind:
  //     'noSource'  … 電池がない          'noLoad' … 豆電球（電気を使う部品）がない
  //     'short'     … ショート回路（ids＝熱くなる電池）
  //     'ok'        … どれかがついている
  //     'switchOff' … スイッチを入れればつく（ids＝切れているスイッチ）
  //     'blocked'   … 電気を通さない物・何もはさんでいない所があるため（ids＝その部品）
  //     'bypassed'  … 豆電球の2つのたんしが、どう線だけでつながっている（ids＝豆電球、terminals＝そのたんし）
  //     'open'      … どこにもつながっていない、たんしがある（terminals＝行き止まりのたんし）
  //     'noLoop'    … ぜんぶつながっているのにつかない（電池の向きが反対どうし など）
  function diagnose(circuit) {
    const els = circuit.elements;
    const sim = solve(circuit);
    const out = (kind, extra) => Object.assign({ kind, ids: [], terminals: [], sim }, extra || {});
    if (!els.some(isSource)) return out('noSource');
    if (!els.some(isLoad)) return out('noLoad');
    if (sim.short) return out('short', { ids: sim.shortIds });
    if (sim.lit) return out('ok');

    // 「もし〜だったら、つくか？」をためす
    const wouldLight = test => {
      const s = solve({ elements: els.map(e => test(e) ? Object.assign({}, e, { forceClosed: true }) : e) });
      return s.lit && !s.short;
    };
    const opened = els.filter(e => !model(e));
    const offSw = opened.filter(e => e.type === 'switch');
    const others = opened.filter(e => e.type !== 'switch');
    if (offSw.length && wouldLight(e => e.type === 'switch')) return out('switchOff', { ids: offSw.map(e => e.id) });
    if (others.length && wouldLight(e => e.type !== 'switch')) return out('blocked', { ids: others.map(e => e.id) });
    if (opened.length && wouldLight(() => true)) return out('switchOff', { ids: opened.map(e => e.id) });

    // どう線だけで（電気を使う部品を通らずに）つながっている点を、1つのグループにする
    const { index, list, n } = prepare(circuit);
    const uf = makeUF(n);
    list.forEach(it => { if (it.m && !it.m.emf && it.m.R <= LOW_R) uf.union(it.a, it.b); });
    const byp = list.filter(it => isLoad(it.el) && uf.find(it.a) === uf.find(it.b));
    if (byp.length) return out('bypassed', { ids: byp.map(it => it.el.id), terminals: byp.flatMap(it => [it.el.a, it.el.b]) });

    // 行き止まり（自分の部品にしかつながっていない）たんし
    const deg = new Array(n).fill(0);
    list.forEach(it => { deg[it.a]++; deg[it.b]++; });
    const name = [...index.keys()];
    const dead = [];
    list.forEach(it => {
      const lonely = deg[it.a] <= 1 && deg[it.b] <= 1;
      // どこにもつないでいない部品は、電池と豆電球だけヒントに出す（使っていないスイッチなどは出さない）
      if (lonely && !isSource(it.el) && !isLoad(it.el)) return;
      [it.a, it.b].forEach(i => { if (deg[i] <= 1 && it.el.type !== 'wire') dead.push(name[i]); });
    });
    if (dead.length) return out('open', { terminals: [...new Set(dead)] });
    return out('noLoop');
  }

  global.CircuitEngine = { solve, diagnose, defineType, TYPES, model, isSource, isLoad, EMF };
})(typeof window !== 'undefined' ? window : globalThis);
