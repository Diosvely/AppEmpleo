-- =====================================================================
--  APPEMPLEO — ESQUEMA BASE
--  Pegar entero en Supabase > SQL Editor > New query > Run.
--  Se puede ejecutar varias veces sin romper nada.
-- =====================================================================

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------
-- 1. EJECUCION
-- Un registro por cada vez que el robot sale a buscar. Sirve para saber
-- si una fuente fallo, y asi no dar por muertas sus ofertas.
-- ---------------------------------------------------------------------
create table if not exists ejecucion (
  id              uuid primary key default gen_random_uuid(),
  fuente          text        not null,
  iniciada_en     timestamptz not null default now(),
  terminada_en    timestamptz,
  estado          text        not null default 'en_curso'
                    check (estado in ('en_curso', 'ok', 'error')),
  llamadas_api    integer     not null default 0,
  ofertas_vistas  integer     not null default 0,
  ofertas_nuevas  integer     not null default 0,
  mensaje_error   text
);

create index if not exists ix_ejecucion_fuente_fecha
  on ejecucion (fuente, iniciada_en desc);

-- ---------------------------------------------------------------------
-- 2. OFERTA
-- Una fila por oferta REAL. Si la misma oferta llega por tres portales
-- distintos, aqui sigue habiendo una sola fila.
-- ---------------------------------------------------------------------
create table if not exists oferta (
  id                      bigint generated always as identity primary key,

  -- huella: identidad de la oferta. empresa + titulo + provincia,
  -- todo normalizado. Es lo que impide los duplicados.
  huella                  text        not null unique,

  titulo                  text        not null,
  titulo_norm             text        not null,
  empresa                 text,
  empresa_norm            text,

  ubicacion_texto         text,
  pais                    text,
  comunidad               text,
  provincia               text,
  municipio               text,

  modalidad               text        not null default 'desconocida'
                            check (modalidad in ('presencial','hibrido','remoto','desconocida')),
  contrato                text        not null default 'desconocido'
                            check (contrato in ('indefinido','temporal','practicas','desconocido')),
  jornada                 text,

  -- Salario tal y como lo publica la fuente
  salario_min             numeric,
  salario_max             numeric,
  salario_periodo         text,
  salario_publicado       boolean     not null default false,
  salario_estimado        boolean     not null default false,

  -- Salario traducido a bruto anual para poder comparar
  salario_bruto_anual_min numeric,
  salario_bruto_anual_max numeric,
  cumple_salario          text        not null default 'no_publicado'
                            check (cumple_salario in ('cumple','no_cumple','no_publicado')),

  descripcion             text,
  url                     text,

  -- Clasificacion
  canal_a                 boolean     not null default false,
  canal_b                 boolean     not null default false,
  grupo_rol               text,
  prioridad               integer,
  encaja_geografia        boolean     not null default false,

  publicada_en            date,

  -- Ciclo de vida. Esto es lo irrecuperable: nunca se borra nada.
  primera_vez_vista       timestamptz not null default now(),
  ultima_vez_vista        timestamptz not null default now(),
  activa                  boolean     not null default true,

  -- Tu triaje manual. La ingesta NUNCA toca estas dos columnas.
  estado                  text        not null default 'nueva'
                            check (estado in ('nueva','interesante','descartada',
                                              'aplicada','entrevista','cerrada')),
  notas                   text,

  actualizada_en          timestamptz not null default now()
);

create index if not exists ix_oferta_activa      on oferta (activa, prioridad, publicada_en desc);
create index if not exists ix_oferta_estado      on oferta (estado);
create index if not exists ix_oferta_canal_a     on oferta (canal_a) where canal_a;
create index if not exists ix_oferta_canal_b     on oferta (canal_b) where canal_b;
create index if not exists ix_oferta_provincia   on oferta (provincia);
create index if not exists ix_oferta_primera_vez on oferta (primera_vez_vista desc);

-- ---------------------------------------------------------------------
-- 3. OFERTA_FUENTE
-- Por que portales ha aparecido cada oferta. Una oferta, varias filas.
-- ---------------------------------------------------------------------
create table if not exists oferta_fuente (
  id                bigint generated always as identity primary key,
  oferta_id         bigint      not null references oferta(id) on delete cascade,
  fuente            text        not null,
  id_origen         text        not null,
  url_origen        text,
  primera_vez_vista timestamptz not null default now(),
  ultima_vez_vista  timestamptz not null default now(),
  unique (fuente, id_origen)
);

create index if not exists ix_oferta_fuente_oferta on oferta_fuente (oferta_id);

