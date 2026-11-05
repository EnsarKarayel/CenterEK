// Small DOM harness: exercise port filters, stale values and pagination without a server.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map();
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.value='';this.dataset={};this.classList={toggle(){}};this.textContent=''}
 set id(value){this._id=value;nodes.set(value,this)}get id(){return this._id}
 append(...items){for(const item of items){this.children.push(item);if(this.tag==='select'&&this.children.length===1)this.value=item.value}}
 replaceChildren(...items){this.children=[];this.append(...items)}
 addEventListener(){}setAttribute(){}after(){}scrollIntoView(){}
}
for(const id of ['device-search','client-search','ad-search','session-search','logout','live-dashboard']){const e=new Element('div');e.id=id}
const main=new Element('main');
const context=vm.createContext({Node:Element,document:{getElementById:id=>nodes.get(id),createElement:tag=>new Element(tag),querySelectorAll:()=>[],querySelector:()=>main,addEventListener(){}},fetch:()=>new Promise(()=>{}),AbortSignal:{timeout(){}},console,setTimeout(){},Date,Number});
vm.runInContext(fs.readFileSync('web/app.js','utf8'),context);
vm.runInContext(`state.data={devices:[{id:'sw1',name:'Core Switch',kind:'Switch',host:'192.0.2.2',status:'up',stale:false,metrics:{status:'ok',stale:false,checked:1,values:{interfaces:Array.from({length:60},(_,n)=>({name:'Port '+(n+1),oper_status:n===0?2:1,admin_status:1,high_speed:10000,rx_mbps:n,tx_mbps:0,rx_errors:0,tx_errors:0}))}}}]};renderSwitches()`,context);
assert.equal(nodes.get('switch-ports').children[0].children[1].children.length,50);
assert.equal(nodes.get('switch-panels').children.length,1);
nodes.get('switch-link').value='down';vm.runInContext('renderSwitches()',context);
assert.equal(nodes.get('switch-ports').children[0].children[1].children.length,1);
nodes.get('switch-link').value='unknown';vm.runInContext('state.data.devices[0].metrics.stale=true;renderSwitches()',context);
assert.equal(nodes.get('switch-ports').children[0].children[1].children.length,50);
const first=nodes.get('switch-ports').children[0].children[1].children[0];
assert.equal(first.children[4].children[0].textContent,'—');
nodes.get('switch-search').value='no-match';vm.runInContext('renderSwitches()',context);
assert.equal(nodes.get('switch-ports').children[0].textContent,'Gösterilecek kayıt yok.');
console.log('Switch UI: pagination, status filters, stale suppression and empty search passed.');
