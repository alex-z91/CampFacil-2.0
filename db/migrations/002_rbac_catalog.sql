-- Camp Fácil 2.0: catálogo RBAC, escopo obrigatório e papéis
CREATE TABLE IF NOT EXISTS public.permissions (
 key text PRIMARY KEY,
 description text NOT NULL
);
CREATE TABLE IF NOT EXISTS public.roles (
 key text PRIMARY KEY,
 scope text NOT NULL CHECK (scope IN ('platform','organizer')),
 description text NOT NULL
);
CREATE TABLE IF NOT EXISTS public.role_permissions (
 role_key text NOT NULL REFERENCES public.roles(key) ON DELETE CASCADE,
 permission_key text NOT NULL REFERENCES public.permissions(key) ON DELETE CASCADE,
 PRIMARY KEY(role_key, permission_key)
);
INSERT INTO public.permissions(key,description) VALUES
 ('platform.organizers.read','Consultar organizadores'),('platform.organizers.manage','Aprovar ou suspender organizadores'),
 ('platform.users.manage','Gerenciar usuários da plataforma'),('platform.audit.read','Consultar auditoria global'),
 ('organizer.events.read','Consultar eventos da organização'),('organizer.events.manage','Criar e editar eventos'),
 ('organizer.members.manage','Gerenciar membros da organização'),('organizer.registrations.manage','Gerenciar inscrições'),
 ('organizer.finance.read','Consultar financeiro'),('organizer.finance.manage','Gerenciar lançamentos e cobranças'),
 ('organizer.checkin.manage','Realizar checagem'),('organizer.brackets.manage','Gerenciar chaveamento'),
 ('organizer.scoring.manage','Registrar resultados'),('organizer.reports.read','Consultar relatórios')
 ON CONFLICT (key) DO NOTHING;
INSERT INTO public.roles(key,scope,description) VALUES
 ('master','platform','Gerente Master'),('support','platform','Suporte da plataforma'),
 ('admin','organizer','Administrador de organizador'),('manager','organizer','Gerente de evento'),
 ('finance','organizer','Financeiro'),('checkin','organizer','Operador de checagem'),
 ('scorer','organizer','Pontuador'),('viewer','organizer','Consulta e relatórios')
 ON CONFLICT (key) DO NOTHING;
INSERT INTO public.role_permissions(role_key,permission_key)
 SELECT r.key,p.key FROM public.roles r CROSS JOIN public.permissions p WHERE
 (r.key='master') OR
 (r.key='support' AND p.key IN ('platform.organizers.read','platform.audit.read')) OR
 (r.key='admin' AND p.key LIKE 'organizer.%') OR
 (r.key='manager' AND p.key IN ('organizer.events.read','organizer.events.manage','organizer.registrations.manage','organizer.checkin.manage','organizer.brackets.manage','organizer.scoring.manage','organizer.reports.read','organizer.finance.read')) OR
 (r.key='finance' AND p.key IN ('organizer.events.read','organizer.finance.read','organizer.finance.manage','organizer.reports.read')) OR
 (r.key='checkin' AND p.key IN ('organizer.events.read','organizer.checkin.manage','organizer.registrations.manage')) OR
 (r.key='scorer' AND p.key IN ('organizer.events.read','organizer.brackets.manage','organizer.scoring.manage')) OR
 (r.key='viewer' AND p.key IN ('organizer.events.read','organizer.reports.read'))
 ON CONFLICT DO NOTHING;