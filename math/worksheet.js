/* =====================================================================
   worksheet.js — 中学数学アプリ共通「ワークシート」部品
   ---------------------------------------------------------------------
   「①予想 → ②操作 → ③気づき → ④まとめ（式とことば）」のワークシートを、
   どの数学アプリにも差しこめるようにした部品です。
   使い方・見た目は理科の science/worksheet.js とそろえています。
   外部ライブラリは使っていません（オフラインでも動きます）。

   【使い方】アプリの HTML に、次のように書きます。
   （math-render.js を先に読みこんでおくと、表やまとめの式がきれいな数式で出ます。なくても動きます）

     <link rel="stylesheet" href="worksheet.css">
     <script src="math-render.js"></script>
     <script src="worksheet.js"></script>
     <script>
       Worksheet.init({
         title: '連立方程式をグラフで見る',                       // 題名
         question: '2本の直線の交点の座標は、連立方程式の何になっているだろうか？',
         predictions: ['解になっている', '解とは関係ない', 'わからない'],   // ①予想の選択肢（HTML も可）
         fields: [                                                // ②操作で記録する表の列
           { key: 'a', label: 'a' },
           { key: 'b', label: 'b' },
           { key: 'cross', label: '交点' }                          // 値は "(1, 5)" のような式の文字列でもよい
         ],
         capture: () => ({ a: 2, b: 3, cross: '(1, 5)' }),        // 「記録する」ボタンを押したときの値
         summaryHint: '「交点の x 座標・y 座標は〜」の形で書いてみよう',
         teacher: { hint: '先生用のヒント', answer: '先生用の解答例' }   // ?teacher=1 のときだけ表示
       });

       // capture を書かないときは、アプリ側から記録をわたす：
       Worksheet.addRecord({ a: 2, b: 3, cross: '(1, 5)' });
     </script>

   【そのほかのオプション】（書かなくてもよい）
     key: '連立方程式のグラフ'  … 保存の名前（書かなければファイル名）。保存キーは「ikechan-math-○○」
     operationNote: '②操作に出す説明文'
     mount: '#ここに入れたい場所'  … 書くと、右に固定せず、その場所の中に表示する
     open: false   … はじめは、ワークシートをとじておく（URL に ?ws=0 を付けても同じ。?ws=1 でひらく）
     fields の { math: false } … その列は数式にせず、ふつうの文字で出す
     fields の { unit: 'cm' }  … 見出しに単位を付ける

   【そのほかの命令】
     Worksheet.addRecord(記録)   … 表に1行足す（値は数・文字・分数 Fraction のどれでもよい）
     Worksheet.getRecords()      … 記録の一覧（配列）を返す
     Worksheet.removeRecord(i)   … i 番目（0から数える）の記録を消す
     Worksheet.open() / close()  … ワークシートをひらく／とじる
     Worksheet.toText()          … ワークシートの中身をテキストにして返す（コピーと同じもの）
     Worksheet.reset()           … ワークシートをはじめにもどす（確認あり）
     Worksheet.isTeacher()       … 先生モードなら true
     Worksheet.appData(名前, 値)  … アプリ自身のデータも同じ保存キーの中に入れる（値を書かなければ読み出す）

   【保存】localStorage に自動で保存します。キーは「ikechan-math-ファイル名」（例: ikechan-math-連立方程式のグラフ）。
   ===================================================================== */
