-- =====================================================================
--  APPEMPLEO — MIGRACION 04
--  Seguimiento de candidaturas.
--
--  Idea central: NO se guarda "en que estado esta la oferta", se guarda
--  CADA MOVIMIENTO con su fecha. El estado actual es el ultimo movimiento.
--  Asi, dentro de tres meses, puedes saber cuanto tardan en contestarte,
--  que CV convierte mejor y donde se cae el embudo. Con una sola columna
--  de estado esa informacion no existiria y no se puede reconstruir.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. VERSIONES DE CV
-- ---------------------------------------------------------------------
create table if not exists cv_version (
  id       bigint generated always as identity primary key,
  nombre   text not null unique,
  notas    text,
  activa   boolean not null default true,
  creada_en timestamptz not null default now()
);

insert into cv_version (nombre, notas) values
  ('Controller', 'Perfil de control de gestion y costes industriales'),
  ('Datos',      'Perfil de Analytics Engineer, Fabric y Power BI')
on conflict (nombre) do nothing;

-- ---------------------------------------------------------------------
-- 2. MOVIMIENTOS DE CANDIDATURA
-- ---------------------------------------------------------------------
create table if not exists candidatura (
  id            bigint generated always as identity primary key,
  oferta_id     bigint      not null references oferta(id) on delete cascade,
  estado        text        not null
                  check (estado in ('interesante','aplicada','contactado',
                                    'entrevista','segunda_entrevista',
                                    'oferta_recibida','rechazado',
                                    'sin_respuesta','descartada')),
  fecha         timestamptz not null default now(),
  cv_version_id bigint      references cv_version(id),
  canal         text,      -- por donde aplicaste: web, email, LinkedIn...
  notas         text,
  creada_en     timestamptz not null default now()
);

create index if not exists ix_candidatura_oferta on candidatura (oferta_id, fecha desc);
create index if not exists ix_candidatura_estado on candidatura (estado, fecha desc);

-- ---------------------------------------------------------------------
-- 3. AMPLIAR LOS ESTADOS DE LA OFERTA
-- La columna oferta.estado pasa a ser un reflejo del ultimo movimiento,
-- para que la bandeja siga filtrando rapido sin recorrer el historial.
-- ---------------------------------------------------------------------
alter table oferta drop constraint if exists oferta_estado_check;
alter table oferta add constraint oferta_estado_check
  check (estado in ('nueva','interesante','aplicada','contactado','entrevista',
                    'segunda_entrevista','oferta_recibida','rechazado',
                    'sin_respuesta','descartada','cerrada'));

create or replace function sincronizar_estado_oferta()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  update oferta
     set estado = (select c.estado from candidatura c
                    where c.oferta_id = new.oferta_id
                    order by c.fecha desc, c.id desc limit 1),
         actualizada_en = now()
   where id = new.oferta_id;
  return new;
end;
$$;

drop trigger if exists tg_sincronizar_estado on candidatura;
create trigger tg_sincronizar_estado
  after insert on candidatura
  for each row execute function sincronizar_estado_oferta();

-- ---------------------------------------------------------------------
-- 4. REGISTRAR UN MOVIMIENTO (lo que llama la pagina web)
-- ---------------------------------------------------------------------
create or replace function registrar_movimiento(
  p_oferta_id bigint,
  p_estado    text,
  p_cv        text default null,
  p_canal     text default null,
  p_notas     text default null
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_cv_id bigint;
  v_id    bigint;
begin
  if p_cv is not null then
    select id into v_cv_id from cv_version where nombre = p_cv;
  end if;

  insert into candidatura (oferta_id, estado, cv_version_id, canal, notas)
  values (p_oferta_id, p_estado, v_cv_id, p_canal, p_notas)
  returning id into v_id;

  return jsonb_build_object('id', v_id, 'estado', p_estado);
end;
$$;

-- ---------------------------------------------------------------------
-- 5. VISTAS
-- ---------------------------------------------------------------------

-- Estado actual de cada candidatura, con cuanto lleva parada
create or replace view v_candidaturas as
select
  o.id            as oferta_id,
  o.titulo,
  o.empresa,
  o.provincia,
  o.modalidad,
  o.url,
  case when o.canal_a and o.canal_b then 'A+B'
       when o.canal_a then 'A' else 'B' end as canal_busqueda,
  ultimo.estado,
  ultimo.fecha    as fecha_ultimo_movimiento,
  primera.fecha   as fecha_aplicacion,
  cv.nombre       as cv_usado,
  ultimo.canal    as canal_aplicacion,
  ultimo.notas,
  (current_date - ultimo.fecha::date) as dias_sin_novedad,
  (select count(*) from candidatura c2 where c2.oferta_id = o.id) as movimientos
from oferta o
join lateral (
  select c.* from candidatura c
   where c.oferta_id = o.id
   order by c.fecha desc, c.id desc limit 1
) ultimo on true
left join lateral (
  select c.fecha from candidatura c
   where c.oferta_id = o.id and c.estado = 'aplicada'
   order by c.fecha asc limit 1
) primera on true
left join cv_version cv on cv.id = ultimo.cv_version_id
order by ultimo.fecha desc;

-- El embudo: cuantas ofertas han pasado alguna vez por cada fase
create or replace view v_embudo as
with fases as (
  select unnest(array['interesante','aplicada','contactado','entrevista',
                      'segunda_entrevista','oferta_recibida']) as estado,
         generate_series(1, 6) as orden
)
select f.orden, f.estado,
       count(distinct c.oferta_id) as ofertas
from fases f
left join candidatura c on c.estado = f.estado
group by f.orden, f.estado
order by f.orden;

-- Que CV convierte mejor
create or replace view v_rendimiento_cv as
select
  cv.nombre as cv,
  count(distinct c.oferta_id) filter (where c.estado = 'aplicada')   as aplicadas,
  count(distinct c.oferta_id) filter (where c.estado = 'contactado') as contactos,
  count(distinct c.oferta_id) filter (where c.estado in ('entrevista','segunda_entrevista')) as entrevistas,
  round(100.0 * count(distinct c.oferta_id) filter (where c.estado = 'contactado')
        / nullif(count(distinct c.oferta_id) filter (where c.estado = 'aplicada'), 0), 1)
        as tasa_respuesta_pct
from cv_version cv
left join candidatura c on c.cv_version_id = cv.id
group by cv.nombre;

-- ---------------------------------------------------------------------
-- 6. SEGURIDAD
-- ---------------------------------------------------------------------
alter table candidatura enable row level security;
alter table cv_version  enable row level security;

drop policy if exists p_candidatura_auth on candidatura;
create policy p_candidatura_auth on candidatura
  for all to authenticated using (true) with check (true);

drop policy if exists p_cv_version_auth on cv_version;
create policy p_cv_version_auth on cv_version
  for all to authenticated using (true) with check (true);

-- La pagina web necesita leer y actualizar ofertas con tu sesion iniciada
grant select on v_bandeja, v_candidaturas, v_embudo, v_rendimiento_cv to authenticated;
grant execute on function registrar_movimiento(bigint, text, text, text, text) to authenticated;
