"""
Ingesta diaria. Esto es lo que ejecuta GitHub Actions cada manana.

Pasos: leer perfil -> pedir a Adzuna -> guardar el crudo -> normalizar
-> clasificar -> descartar lo que no encaja -> guardar en Supabase
-> apagar las ofertas que ya no aparecen.
"""

import gzip
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import normalizar as nz
import geografia as geo
from conectores.adzuna import CODIGO_FUENTE, Adzuna, a_formato_comun
from conectores.alertas_correo import (CODIGO_INFOJOBS, CODIGO_LINKEDIN,
                                       interpretar_infojobs, interpretar_linkedin)
from conectores.correo import Buzon, asunto, extraer_parte
from db import Supabase, comprobar_entorno

ETIQUETAS = {"AppEmpleo/LinkedIn": CODIGO_LINKEDIN,
             "AppEmpleo/InfoJobs": CODIGO_INFOJOBS}

RAIZ = Path(__file__).resolve().parent.parent
LOTE = 200


def cargar_perfil() -> dict:
    with open(RAIZ / "config" / "profile.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def guardar_crudo(anuncios: list[dict], momento: datetime,
                  fuente: str = CODIGO_FUENTE) -> Path:
    """El crudo se guarda comprimido en el repo. Nunca se modifica."""
    carpeta = RAIZ / "raw" / fuente / momento.strftime("%Y/%m/%d")
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"{momento.strftime('%Y%m%d_%H%M%S')}.json.gz"
    with gzip.open(destino, "wt", encoding="utf-8") as f:
        json.dump(anuncios, f, ensure_ascii=False)
    return destino


def preparar(anuncio: dict, perfil: dict, umbral_bruto: float) -> dict | None:
    c = a_formato_comun(anuncio)

    clas = nz.clasificar(c["titulo"], c["descripcion"] or "", perfil)
    if not (clas["canal_a"] or clas["canal_b"]):
        return None

    contrato = nz.detectar_contrato(c["titulo"], c["descripcion"] or "", c["contrato_api"])
    if contrato in perfil["contrato"]["excluidos"]:
        return None

    modalidad = nz.detectar_modalidad(c["titulo"], c["descripcion"] or "",
                                      c["ubicacion_texto"] or "")
    alcance = nz.evaluar_alcance(c["provincia"] or "", modalidad, c["pais"] or "",
                                 perfil, clas["canal_a"], clas["canal_b"])
    nivel = nz.detectar_nivel(c["titulo"], perfil)

    titulo_norm = nz.normalizar_titulo(c["titulo"])
    empresa_norm = nz.normalizar_empresa(c["empresa"] or "")
    publicado = bool(c["salario_min"] or c["salario_max"]) and not c["salario_estimado"]

    return {
        "huella": nz.calcular_huella(empresa_norm, titulo_norm, c["provincia"] or ""),
        "titulo": c["titulo"],
        "titulo_norm": titulo_norm,
        "empresa": c["empresa"],
        "empresa_norm": empresa_norm,
        "ubicacion_texto": c["ubicacion_texto"],
        "pais": c["pais"],
        "comunidad": c["comunidad"],
        "provincia": c["provincia"],
        "municipio": c["municipio"],
        "modalidad": modalidad,
        "contrato": contrato,
        "jornada": c["jornada"],
        "salario_min": c["salario_min"],
        "salario_max": c["salario_max"],
        "salario_periodo": "anual",
        "salario_publicado": publicado,
        "salario_estimado": c["salario_estimado"],
        "salario_bruto_anual_min": c["salario_min"] if publicado else None,
        "salario_bruto_anual_max": c["salario_max"] if publicado else None,
        "cumple_salario": nz.evaluar_salario(c["salario_min"], c["salario_max"],
                                             umbral_bruto, publicado),
        "descripcion": c["descripcion"],
        "url": c["url"],
        "canal_a": clas["canal_a"],
        "canal_b": clas["canal_b"],
        "grupo_rol": clas["grupo_rol"],
        "prioridad": clas["prioridad"],
        "alcance": alcance,
        "nivel": nivel,
        "publicada_en": nz.a_fecha(c["publicada_en"]),
        "fuente": CODIGO_FUENTE,
        "id_origen": c["id_origen"],
    }


