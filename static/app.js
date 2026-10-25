const $=id=>document.getElementById(id), token=document.querySelector('meta[name="token"]').content;
const hasKey=document.querySelector('meta[name="has-key"]').content==='true';
if(hasKey){$('key').hidden=true;$('keyLabel').hidden=true;$('apiHelper').textContent='La app ya tiene una clave de API configurada en el servidor. Pulsa «Generar» para crear el plano (tiene coste de uso).';}
let imageURL=null, zoom=1, pending=false;
function status(message,error=false){$('status').textContent=message;$('status').classList.toggle('error',error);}
async function call(path,data){const r=await fetch(path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-Plano-Token':token},body:data===undefined?undefined:JSON.stringify(data)});if(!r.ok){const e=await r.json();throw Error(e.error||'Error inesperado');}return r;}
async function json(path,data){return (await call(path,data)).json();}
function showSVG(svg,count){if(imageURL)URL.revokeObjectURL(imageURL);imageURL=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'}));$('drawing').src=imageURL;$('drawing').hidden=!count;$('empty').hidden=!!count;zoom=1;$('drawing').style.width='100%';$('drawing').style.height='100%';}
function stats(s){$('stats').textContent=`${s.count} entidades · Modelo en mm · ${Object.keys(s.layers).length} capas`;$('layers').replaceChildren();for(const [name,n] of Object.entries(s.layers)){const row=document.createElement('div');row.className='layer';for(const t of [name,String(n)]){const span=document.createElement('span');span.textContent=t;row.append(span);}$('layers').append(row);}}
function state(s){pending=false;$('proposal').hidden=true;showSVG(s.svg,s.summary.count);stats(s.summary);$('undo').disabled=!s.undo;}
function proposal(s){pending=true;showSVG(s.svg,s.summary.count);stats(s.summary);$('proposal').hidden=false;$('proposalText').textContent=s.message;$('assumptions').replaceChildren();for(const a of Array.isArray(s.assumptions)?s.assumptions:[]){const li=document.createElement('li');li.textContent=String(a);$('assumptions').append(li);}status(`${s.operations} operaciones preparadas. Revisa y aplica la propuesta.`);}
async function run(fn){const buttons=[...document.querySelectorAll('button')];const disabled=buttons.map(b=>b.disabled);buttons.forEach(b=>b.disabled=true);try{await fn();}catch(e){status(e.message,true);}finally{buttons.forEach((b,i)=>b.disabled=disabled[i]);try{const s=await json('/state');$('undo').disabled=!s.undo;}catch{}}}
function prompt(){const p=$('prompt').value.trim();if(!p)throw Error('Describe primero qué quieres dibujar o modificar.');return p;}
document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>{$('prompt').value=b.dataset.prompt;});
$('generate').onclick=()=>run(async()=>{const p=prompt();status('La IA está preparando el plano. Puede tardar unos minutos…');try{proposal(await json('/ai',{prompt:p,key:$('key').value.trim(),model:$('model').value.trim()}));}catch(e){state(await json('/cancel',{}));throw e;}});
$('accept').onclick=()=>run(async()=>{state(await json('/accept',{}));status('Cambios aplicados. Ya puedes exportar el plano.');});
$('cancel').onclick=()=>run(async()=>{state(await json('/cancel',{}));status('Propuesta descartada.');});
$('undo').onclick=()=>run(async()=>{state(await json('/undo',{}));status('Último cambio deshecho.');});
$('new').onclick=()=>run(async()=>{state(await json('/new',{}));status('Plano nuevo. Puedes recuperar el anterior con Deshacer.');});
$('example').onclick=()=>run(async()=>{state(await json('/example',{}));status('Ejemplo cargado: estudio de 6 × 4 m. Puedes descargar el DXF y el PDF.');});
$('import').onchange=()=>run(async()=>{const f=$('import').files[0];if(!f)return;if(f.size>12000000)throw Error('El archivo supera 12 MB.');if(!/\.dxf$/i.test(f.name))throw Error('Selecciona un archivo DXF.');status('Importando plano…');const bytes=new Uint8Array(await f.arrayBuffer());let s='';for(let i=0;i<bytes.length;i+=16384)s+=String.fromCharCode(...bytes.subarray(i,i+16384));state(await json('/import',{data:btoa(s),unitless_mm:$('unitless').checked}));status('Plano importado. El archivo original permanece intacto.');$('import').value='';});
async function download(format){if(pending)throw Error('Aplica o descarta la propuesta antes de descargar.');status('Preparando '+format.toUpperCase()+'…');const r=await call('/export',{format,paper:$('paper').value,scale:Number($('scale').value),title:$('title').value,sheet:format==='pdf'||$('sheet').checked});const blob=await r.blob(), url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='plano-estudio.'+format;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);status(format==='dxf'?'DXF descargado. Ábrelo en AutoCAD y usa Guardar como → DWG.':'PDF descargado. Imprime al 100 %, sin ajustar a página.');}
$('dxf').onclick=()=>run(()=>download('dxf'));$('pdf').onclick=()=>run(()=>download('pdf'));
function resize(delta){zoom=Math.max(.5,Math.min(3,zoom+delta));$('drawing').style.width=`${zoom*100}%`;$('drawing').style.height=`${zoom*100}%`;}
$('zoomIn').onclick=()=>resize(.25);$('zoomOut').onclick=()=>resize(-.25);
window.addEventListener('beforeunload',e=>{if($('drawing').hidden===false){e.preventDefault();e.returnValue='';}});
json('/state').then(state).catch(e=>status(e.message,true));