-- ---------------------------------------------------------------------
-- 4. FUNCION DE INGESTA
-- Recibe un lote de ofertas en JSON y las inserta o actualiza.
-- Regla clave: al actualizar NO se tocan estado, notas ni
-- primera_vez_vista. Tu triaje manual es intocable.
-- ---------------------------------------------------------------------
create or replace function ingerir_ofertas(datos jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_nuevas      integer := 0;
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
      encaja_geografia        boolean,
      publicada_en            date,
      fuente                  text,
      id_origen               text
    )
  ),
  -- Si el mismo lote trae la misma huella dos veces, nos quedamos con una
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
      encaja_geografia, publicada_en
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
      u.grupo_rol, u.prioridad, coalesce(u.encaja_geografia, false), u.publicada_en
    from unica u
    on conflict (huella) do update set
      ultima_vez_vista        = now(),
      activa                  = true,
      actualizada_en          = now(),
      -- solo rellenamos huecos, nunca pisamos un dato bueno con uno vacio
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
      grupo_rol               = coalesce(oferta.grupo_rol, excluded.grupo_rol)
    returning oferta.id, oferta.huella, (xmax = 0) as es_nueva
  ),
  conteo as (
    select
      count(*) filter (where es_nueva)     as nuevas,
      count(*) filter (where not es_nueva) as actualizadas
    from guardadas
  ),
  procedencia as (
    insert into oferta_fuente (oferta_id, fuente, id_origen, url_origen)
    select g.id, u.fuente, u.id_origen, u.url
    from unica u
    join guardadas g on g.huella = u.huella
    where u.fuente is not null and u.id_origen is not null
    on conflict (fuente, id_origen) do update set
      ultima_vez_vista = now()
    returning 1
  )
  select nuevas, actualizadas into v_nuevas, v_actualizadas from conteo;

  return jsonb_build_object(
    'nuevas', coalesce(v_nuevas, 0),
    'actualizadas', coalesce(v_actualizadas, 0)
  );
end;
$$;

-- ---------------------------------------------------------------------
-- 5. MARCAR INACTIVAS
-- Solo se llama si la fuente termino BIEN. Y solo apaga ofertas que no
-- sigan vivas en otra fuente. Asi un fallo de Adzuna no borra el mapa.
-- ---------------------------------------------------------------------
create or replace function marcar_inactivas(p_fuente text, p_corte timestamptz)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_total integer;
begin
  update oferta o
     set activa = false,
         actualizada_en = now()
   where o.activa
     and o.ultima_vez_vista < p_corte
     and exists (
       select 1 from oferta_fuente f
        where f.oferta_id = o.id and f.fuente = p_fuente
     )
     and not exists (
       select 1 from oferta_fuente f2
        where f2.oferta_id = o.id
          and f2.fuente <> p_fuente
          and f2.ultima_vez_vista >= p_corte
     );
  get diagnostics v_total = row_count;
  return v_total;
end;
$$;

-- ---------------------------------------------------------------------
-- 6. VISTAS PARA REVISAR A DIARIO
-- ---------------------------------------------------------------------
create or replace view v_bandeja as
select
  id, titulo, empresa, provincia, municipio, modalidad, contrato,
  case
    when canal_a and canal_b then 'A+B'
    when canal_a then 'A'
    when canal_b then 'B'
  end                              as canal,
  grupo_rol, prioridad,
  cumple_salario,
  salario_bruto_anual_min, salario_bruto_anual_max,
  url, publicada_en, primera_vez_vista, estado
from oferta
where activa
  and estado = 'nueva'
  and encaja_geografia
order by prioridad nulls last, primera_vez_vista desc;

create or replace view v_salud_ingesta as
select
  fuente,
  date_trunc('day', iniciada_en) as dia,
  count(*)                        as ejecuciones,
  count(*) filter (where estado = 'error') as fallos,
  sum(ofertas_vistas)             as vistas,
  sum(ofertas_nuevas)             as nuevas,
  sum(llamadas_api)               as llamadas
from ejecucion
group by 1, 2
order by 2 desc;

-- ---------------------------------------------------------------------
-- 7. SEGURIDAD
-- RLS activo. El robot escribe con la clave de servicio, que la salta.
-- Tu usuario, al entrar con correo y contrasena, lee y edita.
-- ---------------------------------------------------------------------
alter table oferta        enable row level security;
alter table oferta_fuente enable row level security;
alter table ejecucion     enable row level security;

drop policy if exists p_oferta_auth on oferta;
create policy p_oferta_auth on oferta
  for all to authenticated using (true) with check (true);

drop policy if exists p_oferta_fuente_auth on oferta_fuente;
create policy p_oferta_fuente_auth on oferta_fuente
  for all to authenticated using (true) with check (true);

drop policy if exists p_ejecucion_auth on ejecucion;
create policy p_ejecucion_auth on ejecucion
  for select to authenticated using (true);
