# Camp Fácil 2.0

Protótipo público e demonstrativo da nova plataforma Camp Fácil. **Não usar para inscrições ou pagamentos reais.**

## Como executar

Abra `index.html` no navegador ou acesse a URL do GitHub Pages depois de habilitá-lo.

## Recursos demonstrativos

- Dashboard responsivo
- Cadastro de atletas fictícios, busca e CSV
- Confirmação manual fictícia de pagamentos e checagem
- Chaveamento demonstrativo para quatro atletas
- Lançamentos financeiros fictícios

Os dados são salvos apenas no `localStorage` do dispositivo e não são sincronizados. Não há autenticação, backend conectado, integração com Neon, pagamentos reais ou regras oficiais completas.

## Publicação

GitHub → Settings → Pages → Build and deployment → Deploy from a branch → `main` / `(root)` → Save.

Para um subdomínio, configure o campo **Custom domain** no Pages e crie um CNAME na GoDaddy para `alex-z91.github.io` (sem `https://`). Só criar um arquivo `CNAME` depois que o subdomínio escolhido estiver definido.

## Desenvolvimento

Backend, controle de acesso, regras de categorias e pagamentos serão implementados em ambiente seguro posteriormente.
