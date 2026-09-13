"""
Normalizacion, huella de duplicados y clasificacion por canal.

Todo lo que aqui se decide es lo que luego no se puede arreglar:
si la huella esta mal calculada, tendras duplicados para siempre.
"""

import hashlib
import re
import unicodedata
from datetime import date, datetime

# Sufijos societarios que sobran al comparar nombres de empresa
SUFIJOS_EMPRESA = [
    "s l u", "s a u", "s l p", "s c p", "s l", "s a", "slu", "sau",
    "sl", "sa", "sociedad limitada", "sociedad anonima", "slne",
    "spain", "espana", "iberia", "group", "grupo", "holding",
]

# Ruido tipico en titulos de oferta espanoles
RUIDO_TITULO = [
    r"\(h/m/d\)", r"\(m/h/d\)", r"\(h/m\)", r"\(m/h\)", r"\(m/f\)",
    r"\(f/m\)", r"\bm/f/d\b", r"\bh/m/x\b", r"\(x\)", r"\(a\)",
    r"\bm/h\b", r"\bh/m\b",
]

PALABRAS_REMOTO = [
    "teletrabajo", "remoto", "remote", "100% remoto", "full remote",
    "en remoto", "trabajo a distancia",
]
PALABRAS_HIBRIDO = ["hibrido", "hybrid", "semipresencial", "mixto"]

PALABRAS_INDEFINIDO = ["indefinido", "permanent", "fijo", "estable"]
PALABRAS_TEMPORAL = ["temporal", "contract", "sustitucion", "obra y servicio",
                     "interinidad", "eventual", "campana"]
PALABRAS_PRACTICAS = ["practicas", "becario", "beca", "internship", "trainee",
                      "formacion dual"]


