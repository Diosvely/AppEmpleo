"""
Acceso a Supabase por su API REST. Sin librerias extra: solo requests.
La clave de servicio se lee del entorno y nunca se escribe en el codigo.
"""

import os

import requests


class Supabase:
    def __init__(self):
        self.url = os.environ["SUPABASE_URL"].rstrip("/")
        clave = os.environ["SUPABASE_SERVICE_KEY"]
        self.cabeceras = {
            "apikey": clave,
            "Authorization": f"Bearer {clave}",
            "Content-Type": "application/json",
        }

    def _rpc(self, funcion: str, cuerpo: dict):
        r = requests.post(
            f"{self.url}/rest/v1/rpc/{funcion}",
            headers=self.cabeceras, json=cuerpo, timeout=90,
        )
        r.raise_for_status()
        return r.json() if r.text else None

    def abrir_ejecucion(self, fuente: str) -> str:
        r = requests.post(
            f"{self.url}/rest/v1/ejecucion",
            headers={**self.cabeceras, "Prefer": "return=representation"},
            json={"fuente": fuente}, timeout=30,
        )
        r.raise_for_status()
        return r.json()[0]["id"]

    def cerrar_ejecucion(self, id_ejecucion: str, estado: str, llamadas: int,
                         vistas: int, nuevas: int, error: str | None = None):
        requests.patch(
            f"{self.url}/rest/v1/ejecucion",
            headers=self.cabeceras,
            params={"id": f"eq.{id_ejecucion}"},
            json={
                "terminada_en": "now()",
                "estado": estado,
                "llamadas_api": llamadas,
                "ofertas_vistas": vistas,
                "ofertas_nuevas": nuevas,
                "mensaje_error": (error or "")[:2000] or None,
            },
            timeout=30,
        ).raise_for_status()

    def ingerir(self, ofertas: list[dict]) -> dict:
        if not ofertas:
            return {"nuevas": 0, "actualizadas": 0}
        return self._rpc("ingerir_ofertas", {"datos": ofertas})

    def marcar_inactivas(self, fuente: str, corte_iso: str) -> int:
        return self._rpc("marcar_inactivas", {"p_fuente": fuente, "p_corte": corte_iso})
