# Publicar Arena Run em arenarun.alexcoder.space

**Atenção:** `alex-z91/MeuCamp` já está reservado ao Arena Pro. O Pages de um repositório aceita um domínio personalizado por site. **Não** configure `arenarun.alexcoder.space` no Pages de `MeuCamp`.

## Repositório exclusivo
1. Crie `alex-z91/Arena-Run` no GitHub (repositório público, se utilizar o plano gratuito).
2. Copie para a **raiz** do novo repositório o arquivo `arena-run/index.html` desta branch. A primeira publicação será a demonstração estática V0.1, que não possui autenticação ou pagamento reais.
3. Copie `arena-run/deploy-pages.yml` para `.github/workflows/pages.yml` do novo repositório.
4. Em Settings → Pages, selecione **Source: GitHub Actions**.
5. No mesmo Settings → Pages, informe **Custom domain: `arenarun.alexcoder.space`** e salve.
6. Na zona DNS de `alexcoder.space` (GoDaddy se for a zona autoritativa), crie:
   - Tipo: **CNAME**
   - Nome/Host: **arenarun**
   - Valor/Destino: **alex-z91.github.io**
   - TTL: padrão
7. Aguarde o GitHub validar DNS/certificado e marque **Enforce HTTPS** quando disponível.
8. Em Actions, execute o workflow de publicação, ou envie um commit para a main.
9. Acesse https://arenarun.alexcoder.space e verifique o certificado HTTPS e as rotas.

**Não** substitua nenhum registro `@,` `www` ou `meucamp` já existente. Não mantenha dois CNAMEs conflitantes para o mesmo host.

## Por que não publicar a tela de homologação no Pages?
`arena-run/homologacao.html` usa chamadas em `/api/*` para um serviço Flask e **não funciona sozinha** em Pages. O backend, banco e credenciais não são hospedados no GitHub Pages. Para homologação pública completa, hospede Flask em serviço de aplicações com HTTPS e defina URL/base de API no frontend, com CORS restritivo e políticas de segurança. Até lá, mantenha apenas o protótipo de demonstração público.

## Verificação no Windows (PowerShell)
```powershell
Resolve-DnsName arenarun.alexcoder.space -Type CNAME
```
O resultado deve apontar para `alex-z91.github.io`.
