// Real headless Chrome QA, isolated from the user's browser profile.
const {spawn}=require('child_process');
const fs=require('fs');
const path=require('path');
const assert=require('assert');
const {pathToFileURL}=require('url');
const run=path.resolve(process.argv[2]);
const records=JSON.parse(fs.readFileSync(path.join(run,'report.html'),'utf8').match(/id="records">([\s\S]*?)<\/script>/)[1]);
const scrubIndex=Math.max(0,Math.min(75,records.length-2));
const root=path.resolve(__dirname,'..');
const profile=path.join(root,'local','browser-report-test');
const child=spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',[
  '--headless','--disable-gpu','--no-first-run','--remote-debugging-address=127.0.0.1',
  '--remote-debugging-port=9227',`--user-data-dir=${profile}`,'about:blank'
],{stdio:'ignore',windowsHide:true});
const pause=ms=>new Promise(r=>setTimeout(r,ms));
let socket;
(async()=>{
 try {
  let target;
  for(let i=0;i<100;i++){
   try {target=await (await fetch('http://127.0.0.1:9227/json/new?'+encodeURIComponent(pathToFileURL(path.join(run,'report.html')).href),{method:'PUT'})).json();break;}
   catch {await pause(100);}
  }
  assert(target?.webSocketDebuggerUrl,'QA browser failed to start');
  socket=new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r,j)=>{socket.addEventListener('open',r,{once:true});socket.addEventListener('error',j,{once:true});});
  const pending=new Map();let id=0;
  socket.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}});
  const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});socket.send(JSON.stringify({id:n,method,params}));});
  const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
  await send('Page.enable');
  for(let i=0;i<100;i++){if(await evaluate("!!document.getElementById('observer')?.src"))break;await pause(50);}
  const results=[];
  for(const [name,width,height] of [['desktop',1440,1080],['mobile',390,844]]){
   await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false});
   await evaluate('Promise.all(Array.from(document.images).map(i=>i.decode()))');
   const metrics=await evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,observer:document.getElementById("observer").naturalWidth})');
   assert(metrics.scroll<=width,`${name} horizontal overflow: ${JSON.stringify(metrics)}`);
   assert.equal(metrics.observer,640);
   const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
   fs.writeFileSync(path.join(run,`viewer-${name}.png`),Buffer.from(shot.data,'base64'));
   results.push({viewport:name,...metrics});
  }
  const frame=await evaluate(`document.getElementById('slider').value='${scrubIndex}';document.getElementById('slider').dispatchEvent(new Event('input'));document.getElementById('frame').textContent`);
  assert(frame.includes(`Step ${records[scrubIndex].step_index}`));
  await evaluate('Promise.all(Array.from(document.images).map(i=>i.decode()))');
  await evaluate("document.getElementById('play').click()");
  await pause(250);
  if(records.length>1)assert(await evaluate(`Number(document.getElementById('slider').value)>${scrubIndex}`));
  await evaluate("document.getElementById('play').click()");
  const output={status:'passed',checks:['real_browser_image_decode','desktop_no_horizontal_overflow','mobile_no_horizontal_overflow','slider_updates_frame','playback_advances'],viewports:results};
  fs.writeFileSync(path.join(run,'browser-check.json'),JSON.stringify(output,null,2));
  console.log(JSON.stringify(output));
 } finally {if(socket)socket.close();child.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
