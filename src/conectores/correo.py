"""
Lector de correo por IMAP.

Se conecta a Gmail, busca solo dentro de las etiquetas que le digas,
y devuelve los mensajes sin procesar. No borra nada: marca como leidos
los que ya ha tratado, para no repetirlos manana.

Necesita dos secretos: GMAIL_USUARIO y GMAIL_APP_PASSWORD.
"""

import email
import email.message
import imaplib
import os
from email.header import decode_header, make_header

SERVIDOR = "imap.gmail.com"
PUERTO = 993


class Buzon:
    def __init__(self):
        faltan = [v for v in ("GMAIL_USUARIO", "GMAIL_APP_PASSWORD")
                  if not os.environ.get(v, "").strip()]
        if faltan:
            raise SystemExit(
                "Faltan secretos en GitHub: " + ", ".join(faltan) + "\n"
                "GMAIL_USUARIO es tu direccion completa. GMAIL_APP_PASSWORD son "
                "los 16 caracteres de la contrasena de aplicacion, sin espacios."
            )
        self.usuario = os.environ["GMAIL_USUARIO"].strip()
        self.clave = os.environ["GMAIL_APP_PASSWORD"].strip().replace(" ", "")
        self.conexion = None

    def __enter__(self):
        try:
            self.conexion = imaplib.IMAP4_SSL(SERVIDOR, PUERTO)
            self.conexion.login(self.usuario, self.clave)
        except imaplib.IMAP4.error as e:
            raise SystemExit(
                "Gmail rechaza la conexion.\n"
                "  - Comprueba que la verificacion en dos pasos sigue activa.\n"
                "  - Si cambiaste la contrasena de Google, la de aplicacion se "
                "anulo sola: genera otra.\n"
                "  - Pega los 16 caracteres sin espacios.\n"
                f"Detalle: {e}"
            )
        return self

    def __exit__(self, *_):
        if self.conexion:
            try:
                self.conexion.close()
            except Exception:
                pass
            self.conexion.logout()

    def leer_etiqueta(self, etiqueta: str, solo_no_leidos: bool = True,
                      limite: int = 200) -> list[tuple[bytes, email.message.Message]]:
        """
        Devuelve [(uid, mensaje), ...] de una etiqueta de Gmail.
        En Gmail las etiquetas se comportan como carpetas IMAP.
        """
        estado, _ = self.conexion.select(f'"{etiqueta}"', readonly=False)
        if estado != "OK":
            print(f"AVISO: no existe la etiqueta '{etiqueta}'. Se omite.")
            return []

        criterio = "(UNSEEN)" if solo_no_leidos else "(ALL)"
        estado, datos = self.conexion.search(None, criterio)
        if estado != "OK" or not datos or not datos[0]:
            return []

        uids = datos[0].split()[-limite:]
        mensajes = []
        for uid in uids:
            estado, crudo = self.conexion.fetch(uid, "(BODY.PEEK[])")
            if estado != "OK" or not crudo or not crudo[0]:
                continue
            mensajes.append((uid, email.message_from_bytes(crudo[0][1])))
        return mensajes

    def marcar_procesado(self, uid: bytes) -> None:
        self.conexion.store(uid, "+FLAGS", "\\Seen")


def asunto(mensaje) -> str:
    bruto = mensaje.get("Subject", "")
    try:
        return str(make_header(decode_header(bruto)))
    except Exception:
        return bruto


def extraer_parte(mensaje, tipo: str) -> str | None:
    """
    Devuelve el contenido de la parte pedida, decodificado con el juego de
    caracteres que declare el propio correo. InfoJobs usa iso-8859-1 y si
    se lee como utf-8 salen los acentos rotos.
    """
    for parte in mensaje.walk():
        if parte.get_content_type() == tipo:
            crudo = parte.get_payload(decode=True)
            if not crudo:
                continue
            juego = parte.get_content_charset() or "utf-8"
            try:
                return crudo.decode(juego, "replace")
            except LookupError:
                return crudo.decode("utf-8", "replace")
    return None
