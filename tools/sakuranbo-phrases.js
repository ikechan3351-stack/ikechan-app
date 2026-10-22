// さくらんぼけいさん.html の <script> を 画面なしで うごかし、collectPhrases()（しゃべる 文の 一覧）を JSON に 書き出す。
// tools/さくらんぼ音声.py から よばれる。 つかい方: node tools/sakuranbo-phrases.js <html> <出力.json>
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');
const code = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');
const stub = new Proxy(function () {}, {
  get: (t, k) => k === Symbol.toPrimitive ? () => '' : k === Symbol.iterator ? function* () {} : k === 'length' ? 0 : stub,
  apply: () => stub, set: () => true, construct: () => stub, has: () => false,
});
const window = new Proxy({ matchMedia: () => stub, Worksheet: undefined, SAKURA_VOICE: undefined }, { get: (t, k) => k in t ? t[k] : stub, has: (t, k) => k in t });
const ctx = { window, document: stub, localStorage: { getItem: () => null, setItem() {} }, location: { search: '' },
  Audio: function () { return stub; }, URLSearchParams, TextEncoder, console, setTimeout, clearTimeout, setInterval, clearInterval };
const fn = new Function(...Object.keys(ctx), code + '\nreturn collectPhrases();');
const list = fn(...Object.values(ctx));
fs.writeFileSync(process.argv[3], JSON.stringify(list, null, 1));
console.log(list.length);