(function () {
  'use strict';

  // ワークシートの状態をまとめて入れておく箱
  const S = { cfg: null, data: null, key: '', teacher: false, el: {}, flash: -1 };

  // ===== 小さな道具 =====
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  // HTML のタグをとって、ふつうの文字だけにする（テキストにコピーするとき・ファイル名用）
  function plain(html) {
    const d = document.createElement('div');
    d.innerHTML = html == null ? '' : String(html);
    d.querySelectorAll('rt, rp').forEach(n => n.remove());
    return d.textContent.trim();
  }
  // 値を文字にする（分数 Fraction は "3/4" に）
  const str = v => (v == null ? '' : String(v));
  // 表のマスに出す HTML。math-render.js があれば数式として描く
  function cellHTML(v, field) {
    const s = str(v);
    if (!s) return '';
    if (field.math !== false && window.MathRender) {
      try { return window.MathRender.html(s, { size: 'inherit' }); } catch (e) { /* 描けないときはふつうの文字 */ }
    }
    return esc(s);
  }
  function today() {
    const d = new Date(), p = n => String(n).padStart(2, '0');
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
  }

  // ===== 保存（localStorage） =====
  // ファイル名から保存のキーを作る：math/連立方程式のグラフ.html → ikechan-math-連立方程式のグラフ
  function fileKey(name) {
    if (!name) {
      name = location.pathname.split('/').pop() || 'index.html';
      try { name = decodeURIComponent(name); } catch (e) { /* そのまま使う */ }
      name = name.replace(/\.html?$/i, '') || 'index';
    }
    return 'ikechan-math-' + name;
  }
  const emptyData = () => ({
    prediction: { choice: null, reason: '' },
    records: [],
    notice: '',                          // ③ 気づき
    summary: { formula: '', words: '' }, // ④ まとめ（式・ことば）
    closed: null,                        // ワークシートをとじているか（null＝まだ決めていない）
    app: {}                              // アプリ自身のデータ（appData で使う）
  });
  function load() {
    const e = emptyData();
    try {
      const raw = localStorage.getItem(S.key);
      if (raw) {
        const d = JSON.parse(raw);
        return {
          prediction: Object.assign(e.prediction, d.prediction),
          records: Array.isArray(d.records) ? d.records : [],
          notice: typeof d.notice === 'string' ? d.notice : '',
          summary: Object.assign(e.summary, d.summary),
          closed: typeof d.closed === 'boolean' ? d.closed : null,
          app: d.app && typeof d.app === 'object' ? d.app : {}
        };
      }
    } catch (err) { /* 読めないときは、まっさらから */ }
    return e;
  }
  function save() {
    const box = S.el.saved;
    try {
      localStorage.setItem(S.key, JSON.stringify(S.data));
      const d = new Date();
      box.className = 'ws-saved';
      box.textContent = '✔ 自動で保存しました（' + d.getHours() + ':' + String(d.getMinutes()).padStart(2, '0') + '）';
    } catch (err) {
      // プライベートブラウズなどで保存できないとき
      box.className = 'ws-saved ws-ng';
      box.textContent = '⚠ このブラウザでは保存できません。「テキストにコピー」や「印刷」を使ってください。';
    }
  }

  // ===== はじめに呼ぶ：ワークシートを作る =====
  function init(cfg) {
    cfg = cfg || {};
    // fields は 'a' のような文字だけでも書けるようにする（理科の columns という名前でもよい）
    const fields = (cfg.fields || cfg.columns || []).map(c => typeof c === 'string' ? { key: c, label: c } : Object.assign({}, c));
    const teacher = Object.assign({ hint: cfg.hint || '', answer: cfg.answer || '' }, cfg.teacher || {});
    S.cfg = Object.assign({
      title: 'ワークシート', question: '', summaryHint: '', operationNote: '', mount: null, capture: null, open: true
    }, cfg, {
      fields, teacher,
      predictions: cfg.predictions || cfg.predictionChoices || []
    });
    S.teacher = isTeacher();
    S.key = fileKey(cfg.key);
    S.data = load();
    build();
    renderAll();
    // はじめにひらくか、とじるか：URL の ?ws= → 前回の状態 → 設定の open の順で決める
    const ws = new URLSearchParams(location.search).get('ws');
    const closed = ws === '0' ? true : ws === '1' ? false : (S.data.closed !== null ? S.data.closed : S.cfg.open === false);
    setClosed(closed, false);
    return api;
  }
  function isTeacher() { return new URLSearchParams(location.search).get('teacher') === '1'; }

  // ===== 画面の部品（HTML）を組み立てる =====
  function build() {
    // 2回 init されたときは、前のものを消してから作り直す
    ['panel', 'open', 'toast'].forEach(k => S.el[k] && S.el[k].remove());

    const c = S.cfg;
    const teacherBox = (title, html) => S.teacher && html
      ? '<div class="ws-teacher"><div class="ws-teacher-h">' + title + '</div><div>' + html + '</div></div>' : '';
    const choiceBtn = (val, html) =>
      '<button type="button" class="ws-btn ws-choice" data-act="predict" data-v="' + val + '" aria-pressed="false">' +
      '<span class="ws-mark" aria-hidden="true"></span><span>' + html + '</span></button>';

    const p = document.createElement('aside');
    p.className = 'ws-panel';
    p.setAttribute('aria-label', 'ワークシート');
    p.innerHTML =
      '<div class="ws-head">' +
        '<h2 class="ws-title">📝 ' + c.title + '</h2>' +
        '<button type="button" class="ws-btn ws-fold ws-noprint" data-act="fold" aria-label="ワークシートをとじる">とじる ▶</button>' +
      '</div>' +
      (S.teacher ? '<div><span class="ws-teacher-badge">👩‍🏫 先生モード</span></div>' : '') +
      '<div class="ws-nameline"><span class="ws-date">' + today() + '</span><span>　</span>年<span>　</span>組<span>　</span>番　なまえ<span class="ws-name">　</span></div>' +
      (c.question ? '<div class="ws-question"><span class="ws-qlabel">もんだい</span><div>' + c.question + '</div></div>' : '') +

      // ① 予想
      '<section class="ws-step" data-step="1">' +
        '<h3 class="ws-step-h"><span class="ws-num">1</span>予想<span class="ws-done" hidden>✔ できた</span></h3>' +
        '<div class="ws-choices" role="group" aria-label="予想の選択肢">' +
          c.predictions.map((t, i) => choiceBtn(i, t)).join('') +
        '</div>' +
        '<label class="ws-label" for="ws-reason">そう考えた理由（ひとこと）</label>' +
        '<input type="text" class="ws-input" id="ws-reason" data-f="reason" placeholder="〜だから、〜になると思う。">' +
        '<div class="ws-print-text ws-print-line" data-p="reason"></div>' +
        teacherBox('💡 先生用：ヒント', c.teacher.hint) +
      '</section>' +

      // ② 操作
      '<section class="ws-step" data-step="2">' +
        '<h3 class="ws-step-h"><span class="ws-num">2</span>操作<span class="ws-done" hidden>✔ できた</span></h3>' +
        '<p class="ws-note">' + (c.operationNote || 'アプリを動かして、気になったところで「記録する」を押そう。') + '</p>' +
        (c.capture ? '<button type="button" class="ws-btn ws-main ws-rec ws-noprint" data-act="rec">＋ 記録する</button>' : '') +
        '<p class="ws-warn" hidden>先に ① の予想をしてから操作しよう。</p>' +
        '<div class="ws-table-wrap"><table class="ws-table"></table></div>' +
      '</section>' +

      // ③ 気づき
      '<section class="ws-step" data-step="3">' +
        '<h3 class="ws-step-h"><span class="ws-num">3</span>気づき<span class="ws-done" hidden>✔ できた</span></h3>' +
        '<div data-r="recall"></div>' +
        '<label class="ws-label" for="ws-notice">記録をくらべて、気づいたこと</label>' +
        '<textarea class="ws-text" id="ws-notice" data-f="notice" placeholder="〜のとき、いつも〜になっている。"></textarea>' +
        '<div class="ws-print-text" data-p="notice"></div>' +
      '</section>' +

      // ④ まとめ
      '<section class="ws-step" data-step="4">' +
        '<h3 class="ws-step-h"><span class="ws-num">4</span>まとめ（きまり）<span class="ws-done" hidden>✔ できた</span></h3>' +
        (c.summaryHint ? '<p class="ws-note ws-hint">' + c.summaryHint + '</p>' : '') +
        '<label class="ws-label" for="ws-formula">式で書くと？</label>' +
        '<input type="text" class="ws-input ws-formula" id="ws-formula" data-f="formula" placeholder="例）y = ax + b" autocomplete="off" spellcheck="false">' +
        '<div class="ws-preview" data-r="preview" aria-live="polite"></div>' +
        '<p class="ws-keys ws-noprint">分数は 1/2、2乗は x^2、√ は「ルート」と入力しても書けます。</p>' +
        '<label class="ws-label" for="ws-words">ことばで言うと？</label>' +
        '<textarea class="ws-text" id="ws-words" data-f="words" placeholder="〜は、〜になる。"></textarea>' +
        '<div class="ws-print-text" data-p="words"></div>' +
        teacherBox('📘 先生用：解答例', c.teacher.answer) +
      '</section>' +

      '<div class="ws-tools ws-noprint">' +
        '<button type="button" class="ws-btn ws-main" data-act="copy">📋 テキストにコピー</button>' +
        '<button type="button" class="ws-btn ws-main" data-act="print">🖨️ 印刷（A4）</button>' +
        '<button type="button" class="ws-btn ws-sub" data-act="reset">ワークシートをはじめから</button>' +
      '</div>' +
      '<div class="ws-saved" aria-live="polite"></div>';

    // 置く場所：mount があればその中、なければ body の最後（大きい画面では右に固定される）
    const mount = c.mount && (typeof c.mount === 'string' ? document.querySelector(c.mount) : c.mount);
    if (mount) { p.classList.add('ws-inline'); mount.appendChild(p); }
    else { document.body.appendChild(p); document.body.classList.add('ws-on'); }

    // とじたときに出す「ワークシート」ボタン
    const open = document.createElement('button');
    open.type = 'button';
    open.className = 'ws-open';
    open.textContent = '📝 ワークシート';
    open.setAttribute('aria-label', 'ワークシートをひらく');
    open.addEventListener('click', () => setClosed(false));
    document.body.appendChild(open);

    // 「記録しました」のお知らせ
    const toastEl = document.createElement('div');
    toastEl.className = 'ws-toast';
    toastEl.setAttribute('role', 'status');
    document.body.appendChild(toastEl);

    S.el = { panel: p, open, toast: toastEl, table: p.querySelector('.ws-table'), saved: p.querySelector('.ws-saved') };

    // ボタンのクリック（まとめて受けとる）
    p.addEventListener('click', ev => {
      const b = ev.target.closest('[data-act]');
      if (!b) return;
      const act = b.dataset.act;
      if (act === 'predict') { S.data.prediction.choice = +b.dataset.v; changed(); }
      else if (act === 'rec') capture();
      else if (act === 'del') removeRecord(+b.dataset.i);
      else if (act === 'copy') copyText();
      else if (act === 'print') printSheet();
      else if (act === 'reset') reset();
      else if (act === 'fold') setClosed(true);
    });
    // 書く欄に入力したら、すぐ保存
    p.addEventListener('input', ev => {
      const f = ev.target.dataset.f, v = ev.target.value;
      if (f === 'reason') S.data.prediction.reason = v;
      else if (f === 'notice') S.data.notice = v;
      else if (f === 'formula') { S.data.summary.formula = v; renderPreview(); }
      else if (f === 'words') S.data.summary.words = v;
      else return;
      save(); renderDone(); renderPrintText();
    });
  }

  // 印刷の前後：書いた文を印刷用の欄に写す／ページの中に置いたときの印刷用の切りかえ
  window.addEventListener('beforeprint', () => {
    if (!S.cfg) return;
    renderPrintText();
    if (S.el.panel.classList.contains('ws-inline')) document.body.classList.add('ws-print-inline');
  });
  window.addEventListener('afterprint', () => document.body.classList.remove('ws-print-inline', 'ws-printing'));
  // 印刷：とじていても印刷できるように、ひらいた形で印刷する
  function printSheet() {
    renderPrintText();
    document.body.classList.add('ws-printing');
    window.print();
  }

  // ワークシートをとじる／ひらく（とじた状態も保存して、次に開いたときも同じにする）
  function setClosed(on, remember) {
    document.body.classList.toggle('ws-collapsed', on);
    S.el.panel.classList.toggle('ws-hide', on);
    if (remember !== false) { S.data.closed = on; save(); }
    // アプリ側の Canvas・座標平面などが、広くなった画面に合わせられるように知らせる
    setTimeout(() => window.dispatchEvent(new Event('resize')), 300);
    if (!on && remember !== false) S.el.panel.querySelector('.ws-fold').focus({ preventScroll: true });
  }

  // ===== 表示を最新にする =====
  function changed() { save(); renderAll(); }
  function renderAll() {
    renderPrediction(); renderTable(); renderNotice(); renderSummary(); renderDone(); renderPrintText();
  }
  function setPressed(btn, on) { btn.classList.toggle('is-on', on); btn.setAttribute('aria-pressed', on ? 'true' : 'false'); }
  function setValue(sel, v) { const t = S.el.panel.querySelector(sel); if (t.value !== v) t.value = v; }

  function renderPrediction() {
    S.el.panel.querySelectorAll('[data-act="predict"]').forEach(b => setPressed(b, +b.dataset.v === S.data.prediction.choice));
    setValue('[data-f="reason"]', S.data.prediction.reason);
    S.el.panel.querySelector('.ws-warn').hidden = !(S.data.records.length && S.data.prediction.choice == null);
  }
  function renderNotice() {
    setValue('[data-f="notice"]', S.data.notice);
    const ch = S.cfg.predictions[S.data.prediction.choice];
    S.el.panel.querySelector('[data-r="recall"]').innerHTML = ch != null
      ? 'あなたの予想：<b>' + ch + '</b>'
      : '<span class="ws-gray">（まだ ① の予想をしていません）</span>';
  }
  function renderSummary() {
    setValue('[data-f="formula"]', S.data.summary.formula);
    setValue('[data-f="words"]', S.data.summary.words);
    renderPreview();
  }
  // 「式で書くと？」に書いた式を、数式の形で見せる
  function renderPreview() {
    const box = S.el.panel.querySelector('[data-r="preview"]');
    const v = S.data.summary.formula.trim();
    if (!v) { box.innerHTML = ''; box.hidden = true; return; }
    box.hidden = false;
    const src = v.replace(/ルート/g, '√');
    box.innerHTML = window.MathRender ? window.MathRender.html(src, { size: 'small' }) : esc(src);
  }
  // できたところに「✔ できた」を付ける
  function renderDone() {
    const d = S.data;
    const done = {
      1: d.prediction.choice != null && d.prediction.reason.trim() !== '',
      2: d.records.length > 0,
      3: d.notice.trim() !== '',
      4: d.summary.formula.trim() !== '' && d.summary.words.trim() !== ''
    };
    S.el.panel.querySelectorAll('.ws-step').forEach(sec => {
      const mark = sec.querySelector('.ws-done');
      if (mark) mark.hidden = !done[sec.dataset.step];
    });
  }
  function renderPrintText() {
    const set = (k, v) => { S.el.panel.querySelector('[data-p="' + k + '"]').textContent = v; };
    set('reason', S.data.prediction.reason);
    set('notice', S.data.notice);
    set('words', S.data.summary.words);
  }

  // ② 記録の表
  function renderTable() {
    const cols = S.cfg.fields, recs = S.data.records;
    if (!cols.length) { S.el.table.innerHTML = ''; return; }
    let h = '<thead><tr><th>回</th>' +
      cols.map(c => '<th>' + c.label + (c.unit ? '<span class="ws-unit">（' + esc(c.unit) + '）</span>' : '') + '</th>').join('') +
      '<th class="ws-del-col"><span style="font-size:0.8em">けす</span></th></tr></thead><tbody>';
    if (!recs.length) {
      h += '<tr><td class="ws-empty" colspan="' + (cols.length + 2) + '">まだ記録がありません</td></tr>';
    }
    recs.forEach((r, i) => {
      h += '<tr' + (i === S.flash ? ' class="ws-flash"' : '') + '><td>' + (i + 1) + '</td>' +
        cols.map(c => '<td>' + cellHTML(r[c.key], c) + '</td>').join('') +
        '<td class="ws-del-col"><button type="button" class="ws-del" data-act="del" data-i="' + i + '" aria-label="' + (i + 1) + '回目の記録をけす">けす</button></td></tr>';
    });
    S.el.table.innerHTML = h + '</tbody>';
    S.el.panel.classList.toggle('ws-many', recs.length > 8);   // 印刷のとき、表を小さくする目じるし
    S.flash = -1;
  }

  // ===== 記録の追加・削除 =====
  // 「記録する」ボタン：アプリの capture() から今の値をもらう
  function capture() {
    let rec = null;
    try { rec = S.cfg.capture(); } catch (e) { console.warn('capture() でエラー', e); }
    if (rec) addRecord(rec);
  }
  function addRecord(rec) {
    if (!S.cfg) { console.warn('Worksheet.init() を先に呼んでください'); return; }
    // 分数（Fraction）なども、保存できるように文字にしておく
    const r = {};
    Object.keys(rec || {}).forEach(k => { r[k] = typeof rec[k] === 'number' ? rec[k] : str(rec[k]); });
    S.data.records.push(r);
    S.flash = S.data.records.length - 1; // 新しい行を光らせる
    save();
    renderTable(); renderPrediction(); renderDone();
    toast('✔ 記録しました（' + S.data.records.length + '回目）');
  }
  function removeRecord(i) {
    if (!S.data.records[i]) return;
    S.data.records.splice(i, 1);
    save();
    renderTable(); renderPrediction(); renderDone();
  }
  // ワークシートをはじめにもどす（ask=false なら確認しない）。アプリのデータ（appData）とひらき方は残す
  function reset(ask) {
    if (ask !== false && !confirm('ワークシートの「予想・記録・気づき・まとめ」をぜんぶ消して、はじめからにします。よろしいですか？')) return;
    const keep = { closed: S.data.closed, app: S.data.app };
    S.data = Object.assign(emptyData(), keep);
    save();
    renderAll();
  }

  let toastTimer = 0;
  function toast(text) {
    const t = S.el.toast;
    t.textContent = text;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 1800);
  }

  // ===== テキストにする・コピーする =====
  function toText() {
    const c = S.cfg, d = S.data, L = [];
    const blank = s => (s && s.trim() ? s.trim() : '（まだ書いていません）');
    L.push('【' + plain(c.title) + '】 ' + today());
    if (c.question) L.push('もんだい：' + plain(c.question));
    L.push('');
    L.push('① 予想');
    const ch = c.predictions[d.prediction.choice];
    L.push('　予想：' + (ch != null ? plain(ch) : '（えらんでいません）'));
    L.push('　理由：' + blank(d.prediction.reason));
    L.push('');
    L.push('② 操作（記録 ' + d.records.length + ' 回）');
    if (c.fields.length) {
      L.push('　回\t' + c.fields.map(f => plain(f.label) + (f.unit ? '（' + f.unit + '）' : '')).join('\t'));
      d.records.forEach((r, i) => L.push('　' + (i + 1) + '\t' + c.fields.map(f => str(r[f.key])).join('\t')));
    }
    L.push('');
    L.push('③ 気づき');
    L.push('　' + blank(d.notice).replace(/\n/g, '\n　'));
    L.push('');
    L.push('④ まとめ');
    L.push('　式で書くと：' + blank(d.summary.formula));
    L.push('　ことばで言うと：' + blank(d.summary.words).replace(/\n/g, '\n　'));
    return L.join('\n');
  }
  function copyText() {
    const text = toText();
    const ok = () => toast('📋 コピーしました。ロイロやメモにはりつけられます');
    const fallback = () => {
      // クリップボードの機能が使えないときの昔ながらの方法
      const ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      let done = false;
      try { done = document.execCommand('copy'); } catch (e) { /* 使えない */ }
      ta.remove();
      if (done) ok(); else toast('⚠ コピーできませんでした');
    };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(ok, fallback);
    else fallback();
  }

  // ===== アプリ自身のデータを、同じ保存キーの中に入れる =====
  function appData(name, value) {
    if (!S.data) return undefined;
    if (arguments.length < 2) return S.data.app[name];
    S.data.app[name] = value;
    save();
    return value;
  }

  // ===== 外から使える命令 =====
  const api = {
    init,
    addRecord,
    removeRecord,
    reset,
    toText,
    appData,
    open: () => setClosed(false),
    close: () => setClosed(true),
    getRecords: () => (S.data ? S.data.records.map(r => Object.assign({}, r)) : []),
    getData: () => (S.data ? JSON.parse(JSON.stringify(S.data)) : null),
    isTeacher,
    get storageKey() { return S.key; }
  };
  window.Worksheet = api;
})();
