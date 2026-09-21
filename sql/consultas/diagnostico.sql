-- Consultas de diagnostico usadas durante el desarrollo.
-- No son migraciones: se ejecutan a mano para mirar los datos.

-- 1. Reparto general
select
  case when canal_a and canal_b then 'A+B'
       when canal_a then 'A' else 'B' end as canal,
  prioridad,
  count(*)                                   as ofertas,
  count(*) filter (where encaja_geografia)   as alcanzables,
  count(*) filter (where salario_publicado)  as con_salario
from oferta
group by 1, 2
order by 1, 2;

-- 2. Los titulos mas repetidos de cada grupo: aqui veras los falsos positivos
select grupo_rol, titulo, count(*) as veces
from oferta
group by 1, 2
order by 1, 3 desc
limit 60;

-- 3. Donde estan
select provincia, modalidad, count(*)
from oferta
group by 1, 2
order by 3 desc
limit 25;


-- Limpiar en curso
update ejecucion set estado = 'error',
       mensaje_error = 'cortada por timeout de Supabase'
 where estado = 'en_curso' and terminada_en is null;
 
 
 
 -- 1. Que pone en la ubicacion cuando no hay provincia
select ubicacion_texto, count(*)
from oferta
where provincia is null and activa
group by 1 order by 2 desc limit 20;

-- 2. Cuantas de las "revisar" ya delatan teletrabajo en el fragmento
select
  case when canal_a and canal_b then 'A+B'
       when canal_a then 'A' else 'B' end as canal,
  count(*) as en_revisar,
  count(*) filter (
    where descripcion ilike '%remot%'
       or descripcion ilike '%teletrabaj%'
       or descripcion ilike '%hibrid%'
       or descripcion ilike '%híbrid%'
  ) as menciona_teletrabajo,
  avg(length(descripcion))::int as largo_medio_fragmento
from oferta
where activa and alcance = 'revisar'
group by 1;



