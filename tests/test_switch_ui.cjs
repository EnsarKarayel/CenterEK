// Small DOM harness: exercise port filters, stale values and pagination without a server.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map(),events=new Map();
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.value='';this.dataset={};this.style={};this.classes=new Set();this.attributes={};this.classList={toggle:(key,value)=>value?this.classes.add(key):this.classes.delete(key),add:key=>this.classes.add(key),remove:key=>this.classes.delete(key),contains:key=>this.classes.has(key)};this.textContent=''}
 set textContent(value){this._text=String(value);this.children=[]}get textContent(){return this._text+this.children.map(c=>c.textContent??'').join('')}
 set id(value){this._id=value;nodes.set(value,this)}get id(){return this._id}
 append(...items){for(const item of items){this.children.push(item);if(item instanceof Element)item.parentNode=this;if(this.tag==='select'&&this.children.length===1)this.value=item.value}}
 prepend(...items){this.children.unshift(...items)}
 replaceChildren(...items){for(const c of this.children)if(c instanceof Element)c.parentNode=null;this.children=[];this.append(...items)}
 addEventListener(){}setAttribute(key,value){this.attributes[key]=value}removeAttribute(key){delete this.attributes[key]}focus(){this.focused=true}after(){}scrollIntoView(){}
}
for(const id of ['device-search','client-search','ad-search','session-search','logout','live-dashboard']){const e=new Element('div');e.id=id}
const main=new Element('main');
const context=vm.createContext({Node:Element,document:{body:new Element('body'),getElementById:id=>nodes.get(id),createElement:tag=>new Element(tag),querySelectorAll:()=>[],querySelector:()=>main,addEventListener(name,callback){const list=events.get(name)||[];list.push(callback);events.set(name,list)}},fetch:()=>new Promise(()=>{}),AbortSignal:{timeout(){}},console,setTimeout(){},Date,Number});
vm.runInContext(fs.readFileSync('web/app.js','utf8'),context);
assert.equal(vm.runInContext('portMode({oper_status:1,admin_status:1},true)',context),'up');
assert.equal(vm.runInContext('portMode({oper_status:2,admin_status:1},true)',context),'down');
assert.equal(vm.runInContext('portMode({oper_status:2,admin_status:2},true)',context),'disabled');
assert.equal(vm.runInContext('portMode({oper_status:1,admin_status:1},false)',context),'unknown');
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
assert.ok(nodes.get('switch-ports').textContent.includes('Gösterilecek kayıt yok.'));
nodes.get('switch-search').value='';vm.runInContext('renderSwitches()',context);
const input=nodes.get('switch-ports').children[0].children[0].children[1].children[1].children[0];input.value='Port 50';input.oninput();
assert.equal(nodes.get('switch-ports').children[0].children[1].children.length,1);
vm.runInContext('renderSwitches()',context);assert.equal(input.value,'Port 50');
assert.equal(nodes.get('switch-ports').children[0].children[1].children.length,1);
console.log('Switch UI: pagination, status filters, stale suppression and empty search passed.');

vm.runInContext(fs.readFileSync('web/dashboard.js','utf8'),context);
vm.runInContext("state.data.alerts=[];state.data.devices[0].metrics.stale=false;state.data.devices[0].metrics.values.memory_percent=50",context);
events.get('centerek:status').at(-1)();
const dashboard=main.children.find(c=>c.dataset.section==='dashboard');assert.ok(dashboard);assert.equal(dashboard.children[1].children.length,9);
assert.ok(dashboard.children[1].children.find(c=>c.dataset.widget==='memory').textContent.includes('50'));
console.log('Dashboard widgets render real measurements.');

const healthCard=dashboard.children[1].children[0],zoom=healthCard.children[0].children[1];zoom.onclick();assert.ok(healthCard.classList.contains('widget-expanded'));assert.equal(healthCard.attributes['aria-modal'],'true');
events.get('centerek:status').at(-1)();assert.ok(healthCard.classList.contains('widget-expanded'));
events.get('keydown').at(-1)({key:'Escape',preventDefault(){}});assert.ok(!healthCard.classList.contains('widget-expanded'));assert.equal(healthCard.attributes['aria-modal'],undefined);assert.ok(zoom.focused);
console.log('Widget expand, live refresh, Escape close and focus restoration passed.');

vm.runInContext("state.data.devices.push({id:'srv',name:'Capacity Server',kind:'Sunucu',host:'192.0.2.50',status:'up',stale:false,metrics:{status:'ok',stale:false,values:{memory_total_gb:200,memory_used_gb:80,cpu_percent:25,health:'green',datastores:[{name:'data1',capacity_gb:1000,free_gb:400,accessible:true}],network_adapters:[{name:'vmnic0',mac:'aa:bb:cc:dd:ee:ff'}]}}})",context);events.get('centerek:status').at(-1)();
const serverWidget=dashboard.children[1].children.find(c=>c.dataset.widget==='servers');assert.ok(serverWidget.textContent.includes('120 GB'));assert.ok(serverWidget.textContent.includes('aa:bb:cc:dd:ee:ff'));assert.ok(serverWidget.textContent.includes('400 / 1.000 GB'));
vm.runInContext("state.data.devices.at(-1).metrics.stale=true",context);events.get('centerek:status').at(-1)();assert.ok(!serverWidget.textContent.includes('120 GB'));assert.ok(serverWidget.textContent.includes('Kaynak bekleniyor'));
console.log('Server RAM free, datastore, NIC MAC and stale suppression passed.');
