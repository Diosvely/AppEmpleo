"""
Acceso a Supabase por su API REST. Sin librerias extra: solo requests.
Las claves se leen del entorno y nunca se escriben en el codigo.
"""

import os

import requests

VARIABLES_NECESARIAS = [
    "ADZUNA_APP_ID",
    "ADZUNA_APP_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
]


def comprobar_entorno() -> None:
    """
    Se llama antes de nada. Si falta algo, lo dice claro y en castellano
    en vez de fallar mas adelante con un mensaje ininteligible.
    """
    faltan = [v for v in VARIABLES_NECESARIAS if not os.environ.get(v, "").strip()]
    if faltan:
        raise SystemExit(
            "Faltan estos secretos en GitHub (Settings > Secrets and variables > "
            "Actions):\n  - " + "\n  - ".join(faltan) +
            "\nComprueba que el nombre esta escrito igual, en mayusculas, "
            "y que el valor no esta vacio."
        )

    clave = os.environ["SUPABASE_SERVICE_KEY"].strip()
    if clave.startswith("sb_publishable_"):
        raise SystemExit(
            "El secreto SUPABASE_SERVICE_KEY contiene la clave PUBLICA "
            "(sb_publishable_...). Hace falta la SECRETA, la que empieza "
            "por sb_secret_... en Supabase > Settings > API Keys."
        )

    url = os.environ["SUPABASE_URL"].strip()
    if "supabase.co" not in url and "supabase.in" not in url:
        raise SystemExit(
            "El secreto SUPABASE_URL no parece una direccion de Supabase. "
            "Debe ser la Project URL que sale en Project Settings > API, "
            "algo como https://xxxxxxxx.supabase.co"
        )


def normalizar_url(url: str) -> str:
    """Acepta la URL con o sin https:// y con o sin barra final."""
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


class Supabase:
    def __init__(self):
        self.url = normalizar_url(os.environ["SUPABASE_URL"])
        clave = os.environ["SUPABASE_SERVICE_KEY"].strip()

        # Supabase tiene dos generaciones de claves conviviendo:
        #   - nuevas:  sb_secret_...  (cadena corta, NO es un JWT)
        #   - antiguas: service_role  (token largo que empieza por eyJ)
        # Las nuevas van solo en la cabecera apikey. Las antiguas admiten
        # ademas Authorization: Bearer. Enviamos lo que corresponda.
        self.cabeceras = {
            "apikey": clave,
            "Content-Type": "application/json",
        }
        if clave.startswith("eyJ"):
            self.cabeceras["Authorization"] = f"Bearer {clave}"

    def _comprobar(self, r: requests.Response) -> None:
        if r.status_code in (401, 403):
            raise SystemExit(
                "Supabase rechaza la clave (codigo " + str(r.status_code) + ").\n"
                "Necesitas la clave SECRETA, no la publica.\n"
                "  Supabase > Settings > API Keys\n"
                "  Vale la que empieza por  sb_secret_...\n"
                "  (o, si tu proyecto aun usa las antiguas, la service_role)\n"
                "NO vale la que empieza por sb_publishable_ ni la anon."
            )
        if r.status_code == 404:
            raise SystemExit(
                "Supabase responde 404. Lo mas probable es que el esquema no "
                "este creado: pega sql/01_esquema.sql en el SQL Editor y pulsa Run."
            )
        r.raise_for_status()

    def _rpc(self, funcion: str, cuerpo: dict):
        r = requests.post(
            f"{self.url}/rest/v1/rpc/{funcion}",
            headers=self.cabeceras, json=cuerpo, timeout=90,
        )
        self._comprobar(r)
        return r.json() if r.text else None

    def abrir_ejecucion(self, fuente: str) -> str:
        r = requests.post(
            f"{self.url}/rest/v1/ejecucion",
            headers={**self.cabeceras, "Prefer": "return=representation"},
            json={"fuente": fuente}, timeout=30,
        )
        self._comprobar(r)
        return r.json()[0]["id"]

    def cerrar_ejecucion(self, id_ejecucion: str, estado: str, llamadas: int,
                         vistas: int, nuevas: int, error: str | None = None):
        r = requests.patch(
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
        )
        self._comprobar(r)

    def ingerir(self, ofertas: list[dict]) -> dict:
        if not ofertas:
            return {"nuevas": 0, "actualizadas": 0}
        return self._rpc("ingerir_ofertas", {"datos": ofertas})

    def marcar_inactivas(self, fuente: str, corte_iso: str) -> int:
        return self._rpc("marcar_inactivas", {"p_fuente": fuente, "p_corte": corte_iso})
