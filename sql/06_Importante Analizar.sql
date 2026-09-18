

-- 1. Reparto por fuente. Cuanto aporta cada una.
select f.fuente,
       count(distinct o.id)                                         as ofertas,
       count(distinct o.id) filter (where o.alcance = 'alcanzable') as alcanzables,
       count(distinct o.id) filter (where o.salario_publicado)      as con_salario,
       count(distinct o.id) filter (where o.modalidad <> 'desconocida') as con_modalidad
from oferta o
join oferta_fuente f on f.oferta_id = o.id
where o.activa
group by 1 order by 2 desc;

-- 2. Ofertas vistas por mas de una fuente: la deduplicacion cruzada
select o.titulo, o.empresa, o.provincia,
       string_agg(distinct f.fuente, ' + ') as fuentes
from oferta o
join oferta_fuente f on f.oferta_id = o.id
group by o.id, o.titulo, o.empresa, o.provincia
having count(distinct f.fuente) > 1;

-- 3. Lo alcanzable y sin mirar, que es lo unico que importa hoy
select fuente_principal, titulo, empresa, provincia, modalidad, cumple_salario, url
from (
  select o.*, (select min(f.fuente) from oferta_fuente f where f.oferta_id = o.id) as fuente_principal
  from oferta o
  where o.activa and o.alcance = 'alcanzable' and o.estado = 'nueva'
) t
order by prioridad nulls last
limit 30;