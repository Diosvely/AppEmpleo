-- =====================================================================
--  APPEMPLEO — MIGRACION 03
--  Modalidad "nacional" para los anuncios publicados sin plaza concreta.
--  Pegar entero en Supabase > SQL Editor > New query > Run.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. AMPLIAR LOS VALORES PERMITIDOS DE MODALIDAD
-- ---------------------------------------------------------------------
alter table oferta drop constraint if exists oferta_modalidad_check;
alter table oferta add constraint oferta_modalidad_check
  check (modalidad in ('presencial','hibrido','remoto','nacional','desconocida'));

-- ---------------------------------------------------------------------
-- 2. RECLASIFICAR LAS QUE YA ESTAN
-- Las 75 que ponen solo "Espana" en la ubicacion no son un dato que
-- falte: son anuncios sin plaza atada a una ciudad.
-- ---------------------------------------------------------------------
update oferta
   set modalidad = 'nacional',
       actualizada_en = now()
 where modalidad = 'desconocida'
   and lower(trim(ubicacion_texto)) in ('espana', 'españa', 'spain');

-- ---------------------------------------------------------------------
-- 3. VISTA DE BANDEJA: las "nacional" van primero dentro de "revisar"
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
  case alcance   when 'alcanzable' then 0 else 1 end,
  case modalidad when 'remoto' then 0 when 'nacional' then 1 else 2 end,
  prioridad nulls last,
  primera_vez_vista desc;

-- ---------------------------------------------------------------------
-- 4. TRIAJE MASIVO — LEE ESTO ANTES DE EJECUTARLO
--
-- Esta parte SI modifica tu columna de estado. Por eso va comentada.
-- Primero mira lo que va a tocar con la consulta A. Si estas conforme,
-- descomenta la B y ejecutala.
--
-- Que hace: descarta el canal A presencial en la peninsula. Controller
-- en Madrid con presencia obligatoria no es alcanzable desde Tenerife,
-- y ese grupo es el grueso del monton pendiente.
--
-- No borra nada: solo marca estado = 'descartada'. La oferta sigue en
-- la base y sigue contando para el historico del mercado.
-- ---------------------------------------------------------------------

-- A) PREVISUALIZAR (esta es segura, solo lee)
select provincia, modalidad, count(*) as se_descartarian
from oferta
where activa
  and estado = 'nueva'
  and alcance = 'revisar'
  and canal_a and not canal_b
  and modalidad in ('desconocida', 'hibrido')
  and provincia is not null
  and provincia not in ('Santa Cruz de Tenerife', 'Las Palmas')
group by 1, 2
order by 3 desc;

-- B) APLICAR (descomenta las lineas siguientes cuando lo hayas mirado)
-- update oferta
--    set estado = 'descartada',
--        notas = coalesce(notas || ' | ', '') || 'triaje masivo: canal A presencial peninsula',
--        actualizada_en = now()
--  where activa
--    and estado = 'nueva'
--    and alcance = 'revisar'
--    and canal_a and not canal_b
--    and modalidad in ('desconocida', 'hibrido')
--    and provincia is not null
--    and provincia not in ('Santa Cruz de Tenerife', 'Las Palmas');

-- C) DESHACER, por si te arrepientes (descomenta si hace falta)
-- update oferta
--    set estado = 'nueva', actualizada_en = now()
--  where estado = 'descartada'
--    and notas like '%triaje masivo%';
