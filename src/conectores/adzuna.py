"""
Conector de Adzuna.

Cuenta cada llamada y se detiene en cuanto alcanza el tope del perfil,
porque el plan de prueba tiene cupo mensual limitado.
"""

import time

import requests

URL_BASE = "https://api.adzuna.com/v1/api/jobs"
CODIGO_FUENTE = "adzuna"


class CupoAgotado(Exception):
    pass


class Adzuna:
    def __init__(self, app_id: str, app_key: str, opciones: dict):
        self.app_id = app_id
        self.app_key = app_key
        self.opciones = opciones
        self.llamadas = 0
        self.sesion = requests.Session()
        self.sesion.headers.update({"User-Agent": "AppEmpleo/0.1 (proyecto personal)"})

    def _pedir(self, consulta: str, pagina: int) -> dict:
        tope = self.opciones.get("maximo_llamadas_por_ejecucion", 60)
        if self.llamadas >= tope:
            raise CupoAgotado(f"Alcanzado el tope de {tope} llamadas")

        pais = self.opciones.get("pais", "es")
        parametros = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": self.opciones.get("resultados_por_pagina", 50),
            "what_phrase": consulta,
            "max_days_old": self.opciones.get("dias_maximos_antiguedad", 30),
            "sort_by": "date",
            "content-type": "application/json",
        }
        if self.opciones.get("buscar_solo_en_titulo", True):
            parametros["title_only"] = consulta

        respuesta = self.sesion.get(
            f"{URL_BASE}/{pais}/search/{pagina}", params=parametros, timeout=40
        )
        self.llamadas += 1
        time.sleep(self.opciones.get("segundos_entre_llamadas", 1.5))

        if respuesta.status_code == 429:
            raise CupoAgotado("Adzuna respondio 429: cupo de la API agotado")
        respuesta.raise_for_status()
        return respuesta.json()

    def recolectar(self, consultas: list[str]) -> tuple[list[dict], list[str]]:
        """Devuelve (anuncios en crudo, avisos)."""
        anuncios: list[dict] = []
        avisos: list[str] = []
        paginas = self.opciones.get("paginas_por_consulta", 3)

        for consulta in consultas:
            for pagina in range(1, paginas + 1):
                try:
                    datos = self._pedir(consulta, pagina)
                except CupoAgotado as e:
                    avisos.append(str(e))
                    return anuncios, avisos
                except requests.RequestException as e:
                    avisos.append(f"Fallo en '{consulta}' pagina {pagina}: {e}")
                    break

                resultados = datos.get("results", [])
                for r in resultados:
                    r["_consulta"] = consulta
                anuncios.extend(resultados)

                if len(resultados) < self.opciones.get("resultados_por_pagina", 50):
                    break

        return anuncios, avisos


def a_formato_comun(anuncio: dict) -> dict:
    """Traduce un anuncio de Adzuna a nuestro vocabulario interno."""
    area = (anuncio.get("location") or {}).get("area") or []
    return {
        "id_origen": str(anuncio.get("id")),
        "titulo": anuncio.get("title") or "",
        "empresa": (anuncio.get("company") or {}).get("display_name"),
        "ubicacion_texto": (anuncio.get("location") or {}).get("display_name"),
        "pais": area[0] if len(area) > 0 else None,
        "comunidad": area[1] if len(area) > 1 else None,
        "provincia": area[2] if len(area) > 2 else None,
        "municipio": area[3] if len(area) > 3 else None,
        "descripcion": anuncio.get("description"),
        "url": anuncio.get("redirect_url"),
        "salario_min": anuncio.get("salary_min"),
        "salario_max": anuncio.get("salary_max"),
        "salario_estimado": bool(anuncio.get("salary_is_predicted") in (1, "1", True)),
        "contrato_api": anuncio.get("contract_type"),
        "jornada": anuncio.get("contract_time"),
        "publicada_en": anuncio.get("created"),
    }
