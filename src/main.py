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
from conectores.adzuna import CODIGO_FUENTE, Adzuna, a_formato_comun
from db import Supabase

RAIZ = Path(__file__).resolve().parent.parent
LOTE = 200


def cargar_perfil() -> dict:
    with open(RAIZ / "config" / "profile.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def guardar_crudo(anuncios: list[dict], momento: datetime) -> Path:
    """El crudo se guarda comprimido en el repo. Nunca se modifica."""
    carpeta = RAIZ / "raw" / CODIGO_FUENTE / momento.strftime("%Y/%m/%d")
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
    encaja = nz.evaluar_geografia(c["provincia"] or "", modalidad, c["pais"] or "",
                                  perfil, clas["canal_a"], clas["canal_b"])

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
        "encaja_geografia": encaja,
        "publicada_en": nz.a_fecha(c["publicada_en"]),
        "fuente": CODIGO_FUENTE,
        "id_origen": c["id_origen"],
    }


def main() -> int:
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
        print(f"RESUMEN  nuevas={nuevas}  actualizadas={actualizadas}  "
              f"llamadas_api={cliente.llamadas}")
        return 0

    except Exception as e:
        bd.cerrar_ejecucion(id_ejecucion, "error", cliente.llamadas, 0, 0, str(e))
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
