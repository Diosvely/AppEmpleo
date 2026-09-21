"""
Interpretes de las alertas de empleo por correo.

LinkedIn : texto plano, formato digest. Titulo / empresa / ubicacion /
           enlace con el identificador numerico. Unas 8 ofertas por correo.
InfoJobs : solo HTML, codificacion iso-8859-1, un correo por alerta.
           Trae municipio, modalidad, contrato y salario, que es justo
           lo que Adzuna no da.
"""

import hashlib
import re

from bs4 import BeautifulSoup

CODIGO_LINKEDIN = "linkedin"
CODIGO_INFOJOBS = "infojobs"

# Lineas de adorno que LinkedIn intercala dentro de cada bloque
RUIDO_LINKEDIN = re.compile(
    r"^(\d+\s+contactos?"
    r"|Esta empresa busca personal activamente"
    r"|Se busca activamente"
    r"|Tu perfil coincide"
    r"|\d+\s+(ex)?compañer\w+"
    r"|Alumnado de"
    r"|Ver todos los empleos"
    r"|Editar alerta"
    r"|Empleos de)",
    re.I,
)

# El pie del correo tambien lleva enlaces con identificador: hay que cortar antes
CORTES_PIE_LINKEDIN = [
    "Ver todos los empleos",
    "Editar alerta",
    "Has recibido este correo",
    "Este correo electrónico",
    "Darse de baja",
]


def _limpio(texto: str) -> str:
    return re.sub(r"\s+", " ", (texto or "")).strip()


# ---------------------------------------------------------------------
# LINKEDIN
# ---------------------------------------------------------------------
def interpretar_linkedin(texto_plano: str) -> list[dict]:
    if not texto_plano:
        return []

    cuerpo = texto_plano
    for marca in CORTES_PIE_LINKEDIN:
        pos = cuerpo.find(marca)
        if pos > 500:          # no cortar si aparece al principio
            cuerpo = cuerpo[:pos]
            break

    ofertas, vistos = [], set()
    for bloque in re.split(r"-{20,}", cuerpo):
        encontrado = re.search(r"/jobs/view/(\d+)", bloque)
        if not encontrado:
            continue
        id_origen = encontrado.group(1)
        if id_origen in vistos:
            continue

        lineas = [l.strip() for l in bloque.split("\n") if l.strip()]
        lineas = [l for l in lineas
                  if not l.startswith(("Ver anuncio", "Gestionar alertas",
                                       "Tu alerta", "Nuevos empleos", "http"))
                  and not RUIDO_LINKEDIN.match(l)
                  and "<" not in l]          # descarta restos de HTML del pie
        if len(lineas) < 2:
            continue

        vistos.add(id_origen)
        ofertas.append({
            "fuente": CODIGO_LINKEDIN,
            "id_origen": id_origen,
            "titulo": _limpio(lineas[0]),
            "empresa": _limpio(lineas[1]),
            "ubicacion_texto": _limpio(lineas[2]) if len(lineas) > 2 else None,
            "url": f"https://www.linkedin.com/jobs/view/{id_origen}/",
            "descripcion": None,
            "modalidad_fuente": None,
            "contrato_fuente": None,
            "salario_min": None,
            "salario_max": None,
        })
    return ofertas


# ---------------------------------------------------------------------
# INFOJOBS
# ---------------------------------------------------------------------
# "El Rosario |  Presencial |   Indefinido  |   18.000€ - 21.000€ Bruto/año"
LINEA_DATOS = re.compile(
    r"^(?P<municipio>[^|]{2,60})\|"
    r"(?P<resto>.+)$"
)
SALARIO = re.compile(
    r"(?P<min>\d{1,3}(?:\.\d{3})*)\s*€?\s*(?:-|a)\s*(?P<max>\d{1,3}(?:\.\d{3})*)\s*€"
    r"|(?P<unico>\d{1,3}(?:\.\d{3})*)\s*€"
)
MODALIDADES = {"presencial": "presencial", "híbrido": "hibrido",
               "hibrido": "hibrido", "teletrabajo": "remoto", "remoto": "remoto"}
CONTRATOS = {"indefinido": "indefinido", "temporal": "temporal",
             "prácticas": "practicas", "practicas": "practicas",
             "fijo discontinuo": "temporal", "obra y servicio": "temporal"}


