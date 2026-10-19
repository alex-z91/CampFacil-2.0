'use strict';
// Esta URL deve corresponder ao domínio personalizado configurado no Render.
const API = 'https://api.meucamp.alexcoder.space';
const form = document.querySelector('#login-form');
const status = document.querySelector('#status');
const submit = form.querySelector('button[type="submit"]');
document.querySelector('#toggle').addEventListener('click', () => {
  const field = document.querySelector('#password');
  field.type = field.type === 'password' ? 'text' : 'password';
});
function feedback(message) { status.textContent = message; }
form.addEventListener('submit', async event => {
  event.preventDefault();
  submit.disabled = true;
  feedback('Verificando suas credenciais...');
  try {
    const response = await fetch(API + '/api/auth/login', {
      method: 'POST', credentials: 'include',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        email: document.querySelector('#email').value.trim(),
        password: document.querySelector('#password').value,
        remember: document.querySelector('#remember').checked
      })
    });
    if (!response.ok) throw new Error(response.status === 401
      ? 'Credenciais não reconhecidas. Confira o e-mail e a senha ou solicite a ativação da conta.'
      : 'Não foi possível autenticar. Verifique o serviço da API e tente novamente.');
    const meResponse = await fetch(API + '/api/me', { credentials: 'include', cache: 'no-store' });
    if (!meResponse.ok) throw new Error('Sessão iniciada, mas a verificação de acesso falhou.');
    const me = await meResponse.json();
    if (me.master) {
      feedback('Acesso Master validado. Redirecionando...');
      window.location.assign('plataforma.html');
    } else if (Array.isArray(me.organizations) && me.organizations.length) {
      feedback('Acesso de organizador validado. Redirecionando...');
      window.location.assign('admin.html');
    } else {
      feedback('Sua identidade foi confirmada, mas você ainda não possui permissões ativas no MEUCAMP.');
    }
  } catch (error) {
    feedback(error instanceof TypeError
      ? 'API indisponível. O subdomínio api.meucamp.alexcoder.space precisa estar configurado no Render e no DNS.'
      : error.message);
  } finally {
    submit.disabled = false;
  }
});
