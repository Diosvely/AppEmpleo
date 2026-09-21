/* =====================================================================
   MODO DEMOSTRACION

   Sustituye al cliente de Supabase por uno falso con datos inventados.
   No hay red, no hay base de datos, no hay cuenta. Sirve para que
   cualquiera vea como funciona la aplicacion sin tener que montar nada,
   y para hacer capturas de pantalla sin ensenar datos reales.

   Este archivo lo inserta build.js en el sitio exacto donde index.html
   crea su conexion, asi que la demostracion nunca se queda desfasada:
   es la misma aplicacion, con otra fuente de datos.
   ===================================================================== */

const REPO_GITHUB = "";   // sin boton de ingesta en la demostracion

const DEMO_OFERTAS = [
  { id:1, titulo:"Cost Controller", empresa:"Hotel Atlántico Sur",
    provincia:"Santa Cruz de Tenerife", municipio:"Adeje", canal:"A",
    alcance:"alcanzable", modalidad:"presencial", nivel:"senior",
    cumple_salario:"cumple", salario_bruto_anual_min:30000,
    salario_bruto_anual_max:36000, prioridad:1, url:"#" },
  { id:2, titulo:"Técnico/a de Control Financiero", empresa:"Grupo Insular de Distribución",
    provincia:"Santa Cruz de Tenerife", municipio:"La Laguna", canal:"A",
    alcance:"alcanzable", modalidad:"hibrido", nivel:"desconocido",
    cumple_salario:"no_publicado", salario_bruto_anual_min:null, prioridad:1, url:"#" },
  { id:3, titulo:"Analytics Engineer (100% remoto)", empresa:"Nubia Data",
    provincia:null, municipio:"España", canal:"B", alcance:"alcanzable",
    modalidad:"remoto", nivel:"senior", cumple_salario:"cumple",
    salario_bruto_anual_min:38000, salario_bruto_anual_max:45000, prioridad:1, url:"#" },
  { id:4, titulo:"Analista de Datos · Power BI", empresa:"Meridiano Consultores",
    provincia:null, municipio:"España", canal:"B", alcance:"alcanzable",
    modalidad:"nacional", nivel:"desconocido", cumple_salario:"no_publicado",
    salario_bruto_anual_min:null, prioridad:2, url:"#" },
  { id:5, titulo:"Controller de Gestión Industrial", empresa:"Cerámicas del Teide",
    provincia:"Santa Cruz de Tenerife", municipio:"Granadilla de Abona", canal:"A",
    alcance:"alcanzable", modalidad:"presencial", nivel:"desconocido",
    cumple_salario:"no_cumple", salario_bruto_anual_min:21000,
    salario_bruto_anual_max:23000, prioridad:2, url:"#" },
  { id:6, titulo:"Financial Controller", empresa:"Vega Retail Group",
    provincia:"Madrid", municipio:"Madrid", canal:"A", alcance:"revisar",
    modalidad:"desconocida", nivel:"senior", cumple_salario:"no_publicado",
    salario_bruto_anual_min:null, prioridad:1, url:"#" },
  { id:7, titulo:"Business Intelligence Analyst", empresa:"Sotavento Logística",
    provincia:"Barcelona", municipio:"Barcelona", canal:"B", alcance:"revisar",
    modalidad:"hibrido", nivel:"junior", cumple_salario:"no_publicado",
    salario_bruto_anual_min:null, prioridad:2, url:"#" },
  { id:8, titulo:"Analista de Costes", empresa:"Conservas Puerto Norte",
    provincia:"Valencia", municipio:"Valencia", canal:"A", alcance:"revisar",
    modalidad:"presencial", nivel:"desconocido", cumple_salario:"cumple",
    salario_bruto_anual_min:27000, salario_bruto_anual_max:31000, prioridad:2, url:"#" },
  { id:9, titulo:"Data Analyst · Sector Turismo", empresa:"Islas Analytics",
    provincia:"Las Palmas", municipio:"Las Palmas de Gran Canaria", canal:"B",
    alcance:"revisar", modalidad:"desconocida", nivel:"desconocido",
    cumple_salario:"no_publicado", salario_bruto_anual_min:null, prioridad:3, url:"#" },
];

