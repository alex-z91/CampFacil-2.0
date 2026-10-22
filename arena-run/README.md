# Arena Run V0.1 — protótipo de homologação

Este diretório contém um protótipo estático isolado do Arena Pro. Não modifica rotas existentes.

## Executar
Abra `arena-run/index.html` no navegador, ou execute `python -m http.server 8000` na raiz do repositório e acesse `http://localhost:8000/arena-run/`.

## Roteiro de teste
1. Abrir o catálogo, testar cards e responsividade.
2. Selecionar corrida e distância.
3. Preencher **somente dados fictícios** e selecionar camiseta.
4. Revisar o resumo; confirmar inscrição **simulada**.
5. Abrir Organizador, conferir contagem, receita **fictícia** e exportação CSV.
6. Atualizar a página, confirmar persistência local; apagar dados de teste.

## Limites
Sem autenticação, banco de dados remoto, pagamento, QR Code, webhook, CPF real ou validação federativa. O painel é público e demonstrativo. Dados são guardados em `localStorage` no navegador e não são compartilhados entre dispositivos, portanto jamais usar inscrições reais ou dados pessoais.

## Próximos incrementos para produção
- API com autenticação e isolamento multi-organizador, RBAC e trilhas de auditoria.
- Banco PostgreSQL/Neon, migrations e estado transacional de vagas.
- Inscrição com regras de categoria e idade parametrizadas, autorização de responsáveis e LGPD.
- Reserva expirada de vaga, idempotência, PIX/cartão e confirmação via webhook.
- E-mail/QR Code, kit, retirada, números de peito, cronômetro terceirizado e relatórios.

Branch: `feat/arena-run-mvp`.
