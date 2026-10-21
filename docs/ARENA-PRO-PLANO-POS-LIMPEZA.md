# Arena Pro — plano de implementação pós-limpeza de 21/10/2026

## Escopo confirmado
1. Cadastro completo do organizador, com senha e confirmação de e-mail via Neon Auth. Login disponível imediatamente; conta fica em onboarding, sem capacidade de publicar evento ou cobrar inscrição.
2. Organizadores autenticados criam e editam campeonatos em **rascunho** sem autorização da equipe Arena Pro.
3. Primeira publicação precisa de revisão e aprovação Master. A autorização é auditada e por organização/evento; nível de autonomia posterior é concedido expressamente pelo Master.
4. Duas datas obrigatórias e distintas por evento: encerramento de novas inscrições e encerramento de pagamento, sendo pagamento posterior ou igual ao encerramento das inscrições.
5. Inscrição registrada com pagamento pendente. Confirmação financeira somente por webhook validado do provedor ou por confirmação presencial auditada. Status de pagamento é separado de elegibilidade esportiva.
6. Lista pública de inscritos inclui pendentes com etiqueta; nenhuma informação financeira sensível, CPF, endereço ou e-mail é publicada.
7. Ao término do prazo de pagamento, uma tarefa **persistente e idempotente no servidor** congela a elegibilidade e gera rascunhos das chaves. Não depender de abertura de página ou cron do navegador. Registrar data, evento, versão e falhas, com reprocessamento seguro. Se o serviço estiver suspenso, processar a fila ao retomar.
8. Chaves incluem apenas inscrições elegíveis, com pagamento registrado até o prazo ou cortesia explicitamente autorizada; eventos devem permitir prazo para liquidação de webhooks atrasados, sem misturar data da transação com data de notificação. Nenhuma alteração silenciosa depois de publicar.
9. Catálogos versionados por regulamento (CBJJ/IBJJF, CBJJE, Personalizado), sexo, idade por ano de nascimento, faixa, Gi/No-Gi, peso. Exibir intervalo completo e pesagem com uniforme. Infantil/juvenil NÃO herda pesos de adultos. O catálogo precisa ser importado e testado por fonte oficial antes da seleção obrigatória.

## Entregue neste ciclo
- Lista pública mostra inscrições ainda pendentes com etiqueta e mantém a exclusão dos cancelados.
- Inscrição administrativa identifica Gi / No-Gi e peso mínimo–máximo para as categorias efetivamente cadastradas.

## A implementar em migrações independentes
A. Neon Auth: cadastro direto, onboarding de organização, RBAC sem escalonamento de permissões, recuperação/validação de e-mail, testes.
B. Política de aprovação: status + solicitações + auditoria + liberação exclusivamente Master; autenticação não pode significar aprovação comercial.
C. Migração DB do prazo de pagamento (TIMESTAMPTZ), constraints e transições; interface para organizador.
D. Job server-side de fechamento e geração de chaves com exclusão mútua, idempotência, atrasos de liquidação, log e testes.
E. Tabelas oficiais versionadas e importação validada Gi/No-Gi/infantil/juvenil/master, vínculo de regulamento ao evento.
F. Inscrição pública autenticada/antifraude, classificação por peso no servidor, fluxos de pagamento e recibos.
G. Teste de integração (Neon staging, cobrança simulada, calendário, geração, impressão, aprovação).

## Restrições de segurança
Não resetar banco nem alterar registros financeiros em produção; backup antes de migrações. Manter acesso Master, papéis e permissões. Nunca marcar pagamento como recebido a partir de formulário público. Não aceitar categoria por valores informados pelo cliente sem validação no servidor.

## Fontes para validação do catálogo
- CBJJE: https://www.cbjje.com.br/?p=tabela-de-peso (Gi/No-Gi 2026)
- CBJJ pesagem: https://cbjj.com.br/weigh-ins
- Regulamentos por evento podem diferir do catálogo padrão.