def preparar_correo(oferta: dict, perfil: dict, umbral_bruto: float) -> dict | None:
    """
    Traduce una oferta sacada de una alerta por correo al mismo formato que
    usa Adzuna, para que siga exactamente la misma tuberia.
    """
    clas = nz.clasificar(oferta["titulo"], "", perfil)
    if not (clas["canal_a"] or clas["canal_b"]):
        return None

    ubicacion = oferta.get("ubicacion_texto") or ""
    provincia = geo.provincia_de(ubicacion)

    # la modalidad que declara el portal manda sobre lo que adivinemos
    modalidad = oferta.get("modalidad_fuente")
    if not modalidad:
        modalidad = nz.detectar_modalidad(oferta["titulo"], "", ubicacion)
        if modalidad == "desconocida" and geo.es_ambito_nacional(ubicacion):
            modalidad = "nacional"

    contrato = oferta.get("contrato_fuente") or nz.detectar_contrato(
        oferta["titulo"], "", None)
    if contrato in perfil["contrato"]["excluidos"]:
        return None

    alcance = nz.evaluar_alcance(provincia or "", modalidad, "Espana",
                                 perfil, clas["canal_a"], clas["canal_b"])

    # InfoJobs a veces da mensual: lo pasamos a bruto anual para comparar
    minimo, maximo = oferta.get("salario_min"), oferta.get("salario_max")
    if oferta.get("salario_periodo") == "mensual":
        minimo = minimo * perfil["salario"]["pagas_anuales"] if minimo else None
        maximo = maximo * perfil["salario"]["pagas_anuales"] if maximo else None
    publicado = bool(minimo or maximo)

    titulo_norm = nz.normalizar_titulo(oferta["titulo"])
    empresa_norm = nz.normalizar_empresa(oferta.get("empresa") or "")

    # InfoJobs oculta la empresa: sin ella, la huella usa el municipio para
    # no fundir ofertas distintas bajo una misma "empresa vacia"
    semilla_empresa = empresa_norm or f"sinempresa-{nz.normalizar(ubicacion)}"

    return {
        "huella": nz.calcular_huella(semilla_empresa, titulo_norm, provincia or ""),
        "titulo": oferta["titulo"],
        "titulo_norm": titulo_norm,
        "empresa": oferta.get("empresa"),
        "empresa_norm": empresa_norm or None,
        "ubicacion_texto": ubicacion or None,
        "pais": "Espana",
        "comunidad": None,
        "provincia": provincia,
        "municipio": ubicacion or None,
        "modalidad": modalidad,
        "contrato": contrato,
        "jornada": None,
        "salario_min": minimo,
        "salario_max": maximo,
        "salario_periodo": "anual",
        "salario_publicado": publicado,
        "salario_estimado": False,
        "salario_bruto_anual_min": minimo,
        "salario_bruto_anual_max": maximo,
        "cumple_salario": nz.evaluar_salario(minimo, maximo, umbral_bruto, publicado),
        "descripcion": oferta.get("descripcion"),
        "url": oferta.get("url"),
        "canal_a": clas["canal_a"],
        "canal_b": clas["canal_b"],
        "grupo_rol": clas["grupo_rol"],
        "prioridad": clas["prioridad"],
        "alcance": alcance,
        "nivel": nz.detectar_nivel(oferta["titulo"], perfil),
        "publicada_en": None,
        "fuente": oferta["fuente"],
        "id_origen": oferta["id_origen"],
    }


