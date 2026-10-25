const form=document.getElementById('loginForm'), pass=document.getElementById('password'), err=document.getElementById('loginError');
form.addEventListener('submit',async e=>{
  e.preventDefault();
  err.hidden=true;
  const btn=form.querySelector('button'); btn.disabled=true;
  try{
    const r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pass.value})});
    if(r.ok){location.href='/';return;}
    const data=await r.json().catch(()=>({}));
    err.textContent=data.error||'No se pudo iniciar sesión.'; err.hidden=false;
  }catch{
    err.textContent='No se pudo conectar con el servidor.'; err.hidden=false;
  }finally{
    btn.disabled=false; pass.select();
  }
});
