const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const html = fs.readFileSync(process.argv[2], 'utf8');
const payload = html.match(/<script type="application\/json" id="records">([\s\S]*?)<\/script>/)[1];
const records = JSON.parse(payload);
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const nodes = new Map();
function get(id) {
  if (!nodes.has(id)) nodes.set(id, { value: '0', textContent: '', attrs: {}, setAttribute(k,v) { this.attrs[k]=v; } });
  return nodes.get(id);
}
get('records').textContent = payload;
let tick;
vm.runInNewContext(script, {document:{getElementById:get}, setInterval: fn => {tick=fn;}, console});
assert.equal(get('slider').max, records.length-1);
assert.equal(get('eye').src, 'frames/000000.png');
assert.equal(get('observer').src, 'frames/observer_000000.png');
const index=Math.min(45,records.length-1);
get('slider').value = String(index); get('slider').oninput();
assert(get('frame').textContent.includes(`Step ${index}`));
assert(get('frame').textContent.includes(`contact ${records[index].observation.contacts.blocked}`));
assert.equal(get('observer').src, records[index].privileged.observer_rgb.path);
assert.equal(Number(get('agent').attrs.cx),records[index].privileged.position_cm[0]);
get('play').onclick(); tick();
assert.equal(Number(get('slider').value), (index+1)%records.length);
console.log(JSON.stringify({check:'report_javascript_logic',status:'passed',scope:'Node DOM stub; not a browser rendering test'}));
