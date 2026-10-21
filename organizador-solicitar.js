(()=>{'use strict';
const form=document.querySelector('#application'),status=document.querySelector('#feedback'),btn=form.querySelector('[type=submit]');
function notice(title,detail,kind='error',link){
 status.dataset.state=kind;status.replaceChildren();
 const icon=document.createElement('span');icon.className='alert-icon';icon.setAttribute('aria-hidden','true');icon.textContent=kind==='success'?'✓':kind==='loading'?'…':'!';
 const body=document.createElement('span');body.className='alert-body';
 const head=document.createElement('strong');head.textContent=title;body.append(head);
 if(detail){const p=document.createElement('span');p.textContent=detail;body.append(p)}
 if(link){const a=document.createElement('a');a.href=link.href;a.textContent=link.label;body.append(a)}
 status.append(icon,body);
 if(kind!=='loading'){status.scrollIntoView({behavior:'smooth',block:'nearest'});status.focus({preventScroll:true})}
}
form.addEventListener('submit',async e=>{
 e.preventDefault();if(!form.reportValidity())return;
 btn.disabled=true;notice('Criando sua conta','Aguarde enquanto validamos os dados.','loading');
 const d=Object.fromEntries(new FormData(form));d.consent=!!form.elements.consent.checked;
 d.state=(d.state||'').trim().toUpperCase();d.email=(d.email||'').trim().toLowerCase();
 try{
  const r=await fetch('https://api.meucamp.alexcoder.space/api/public/organizer-signup',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(d)});
  const result=await r.json().catch(()=>({}));
  if(!r.ok)throw Error(typeof result.detail==='string'?result.detail:'Não foi possível concluir o cadastro. Tente novamente.');
  form.reset();notice('Conta criada!','Confirme seu e-mail e faça login para preparar seu campeonato.','success',{href:'login.html',label:'Ir para o login →'});
 }catch(err){
  notice('Não foi possível criar a conta',err.message||'Tente novamente mais tarde.','error',{href:'recuperar-acesso.html',label:'Já tem cadastro? Recuperar acesso →'});
 }finally{btn.disabled=false}
});
})();