def ingerir_correo(bd: Supabase, perfil: dict, umbral_bruto: float) -> None:
    """Lee las alertas de LinkedIn e InfoJobs desde Gmail."""
    if not os.environ.get("GMAIL_USUARIO", "").strip():
        print("Sin credenciales de Gmail: se omite la fuente correo.")
        return

    momento = datetime.now(timezone.utc)
    id_ejecucion = bd.abrir_ejecucion("correo")
    crudos, preparadas, procesados = [], [], []

    try:
        with Buzon() as buzon:
            for etiqueta, codigo in ETIQUETAS.items():
                for uid, mensaje in buzon.leer_etiqueta(etiqueta):
                    tema = asunto(mensaje)
                    if codigo == CODIGO_LINKEDIN:
                        hallazgos = interpretar_linkedin(
                            extraer_parte(mensaje, "text/plain") or "")
                    else:
                        hallazgos = interpretar_infojobs(
                            extraer_parte(mensaje, "text/html") or "", tema)

                    crudos.append({"etiqueta": etiqueta, "asunto": tema,
                                   "ofertas": hallazgos})
                    preparadas.extend(
                        p for p in (preparar_correo(o, perfil, umbral_bruto)
                                    for o in hallazgos) if p)
                    procesados.append((buzon, uid))
                    print(f"  {etiqueta}: '{tema[:55]}' -> {len(hallazgos)} ofertas")

            guardar_crudo(crudos, momento, "correo")

            nuevas = actualizadas = 0
            for i in range(0, len(preparadas), LOTE):
                r = bd.ingerir(preparadas[i:i + LOTE])
                nuevas += r.get("nuevas", 0)
                actualizadas += r.get("actualizadas", 0)

            # solo se marcan como leidos si todo fue bien
            for buzon_, uid in procesados:
                buzon_.marcar_procesado(uid)

        bd.cerrar_ejecucion(id_ejecucion, "ok", 0, len(preparadas), nuevas)
        print(f"CORREO  nuevas={nuevas}  actualizadas={actualizadas}  "
              f"mensajes={len(procesados)}")

    except SystemExit:
        raise
    except Exception as e:
        bd.cerrar_ejecucion(id_ejecucion, "error", 0, 0, 0, str(e))
        print(f"ERROR en la fuente correo: {e}", file=sys.stderr)


def main() -> int:
    comprobar_entorno()
    perfil = cargar_perfil()
    momento = datetime.now(timezone.utc)
    sal = perfil["salario"]
    umbral_bruto = nz.neto_mensual_a_bruto_anual(
        sal["neto_mensual_minimo"], sal["pagas_anuales"], sal["factor_neto_a_bruto"]
    )

    consultas: list[str] = []
    for canal in perfil["canales"].values():
        consultas.extend(canal["consultas_api"])

    bd = Supabase()
    id_ejecucion = bd.abrir_ejecucion(CODIGO_FUENTE)
    corte = momento.isoformat()
    cliente = Adzuna(os.environ["ADZUNA_APP_ID"], os.environ["ADZUNA_APP_KEY"],
                     perfil["adzuna"])

    try:
        anuncios, avisos = cliente.recolectar(consultas)
        for aviso in avisos:
            print(f"AVISO: {aviso}")

        ruta = guardar_crudo(anuncios, momento)
        print(f"Crudo guardado en {ruta.relative_to(RAIZ)} ({len(anuncios)} anuncios)")

        preparadas = [p for p in (preparar(a, perfil, umbral_bruto) for a in anuncios) if p]
        print(f"{len(anuncios)} anuncios recibidos -> {len(preparadas)} encajan en algun canal")

        nuevas = actualizadas = 0
        for i in range(0, len(preparadas), LOTE):
            r = bd.ingerir(preparadas[i:i + LOTE])
            nuevas += r.get("nuevas", 0)
            actualizadas += r.get("actualizadas", 0)

        hubo_fallo_grave = any("cupo" in a.lower() for a in avisos)
        if not hubo_fallo_grave:
            apagadas = bd.marcar_inactivas(CODIGO_FUENTE, corte)
            print(f"Ofertas marcadas como ya no publicadas: {apagadas}")
        else:
            print("No se apaga nada: la fuente no se recorrio entera.")

        bd.cerrar_ejecucion(id_ejecucion, "ok", cliente.llamadas,
                            len(preparadas), nuevas)
        print(f"ADZUNA  nuevas={nuevas}  actualizadas={actualizadas}  "
              f"llamadas_api={cliente.llamadas}")

        ingerir_correo(bd, perfil, umbral_bruto)
        return 0

    except Exception as e:
        bd.cerrar_ejecucion(id_ejecucion, "error", cliente.llamadas, 0, 0, str(e))
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