def _numero(texto: str) -> float | None:
    if not texto:
        return None
    try:
        return float(texto.replace(".", ""))
    except ValueError:
        return None


def _interpretar_linea_datos(linea: str) -> dict:
    datos = {"municipio": None, "modalidad_fuente": None,
             "contrato_fuente": None, "salario_min": None,
             "salario_max": None, "salario_periodo": None}
    trozos = [t.strip() for t in linea.split("|") if t.strip()]
    if not trozos:
        return datos

    datos["municipio"] = trozos[0]
    for trozo in trozos[1:]:
        bajo = trozo.lower()
        for clave, valor in MODALIDADES.items():
            if clave in bajo:
                datos["modalidad_fuente"] = valor
        for clave, valor in CONTRATOS.items():
            if clave in bajo:
                datos["contrato_fuente"] = valor
        if "€" in trozo:
            m = SALARIO.search(trozo)
            if m:
                if m.group("min"):
                    datos["salario_min"] = _numero(m.group("min"))
                    datos["salario_max"] = _numero(m.group("max"))
                else:
                    datos["salario_min"] = _numero(m.group("unico"))
                    datos["salario_max"] = datos["salario_min"]
            datos["salario_periodo"] = "mensual" if "mes" in bajo else "anual"
    return datos


def interpretar_infojobs(html: str, asunto_alerta: str) -> list[dict]:
    if not html:
        return []
    sopa = BeautifulSoup(html, "lxml")
    for etiqueta in sopa(["style", "script"]):
        etiqueta.decompose()

    # El correo de InfoJobs es una tabla anidada: el contenedor de un enlace
    # no contiene la linea de datos. Trabajamos sobre el texto visible entero,
    # que si respeta el orden: titulo / empresa / municipio | modalidad | ...
    lineas = [l.strip() for l in sopa.get_text("\n", strip=True).split("\n") if l.strip()]

    titulos = {}
    for enlace in sopa.find_all("a", href=True):
        titulo = _limpio(enlace.get_text(" ", strip=True))
        if not titulo or len(titulo) < 4:
            continue
        if any(p in titulo.lower() for p in
               ("ver más ofertas", "ver mas ofertas", "gestionar mis alertas",
                "eliminar esta alerta", "dar opinión", "dar opinion", "política",
                "politica", "privacidad", "baja", "menú privado", "menu privado",
                "infojobs")):
            continue
        if "infojobs.net" not in enlace["href"]:
            continue
        titulos.setdefault(titulo, enlace["href"])

    ofertas = []
    for titulo, url in titulos.items():
        try:
            i = lineas.index(titulo)
        except ValueError:
            continue

        empresa, datos = None, {}
        for linea in lineas[i + 1:i + 4]:
            if "|" in linea and not datos:
                datos = _interpretar_linea_datos(linea)
            elif empresa is None and "|" not in linea:
                empresa = _limpio(linea)
        if empresa and ("anónima" in empresa.lower() or "anonima" in empresa.lower()):
            empresa = None      # InfoJobs oculta el nombre: no lo inventamos

        # sin identificador propio: lo derivamos de titulo + municipio + alerta
        semilla = f"{titulo}|{datos.get('municipio') or ''}|{asunto_alerta}"
        id_origen = hashlib.sha256(semilla.encode("utf-8")).hexdigest()[:24]

        ofertas.append({
            "fuente": CODIGO_INFOJOBS,
            "id_origen": id_origen,
            "titulo": titulo,
            "empresa": empresa,
            "ubicacion_texto": datos.get("municipio"),
            "url": url,
            "descripcion": None,
            "modalidad_fuente": datos.get("modalidad_fuente"),
            "contrato_fuente": datos.get("contrato_fuente"),
            "salario_min": datos.get("salario_min"),
            "salario_max": datos.get("salario_max"),
            "salario_periodo": datos.get("salario_periodo"),
            "alerta": asunto_alerta,
        })

    # un mismo titulo puede venir enlazado dos veces (imagen y texto)
    unicas, vistos = [], set()
    for o in ofertas:
        if o["id_origen"] in vistos:
            continue
        vistos.add(o["id_origen"])
        unicas.append(o)
    return unicas
