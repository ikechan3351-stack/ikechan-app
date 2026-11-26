// 漢字ガンバ の 漢字データと 読み上げる ほめことば・単元テストの問題文を JSON で出す（tools/build-kanji-voice.py が使う）
const fs = require('fs');
const h = fs.readFileSync(process.argv[2], 'utf8');
const a = h.indexOf('const RAW'), b = h.indexOf('const K = {}');
const rows = [];
eval(h.slice(a, b) + `
;[RAW,RAW2,RAW3,RAW4,RAW5,RAW6].forEach(raw=>raw.trim().split('\\n').forEach(line=>{
  const [k,on,kun,word,yomi,emo,ex]=line.split('|'); rows.push({k,on,kun,word,yomi,ex});}));`);
// 単元テストの問題文（[漢字]{よみ} の ところ）
const window = {};
eval(fs.readFileSync(require('path').join(require('path').dirname(process.argv[2]), 'kanji-ganba', 'test.js'), 'utf8'));
const tests = [];
Object.values(window.KANJI_TEST).forEach(raw => raw.trim().split('\n').forEach(line => {
  const [k, r, w] = line.split('|');
  [r, w].forEach(t => { const m = (t || '').match(/^(.*)\[(.+?)\]\{(.+?)\}(.*)$/); if (m) tests.push({ k, pre: m[1], kj: m[2], yomi: m[3], post: m[4] }); });
}));
const m = h.match(/speak\(allDone \? '([^']+)' : '([^']+)'\)/);
console.log(JSON.stringify({ rows, tests, extra: [m[1], m[2]] }));
