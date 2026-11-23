// 漢字ガンバ の 漢字データと 読み上げる ほめことばを JSON で出す（tools/build-kanji-voice.py が使う）
const fs = require('fs');
const h = fs.readFileSync(process.argv[2], 'utf8');
const a = h.indexOf('const RAW'), b = h.indexOf('const K = {}');
const rows = [];
eval(h.slice(a, b) + `
;[RAW,RAW2,RAW3,RAW4,RAW5,RAW6].forEach(raw=>raw.trim().split('\\n').forEach(line=>{
  const [k,on,kun,word,yomi,emo,ex]=line.split('|'); rows.push({k,word,yomi,ex});}));`);
const m = h.match(/speak\(allDone \? '([^']+)' : '([^']+)'\)/);
console.log(JSON.stringify({ rows, extra: [m[1], m[2]] }));
