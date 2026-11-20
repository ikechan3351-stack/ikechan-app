// 漢字ガンバ 4年：都道府県の字の絵（日本地図で その県に色をぬったもの）を作る
// 地図データは social/都道府県パズル.html の PREF_DATA（Geolonia japanese-prefectures, MIT License）
// 使い方：
//   node tools/kanji-ganba-pref-map.js social/都道府県パズル.html <出力フォルダ>
//   cd <出力フォルダ> && qlmanage -t -s 400 -o . *.svg      ← SVG を 400×400 の PNG にする（macOS）
//   できた 字.svg.png を japanese/kanji-ganba/img/字.png にコピーする
const fs=require('fs');
const html=fs.readFileSync(process.argv[2],'utf8');
const P=JSON.parse(html.match(/const PREF_DATA = (\[.*?\]);\n/)[1]);
const B=JSON.parse(html.match(/const BOUNDARY_LINES = (\[.*?\]);/)[1]);
const out=process.argv[3];
// 字 → 県
const T={茨:'茨城県',城:'宮城県',栃:'栃木県',群:'群馬県',埼:'埼玉県',潟:'新潟県',富:'富山県',井:'福井県',岐:'岐阜県',阜:'岐阜県',静:'静岡県',
梨:'山梨県',奈:'神奈川県',阪:'大阪府',滋:'滋賀県',賀:'滋賀県',府:'京都府',岡:'岡山県',香:'香川県',媛:'愛媛県',徳:'徳島県',佐:'佐賀県',
崎:'長崎県',熊:'熊本県',鹿:'鹿児島県',沖:'沖縄県',縄:'沖縄県'};
// 県の外わく（おおよそ）を点から求める
function bbox(p){const nums=[...p.s.matchAll(/(?:points="([^"]+)")|(?:d="([^"]+)")/g)].flatMap(m=>(m[1]||m[2]).match(/-?\d+(\.\d+)?/g).map(Number));
 let xs=[],ys=[];for(let i=0;i<nums.length;i+=2){xs.push(nums[i]+p.tx);ys.push(nums[i+1]+p.ty);} return [Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)];}
for(const [k,name] of Object.entries(T)){
 const t=P.find(p=>p.n===name); let [x0,y0,x1,y1]=bbox(t);
 if(name==='鹿児島県'){ // 本土の部分だけで わくを決める（島は遠い）
   x0=96+22;y0=17+836;x1=96+82;y1=17+920; }
 if(name==='長崎県'){ x0=44+50;y0=700+80;x1=44+95;y1=700+135; }
 if(name==='沖縄県'){ x0=52+262;y0=193+0;x1=52+312;y1=193+48; }
 const cx=(x0+x1)/2, cy=(y0+y1)/2; const size=Math.max(x1-x0,y1-y0)*2.6, S=Math.max(size,230);
 const vb=`${cx-S/2} ${cy-S/2} ${S} ${S}`; const sw=S/400;
 let g='';
 for(const p of [...P.filter(q=>q.n!==name),t]){ const on=p.n===name;
   g+=`<g transform="translate(${p.tx},${p.ty})" fill="${on?'#ff8a3d':'#e3efd3'}" stroke="${on?'#c0531a':'#9db58a'}" stroke-width="${(on?2.2:1)*sw}" stroke-linejoin="round">${p.s}</g>`; }
 // 目立たせる：県のまわりに 赤い まる
 const r=Math.max(x1-x0,y1-y0)/2+14*sw;
 const ring=`<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#e53935" stroke-width="${3*sw}" stroke-dasharray="${8*sw} ${5*sw}"/>`;
 const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="${vb}"><rect x="${cx-S/2}" y="${cy-S/2}" width="${S}" height="${S}" fill="#dff1fb"/>${g}${ring}</svg>`;
 fs.writeFileSync(`${out}/${k}.svg`,svg);
}
console.log(Object.keys(T).length);
