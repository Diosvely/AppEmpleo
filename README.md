# AppEmpleo

Observatorio personal del mercado de control de gestion y datos en Espana.

Cada manana un robot consulta portales de empleo, normaliza lo que
encuentra, elimina duplicados y lo guarda en una base de datos que nunca
borra nada. Con el tiempo eso deja de ser un buscador y se convierte en
un historico propio del mercado laboral.

## Estado

Fase 1 de 7. Una sola fuente (Adzuna) y sin interfaz todavia.

## Como funciona

```
GitHub Actions (cron diario)
        |
        v
   src/main.py  ---> raw/  (JSON comprimido, se guarda en el repo)
        |
        v
  Supabase / PostgreSQL
        |
        +--> v_bandeja        (lo que revisas cada dia)
        +--> v_salud_ingesta  (si el robot va bien o falla)
```

## Estructura

```
config/profile.yaml        tus criterios. El unico archivo que tocas tu.
sql/01_esquema.sql         tablas y funciones. Se pega en Supabase.
src/main.py                el orquestador
src/normalizar.py          limpieza, huella de duplicados, clasificacion
src/conectores/adzuna.py   la fuente
src/db.py                  acceso a Supabase
src/probar.py              prueba en seco, sin internet
raw/                       el crudo. Nunca se modifica ni se borra.
```

## Puesta en marcha

1. **Supabase.** Abre tu proyecto, entra en SQL Editor, pega entero
   `sql/01_esquema.sql` y pulsa Run.
2. **Claves.** En Supabase, Project Settings > API, copia la Project URL
   y la clave `service_role`.
3. **Secretos.** En GitHub, Settings > Secrets and variables > Actions >
   New repository secret. Crea cuatro:
   `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `SUPABASE_URL`,
   `SUPABASE_SERVICE_KEY`.
4. **Primera ejecucion.** Pestana Actions > Ingesta diaria > Run workflow.
5. **Comprobar.** En Supabase, Table Editor > `oferta`.

## Decisiones que no se pueden deshacer

- **Nada se borra.** Cuando una oferta desaparece del portal se marca
  `activa = false` y se conserva. Asi se puede medir cuanto dura
  publicada una oferta de controller en Tenerife.
- **La huella no incluye la descripcion.** Cada portal la recorta de una
  forma distinta; incluirla impediria detectar que dos anuncios son la
  misma oferta.
- **El salario no filtra, etiqueta.** La mayoria de ofertas espanolas no
  lo publican. Filtrar por sueldo tiraria a la basura la mayor parte del
  mercado sin saber que habia dentro.
- **Tu triaje es intocable.** La ingesta jamas escribe en las columnas
  `estado` ni `notas`.
- **Solo se apaga lo que se ha mirado.** Si una fuente falla a medias,
  sus ofertas no se dan por muertas.

## Siguientes fases

2. Alertas de InfoJobs y LinkedIn leidas desde el correo
3. Paginas de empleo de las empresas objetivo
4. Puntuacion de encaje explicable
5. Interfaz de triaje (HTML + Supabase, alojado en Netlify)
6. Seguimiento de candidaturas
7. Power BI sobre el historico