def quitar_acentos(texto: str) -> str:
    if not texto:
        return ""
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def normalizar(texto: str) -> str:
    """minusculas, sin acentos, sin puntuacion, un solo espacio."""
    if not texto:
        return ""
    t = quitar_acentos(texto).lower()
    t = re.sub(r"[^a-z0-9&+ ]+", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def normalizar_empresa(nombre: str) -> str:
    t = normalizar(nombre)
    for sufijo in SUFIJOS_EMPRESA:
        t = re.sub(rf"\b{re.escape(sufijo)}\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def normalizar_titulo(titulo: str) -> str:
    if not titulo:
        return ""
    t = quitar_acentos(titulo).lower()
    for patron in RUIDO_TITULO:
        t = re.sub(patron, " ", t)
    # quita la coletilla de ciudad al final: "controller - madrid"
    t = re.sub(r"\s+[-|/]\s+[a-z ]{3,25}$", " ", t)
    t = re.sub(r"[^a-z0-9&+ ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def calcular_huella(empresa_norm: str, titulo_norm: str, provincia: str) -> str:
    """
    Identidad de la oferta. A proposito NO incluye la descripcion:
    cada portal la recorta distinto y eso impediria detectar que la
    misma oferta viene de dos sitios.
    """
    base = f"{empresa_norm or 'sin-empresa'}|{titulo_norm}|{normalizar(provincia)}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def detectar_modalidad(titulo: str, descripcion: str, ubicacion: str) -> str:
    """
    Cuatro estados. 'nacional' es el caso de los anuncios publicados sin
    plaza concreta: la fuente pone solo "Espana". No es remoto confirmado,
    pero tampoco es una plaza atada a una ciudad, asi que va primero en la
    cola de revision.
    """
    texto = normalizar(f"{titulo} {descripcion} {ubicacion}")
    if any(p in texto for p in PALABRAS_HIBRIDO):
        return "hibrido"
    if any(normalizar(p) in texto for p in PALABRAS_REMOTO):
        return "remoto"
    if normalizar(ubicacion) in ("espana", "spain"):
        return "nacional"
    return "desconocida"


def detectar_contrato(titulo: str, descripcion: str, contrato_api: str) -> str:
    if contrato_api == "permanent":
        return "indefinido"
    if contrato_api == "contract":
        return "temporal"
    texto = normalizar(f"{titulo} {descripcion}")
    if any(p in texto for p in PALABRAS_PRACTICAS):
        return "practicas"
    if any(p in texto for p in PALABRAS_INDEFINIDO):
        return "indefinido"
    if any(p in texto for p in PALABRAS_TEMPORAL):
        return "temporal"
    return "desconocido"


def neto_mensual_a_bruto_anual(neto: float, pagas: int, factor: float) -> float:
    return round(neto * pagas * factor, 2)


def evaluar_salario(bruto_min, bruto_max, umbral_bruto_anual, publicado: bool) -> str:
    if not publicado:
        return "no_publicado"
    referencia = bruto_max or bruto_min
    if referencia is None:
        return "no_publicado"
    return "cumple" if referencia >= umbral_bruto_anual else "no_cumple"


def _contiene_frase(texto_norm: str, frase: str) -> bool:
    """Coincidencia por palabra completa, no por trozo suelto."""
    f = normalizar(frase)
    if not f:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(f)}(?![a-z0-9])", texto_norm) is not None


def clasificar(titulo: str, descripcion: str, perfil: dict) -> dict:
    """
    Devuelve en que canales cae la oferta, su grupo de rol y su prioridad.
    Si no cae en ninguno, canal_a y canal_b vienen a False y la oferta
    se descarta antes de llegar a la base de datos.
    """
    titulo_norm = normalizar_titulo(titulo)
    texto = f"{titulo_norm} {normalizar(descripcion)}"

    for palabra in perfil.get("exclusiones_titulo", []):
        if _contiene_frase(titulo_norm, palabra):
            return {"canal_a": False, "canal_b": False,
                    "grupo_rol": None, "prioridad": None}

    resultado = {"canal_a": False, "canal_b": False,
                 "grupo_rol": None, "prioridad": None}

    for codigo_canal, canal in perfil["canales"].items():
        for grupo in canal["grupos"]:
            for sinonimo in grupo["sinonimos"]:
                # el titulo manda; la descripcion solo vale para siglas largas
                acierto = _contiene_frase(titulo_norm, sinonimo)
                if not acierto and len(normalizar(sinonimo)) >= 12:
                    acierto = _contiene_frase(texto, sinonimo)
                if not acierto:
                    continue

                if codigo_canal == "A":
                    resultado["canal_a"] = True
                else:
                    resultado["canal_b"] = True

                prio = grupo.get("prioridad", 9)
                if resultado["prioridad"] is None or prio < resultado["prioridad"]:
                    resultado["prioridad"] = prio
                    resultado["grupo_rol"] = grupo["grupo"]
                break

    return resultado


def detectar_nivel(titulo: str, perfil: dict) -> str:
    """Etiqueta, no filtro. Nunca descarta una oferta."""
    titulo_norm = normalizar_titulo(titulo)
    for nivel in ("directivo", "lead", "senior", "junior"):
        for marca in perfil.get("niveles", {}).get(nivel, []):
            if _contiene_frase(titulo_norm, marca):
                return nivel
    return "desconocido"


def evaluar_alcance(provincia: str, modalidad: str, pais: str, perfil: dict,
                    canal_a: bool, canal_b: bool) -> str:
    """
    Tres estados, no dos:
      alcanzable  -> encaja seguro
      revisar     -> no se sabe. Casi siempre porque la fuente recorta la
                     descripcion y la palabra "teletrabajo" no llega.
      descartada  -> no encaja
    Lo que antes era un no rotundo pasa a ser "revisar": el sistema no
    puede tirar a la basura media Espana por falta de informacion.
    """
    if pais and normalizar(pais) not in ("espana", "spain", ""):
        return "descartada"

    prov_norm = normalizar(provincia)
    canales = []
    if canal_a:
        canales.append(perfil["canales"]["A"])
    if canal_b:
        canales.append(perfil["canales"]["B"])

    resultado = "descartada"
    for canal in canales:
        geo = canal["geografia"]
        en_casa = prov_norm in [normalizar(x) for x in geo["presencial_provincias"]]

        if en_casa:
            return "alcanzable"
        if modalidad == "remoto" and geo.get("acepta_remoto"):
            return "alcanzable"
        if modalidad == "hibrido":
            # hibrido en la peninsula exige pisar oficina: no sirve
            continue
        if modalidad in ("desconocida", "nacional"):
            # la fuente no dice si hay teletrabajo. Se mira a mano.
            resultado = "revisar"

    return resultado


def a_fecha(valor) -> str | None:
    if not valor:
        return None
    try:
        if isinstance(valor, (date, datetime)):
            return valor.date().isoformat() if isinstance(valor, datetime) else valor.isoformat()
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).date().isoformat()
    except (ValueError, TypeError):
        return None