const DEMO_CANDIDATURAS = [
  { oferta_id:101, titulo:"Controller Financiero", empresa:"Bodegas Valle Verde",
    provincia:"Santa Cruz de Tenerife", estado:"entrevista", cv_usado:"Controller",
    dias_sin_novedad:2, url:"#", fecha_aplicacion:"2026-09-02" },
  { oferta_id:102, titulo:"Analytics Engineer", empresa:"Nubia Data",
    provincia:"España", estado:"contactado", cv_usado:"Datos",
    dias_sin_novedad:1, url:"#", fecha_aplicacion:"2026-09-08" },
  { oferta_id:103, titulo:"Analista de Control de Gestión", empresa:"Naviera Bahía Azul",
    provincia:"Las Palmas", estado:"aplicada", cv_usado:"Controller",
    dias_sin_novedad:5, url:"#", fecha_aplicacion:"2026-09-11" },
  { oferta_id:104, titulo:"Data Analyst · Retail", empresa:"Vega Retail Group",
    provincia:"Madrid", estado:"aplicada", cv_usado:"Datos",
    dias_sin_novedad:0, url:"#", fecha_aplicacion:"2026-09-16" },
  { oferta_id:105, titulo:"Responsable de Administración", empresa:"Transportes Anaga",
    provincia:"Santa Cruz de Tenerife", estado:"rechazado", cv_usado:"Controller",
    dias_sin_novedad:14, url:"#", fecha_aplicacion:"2026-08-28" },
  { oferta_id:106, titulo:"BI Developer", empresa:"Sotavento Logística",
    provincia:"Barcelona", estado:"descartada", cv_usado:null,
    dias_sin_novedad:9, url:"#", fecha_aplicacion:null },
];

const DEMO_EMBUDO = [
  { orden:1, estado:"interesante",        ofertas:14 },
  { orden:2, estado:"aplicada",           ofertas:9  },
  { orden:3, estado:"contactado",         ofertas:4  },
  { orden:4, estado:"entrevista",         ofertas:2  },
  { orden:5, estado:"segunda_entrevista", ofertas:1  },
  { orden:6, estado:"oferta_recibida",    ofertas:0  },
];

const DEMO_CV = [
  { cv:"Controller", aplicadas:6, contactos:3, entrevistas:2, tasa_respuesta_pct:50.0 },
  { cv:"Datos",      aplicadas:3, contactos:1, entrevistas:0, tasa_respuesta_pct:33.3 },
];

const DEMO = {
  v_bandeja: DEMO_OFERTAS,
  v_candidaturas: DEMO_CANDIDATURAS,
  v_embudo: DEMO_EMBUDO,
  v_rendimiento_cv: DEMO_CV,
};

// Cliente falso con la misma forma que el de Supabase, para que la
// aplicacion no note la diferencia y no haya que tocar su codigo.
const bd = {
  auth: {
    getSession: async () => ({ data: { session: { demo: true } } }),
    signInWithPassword: async () => ({ error: null }),
    signOut: async () => {},
  },
  from(tabla) {
    const respuesta = { data: DEMO[tabla] || [], error: null };
    const consulta = {
      select: () => consulta,
      limit: async () => respuesta,
      then: (fn) => fn(respuesta),
    };
    return consulta;
  },
  // Los cambios se quedan en memoria: al recargar vuelve al estado inicial.
  rpc: async (_fn, args) => {
    const { p_oferta_id, p_estado, p_cv } = args;
    const i = DEMO.v_bandeja.findIndex(o => o.id === p_oferta_id);
    if (i >= 0) {
      const o = DEMO.v_bandeja[i];
      DEMO.v_bandeja.splice(i, 1);
      if (p_estado !== "descartada" || true) {
        DEMO.v_candidaturas.unshift({
          oferta_id:o.id, titulo:o.titulo, empresa:o.empresa,
          provincia:o.provincia, estado:p_estado, cv_usado:p_cv,
          dias_sin_novedad:0, url:o.url,
          fecha_aplicacion: p_estado === "aplicada" ? "hoy" : null });
      }
    } else {
      const c = DEMO.v_candidaturas.find(c => c.oferta_id === p_oferta_id);
      if (c) { c.estado = p_estado; c.dias_sin_novedad = 0; }
    }
    return { error: null };
  },
};

// Aviso permanente, para que nadie confunda esto con datos reales.
addEventListener("DOMContentLoaded", () => {
  const aviso = document.createElement("div");
  aviso.textContent = "Demostración con datos inventados";
  aviso.style.cssText = "background:#16202B;color:#fff;text-align:center;" +
    "padding:.4rem .8rem;font-size:.8rem;letter-spacing:.01em";
  document.body.prepend(aviso);
});
