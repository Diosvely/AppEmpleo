# Historial de versiones

La versión que ves en la esquina de la aplicación sale de la constante
`VERSION` de `web/index.html`. Cuando cambies algo, súbela aquí y allí.

- Cambio que arregla un fallo: 1.0.0 → 1.0.1
- Cambio que añade algo: 1.0.0 → 1.1.0
- Cambio que rompe lo anterior (por ejemplo, una migración obligatoria): 1.0.0 → 2.0.0

## 1.0.1 — 7 de octubre de 2026

Corregido: la bandeja y las candidaturas solo mostraban las primeras 300
filas, y los contadores de los filtros contaban sobre esas 300 en vez de
sobre el total. Ahora las filas se piden por páginas hasta traerlas todas,
porque Supabase no devuelve más de 1000 por petición.

- Las filas se piden ordenadas por su identificador y se ordenan después en
  la página con las mismas reglas que definen las vistas. Con páginas, un
  orden con empates puede repetir una fila y perder otra.
- La copia que se guarda para mirar sin conexión se limita a 400 ofertas y
  ya no rompe la pantalla si el navegador se queda sin hueco.

## 1.0.0 — 21 de septiembre de 2026

Primera versión pública.

- Ingesta diaria desde Adzuna y desde las alertas de LinkedIn e InfoJobs por correo.
- Normalización, huella de duplicados entre fuentes y clasificación en dos canales.
- Histórico que no borra nunca: las ofertas retiradas se marcan como inactivas.
- Aplicación web con bandeja, búsqueda, seguimiento de candidaturas y embudo.
- Acceso atado a un único propietario y vistas que respetan esa seguridad.
- Credenciales fuera del código, inyectadas al desplegar en Cloudflare Workers.
- Demostración con datos inventados, generada desde la misma aplicación.
- 
