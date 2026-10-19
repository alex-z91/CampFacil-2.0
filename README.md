# Camp Fácil 2.0

Protótipo de plataforma de eventos e inscrições de jiu-jítsu.

## Rotas

- `/` ou `index.html`: portal público com lista de eventos.
- `/#/evento/copa-kings`: detalhes demonstrativos da Copa Kings.
- `/#/inscricao/copa-kings`: simulação de inscrição, sem envio ou armazenamento de dados.
- `/admin.html`: painel administrativo demonstrativo; **não possui autenticação**.

## Segurança e limites

Projeto estático demonstrativo hospedável no GitHub Pages. Não coletar dados pessoais reais nem utilizar para pagamentos. O formulário público não persiste inscrições, enquanto os exemplos do painel administrativo usam `localStorage` do navegador. O banco Neon foi criado separadamente e ainda não está integrado.

## Publicação

GitHub → Settings → Pages → Deploy from a branch → `main` / `/(root)`. O arquivo `CNAME` contém `meucamp.alexcoder.space`, que precisa ter um registro DNS CNAME apontando para `alex-z91.github.io` na GoDaddy e ser confirmado no Pages.

## Próximas etapas

API autenticada, isolamento organizador/evento, cadastro seguro de atletas e responsáveis, tabela de categorias baseada em regulamento versionado, lotes e pagamento, checagem, chaves, resultados e publicação.
