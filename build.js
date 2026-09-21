/**
 * Compilacion para Cloudflare Workers.
 *
 * La pagina se publica con marcadores de posicion en vez de credenciales.
 * Este script los sustituye por variables de entorno al desplegar, asi el
 * repositorio puede ser publico sin llevar dentro la direccion de la base
 * de datos de nadie.
 *
 * Variables que espera (Settings > Build > variables de compilacion):
 *   SUPABASE_URL            https://xxxxx.supabase.co
 *   SUPABASE_CLAVE_PUBLICA  la clave publishable (sb_publishable_...)
 *   REPO_GITHUB             usuario/repositorio, para el boton "Ingestar"
 *
 * No necesita dependencias: solo Node, que Cloudflare ya trae.
 */

const fs = require("fs");
const path = require("path");

const ORIGEN = "web";
const DESTINO = "dist";

const SUSTITUCIONES = {
  __SUPABASE_URL__: process.env.SUPABASE_URL,
  __SUPABASE_CLAVE_PUBLICA__: process.env.SUPABASE_CLAVE_PUBLICA,
  __REPO_GITHUB__: process.env.REPO_GITHUB || "",
};

// Sin estas dos la pagina no puede hablar con la base de datos.
const OBLIGATORIAS = ["__SUPABASE_URL__", "__SUPABASE_CLAVE_PUBLICA__"];

const faltan = OBLIGATORIAS.filter((k) => !SUSTITUCIONES[k]);
if (faltan.length) {
  const nombres = faltan.map((k) => k.replace(/__/g, "")).join(", ");
  console.error(
    `\nFalta configurar: ${nombres}\n\n` +
      `Anadelas como variables de compilacion en el panel de Cloudflare,\n` +
      `en Settings > Build. No son secretos: la clave publishable es\n` +
      `publica por diseno y lo que protege los datos es la seguridad a\n` +
      `nivel de fila de Supabase.\n`
  );
  process.exit(1);
}

fs.rmSync(DESTINO, { recursive: true, force: true });
fs.mkdirSync(DESTINO, { recursive: true });

let copiados = 0;
for (const archivo of fs.readdirSync(ORIGEN)) {
  const entrada = path.join(ORIGEN, archivo);
  if (!fs.statSync(entrada).isFile()) continue;
  if (archivo === "demo-conexion.js") continue;   // solo alimenta a demo.html

  if (archivo.endsWith(".html")) {
    let contenido = fs.readFileSync(entrada, "utf8");
    for (const [marcador, valor] of Object.entries(SUSTITUCIONES)) {
      contenido = contenido.split(marcador).join(valor);
    }
    // Si queda algun marcador sin sustituir, mejor fallar aqui que
    // desplegar una pagina rota que nadie entiende por que no entra.
    const restantes = contenido.match(/__[A-Z_]+__/g);
    if (restantes) {
      console.error(`\n${archivo} aun tiene marcadores sin valor: ` +
                    `${[...new Set(restantes)].join(", ")}\n`);
      process.exit(1);
    }
    fs.writeFileSync(path.join(DESTINO, archivo), contenido);
  } else {
    fs.copyFileSync(entrada, path.join(DESTINO, archivo));
  }
  copiados++;
}

/* ---------------------------------------------------------------------
   DEMOSTRACION

   demo.html no se escribe a mano: se genera desde index.html cambiando
   solo su conexion. Asi la demostracion es literalmente la misma
   aplicacion y no puede quedarse desfasada cuando toques la interfaz.
   --------------------------------------------------------------------- */
const ETIQUETA_CDN =
  '<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"><\/script>';

const INICIO_CONEXION = 'const SUPABASE_URL = "';
const FIN_CONEXION =
  "const bd = supabase.createClient(SUPABASE_URL, SUPABASE_CLAVE_PUBLICA);";

function generarDemo() {
  let html = fs.readFileSync(path.join(ORIGEN, "index.html"), "utf8");
  const demo = fs.readFileSync(path.join(ORIGEN, "demo-conexion.js"), "utf8");

  if (!html.includes(ETIQUETA_CDN)) {
    throw new Error("No encuentro la etiqueta del cliente de Supabase en index.html");
  }
  html = html.replace(ETIQUETA_CDN, "");

  const i = html.indexOf(INICIO_CONEXION);
  const j = html.indexOf(FIN_CONEXION);
  if (i < 0 || j < 0 || j < i) {
    throw new Error("No encuentro el bloque de conexion en index.html");
  }
  html = html.slice(0, i) + demo + html.slice(j + FIN_CONEXION.length);

  html = html.replace("<title>AppEmpleo</title>",
                      "<title>AppEmpleo · demostración</title>");

  fs.writeFileSync(path.join(DESTINO, "demo.html"), html);
}

try {
  generarDemo();
  console.log(`Listo: ${copiados} archivos + demo.html en ${DESTINO}/`);
} catch (e) {
  console.error(`\nNo se pudo generar la demostracion: ${e.message}\n`);
  process.exit(1);
}
