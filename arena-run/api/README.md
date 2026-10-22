# API de homologação — Arena Run

Esta API é experimental e ainda **não está pronta para produção**. Sem gateway real, rate limits, CSRF se migrar para cookies, recuperação de senha, LGPD completa, expiração de reserva e controle transacional de vagas sob concorrência.

## Instalação local
```sh
cd arena-run/api
python -m venv .venv
# Ative a .venv no seu terminal
pip install -r requirements.txt
```
Defina APP_ENV=development, SECRET_KEY aleatória, BOOTSTRAP_MASTER_EMAIL e BOOTSTRAP_MASTER_PASSWORD (mínimo 12 caracteres) nas variáveis de ambiente. Não copie senhas reais para o repositório. Para PostgreSQL, defina DATABASE_URL com URI do seu banco Neon. Se não configurar DATABASE_URL, usa SQLite local apenas para desenvolvimento.

```sh
python app.py
```
A API atenderá em http://127.0.0.1:5001. O cliente em homologacao.html funciona quando servido na **mesma origem da API**. Execute a partir do diretório `arena-run`:
```sh
# em outro terminal, depois de instalar as dependências
cd arena-run
python -c "from api.app import create_app; a=create_app(); a.run(host='127.0.0.1',port=5001)"
```
O cliente SPA de homologação está disponível em `/homologacao.html` pela API depois de configurar a rota estática (veja app.py). Endpoints em `/api/*`.

## Endpoints
- POST /api/auth/register — {name,email,password,role:"runner"|"organizer"}
- POST /api/auth/login — {email,password}
- GET /api/me — Bearer token
- GET /api/events — catálogo público
- POST /api/events — organizador aprovado/master, inclui distances:[{label,price_cents,capacity}]
- POST /api/registrations — atleta autenticado, {distance_id,shirt_size}
- GET /api/registrations/me — inscrições do usuário
- GET /api/organizer/registrations — inscrições dos eventos do organizador
- GET /api/master/organizers — cadastro organizadores
- POST /api/master/organizers/{id}/approve — aprova organizador
- POST /api/demo/registrations/{id}/confirm — master e ENABLE_DEMO_PAYMENT=1, apenas teste

Todos os preços em centavos. Um cadastro de organizador aguarda aprovação. As inscrições iniciam com status `awaiting_payment` e **não representam vaga paga**. Não habilite pagamentos de demonstração em produção.

## Próximos bloqueios para produção
Criar migrations Alembic; autenticação com tokens revogáveis e rate limiting; lock na transação da capacidade e reserva com TTL; webhook assinado/idempotente do PSP em sandbox; política de dados pessoais e consentimento; testes automatizados e deploy privado com HTTPS.
