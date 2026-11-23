const fs=require('fs');const h=fs.readFileSync(process.argv[2],'utf8');
const pics=fs.readFileSync(process.argv[3],'utf8');
const a=h.indexOf('const KANA'),b=h.indexOf('const PENS');const p=h.match(/const PRAISE = .*;/)[0];
const code=pics+'\n'+h.slice(a,b).replace('let ROWS','var ROWS')+'\n'+p+`
const T=new Set();const add=s=>T.add(s);
Object.values(KANA).forEach(s=>s.all.forEach(k=>add(sayName(k))));
Object.values(PICS).flat().forEach(add);Object.values(WORDS).forEach(w=>add(w[1]));PRAISE.forEach(add);
console.log(JSON.stringify([...T]));`;
eval(code.replace(/^const S =.*$/m,''));
