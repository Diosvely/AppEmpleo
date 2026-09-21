-- =====================================================================
--  APPEMPLEO — MIGRACION 05
--  Cerrar el acceso a un unico propietario.
--
--  POR QUE HACE FALTA
--  Las politicas anteriores decian "to authenticated using (true)":
--  CUALQUIER usuario autenticado, no solo tu. Mientras el repositorio
--  era privado daba igual. Al publicarlo, la direccion del proyecto
--  queda a la vista, y si el registro de usuarios esta abierto
--  cualquiera podria crearse una cuenta y leer tus candidaturas.
--
--  Esto se cierra en dos sitios, y hay que hacer LOS DOS:
--    1. Aqui, atando las politicas a tu identificador de usuario.
--    2. En el panel de Supabase, desactivando el registro abierto:
--       Authentication > Sign In / Providers > Email >
--       "Allow new users to sign up"  ->  apagado.
--
--  Pegar entero en Supabase > SQL Editor > New query > Run.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. QUIEN ES EL PROPIETARIO
--
-- Una sola fila con tu identificador. Se guarda aqui en vez de
-- escribirlo dentro de cada politica para que, si algun dia cambias de
-- cuenta, solo tengas que tocar una linea.
-- ---------------------------------------------------------------------
create table if not exists propietario (
  id       boolean primary key default true check (id),   -- fuerza fila unica
  user_id  uuid not null,
  email    text,
  fijado_en timestamptz not null default now()
);

alter table propietario enable row level security;
-- Nadie la lee desde la aplicacion: solo la usan las funciones internas.
revoke all on propietario from anon, authenticated;

-- Se rellena sola con el primer usuario que existe en el proyecto, que
-- eres tu. Si hubiera varios, coge el mas antiguo.
insert into propietario (id, user_id, email)
select true, u.id, u.email
from auth.users u
order by u.created_at asc
limit 1
on conflict (id) do nothing;

-- Comprueba que ha cogido a alguien. Si esto falla es que aun no has
-- creado tu usuario en Authentication > Users.
do $$
begin
  if not exists (select 1 from propietario) then
    raise exception
      'No hay ningun usuario en el proyecto. Crea el tuyo en '
      'Authentication > Users y vuelve a ejecutar esta migracion.';
  end if;
end $$;


-- ---------------------------------------------------------------------
-- 2. LA COMPROBACION
--
-- stable: Postgres la cachea dentro de la misma consulta en vez de
-- ejecutarla fila a fila, que en una tabla de miles de ofertas importa.
-- ---------------------------------------------------------------------
create or replace function es_propietario()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from propietario p where p.user_id = auth.uid()
  );
$$;

grant execute on function es_propietario() to authenticated;


-- ---------------------------------------------------------------------
-- 3. REEMPLAZAR LAS POLITICAS
-- ---------------------------------------------------------------------
drop policy if exists p_oferta_auth        on oferta;
drop policy if exists p_oferta_fuente_auth on oferta_fuente;
drop policy if exists p_ejecucion_auth     on ejecucion;
drop policy if exists p_candidatura_auth   on candidatura;
drop policy if exists p_cv_version_auth    on cv_version;

create policy p_oferta_propietario on oferta
  for all to authenticated using (es_propietario()) with check (es_propietario());

create policy p_oferta_fuente_propietario on oferta_fuente
  for all to authenticated using (es_propietario()) with check (es_propietario());

create policy p_ejecucion_propietario on ejecucion
  for select to authenticated using (es_propietario());

create policy p_candidatura_propietario on candidatura
  for all to authenticated using (es_propietario()) with check (es_propietario());

create policy p_cv_version_propietario on cv_version
  for all to authenticated using (es_propietario()) with check (es_propietario());


-- ---------------------------------------------------------------------
-- 3bis. LAS VISTAS TAMBIEN
--
-- Por defecto una vista se ejecuta con los permisos de quien la creo,
-- no de quien la consulta. Eso significa que v_bandeja y compania se
-- saltarian las politicas de arriba y ensenarian todo a cualquiera que
-- tuviera sesion. security_invoker lo corrige: la vista pasa a aplicar
-- la seguridad del usuario que pregunta.
--
-- Se recorren todas las vistas del esquema para no dejarse ninguna,
-- incluidas las que anadas mas adelante.
-- ---------------------------------------------------------------------
do $$
declare
  v record;
begin
  for v in
    select schemaname, viewname from pg_views where schemaname = 'public'
  loop
    execute format('alter view %I.%I set (security_invoker = on)',
                   v.schemaname, v.viewname);
  end loop;
end $$;


-- ---------------------------------------------------------------------
-- 4. COMPROBAR QUE HA QUEDADO BIEN
--
-- Las cinco politicas deben apelar a es_propietario(). Si alguna sigue
-- diciendo "true", no se ha aplicado.
-- ---------------------------------------------------------------------
select
  tablename                                        as tabla,
  policyname                                       as politica,
  case when qual like '%es_propietario%' then 'atada al propietario'
       else 'ABIERTA — revisar' end                as estado
from pg_policies
where schemaname = 'public'
  and tablename in ('oferta','oferta_fuente','ejecucion','candidatura','cv_version')
order by 1;

-- Las vistas deben aplicar la seguridad de quien consulta
select
  c.relname as vista,
  case when 'security_invoker=on' = any(c.reloptions)
       then 'aplica tus politicas'
       else 'SE LAS SALTA — revisar' end as estado
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where c.relkind = 'v' and n.nspname = 'public'
order by 1;

-- Y quien ha quedado como propietario
select user_id, email, fijado_en from propietario;
