# API autenticada — Camp Fácil

Esta API é um **esqueleto de desenvolvimento**, não um serviço publicado. Implementa consultas protegidas que falham com 401/403 por padrão.

## Iniciar localmente

1. Criar ambiente virtual Python e instalar `pip install -r backend/requirements.txt`.
2. Definir `DATABASE_URL`, `NEON_AUTH_URL` e `FRONTEND_ORIGIN` exclusivamente no ambiente do servidor.
3. Executar `uvicorn backend.main:app --reload` no diretório do projeto.

## Observações de autenticação

A API encaminha o cookie de sessão ao endpoint do Neon Auth para verificar o usuário e consulta permissões no PostgreSQL. Antes de habilitar o login, será necessário publicar a API com HTTPS e integrar o cliente Neon Auth, testar CORS e cookies entre origens e implementar recuperação de senha, convites/verificação de e-mail, proteção contra CSRF e monitoramento. **Hospedar o frontend no GitHub Pages não executa esta API**. Recomenda-se proxy reverso no mesmo domínio do frontend para os endpoints `/api/*` e autenticação, ou arquitetura equivalente com sessões testadas.

A conta Master existente segue `enabled=false`; nenhum vínculo de organizador foi ativado automaticamente.

## Rotas iniciais

- `GET /api/health` — saúde
- `GET /api/me` — identidade verificada, papéis disponíveis
- `GET /api/platform/organizers` — permissão global
- `GET /api/organizers/{id}/permissions` — escopo de organização

Não coletar dados reais até testes de segurança e implantação completos.
