/* =====================================================================
   worksheet.js — 理科シミュレーション共通「ワークシート」部品
   ---------------------------------------------------------------------
   「①予想 → ②実験 → ③結果 → ④考察」のワークシートを、
   どのシミュレーションにも差しこめるようにした部品です。
   外部ライブラリは使っていません（オフラインでも動きます）。

   【使い方】シミュレーションの HTML に、次のように書きます。

     <link rel="stylesheet" href="worksheet.css">
     <script src="worksheet.js"></script>
     <script>
       Worksheet.init({
         title: 'ふりこの実験',                                  // 題名（<ruby> も使えます）
         question: 'ふりこの長さをかえると、10往復の時間はかわるだろうか？',
         predictionChoices: ['長くなる', '短くなる', 'かわらない'],  // ①予想の選択肢
         columns: [                                              // ③結果の表の列
           { key: 'len',  label: 'ふりこの長さ', unit: 'cm' },
           { key: 'time', label: '10往復の時間', unit: '秒', digits: 1 }  // digits＝小数第何位まで出すか
         ],
         chart: { type: 'line', x: 'len', y: 'time' },  // type は 'line'（折れ線）・'bar'（棒）・'scatter'（散布図）
                                                       // y を ['a','b'] のように書くと、線や棒が2本になる
         hint:   '先生用のヒント',                      // ?teacher=1 のときだけ表示
         answer: '先生用の解答例'                       // ?teacher=1 のときだけ表示
       });

       // 実験を1回したら、シミュレーション側から結果をわたす：
       Worksheet.addRecord({ len: 50, time: 14.2 });
     </script>

   【そのほかのオプション】（書かなくてもよい）
     experimentNote: '②実験に出す説明文'
     mount: '#ここに入れたい場所'  … 書くと、右に固定せず、その場所の中に表示する
     chart.sortBy: 'h'  … 横じくが文字（例：'正午'）のとき、記録の中の h の小さい順にならべる
                          （h は表に出さない記録の項目でもよい）

   【そのほかの命令】
     Worksheet.getRecords()      … 記録の一覧（配列）を返す
     Worksheet.removeRecord(i)   … i 番目（0から数える）の記録を消す
     Worksheet.setChart({type:'bar'}) … グラフの種類などをあとから変える
     Worksheet.reset()           … ワークシートをはじめにもどす（確認あり）
     Worksheet.isTeacher()       … 先生モードなら true

   【保存】localStorage に自動で保存します。
     キーは「ikechan-science-ファイル名」（例: ikechan-science-ふりこの実験）。
   ===================================================================== */
