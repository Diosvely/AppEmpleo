-- =====================================================================
--  APPEMPLEO — MIGRACION 02
--  Geografia de tres estados + nivel del puesto.
--  Pegar entero en Supabase > SQL Editor > New query > Run.
--  No borra ninguna oferta ni toca tu triaje manual.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. COLUMNAS NUEVAS
-- ---------------------------------------------------------------------
alter table oferta add column if not exists alcance text;
alter table oferta add column if not exists nivel   text;

-- Rellenar lo que ya hay antes de poner las restricciones.
-- Lo que antes valia false pasa a 'revisar', no a 'descartada':
-- no sabemos si era inalcanzable o si solo faltaba informacion.
update oferta
   set alcance = case when encaja_geografia then 'alcanzable' else 'revisar' end
 where alcance is null;

update oferta set nivel = 'desconocido' where nivel is null;

alter table oferta alter column alcance set default 'revisar';
alter table oferta alter column nivel   set default 'desconocido';
alter table oferta alter column alcance set not null;
alter table oferta alter column nivel   set not null;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'oferta_alcance_check') then
    alter table oferta add constraint oferta_alcance_check
      check (alcance in ('alcanzable','revisar','descartada'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'oferta_nivel_check') then
    alter table oferta add constraint oferta_nivel_check
      check (nivel in ('junior','senior','lead','directivo','desconocido'));
  end if;
end $$;

create index if not exists ix_oferta_alcance on oferta (alcance, prioridad, primera_vez_vista desc);
create index if not exists ix_oferta_nivel   on oferta (nivel);

-- La columna vieja se deja un tiempo por si quieres comparar.
-- Cuando estes conforme, descomenta esta linea y ejecutala:
-- alter table oferta drop column encaja_geografia;

-- ---------------------------------------------------------------------
-- 2. FUNCION DE INGESTA ACTUALIZADA
-- alcance y nivel se recalculan en cada pasada: son datos derivados,
-- asi que si mejoramos las reglas, las ofertas antiguas se corrigen solas.
-- ---------------------------------------------------------------------
create or replace function ingerir_ofertas(datos jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_nuevas       integer := 0;
  v_actualizadas integer := 0;
begin
  with entrada as (
    select * from jsonb_to_recordset(datos) as x(
      huella                  text,
      titulo                  text,
      titulo_norm             text,
      empresa                 text,
      empresa_norm            text,
      ubicacion_texto         text,
      pais                    text,
      comunidad               text,
      provincia               text,
      municipio               text,
      modalidad               text,
      contrato                text,
      jornada                 text,
      salario_min             numeric,
      salario_max             numeric,
      salario_periodo         text,
      salario_publicado       boolean,
      salario_estimado        boolean,
      salario_bruto_anual_min numeric,
      salario_bruto_anual_max numeric,
      cumple_salario          text,
      descripcion             text,
      url                     text,
      canal_a                 boolean,
      canal_b                 boolean,
      grupo_rol               text,
      prioridad               integer,
      alcance                 text,
      nivel                   text,
      publicada_en            date,
      fuente                  text,
      id_origen               text
    )
  ),
  unica as (
    select distinct on (huella) * from entrada order by huella, prioridad nulls last
  ),
  guardadas as (
    insert into oferta (
      huella, titulo, titulo_norm, empresa, empresa_norm,
      ubicacion_texto, pais, comunidad, provincia, municipio,
      modalidad, contrato, jornada,
      salario_min, salario_max, salario_periodo, salario_publicado, salario_estimado,
      salario_bruto_anual_min, salario_bruto_anual_max, cumple_salario,
      descripcion, url, canal_a, canal_b, grupo_rol, prioridad,
      alcance, nivel, publicada_en
    )
    select
      u.huella, u.titulo, u.titulo_norm, u.empresa, u.empresa_norm,
      u.ubicacion_texto, u.pais, u.comunidad, u.provincia, u.municipio,
      coalesce(u.modalidad, 'desconocida'), coalesce(u.contrato, 'desconocido'), u.jornada,
      u.salario_min, u.salario_max, u.salario_periodo,
      coalesce(u.salario_publicado, false), coalesce(u.salario_estimado, false),
      u.salario_bruto_anual_min, u.salario_bruto_anual_max,
      coalesce(u.cumple_salario, 'no_publicado'),
      u.descripcion, u.url, coalesce(u.canal_a, false), coalesce(u.canal_b, false),
      u.grupo_rol, u.prioridad,
      coalesce(u.alcance, 'revisar'), coalesce(u.nivel, 'desconocido'),
      u.publicada_en
    from unica u
    on conflict (huella) do update set
      ultima_vez_vista        = now(),
      activa                  = true,
      actualizada_en          = now(),
      empresa                 = coalesce(oferta.empresa, excluded.empresa),
      url                     = coalesce(oferta.url, excluded.url),
      descripcion             = coalesce(oferta.descripcion, excluded.descripcion),
      salario_min             = coalesce(oferta.salario_min, excluded.salario_min),
      salario_max             = coalesce(oferta.salario_max, excluded.salario_max),
      salario_bruto_anual_min = coalesce(oferta.salario_bruto_anual_min, excluded.salario_bruto_anual_min),
      salario_bruto_anual_max = coalesce(oferta.salario_bruto_anual_max, excluded.salario_bruto_anual_max),
      salario_publicado       = oferta.salario_publicado or excluded.salario_publicado,
      cumple_salario          = case when oferta.salario_publicado then oferta.cumple_salario
                                     else excluded.cumple_salario end,
      modalidad               = case when oferta.modalidad = 'desconocida' then excluded.modalidad
                                     else oferta.modalidad end,
      contrato                = case when oferta.contrato = 'desconocido' then excluded.contrato
                                     else oferta.contrato end,
      canal_a                 = oferta.canal_a or excluded.canal_a,
      canal_b                 = oferta.canal_b or excluded.canal_b,
      prioridad               = least(coalesce(oferta.prioridad, 9), coalesce(excluded.prioridad, 9)),
      grupo_rol               = coalesce(oferta.grupo_rol, excluded.grupo_rol),
      -- derivados: siempre se recalculan
      alcance                 = excluded.alcance,
      nivel                   = excluded.nivel
    returning oferta.id, oferta.huella, (xmax = 0) as es_nueva
  ),
  conteo as (
    select count(*) filter (where es_nueva)     as nuevas,
           count(*) filter (where not es_nueva) as actualizadas
    from guardadas
  ),
  procedencia as (
    insert into oferta_fuente (oferta_id, fuente, id_origen, url_origen)
    select g.id, u.fuente, u.id_origen, u.url
    from unica u
    join guardadas g on g.huella = u.huella
    where u.fuente is not null and u.id_origen is not null
    on conflict (fuente, id_origen) do update set ultima_vez_vista = now()
    returning 1
  )
  select nuevas, actualizadas into v_nuevas, v_actualizadas from conteo;

  return jsonb_build_object('nuevas', coalesce(v_nuevas, 0),
                            'actualizadas', coalesce(v_actualizadas, 0));
end;
$$;

-- ---------------------------------------------------------------------
-- 3. VISTAS
-- ---------------------------------------------------------------------
drop view if exists v_bandeja;
create view v_bandeja as
select
  id, titulo, empresa, provincia, municipio, modalidad, contrato,
  case when canal_a and canal_b then 'A+B'
       when canal_a then 'A' else 'B' end as canal,
  grupo_rol, nivel, prioridad, alcance,
  cumple_salario, salario_bruto_anual_min, salario_bruto_anual_max,
  url, publicada_en, primera_vez_vista, estado
from oferta
where activa
  and estado = 'nueva'
  and alcance in ('alcanzable', 'revisar')
order by
  case alcance when 'alcanzable' then 0 else 1 end,
  prioridad nulls last,
  primera_vez_vista desc;

-- Cuanto trabajo manual queda pendiente en el monton de "revisar"
create or replace view v_pendiente_revisar as
select
  case when canal_a and canal_b then 'A+B'
       when canal_a then 'A' else 'B' end as canal,
  provincia,
  count(*)                                          as ofertas,
  count(*) filter (where estado = 'nueva')          as sin_mirar
from oferta
where activa and alcance = 'revisar'
group by 1, 2
order by 4 desc;
