# Historial de versiones

La versión que ves en la esquina de la aplicación sale de la constante
`VERSION` de `web/index.html`. Cuando cambies algo, súbela aquí y allí.

- Cambio que arregla un fallo: 1.0.0 → 1.0.1
- Cambio que añade algo: 1.0.0 → 1.1.0
- Cambio que rompe lo anterior (por ejemplo, una migración obligatoria): 1.0.0 → 2.0.0

## 1.0.0 — 21 de septiembre de 2026

Primera versión pública.

- Ingesta diaria desde Adzuna y desde las alertas de LinkedIn e InfoJobs por correo.
- Normalización, huella de duplicados entre fuentes y clasificación en dos canales.
- Histórico que no borra nunca: las ofertas retiradas se marcan como inactivas.
- Aplicación web con bandeja, búsqueda, seguimiento de candidaturas y embudo.
- Acceso atado a un único propietario y vistas que respetan esa seguridad.
- Credenciales fuera del código, inyectadas al desplegar en Cloudflare Workers.
- Demostración con datos inventados, generada desde la misma aplicación.