(function () {
  'use strict';

  // ---- グラフの色（色覚のちがいがあっても見分けやすい Okabe-Ito の色）と、マークの形・線のもよう ----
  // 色だけで区別しないように、2本目からは形・点線・しまもようも変えています。
  const SERIES_COLORS = ['#0072B2', '#D55E00', '#009E73', '#CC79A7'];
  const SERIES_MARKS = ['circle', 'square', 'triangle', 'diamond'];
  const SERIES_DASH = [[], [9, 5], [2, 5], [12, 4, 2, 4]];
  const FONT = '"Hiragino Sans", "Yu Gothic", sans-serif';

  // ワークシートの状態をまとめて入れておく箱
  const S = { cfg: null, data: null, key: '', teacher: false, el: {}, flash: -1, ro: null };

  // ===== 小さな道具 =====
  const R = (k, y) => '<ruby>' + k + '<rt>' + y + '</rt></ruby>'; // ふりがな付きの文字を作る
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  // <ruby> などのタグをとって、ふつうの文字だけにする（Canvas に書くとき・ファイル名用）
  function plain(html) {
    const d = document.createElement('div');
    d.innerHTML = html == null ? '' : String(html);
    d.querySelectorAll('rt, rp').forEach(n => n.remove());
    return d.textContent.trim();
  }
  const num = v => { const n = parseFloat(v); return isFinite(n) ? n : null; };
  const colOf = k => S.cfg.columns.find(c => c.key === k) || { key: k, label: k };
  const colTitle = c => plain(c.label) + (c.unit ? '（' + c.unit + '）' : '');
  // 数字を表に出す形にする（digits があれば小数の位をそろえる）
  function fmt(v, col) {
    if (v == null || v === '') return '';
    if (col && col.digits != null && num(v) !== null) return num(v).toFixed(col.digits);
    return String(v);
  }
  function today() {
    const d = new Date(), p = n => String(n).padStart(2, '0');
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate());
  }

  // ===== 保存（localStorage） =====
  // ファイル名から保存のキーを作る：science/ふりこの実験.html → ikechan-science-ふりこの実験
  function fileKey() {
    let name = location.pathname.split('/').pop() || 'index.html';
    try { name = decodeURIComponent(name); } catch (e) { /* そのまま使う */ }
    name = name.replace(/\.html?$/i, '') || 'index';
    return 'ikechan-science-' + name;
  }
  const emptyData = () => ({ prediction: { choice: null, reason: '' }, records: [], conclusion: { match: null, text: '' } });
  function load() {
    const e = emptyData();
    try {
      const raw = localStorage.getItem(S.key);
      if (raw) {
        const d = JSON.parse(raw);
        return {
          prediction: Object.assign(e.prediction, d.prediction),
          records: Array.isArray(d.records) ? d.records : [],
          conclusion: Object.assign(e.conclusion, d.conclusion)
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
      box.innerHTML = '✔ ' + R('自動', 'じどう') + 'で' + R('保存', 'ほぞん') + 'しました（' + d.getHours() + ':' + String(d.getMinutes()).padStart(2, '0') + '）';
    } catch (err) {
      // プライベートブラウズなどで保存できないとき
      box.className = 'ws-saved ws-ng';
      box.innerHTML = '⚠ このブラウザでは' + R('保存', 'ほぞん') + 'できません。「' + R('画像', 'がぞう') + 'で' + R('保存', 'ほぞん') + '」を使ってください。';
    }
  }

  // ===== はじめに呼ぶ：ワークシートを作る =====
  function init(cfg) {
    cfg = cfg || {};
    // columns は 'len' のような文字だけでも書けるようにする
    const columns = (cfg.columns || []).map(c => typeof c === 'string' ? { key: c, label: c } : Object.assign({}, c));
    const chart = Object.assign({ type: 'line', x: columns[0] && columns[0].key, y: columns[1] && columns[1].key }, cfg.chart || {});
    if (!Array.isArray(chart.y)) chart.y = chart.y ? [chart.y] : [];
    S.cfg = Object.assign({
      title: 'ワークシート', question: '', predictionChoices: [], hint: '', answer: '', experimentNote: '', mount: null
    }, cfg, { columns, chart });
    S.teacher = new URLSearchParams(location.search).get('teacher') === '1';
    S.key = cfg.storageKey || fileKey(); // storageKey はふつうは書かない
    S.data = load();
    build();
    renderAll();
    return api;
  }

  // ===== 画面の部品（HTML）を組み立てる =====
  function build() {
    // 2回 init されたときは、前のものを消してから作り直す
    ['panel', 'open', 'toast'].forEach(k => S.el[k] && S.el[k].remove());
    if (S.ro) S.ro.disconnect();

    const c = S.cfg;
    const teacherBox = (title, html) => S.teacher && html
      ? '<div class="ws-teacher"><div class="ws-teacher-h">' + title + '</div><div>' + html + '</div></div>' : '';
    const choiceBtn = (act, val, html) =>
      '<button type="button" class="ws-btn ws-choice" data-act="' + act + '" data-v="' + val + '" aria-pressed="false">' +
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
      '<div class="ws-nameline"><span>　</span>年<span>　</span>組　なまえ<span class="ws-name">　</span></div>' +
      (c.question ? '<div class="ws-question"><span class="ws-qlabel">もんだい</span><div>' + c.question + '</div></div>' : '') +

      // ① 予想
      '<section class="ws-step" data-step="1">' +
        '<h3 class="ws-step-h"><span class="ws-num">1</span>' + R('予想', 'よそう') + '<span class="ws-done" hidden>✔ できた</span></h3>' +
        '<div class="ws-choices" role="group" aria-label="予想の選択肢">' +
          c.predictionChoices.map((t, i) => choiceBtn('predict', i, t)).join('') +
        '</div>' +
        '<label class="ws-label" for="ws-reason">そう考えた' + R('理由', 'りゆう') + '</label>' +
        '<textarea class="ws-text" id="ws-reason" data-f="reason" placeholder="〜だから、〜になると思う。"></textarea>' +
        '<div class="ws-print-text" data-p="reason"></div>' +
        teacherBox('💡 先生用：ヒント', c.hint) +
      '</section>' +

      // ② 実験
      '<section class="ws-step" data-step="2">' +
        '<h3 class="ws-step-h"><span class="ws-num">2</span>' + R('実験', 'じっけん') + '<span class="ws-done" hidden>✔ できた</span></h3>' +
        '<p class="ws-note">' + (c.experimentNote || 'シミュレーションで' + R('実験', 'じっけん') + 'して、' + R('結果', 'けっか') + 'を' + R('記録', 'きろく') + 'しよう。') + '</p>' +
        '<div class="ws-count">' + R('記録', 'きろく') + '：<b data-r="count">0</b> ' + R('回', 'かい') + '</div>' +
        '<p class="ws-warn" hidden>先に ① の' + R('予想', 'よそう') + 'をしてから' + R('実験', 'じっけん') + 'しよう。</p>' +
      '</section>' +

      // ③ 結果
      '<section class="ws-step" data-step="3">' +
        '<h3 class="ws-step-h"><span class="ws-num">3</span>' + R('結果', 'けっか') + '</h3>' +
        '<div class="ws-table-wrap"><table class="ws-table"></table></div>' +
        '<div class="ws-chart-wrap"><canvas class="ws-chart" role="img" aria-label="結果のグラフ"></canvas></div>' +
      '</section>' +

      // ④ 考察
      '<section class="ws-step" data-step="4">' +
        '<h3 class="ws-step-h"><span class="ws-num">4</span>' + R('考察', 'こうさつ') + '<span class="ws-done" hidden>✔ できた</span></h3>' +
        '<div data-r="recall"></div>' +
        '<div class="ws-label">' + R('予想', 'よそう') + 'とくらべてどうだった？</div>' +
        '<div class="ws-match" role="group" aria-label="予想とくらべて">' +
          choiceBtn('match', 'ok', 'あっていた') + choiceBtn('match', 'ng', 'ちがった') +
        '</div>' +
        '<label class="ws-label" for="ws-text">わかったこと</label>' +
        '<textarea class="ws-text" id="ws-text" data-f="text" placeholder="〜すると、〜になることがわかった。"></textarea>' +
        '<div class="ws-print-text" data-p="text"></div>' +
        teacherBox('📘 先生用：解答例', c.answer) +
      '</section>' +

      '<div class="ws-tools ws-noprint">' +
        '<button type="button" class="ws-btn ws-main" data-act="png">🖼️ ' + R('画像', 'がぞう') + 'で' + R('保存', 'ほぞん') + '（PNG）</button>' +
        '<button type="button" class="ws-btn ws-main" data-act="print">🖨️ ' + R('印刷', 'いんさつ') + '</button>' +
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
    open.innerHTML = '📝 ワークシート';
    open.addEventListener('click', () => fold(false));
    document.body.appendChild(open);

    // 「記録しました」のお知らせ
    const toastEl = document.createElement('div');
    toastEl.className = 'ws-toast';
    toastEl.setAttribute('role', 'status');
    document.body.appendChild(toastEl);

    S.el = {
      panel: p, open, toast: toastEl,
      table: p.querySelector('.ws-table'),
      canvas: p.querySelector('.ws-chart'),
      saved: p.querySelector('.ws-saved')
    };

    // ボタンのクリック（まとめて受けとる）
    p.addEventListener('click', ev => {
      const b = ev.target.closest('[data-act]');
      if (!b) return;
      const act = b.dataset.act;
      if (act === 'predict') { S.data.prediction.choice = +b.dataset.v; changed(); }
      else if (act === 'match') { S.data.conclusion.match = b.dataset.v; changed(); }
      else if (act === 'del') removeRecord(+b.dataset.i);
      else if (act === 'png') saveImage();
      else if (act === 'print') window.print();
      else if (act === 'reset') reset();
      else if (act === 'fold') fold(true);
    });
    // 書く欄に入力したら、すぐ保存
    p.addEventListener('input', ev => {
      const f = ev.target.dataset.f;
      if (f === 'reason') S.data.prediction.reason = ev.target.value;
      else if (f === 'text') S.data.conclusion.text = ev.target.value;
      else return;
      save(); renderDone(); renderPrintText();
    });

    // 画面のはばが変わったら、グラフをかき直す
    if (window.ResizeObserver) {
      S.ro = new ResizeObserver(() => renderChart());
      S.ro.observe(S.el.canvas.parentNode);
    } else {
      window.addEventListener('resize', renderChart);
    }
  }

  // 印刷の前後：書いた文を印刷用の欄に写す／ページの中に置いたときの印刷用の切りかえ
  window.addEventListener('beforeprint', () => {
    if (!S.cfg) return;
    renderPrintText();
    if (S.el.panel.classList.contains('ws-inline')) document.body.classList.add('ws-print-inline');
  });
  window.addEventListener('afterprint', () => document.body.classList.remove('ws-print-inline'));

  // ワークシートを右にとじる／ひらく（大きい画面のとき）
  function fold(on) {
    document.body.classList.toggle('ws-collapsed', on);
    // シミュレーション側の Canvas などが、広くなった画面に合わせられるように知らせる
    setTimeout(() => window.dispatchEvent(new Event('resize')), 300);
    if (!on) S.el.panel.querySelector('.ws-fold').focus();
  }

  // ===== 表示を最新にする =====
  function changed() { save(); renderAll(); }
  function renderAll() {
    renderPrediction(); renderCount(); renderTable(); renderChart(); renderConclusion(); renderDone(); renderPrintText();
  }
  function setPressed(btn, on) { btn.classList.toggle('is-on', on); btn.setAttribute('aria-pressed', on ? 'true' : 'false'); }
  function setValue(sel, v) { const t = S.el.panel.querySelector(sel); if (t.value !== v) t.value = v; }

  function renderPrediction() {
    S.el.panel.querySelectorAll('[data-act="predict"]').forEach(b => setPressed(b, +b.dataset.v === S.data.prediction.choice));
    setValue('[data-f="reason"]', S.data.prediction.reason);
  }
  function renderCount() {
    S.el.panel.querySelector('[data-r="count"]').textContent = S.data.records.length;
    S.el.panel.querySelector('.ws-warn').hidden = !(S.data.records.length && S.data.prediction.choice == null);
  }
  function renderConclusion() {
    S.el.panel.querySelectorAll('[data-act="match"]').forEach(b => setPressed(b, b.dataset.v === S.data.conclusion.match));
    setValue('[data-f="text"]', S.data.conclusion.text);
    const ch = S.cfg.predictionChoices[S.data.prediction.choice];
    S.el.panel.querySelector('[data-r="recall"]').innerHTML = ch != null
      ? 'あなたの' + R('予想', 'よそう') + '：<b>' + ch + '</b>'
      : '<span style="color:#888">（まだ ① の' + R('予想', 'よそう') + 'をしていません）</span>';
  }
  // できたところに「✔ できた」を付ける
  function renderDone() {
    const d = S.data;
    const done = {
      1: d.prediction.choice != null && d.prediction.reason.trim() !== '',
      2: d.records.length > 0,
      4: d.conclusion.match != null && d.conclusion.text.trim() !== ''
    };
    S.el.panel.querySelectorAll('.ws-step').forEach(sec => {
      const mark = sec.querySelector('.ws-done');
      if (mark) mark.hidden = !done[sec.dataset.step];
    });
  }
  function renderPrintText() {
    S.el.panel.querySelector('[data-p="reason"]').textContent = S.data.prediction.reason;
    S.el.panel.querySelector('[data-p="text"]').textContent = S.data.conclusion.text;
  }

  // ③ 結果の表
  function renderTable() {
    const cols = S.cfg.columns, recs = S.data.records;
    let h = '<thead><tr><th>' + R('回', 'かい') + '</th>' +
      cols.map(c => '<th>' + c.label + (c.unit ? '<span class="ws-unit">（' + esc(c.unit) + '）</span>' : '') + '</th>').join('') +
      '<th class="ws-del-col"><span style="font-size:0.8em">けす</span></th></tr></thead><tbody>';
    if (!recs.length) {
      h += '<tr><td class="ws-empty" colspan="' + (cols.length + 2) + '">まだ' + R('記録', 'きろく') + 'がありません</td></tr>';
    }
    recs.forEach((r, i) => {
      h += '<tr' + (i === S.flash ? ' class="ws-flash"' : '') + '><td>' + (i + 1) + '</td>' +
        cols.map(c => '<td>' + esc(fmt(r[c.key], c)) + '</td>').join('') +
        '<td class="ws-del-col"><button type="button" class="ws-del" data-act="del" data-i="' + i + '" aria-label="' + (i + 1) + '回目の記録をけす">けす</button></td></tr>';
    });
    S.el.table.innerHTML = h + '</tbody>';
    S.flash = -1;
  }

  // ③ グラフ（画面のはばに合わせて、くっきりかく）
  function renderChart() {
    if (!S.cfg) return;
    const cv = S.el.canvas, w = cv.parentNode.clientWidth;
    if (!w) return;
    const h = Math.round(Math.max(220, Math.min(340, w * 0.7)));
    const dpr = Math.max(2, window.devicePixelRatio || 1); // 印刷してもぼやけにくいように2倍以上でかく
    cv.width = Math.round(w * dpr);
    cv.height = Math.round(h * dpr);
    const ctx = cv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    drawChart(ctx, w, h);
    cv.setAttribute('aria-label', '結果のグラフ（記録 ' + S.data.records.length + ' 回）');
  }

  // ===== グラフをかく本体（画面用にも、画像保存用にも使う） =====
  // ctx：かく場所　W,H：大きさ　fsBig：文字の大きさ（書かなければ自動）
  function drawChart(ctx, W, H, fsBig) {
    const c = S.cfg.chart, recs = S.data.records;
    const xc = colOf(c.x), ycs = c.y.map(colOf);
    const fs = fsBig || (W < 400 ? 13 : 15);
    ctx.save();
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, W, H);
    ctx.font = fs + 'px ' + FONT;
    ctx.textBaseline = 'middle';

    // 記録をあつめる
    const rows = recs.slice();
    const allNumX = rows.length && rows.every(r => num(r[c.x]) !== null);
    if (allNumX) rows.sort((a, b) => num(a[c.x]) - num(b[c.x])); // 横じくの小さい順にならべる
    else if (c.sortBy) rows.sort((a, b) => (num(a[c.sortBy]) ?? 0) - (num(b[c.sortBy]) ?? 0)); // 横じくが文字のときは sortBy の順
    const yvals = [];
    rows.forEach(r => ycs.forEach(yc => { const v = num(r[yc.key]); if (v !== null) yvals.push(v); }));

    if (!yvals.length) {
      ctx.fillStyle = '#888';
      ctx.textAlign = 'center';
      ctx.fillText('記録すると、ここにグラフができます', W / 2, H / 2);
      ctx.restore();
      return;
    }

    const type = c.type === 'bar' || c.type === 'scatter' ? c.type : 'line';
    // 横じく：数なら目もり、数でなければ（または棒グラフなら）同じ間かくでならべる
    const xNumeric = type !== 'bar' && allNumX;
    let cats = null;
    if (!xNumeric) {
      if (type === 'bar') cats = rows.map(r => fmt(r[c.x], xc));
      else { cats = []; rows.forEach(r => { const l = fmt(r[c.x], xc); if (!cats.includes(l)) cats.push(l); }); }
    }
    // たてじくは 0 からはじめる（マイナスがあればそこまで）
    const ys = niceRange(Math.min(0, ...yvals), Math.max(...yvals));
    const xs = xNumeric ? niceRange(Math.min(0, ...rows.map(r => num(r[c.x]))), Math.max(...rows.map(r => num(r[c.x])))) : null;

    // まわりの余白
    const multi = ycs.length > 1;
    // たてじくの名前（2本以上のときは、単位がみんな同じなら単位だけ書く）
    const sameUnit = ycs.every(yc => yc.unit && yc.unit === ycs[0].unit);
    const yTitle = c.yLabel || (multi ? (sameUnit ? '（' + ycs[0].unit + '）' : '') : colTitle(ycs[0]));
    let tickW = 0;
    for (let v = ys.lo; v <= ys.hi + ys.step / 2; v += ys.step) tickW = Math.max(tickW, ctx.measureText(tickLabel(v, ys)).width);
    const L = 10 + (yTitle ? fs * 1.6 : 0) + tickW + 8;
    const T = multi ? fs * 2.6 : fs * 1.2;
    const Rm = fs * 1.9; // 右はしの目もりの数字が切れないように
    const B = fs * 3.6;
    const PW = W - L - Rm, PH = H - T - B;
    const py = v => T + (ys.hi - v) / (ys.hi - ys.lo) * PH;
    const slot = cats ? PW / cats.length : 0;
    const px = v => xNumeric ? L + (v - xs.lo) / (xs.hi - xs.lo) * PW : L + slot * (cats.indexOf(v) + 0.5);

    // 目もりの線と数字（たて）
    ctx.lineWidth = 1;
    ctx.textAlign = 'right';
    for (let v = ys.lo; v <= ys.hi + ys.step / 2; v += ys.step) {
      const y = py(v);
      ctx.strokeStyle = Math.abs(v) < ys.step / 1e6 ? '#888' : '#e3e3e3';
      ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(L + PW, y); ctx.stroke();
      ctx.fillStyle = '#444';
      ctx.fillText(tickLabel(v, ys), L - 6, y);
    }
    // 目もりの数字（横）
    ctx.textAlign = 'center';
    ctx.fillStyle = '#444';
    if (xNumeric) {
      for (let v = xs.lo; v <= xs.hi + xs.step / 2; v += xs.step) {
        const x = px(v);
        ctx.strokeStyle = '#eeeeee';
        ctx.beginPath(); ctx.moveTo(x, T); ctx.lineTo(x, T + PH); ctx.stroke();
        ctx.fillText(tickLabel(v, xs), x, T + PH + fs * 0.9);
      }
    } else {
      // 名前が多いときは小さい文字にする
      const cf = Math.max(10, Math.min(fs, slot / Math.max(1, ...cats.map(s => s.length)) * 1.1));
      ctx.font = cf + 'px ' + FONT;
      cats.forEach((s, i) => ctx.fillText(s, L + slot * (i + 0.5), T + PH + fs * 0.9));
      ctx.font = fs + 'px ' + FONT;
    }
    // じくの線
    ctx.strokeStyle = '#555';
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(L, T); ctx.lineTo(L, T + PH); ctx.lineTo(L + PW, T + PH); ctx.stroke();

    // じくの名前
    ctx.fillStyle = '#333';
    ctx.font = 'bold ' + fs + 'px ' + FONT;
    ctx.fillText(colTitle(xc), L + PW / 2, H - fs * 1.0);
    if (yTitle) {
      // 長くてはみ出すときは、文字を小さくする
      const tw = ctx.measureText(yTitle).width;
      if (tw > PH + T) ctx.font = 'bold ' + Math.max(10, Math.floor(fs * (PH + T) / tw)) + 'px ' + FONT;
      ctx.save();
      ctx.translate(6 + fs * 0.7, T / 2 + PH / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText(yTitle, 0, 0);
      ctx.restore();
    }
    ctx.font = fs + 'px ' + FONT;

    // 線・点・棒をかく
    ycs.forEach((yc, k) => {
      const color = SERIES_COLORS[k % 4];
      const pts = rows.map(r => ({ x: xNumeric ? num(r[c.x]) : fmt(r[c.x], xc), y: num(r[yc.key]) })).filter(p => p.y !== null);
      if (type === 'bar') {
        const gw = slot * 0.72, bw = gw / ycs.length, base = py(Math.max(0, ys.lo));
        rows.forEach((r, i) => {
          const v = num(r[yc.key]);
          if (v === null) return;
          const x0 = L + slot * (i + 0.5) - gw / 2 + k * bw, y0 = py(v);
          const top = Math.min(y0, base), hgt = Math.abs(base - y0);
          ctx.fillStyle = color;
          ctx.fillRect(x0 + 1, top, bw - 2, hgt);
          if (k > 0) { ctx.fillStyle = barPattern(ctx, k); ctx.fillRect(x0 + 1, top, bw - 2, hgt); } // 2本目からはもよう付き
          ctx.strokeStyle = '#333'; ctx.lineWidth = 1;
          ctx.strokeRect(x0 + 1, top, bw - 2, hgt);
          // 棒の上に数字
          if (bw > fs * 1.8) {
            ctx.fillStyle = '#222';
            ctx.font = 'bold ' + Math.round(fs * 0.9) + 'px ' + FONT;
            ctx.fillText(fmt(v, yc), x0 + bw / 2, v >= 0 ? top - fs * 0.6 : top + hgt + fs * 0.6);
            ctx.font = fs + 'px ' + FONT;
          }
        });
      } else {
        if (type === 'line' && pts.length > 1) {
          ctx.strokeStyle = color;
          ctx.lineWidth = 3;
          ctx.setLineDash(SERIES_DASH[k % 4]);
          ctx.beginPath();
          pts.forEach((p, i) => (i ? ctx.lineTo(px(p.x), py(p.y)) : ctx.moveTo(px(p.x), py(p.y))));
          ctx.stroke();
          ctx.setLineDash([]);
        }
        pts.forEach(p => drawMark(ctx, SERIES_MARKS[k % 4], px(p.x), py(p.y), fs * 0.42, color));
      }
    });

    // 2本以上のときは、上に「はんれい（どの線が何か）」をかく
    if (multi) {
      let x = L;
      const y = fs * 1.2;
      ctx.textAlign = 'left';
      ycs.forEach((yc, k) => {
        const color = SERIES_COLORS[k % 4], label = plain(yc.label);
        if (type === 'bar') {
          ctx.fillStyle = color; ctx.fillRect(x, y - fs * 0.45, fs * 1.4, fs * 0.9);
          if (k > 0) { ctx.fillStyle = barPattern(ctx, k); ctx.fillRect(x, y - fs * 0.45, fs * 1.4, fs * 0.9); }
          ctx.strokeStyle = '#333'; ctx.lineWidth = 1; ctx.strokeRect(x, y - fs * 0.45, fs * 1.4, fs * 0.9);
        } else {
          if (type === 'line') {
            ctx.strokeStyle = color; ctx.lineWidth = 3; ctx.setLineDash(SERIES_DASH[k % 4]);
            ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + fs * 1.6, y); ctx.stroke(); ctx.setLineDash([]);
          }
          drawMark(ctx, SERIES_MARKS[k % 4], x + fs * 0.8, y, fs * 0.42, color);
        }
        ctx.fillStyle = '#333';
        ctx.fillText(label, x + fs * 2, y);
        x += fs * 2.8 + ctx.measureText(label).width;
      });
    }
    ctx.restore();
  }

  // 目もりのきりのよい数（1, 2, 2.5, 5, 10 …）を決める
  function niceRange(lo, hi) {
    if (hi === lo) { hi = lo === 0 ? 1 : lo + Math.abs(lo) * 0.5; }
    const raw = (hi - lo) / 5, exp = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / exp;
    const step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * exp;
    const dec = Math.max(0, (String(+step.toPrecision(6)).split('.')[1] || '').length);
    return { lo: Math.floor(lo / step + 1e-9) * step, hi: Math.ceil(hi / step - 1e-9) * step, step, dec };
  }
  function tickLabel(v, r) { return (Math.abs(v) < r.step / 1e6 ? 0 : v).toFixed(r.dec); }

  // マーク（●■▲◆）をかく
  function drawMark(ctx, kind, x, y, r, color) {
    ctx.beginPath();
    if (kind === 'square') ctx.rect(x - r, y - r, r * 2, r * 2);
    else if (kind === 'triangle') { ctx.moveTo(x, y - r * 1.25); ctx.lineTo(x + r * 1.15, y + r * 0.85); ctx.lineTo(x - r * 1.15, y + r * 0.85); ctx.closePath(); }
    else if (kind === 'diamond') { ctx.moveTo(x, y - r * 1.3); ctx.lineTo(x + r * 1.3, y); ctx.lineTo(x, y + r * 1.3); ctx.lineTo(x - r * 1.3, y); ctx.closePath(); }
    else ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();
  }
  // 棒グラフのもよう（2本目＝しま、3本目＝点、4本目＝こうし）
  function barPattern(ctx, k) {
    const t = document.createElement('canvas');
    t.width = t.height = 10;
    const g = t.getContext('2d');
    g.strokeStyle = g.fillStyle = 'rgba(255,255,255,0.75)';
    g.lineWidth = 2.5;
    if (k % 3 === 1) { g.beginPath(); g.moveTo(0, 10); g.lineTo(10, 0); g.moveTo(-5, 5); g.lineTo(5, -5); g.moveTo(5, 15); g.lineTo(15, 5); g.stroke(); }
    else if (k % 3 === 2) { g.beginPath(); g.arc(5, 5, 2.2, 0, Math.PI * 2); g.fill(); }
    else { g.beginPath(); g.moveTo(5, 0); g.lineTo(5, 10); g.moveTo(0, 5); g.lineTo(10, 5); g.stroke(); }
    return ctx.createPattern(t, 'repeat');
  }

  // ===== 記録の追加・削除 =====
  function addRecord(rec) {
    if (!S.cfg) { console.warn('Worksheet.init() を先に呼んでください'); return; }
    S.data.records.push(Object.assign({}, rec));
    S.flash = S.data.records.length - 1; // 新しい行を光らせる
    save();
    renderCount(); renderTable(); renderChart(); renderDone();
    toast('✔ ' + R('記録', 'きろく') + 'しました（' + S.data.records.length + R('回目', 'かいめ') + '）');
  }
  function removeRecord(i) {
    if (!S.data.records[i]) return;
    S.data.records.splice(i, 1);
    save();
    renderCount(); renderTable(); renderChart(); renderDone();
  }
  // ワークシートをはじめにもどす（ask=false なら確認しない）
  function reset(ask) {
    if (ask !== false && !confirm('ワークシートの「予想・記録・考察」をぜんぶ消して、はじめからにします。よろしいですか？')) return;
    S.data = emptyData();
    save();
    renderAll();
  }
  function setChart(opts) {
    Object.assign(S.cfg.chart, opts || {});
    if (!Array.isArray(S.cfg.chart.y)) S.cfg.chart.y = S.cfg.chart.y ? [S.cfg.chart.y] : [];
    renderChart();
  }

  let toastTimer = 0;
  function toast(html) {
    const t = S.el.toast;
    t.innerHTML = html;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 1800);
  }

  // ===== 画像で保存（PNG）：ワークシート全体を1まいの絵にかく =====
  function buildImage() {
    const W = 1000, M = 44, CW = W - M * 2, d = S.data, c = S.cfg;
    // だいたいの高さを見つもって大きめにとり、最後に切りとる
    const est = 1700 + d.records.length * 44 + (plain(c.question).length + d.prediction.reason.length + d.conclusion.text.length) * 2;
    const cv = document.createElement('canvas');
    cv.width = W;
    cv.height = Math.min(est, 14000);
    const ctx = cv.getContext('2d');
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, W, cv.height);
    ctx.textBaseline = 'top';
    let y = M;

    const setFont = (size, bold) => { ctx.font = (bold ? 'bold ' : '') + size + 'px ' + FONT; };
    // 文を、はばに合わせて折り返して書く
    function para(text, size, color, x, maxW) {
      setFont(size);
      ctx.fillStyle = color;
      wrap(ctx, text, maxW).forEach(line => { ctx.fillText(line, x, y); y += size * 1.6; });
    }
    function heading(n, label) {
      y += 14;
      ctx.fillStyle = '#558b2f';
      roundRect(ctx, M, y, CW, 44, 10); ctx.fill();
      setFont(24, true); ctx.fillStyle = '#fff';
      ctx.fillText(n + '　' + label, M + 16, y + 9);
      y += 58;
    }
    const blankOr = s => s.trim() ? s : '（まだ書いていません）';

    // 題名・日付・名前の欄
    setFont(34, true); ctx.fillStyle = '#33691e';
    ctx.fillText('📝 ' + plain(c.title), M, y);
    setFont(20); ctx.fillStyle = '#555'; ctx.textAlign = 'right';
    ctx.fillText(today(), W - M, y + 8);
    ctx.textAlign = 'left';
    y += 58;
    setFont(20); ctx.fillStyle = '#333';
    ctx.fillText('　　年　　組　なまえ', W - M - 420, y);
    ctx.strokeStyle = '#333'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(W - M - 200, y + 28); ctx.lineTo(W - M, y + 28); ctx.stroke();
    y += 44;

    // もんだい
    if (c.question) {
      setFont(22, true);
      const lines = wrap(ctx, plain(c.question), CW - 40);
      const h = 50 + lines.length * 35;
      ctx.fillStyle = '#f1f8e9'; ctx.strokeStyle = '#558b2f'; ctx.lineWidth = 3;
      roundRect(ctx, M, y, CW, h, 14); ctx.fill(); ctx.stroke();
      setFont(18, true); ctx.fillStyle = '#558b2f';
      ctx.fillText('もんだい', M + 20, y + 12);
      y += 42;
      para(plain(c.question), 22, '#222', M + 20, CW - 40);
      y += 12;
    }

    // ① 予想
    heading('①', '予想');
    const ch = c.predictionChoices[d.prediction.choice];
    para('予想：' + (ch != null ? plain(ch) : '（えらんでいません）'), 22, '#222', M + 8, CW - 16);
    y += 4;
    para('理由：' + blankOr(d.prediction.reason), 21, '#333', M + 8, CW - 16);

    // ③ 結果（表とグラフ）
    heading('③', '結果（記録 ' + d.records.length + ' 回）');
    const cols = [{ label: '回' }].concat(c.columns);
    const cw = CW / cols.length, rh = 40;
    const cell = (txt, x, yy, bg, bold) => {
      ctx.fillStyle = bg; ctx.fillRect(x, yy, cw, rh);
      ctx.strokeStyle = '#c5e1a5'; ctx.lineWidth = 2; ctx.strokeRect(x, yy, cw, rh);
      setFont(19, bold); ctx.fillStyle = '#222'; ctx.textAlign = 'center';
      let s = txt;
      while (s.length > 1 && ctx.measureText(s).width > cw - 10) s = s.slice(0, -1); // はみ出すときは切る
      ctx.fillText(s === txt ? s : s + '…', x + cw / 2, yy + 9);
      ctx.textAlign = 'left';
    };
    cols.forEach((col, j) => cell(j ? colTitle(col) : '回', M + j * cw, y, '#f1f8e9', true));
    y += rh;
    if (!d.records.length) { para('（まだ記録がありません）', 20, '#888', M + 8, CW); }
    d.records.forEach((r, i) => {
      cols.forEach((col, j) => cell(j ? fmt(r[col.key], col) : String(i + 1), M + j * cw, y, '#fff', j > 0));
      y += rh;
    });
    if (d.records.length) {
      y += 16;
      ctx.save();
      ctx.translate(M, y);
      drawChart(ctx, CW, 440, 19);
      ctx.restore();
      ctx.strokeStyle = '#c5e1a5'; ctx.lineWidth = 2; ctx.strokeRect(M, y, CW, 440);
      y += 440;
    }

    // ④ 考察
    heading('④', '考察');
    const m = d.conclusion.match;
    para('予想とくらべて：' + (m === 'ok' ? 'あっていた' : m === 'ng' ? 'ちがった' : '（えらんでいません）'), 22, '#222', M + 8, CW - 16);
    y += 4;
    para('わかったこと：' + blankOr(d.conclusion.text), 21, '#333', M + 8, CW - 16);

    y += 20;
    setFont(16); ctx.fillStyle = '#999'; ctx.textAlign = 'right';
    ctx.fillText('いけちゃんアプリ　理科ワークシート', W - M, y);
    y += 40;

    // 使った高さだけ切りとる
    const out = document.createElement('canvas');
    out.width = W;
    out.height = Math.min(y, cv.height);
    out.getContext('2d').drawImage(cv, 0, 0);
    return out;
  }
  function wrap(ctx, text, maxW) {
    const lines = [];
    String(text).split('\n').forEach(par => {
      let line = '';
      for (const ch of par) {
        if (line && ctx.measureText(line + ch).width > maxW) { lines.push(line); line = ch; }
        else line += ch;
      }
      lines.push(line);
    });
    return lines;
  }
  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }
  function saveImage() {
    const cv = buildImage();
    const name = (plain(S.cfg.title) || 'ワークシート').replace(/[\\/:*?"<>|\s]+/g, '_') + '_' + today() + '.png';
    cv.toBlob(blob => {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      toast('🖼️ ' + R('画像', 'がぞう') + 'を' + R('保存', 'ほぞん') + 'しました');
    }, 'image/png');
  }

  // ===== 外から使える命令 =====
  const api = {
    init,
    addRecord,
    removeRecord,
    reset,
    setChart,
    getRecords: () => (S.data ? S.data.records.map(r => Object.assign({}, r)) : []),
    getData: () => (S.data ? JSON.parse(JSON.stringify(S.data)) : null),
    isTeacher: () => new URLSearchParams(location.search).get('teacher') === '1',
    _buildImage: () => buildImage() // 動作確認用
  };
  window.Worksheet = api;
})();
