export const RUTA_API = "/api/v1";
const RUTA_CSRF = "/seguridad/csrf";
const METODOS_MUTABLES = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let tokenCsrf = null;
let solicitudTokenCsrf = null;

export class ErrorApi extends Error {
  constructor({ mensaje, codigo = "ERROR_DESCONOCIDO", estado = 0, campos = {}, reintentarEn = null }) {
    super(mensaje);
    this.name = "ErrorApi";
    this.codigo = codigo;
    this.estado = estado;
    this.campos = campos;
    this.reintentarEn = reintentarEn;
  }
}

function leerSegundosReintento(respuesta, cuerpo) {
  const cabecera = respuesta.headers?.get?.("retry-after");
  const valor = cabecera ?? cuerpo?.reintentar_en;
  const segundos = Number.parseInt(valor, 10);
  return Number.isFinite(segundos) && segundos >= 0 ? segundos : null;
}

async function leerCuerpo(respuesta) {
  const tipo = respuesta.headers?.get?.("content-type") ?? "";
  if (tipo.includes("application/json")) {
    return respuesta.json();
  }

  const texto = await respuesta.text();
  return texto ? { mensaje: texto } : {};
}

function tokenCsrfValido(valor) {
  return typeof valor === "string" && valor.length > 0 && valor.length <= 4096;
}

function leerTokenRotado(respuesta) {
  const valor = respuesta.headers?.get?.("x-csrf-token");
  return tokenCsrfValido(valor) ? valor : null;
}

function crearOpciones(metodo, cabeceras, cuerpo, senal) {
  return {
    method: metodo,
    credentials: "same-origin",
    headers: cabeceras,
    body: cuerpo,
    signal: senal,
    redirect: "error",
    cache: "no-store",
  };
}

function errorConexion(error) {
  if (error?.name === "AbortError") return error;
  return new ErrorApi({ mensaje: "No fue posible comunicarse con el servicio. Inténtalo de nuevo." });
}

async function obtenerTokenCsrf(implementacionFetch, senal) {
  if (tokenCsrf) return tokenCsrf;
  if (solicitudTokenCsrf) return solicitudTokenCsrf;

  solicitudTokenCsrf = (async () => {
    let respuesta;
    try {
      respuesta = await implementacionFetch(
        `${RUTA_API}${RUTA_CSRF}`,
        crearOpciones("GET", { Accept: "application/json" }, undefined, senal),
      );
    } catch (error) {
      throw errorConexion(error);
    }

    let cuerpo;
    try {
      cuerpo = await leerCuerpo(respuesta);
    } catch {
      cuerpo = {};
    }

    if (!respuesta.ok) {
      throw new ErrorApi({
        mensaje: cuerpo.mensaje ?? "No fue posible preparar la solicitud segura.",
        codigo: cuerpo.codigo,
        estado: respuesta.status,
        reintentarEn: leerSegundosReintento(respuesta, cuerpo),
      });
    }

    const recibido = leerTokenRotado(respuesta) ?? cuerpo.token_csrf;
    if (!tokenCsrfValido(recibido)) {
      throw new ErrorApi({
        mensaje: "No fue posible preparar la solicitud segura.",
        codigo: "CSRF_NO_DISPONIBLE",
        estado: respuesta.status,
      });
    }
    tokenCsrf = recibido;
    return tokenCsrf;
  })();

  try {
    return await solicitudTokenCsrf;
  } finally {
    solicitudTokenCsrf = null;
  }
}

export async function solicitarApi(ruta, opciones = {}, implementacionFetch = globalThis.fetch) {
  if (typeof implementacionFetch !== "function") {
    throw new ErrorApi({ mensaje: "No se puede conectar con el servicio." });
  }

  const { metodo = "GET", datos, senal } = opciones;
  const metodoNormalizado = metodo.toUpperCase();
  const cabeceras = { Accept: "application/json" };
  if (datos !== undefined) cabeceras["Content-Type"] = "application/json";
  if (METODOS_MUTABLES.has(metodoNormalizado)) {
    cabeceras["X-CSRF-Token"] = await obtenerTokenCsrf(implementacionFetch, senal);
  }

  let respuesta;
  try {
    respuesta = await implementacionFetch(
      `${RUTA_API}${ruta}`,
      crearOpciones(
        metodoNormalizado,
        cabeceras,
        datos === undefined ? undefined : JSON.stringify(datos),
        senal,
      ),
    );
  } catch (error) {
    throw errorConexion(error);
  }

  let cuerpo;
  try {
    cuerpo = await leerCuerpo(respuesta);
  } catch {
    cuerpo = {};
  }

  const tokenRotado = leerTokenRotado(respuesta);
  if (tokenRotado) tokenCsrf = tokenRotado;

  if (!respuesta.ok) {
    if (!tokenRotado && respuesta.status === 403 && cuerpo.codigo?.startsWith?.("CSRF_")) {
      tokenCsrf = null;
    }
    throw new ErrorApi({
      mensaje: cuerpo.mensaje ?? "No fue posible completar la solicitud.",
      codigo: cuerpo.codigo,
      estado: respuesta.status,
      campos: cuerpo.campos,
      reintentarEn: leerSegundosReintento(respuesta, cuerpo),
    });
  }

  return cuerpo;
}
