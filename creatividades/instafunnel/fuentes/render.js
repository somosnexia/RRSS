const {chromium}=require('playwright');const fs=require('fs');
(async()=>{const list=JSON.parse(fs.readFileSync(process.argv[2]));const only=process.argv[3]?new RegExp(process.argv[3]):null;
const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1920}});
for(const [n,s] of list){if(only&&!only.test(n))continue;const h=s==='s45'?1350:1920;await p.setViewportSize({width:1080,height:h});
await p.goto('file://'+__dirname+'/html/'+n+'.html');await p.evaluate(()=>document.fonts.ready);await p.waitForTimeout(250);
await p.screenshot({path:__dirname+'/png/'+n+'.png',clip:{x:0,y:0,width:1080,height:h}});}
await b.close();})();
