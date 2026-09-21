"""
Prueba en seco. No toca internet ni la base de datos.
Sirve para comprobar que la clasificacion y la huella funcionan.

Uso:  python src/probar.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import normalizar as nz
from main import cargar_perfil, preparar

ANUNCIOS_DE_PRUEBA = [
    {"id": 1, "title": "Controller Financiero (H/M)", "company": {"display_name": "Grupo Hotelero Tenerife S.L."},
     "location": {"display_name": "Adeje", "area": ["Spain", "Canarias", "Santa Cruz de Tenerife", "Adeje"]},
     "description": "Buscamos controller para cierre mensual y analisis de desviaciones. Contrato indefinido.",
     "redirect_url": "https://x/1", "salary_min": 30000, "salary_max": 36000,
     "salary_is_predicted": "0", "contract_type": "permanent", "created": "2026-09-10T08:00:00Z"},

    {"id": 2, "title": "CONTROLLER FINANCIERO - Adeje", "company": {"display_name": "Grupo Hotelero Tenerife SL"},
     "location": {"display_name": "Adeje", "area": ["Spain", "Canarias", "Santa Cruz de Tenerife", "Adeje"]},
     "description": "Misma oferta publicada por otro portal.",
     "redirect_url": "https://x/2", "salary_min": None, "salary_max": None,
     "salary_is_predicted": "0", "contract_type": None, "created": "2026-09-10T09:00:00Z"},

    {"id": 3, "title": "Analista de Datos / Power BI - 100% remoto", "company": {"display_name": "Consultora Datos S.A."},
     "location": {"display_name": "Madrid", "area": ["Spain", "Comunidad de Madrid", "Madrid", "Madrid"]},
     "description": "Teletrabajo total. Power BI, SQL y modelado.",
     "redirect_url": "https://x/3", "salary_min": 24000, "salary_max": 24000,
     "salary_is_predicted": "0", "contract_type": "permanent", "created": "2026-09-11T08:00:00Z"},

    {"id": 4, "title": "Controller de Gestion hibrido Barcelona", "company": {"display_name": "Industrial BCN"},
     "location": {"display_name": "Barcelona", "area": ["Spain", "Cataluna", "Barcelona", "Barcelona"]},
     "description": "Modelo hibrido, 3 dias en oficina.",
     "redirect_url": "https://x/4", "salary_min": None, "salary_max": None,
     "salary_is_predicted": "0", "contract_type": None, "created": "2026-09-11T08:00:00Z"},

    {"id": 5, "title": "Comercial de seguros con formacion en datos", "company": {"display_name": "Seguros XYZ"},
     "location": {"display_name": "Santa Cruz", "area": ["Spain", "Canarias", "Santa Cruz de Tenerife", "Santa Cruz"]},
     "description": "Venta de polizas. Se valora manejo de datos.",
     "redirect_url": "https://x/5", "salary_min": None, "salary_max": None,
     "salary_is_predicted": "0", "contract_type": None, "created": "2026-09-11T08:00:00Z"},

    {"id": 6, "title": "Becario departamento financiero", "company": {"display_name": "Auditora"},
     "location": {"display_name": "Santa Cruz", "area": ["Spain", "Canarias", "Santa Cruz de Tenerife", "Santa Cruz"]},
     "description": "Practicas remuneradas analista financiero.",
     "redirect_url": "https://x/6", "salary_min": None, "salary_max": None,
     "salary_is_predicted": "0", "contract_type": None, "created": "2026-09-11T08:00:00Z"},
    {"id": 7, "title": "Senior Data Analyst - Treasury", "company": {"display_name": "Banco Grande"},
     "location": {"display_name": "Madrid", "area": ["Spain", "Comunidad de Madrid", "Madrid", "Madrid"]},
     "description": "Analisis de datos de tesoreria.",
     "redirect_url": "https://x/7", "salary_min": None, "salary_max": None,
     "salary_is_predicted": "0", "contract_type": None, "created": "2026-09-11T08:00:00Z"},

    {"id": 8, "title": "Data Analyst Intern (Korean Speaker)", "company": {"display_name": "Startup"},
     "location": {"display_name": "Barcelona", "area": ["Spain", "Cataluna", "Barcelona", "Barcelona"]},
     "description": "Programa de practicas.",
     "redirect_url": "https://x/8", "salary_min": None, "salary_max": None,
     "salary_is_predicted": "0", "contract_type": None, "created": "2026-09-11T08:00:00Z"},

    {"id": 9, "title": "Director of FP&A and Analytics", "company": {"display_name": "Multinacional"},
     "location": {"display_name": "Madrid", "area": ["Spain", "Comunidad de Madrid", "Madrid", "Madrid"]},
     "description": "Direccion del area de planificacion.",
     "redirect_url": "https://x/9", "salary_min": None, "salary_max": None,
     "salary_is_predicted": "0", "contract_type": None, "created": "2026-09-11T08:00:00Z"},

    {"id": 10, "title": "Online Data Analyst - Spanish (ES)", "company": {"display_name": "Plataforma"},
     "location": {"display_name": "Madrid", "area": ["Spain", "Comunidad de Madrid", "Madrid", "Madrid"]},
     "description": "Microtareas de evaluacion.",
     "redirect_url": "https://x/10", "salary_min": None, "salary_max": None,
     "salary_is_predicted": "0", "contract_type": None, "created": "2026-09-11T08:00:00Z"},
]


def main():
    perfil = cargar_perfil()
    s = perfil["salario"]
    umbral = nz.neto_mensual_a_bruto_anual(
        s["neto_mensual_minimo"], s["pagas_anuales"], s["factor_neto_a_bruto"])
    print(f"Umbral de salario: {umbral:,.0f} EUR brutos anuales\n")

    huellas = {}
    for anuncio in ANUNCIOS_DE_PRUEBA:
        p = preparar(anuncio, perfil, umbral)
        if p is None:
            print(f"[DESCARTADA] {anuncio['title']}")
            continue
        canal = ("A" if p["canal_a"] else "") + ("B" if p["canal_b"] else "")
        huellas.setdefault(p["huella"], []).append(anuncio["id"])
        print(f"[CANAL {canal}] {p['titulo']}")
        print(f"    grupo={p['grupo_rol']}  nivel={p['nivel']}  prioridad={p['prioridad']}  "
              f"modalidad={p['modalidad']}  contrato={p['contrato']}")
        print(f"    provincia={p['provincia']}  alcance={p['alcance']}  "
              f"salario={p['cumple_salario']}")
        print(f"    huella={p['huella'][:12]}...")

    print("\n--- Deduplicacion ---")
    for huella, ids in huellas.items():
        marca = "DUPLICADA" if len(ids) > 1 else "unica"
        print(f"{huella[:12]}...  anuncios {ids}  -> {marca}")


if __name__ == "__main__":
    main()
