"""
Geografia minima: de lo que pone un anuncio a una provincia.

Las alertas de correo dan municipio, no provincia, y la provincia es lo
que decide si una oferta te es alcanzable. Los municipios canarios estan
completos porque son tu mercado presencial; del resto de Espana basta
con reconocer el nombre de la provincia.
"""

import unicodedata

TENERIFE = """
Adeje Arafo Arico Arona Buenavista del Norte Candelaria Fasnia Garachico
Granadilla de Abona La Guancha Guia de Isora Guimar Icod de los Vinos
La Laguna San Cristobal de La Laguna La Matanza de Acentejo La Orotava
Puerto de la Cruz Los Realejos El Rosario San Juan de la Rambla
San Miguel de Abona Santa Cruz de Tenerife Santa Ursula Santiago del Teide
El Sauzal Los Silos Tacoronte El Tanque Tegueste La Victoria de Acentejo
Vilaflor
Barlovento Brena Alta Brena Baja Fuencaliente de la Palma Garafia
Los Llanos de Aridane El Paso Puntagorda Puntallana San Andres y Sauces
Santa Cruz de La Palma Tazacorte Tijarafe Villa de Mazo
Agulo Alajero Hermigua San Sebastian de la Gomera Valle Gran Rey Vallehermoso
Frontera La Frontera El Pinar de El Hierro Valverde
"""

LAS_PALMAS = """
Agaete Aguimes La Aldea de San Nicolas Artenara Arucas Firgas Galdar
Ingenio Mogan Moya Las Palmas de Gran Canaria San Bartolome de Tirajana
La Santa Brigida Santa Lucia de Tirajana Santa Maria de Guia Tejeda Telde
Teror Valleseco Valsequillo de Gran Canaria Vega de San Mateo
Antigua Betancuria La Oliva Pajara Puerto del Rosario Tuineje
Arrecife Haria San Bartolome Teguise Tias Tinajo Yaiza
"""

PROVINCIAS = """
A Coruna Alava Albacete Alicante Almeria Asturias Avila Badajoz Baleares
Barcelona Bizkaia Vizcaya Burgos Caceres Cadiz Cantabria Castellon Ceuta
Ciudad Real Cordoba Cuenca Gipuzkoa Guipuzcoa Girona Granada Guadalajara
Huelva Huesca Jaen La Rioja Las Palmas Leon Lugo Lleida Madrid Malaga
Melilla Murcia Navarra Ourense Palencia Pontevedra Salamanca
Santa Cruz de Tenerife Segovia Sevilla Soria Tarragona Teruel Toledo
Valencia Valladolid Zamora Zaragoza
"""

# Variantes que usan los portales
ALIAS = {
    "sta cruz de tenerife": "Santa Cruz de Tenerife",
    "tenerife": "Santa Cruz de Tenerife",
    "s c de tenerife": "Santa Cruz de Tenerife",
    "gran canaria": "Las Palmas",
    "lanzarote": "Las Palmas",
    "fuerteventura": "Las Palmas",
    "la palma": "Santa Cruz de Tenerife",
    "la gomera": "Santa Cruz de Tenerife",
    "el hierro": "Santa Cruz de Tenerife",
    "islas canarias": None,          # ambiguo: no se decide provincia
    "canarias": None,
    "bilbao": "Bizkaia",
    "san sebastian": "Gipuzkoa",
    "coruna": "A Coruna",
    "palma de mallorca": "Baleares",
    "mallorca": "Baleares",
}


def _clave(texto: str) -> str:
    if not texto:
        return ""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_acentos.lower().replace(",", " ").split())


def _municipios(bloque: str, provincia: str) -> dict:
    salida = {}
    for linea in bloque.strip().split("\n"):
        # cada linea trae varios municipios; se separan por mayusculas iniciales
        for nombre in _separar(linea):
            salida[_clave(nombre)] = provincia
    return salida


def _separar(linea: str) -> list[str]:
    """Parte una linea en nombres propios, respetando los compuestos."""
    palabras = linea.split()
    nombres, actual = [], []
    menores = {"de", "del", "la", "las", "los", "el", "y", "san", "santa"}
    for palabra in palabras:
        if actual and palabra[0].isupper() and actual[-1].lower() not in menores:
            nombres.append(" ".join(actual))
            actual = [palabra]
        else:
            actual.append(palabra)
    if actual:
        nombres.append(" ".join(actual))
    return nombres


MAPA = {}
MAPA.update(_municipios(TENERIFE, "Santa Cruz de Tenerife"))
MAPA.update(_municipios(LAS_PALMAS, "Las Palmas"))
for _linea in PROVINCIAS.strip().split("\n"):
    for _nombre in _separar(_linea):
        MAPA[_clave(_nombre)] = _nombre
for _alias, _destino in ALIAS.items():
    if _destino:
        MAPA[_alias] = _destino


def provincia_de(ubicacion: str) -> str | None:
    """
    Devuelve la provincia a partir de lo que ponga el anuncio.
    None si no se reconoce: es preferible no saberlo a inventarlo.
    """
    if not ubicacion:
        return None
    clave = _clave(ubicacion)
    if clave in ("espana", "spain", "espana remoto"):
        return None
    if clave in MAPA:
        return MAPA[clave]
    # "Arona, Santa Cruz de Tenerife" o "Madrid, Comunidad de Madrid"
    for trozo in reversed([t.strip() for t in ubicacion.split(",")]):
        if _clave(trozo) in MAPA:
            return MAPA[_clave(trozo)]
    return None


def es_ambito_nacional(ubicacion: str) -> bool:
    return _clave(ubicacion) in ("espana", "spain", "remoto espana", "espana remoto")
