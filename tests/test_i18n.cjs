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
