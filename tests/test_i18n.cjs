const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/i18n.js','utf8');
for(const [language,expected]of [['tr','Genel durum'],['en','Overview'],['fr','Vue générale'],['de','Übersicht']]){
 const window={};const context=vm.createContext({window,localStorage:{getItem:()=>language},document:{readyState:'loading',addEventListener(){}}});
 vm.runInContext(source,context);
 assert.equal(window.CenterEKI18n.translate('Genel durum'),expected);
 assert.equal(window.CenterEKI18n.translate('DESKTOP-PLGB96P'),'DESKTOP-PLGB96P');
 assert.equal(window.CenterEKI18n.translate('192.0.2.1'),'192.0.2.1');
}
console.log('Four language catalogs and identifier preservation passed.');
for(const [language,heading,records]of [['en','Device health','2 / 10 records'],['fr','État des équipements','2 / 10 entrées'],['de','Gerätezustand','2 / 10 Einträge']]){
 const texts=['Cihaz sağlığı','Güncel ölçüm bekleniyor.','2 / 10 kayıt','DESKTOP-PLGB96P','192.0.2.1'];
 const nodes=texts.map(nodeValue=>({nodeValue,parentElement:{closest(){return null}}}));
 const window={},document={readyState:'loading',body:{},documentElement:{},addEventListener(){},querySelectorAll:()=>[],createTreeWalker(){let index=0;return {nextNode:()=>nodes[index++]||null}}};
 vm.runInContext(source,vm.createContext({window,localStorage:{getItem:()=>language},document,NodeFilter:{SHOW_TEXT:4}}));
 window.CenterEKI18n.refresh();assert.equal(nodes[0].nodeValue,heading);assert.equal(nodes[2].nodeValue,records);assert.equal(nodes[3].nodeValue,texts[3]);
 window.CenterEKI18n.setLanguage('tr');assert.deepEqual(nodes.map(n=>n.nodeValue),texts);
 window.CenterEKI18n.setLanguage(language);assert.equal(nodes[0].nodeValue,heading);
 window.CenterEKI18n.protect(['Sunucular']);assert.equal(window.CenterEKI18n.translate('Sunucular'),'Sunucular');
}
console.log('Visible content, dynamic record counts and repeated language switching passed.');
