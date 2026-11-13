import assert from "node:assert/strict";
import { join } from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const directorioFrontend = fileURLToPath(new URL("./", import.meta.url));
let numeroImportacion = 0;

class ElementoFalso {
  constructor(id = "", propiedades = {}) {
    this.id = id;
    this.name = propiedades.name ?? id;
    this.type = propiedades.type ?? "div";
    this.value = propiedades.value ?? "";
    this.checked = propiedades.checked ?? false;
    this.disabled = propiedades.disabled ?? false;
    this.hidden = propiedades.hidden ?? false;
    this.textContent = propiedades.textContent ?? "";
    this.className = propiedades.className ?? "";
    this.dataset = propiedades.dataset ?? {};
    this.children = [];
    this.enfocado = false;
    this.reinicios = 0;
    this.atributos = new Map();
    this.escuchas = new Map();
    this.controles = [];
    this.consultas = new Map();
  }

  addEventListener(tipo, escucha) {
    const escuchas = this.escuchas.get(tipo) ?? [];
    escuchas.push(escucha);
    this.escuchas.set(tipo, escuchas);
  }

  async emitir(tipo) {
    const evento = {
      defaultPrevented: false,
      preventDefault() { this.defaultPrevented = true; },
    };
    const resultados = (this.escuchas.get(tipo) ?? []).map((escucha) => escucha(evento));
    await Promise.all(resultados);
    return evento;
  }

  setAttribute(nombre, valor) {
    this.atributos.set(nombre, String(valor));
  }

  getAttribute(nombre) {
    return this.atributos.get(nombre) ?? null;
  }

  querySelector(selector) {
    if (this.consultas.has(selector)) return this.consultas.get(selector);
    if (selector === '[aria-invalid="true"]') {
      return this.controles.find((control) => control.getAttribute("aria-invalid") === "true") ?? null;
    }
    return null;
  }

  querySelectorAll(selector) {
    if (selector === "button, input") return this.controles;
    if (selector === "[data-alternar-contrasena]") {
      return this.controles.filter((control) => control.dataset.alternarContrasena);
    }
    if (selector === "[aria-invalid]") {
      return this.controles.filter((control) => control.getAttribute("aria-invalid") !== null);
    }
    if (selector === ".error-campo") return [];
    return [];
  }

  append(elemento) {
    this.children.push(elemento);
  }

  replaceChildren(...elementos) {
    this.children = [...elementos];
  }

  focus() {
    this.enfocado = true;
  }

  reset() {
    this.reinicios += 1;
    this.controles.forEach((control) => {
      if (control.type === "checkbox") control.checked = false;
      else if (control.type !== "submit" && control.type !== "button") control.value = "";
    });
  }
}

class FormDataFalso {
  constructor(formulario) {
    this.formulario = formulario;
  }

  get(nombre) {
    const campo = this.formulario.elements.namedItem(nombre);
    if (!campo) return null;
    if (campo.type === "checkbox") return campo.checked ? (campo.value || "on") : null;
    return campo.value;
  }
}

function reemplazarGlobal(nombre, valor) {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, nombre);
  Object.defineProperty(globalThis, nombre, { configurable: true, writable: true, value: valor });
  return () => {
    if (descriptor) Object.defineProperty(globalThis, nombre, descriptor);
    else delete globalThis[nombre];
  };
}

function crearEntorno(url = "https://servicio.test/") {
  const elementos = new Map();
  const asignaciones = [];
  const navegaciones = [];
  const historial = [];
  let impresiones = 0;

  const documento = {
    body: new ElementoFalso("body"),
    getElementById: (id) => elementos.get(id) ?? null,
    createElement: () => new ElementoFalso(),
  };
  const ventana = {
    location: {
      href: url,
      assign: (destino) => navegaciones.push(destino),
    },
    history: {
      replaceState: (_estado, _titulo, destino) => historial.push(destino),
    },
    setInterval: () => 1,
    clearInterval: () => {},
    print: () => { impresiones += 1; },
  };

  asignaciones.push(reemplazarGlobal("document", documento));
  asignaciones.push(reemplazarGlobal("window", ventana));
  asignaciones.push(reemplazarGlobal("HTMLElement", ElementoFalso));
  asignaciones.push(reemplazarGlobal("FormData", FormDataFalso));
  asignaciones.push(reemplazarGlobal("navigator", { credentials: {} }));
  asignaciones.push(reemplazarGlobal("PublicKeyCredential", function CredencialPublica() {}));

  return {
    documento,
    ventana,
    navegaciones,
    historial,
    elementos,
    registrar(elemento) {
      elementos.set(elemento.id, elemento);
      return elemento;
    },
    crearElemento(id, propiedades) {
      const elemento = new ElementoFalso(id, propiedades);
      elementos.set(id, elemento);
      return elemento;
    },
    crearCampo(nombre, propiedades = {}) {
      const campo = new ElementoFalso(nombre, { ...propiedades, name: nombre });
      const error = new ElementoFalso(`error-${nombre}`);
      campo.setAttribute("aria-describedby", `error-${nombre}`);
      campo.setAttribute("aria-invalid", "false");
      elementos.set(nombre, campo);
      elementos.set(error.id, error);
      return campo;
    },
    crearFormulario(id, campos, textoBoton = "Enviar") {
      const formulario = new ElementoFalso(id, { type: "form" });
      const boton = new ElementoFalso(`${id}-enviar`, { type: "submit", textContent: textoBoton });
      const porNombre = Object.fromEntries(campos.map((campo) => [campo.name, campo]));
      formulario.elements = {
        ...porNombre,
        namedItem: (nombre) => porNombre[nombre] ?? null,
      };
      formulario.controles = [...campos, boton];
      formulario.consultas.set('button[type="submit"]', boton);
      elementos.set(id, formulario);
      return { formulario, boton };
    },
    obtenerImpresiones: () => impresiones,
    restaurar() {
      asignaciones.reverse().forEach((restaurar) => restaurar());
    },
  };
}

function respuestaJson(cuerpo, estado = 200, cabeceras = {}) {
  return new Response(JSON.stringify(cuerpo), {
    status: estado,
    headers: { "content-type": "application/json", ...cabeceras },
  });
}

function instalarFetch(entorno, implementacion) {
  const restaurar = reemplazarGlobal("fetch", (ruta, opciones) => {
    if (ruta === "/api/v1/seguridad/csrf") {
      return Promise.resolve(respuestaJson({ token_csrf: "csrf-pruebas-conductuales" }));
    }
    return implementacion(ruta, opciones);
  });
  const restaurarEntorno = entorno.restaurar.bind(entorno);
  entorno.restaurar = () => {
    restaurar();
    restaurarEntorno();
  };
}

async function importarPagina(pagina) {
  numeroImportacion += 1;
  const ruta = join(directorioFrontend, pagina, `${pagina}.js`);
  return import(`${pathToFileURL(ruta).href}?prueba=${numeroImportacion}`);
}

async function completarTareas() {
  await new Promise((resolver) => setImmediate(resolver));
}

function camposRegistro(entorno, contrasena = "  contraseña exacta  ") {
  return [
    entorno.crearCampo("nombre_completo", { value: " María-José O'Connor " }),
    entorno.crearCampo("correo", { value: "persona@ejemplo.test", type: "email" }),
    entorno.crearCampo("contrasena", { value: contrasena, type: "password" }),
    entorno.crearCampo("confirmacion_contrasena", { value: contrasena, type: "password" }),
    entorno.crearCampo("acepta_terminos", { checked: true, type: "checkbox" }),
    entorno.crearCampo("acepta_privacidad", { checked: true, type: "checkbox" }),
  ];
}

function crearCredencialRegistro() {
  return {
    id: "credencial-registro",
    rawId: Uint8Array.from([1]).buffer,
    type: "public-key",
    response: {
      attestationObject: Uint8Array.from([2]).buffer,
      clientDataJSON: Uint8Array.from([3]).buffer,
      getTransports: () => ["internal"],
    },
    getClientExtensionResults: () => ({}),
  };
}

function crearCredencialAutenticacion() {
  return {
    id: "credencial-acceso",
    rawId: Uint8Array.from([1]).buffer,
    type: "public-key",
    response: {
      authenticatorData: Uint8Array.from([2]).buffer,
      clientDataJSON: Uint8Array.from([3]).buffer,
      signature: Uint8Array.from([4]).buffer,
      userHandle: null,
    },
    getClientExtensionResults: () => ({}),
  };
}

test("los documentos legales ofrecen impresión funcional y controlada por cada JS", async () => {
  for (const pagina of ["terminos", "privacidad"]) {
    const entorno = crearEntorno();
    try {
      const boton = entorno.crearElemento("boton-imprimir", { type: "button" });
      const modulo = await importarPagina(pagina);
      assert.equal(modulo.activarImpresion({ getElementById: () => null }, entorno.ventana), false);
      await boton.emitir("click");
      assert.equal(entorno.obtenerImpresiones(), 1);
    } finally {
      entorno.restaurar();
    }
  }
});

test("registro positivo conserva la contraseña exacta y bloquea el envío duplicado", async () => {
  const entorno = crearEntorno();
  const campos = camposRegistro(entorno);
  const { formulario, boton } = entorno.crearFormulario("formulario-registro", campos, "Crear cuenta");
  const mensaje = entorno.crearElemento("mensaje-registro", { hidden: true });
  let resolverSolicitud;
  const llamadas = [];
  instalarFetch(entorno, (ruta, opciones) => {
    llamadas.push({ ruta, opciones });
    return new Promise((resolver) => { resolverSolicitud = resolver; });
  });

  try {
    await importarPagina("registro");
    const primerEnvio = formulario.emitir("submit");
    const segundoEnvio = formulario.emitir("submit");
    await completarTareas();
    assert.equal(llamadas.length, 1);
    assert.equal(formulario.getAttribute("aria-busy"), "true");
    assert.equal(boton.disabled, true);
    resolverSolicitud(respuestaJson({ codigo: "REGISTRO_RECIBIDO" }));
    await Promise.all([primerEnvio, segundoEnvio]);

    const cuerpo = JSON.parse(llamadas[0].opciones.body);
    assert.equal(cuerpo.contrasena, "  contraseña exacta  ");
    assert.equal(cuerpo.confirmacion_contrasena, "  contraseña exacta  ");
    assert.equal(cuerpo.nombre_completo, "María-José O'Connor");
    assert.deepEqual(cuerpo.aceptaciones, ["terminos-demo-1.0", "privacidad-demo-1.0"]);
    assert.equal(formulario.reinicios, 1);
    assert.match(mensaje.textContent, /Si la solicitud puede procesarse/u);
  } finally {
    entorno.restaurar();
  }
});

test("registro rechaza campos inválidos y presenta fallos de red sin filtrar detalles", async () => {
  const entornoInvalido = crearEntorno();
  const camposInvalidos = camposRegistro(entornoInvalido, "corta");
  camposInvalidos[0].value = "   ";
  camposInvalidos[1].value = "correo-invalido";
  camposInvalidos[3].value = "diferente";
  camposInvalidos[4].checked = false;
  const { formulario: formularioInvalido } = entornoInvalido.crearFormulario("formulario-registro", camposInvalidos);
  const mensajeInvalido = entornoInvalido.crearElemento("mensaje-registro", { hidden: true });
  let llamadas = 0;
  instalarFetch(entornoInvalido, async () => { llamadas += 1; return respuestaJson({}); });
  try {
    await importarPagina("registro");
    await formularioInvalido.emitir("submit");
    assert.equal(llamadas, 0);
    assert.equal(mensajeInvalido.getAttribute("role"), "alert");
    assert.match(mensajeInvalido.textContent, /Revisa los campos/u);
    assert.equal(camposInvalidos[0].getAttribute("aria-invalid"), "true");
  } finally {
    entornoInvalido.restaurar();
  }

  const entornoRed = crearEntorno();
  const camposValidos = camposRegistro(entornoRed);
  const { formulario: formularioRed } = entornoRed.crearFormulario("formulario-registro", camposValidos);
  const mensajeRed = entornoRed.crearElemento("mensaje-registro", { hidden: true });
  instalarFetch(entornoRed, async () => { throw new TypeError("servidor privado"); });
  try {
    await importarPagina("registro");
    await formularioRed.emitir("submit");
    assert.match(mensajeRed.textContent, /No se pudo completar/u);
    assert.doesNotMatch(mensajeRed.textContent, /servidor privado/u);
    assert.equal(formularioRed.getAttribute("aria-busy"), "false");
  } finally {
    entornoRed.restaurar();
  }
});

async function ejecutarInicioSesion(respuesta) {
  const entorno = crearEntorno();
  const correo = entorno.crearCampo("correo", { value: "persona@ejemplo.test", type: "email" });
  const contrasena = entorno.crearCampo("contrasena", { value: "contraseña exacta segura", type: "password" });
  const { formulario } = entorno.crearFormulario("formulario-acceso", [correo, contrasena], "Continuar");
  const mensaje = entorno.crearElemento("mensaje-acceso", { hidden: true });
  const llamadas = [];
  instalarFetch(entorno, async (ruta, opciones) => {
    llamadas.push({ ruta, opciones });
    if (respuesta instanceof Error) throw respuesta;
    return respuesta;
  });
  await importarPagina("inicio-sesion");
  await formulario.emitir("submit");
  return { entorno, formulario, mensaje, llamadas };
}

test("login dirige únicamente los estados funcionales permitidos y conserva la contraseña", async () => {
  const casos = new Map([
    ["AUTENTICADO", "../sesion/sesion.html"],
    ["VERIFICACION_CORREO_PENDIENTE", "../verificacion-correo/verificacion-correo.html"],
    ["CONFIGURACION_WEBAUTHN_REQUERIDA", "../configuracion-webauthn/configuracion-webauthn.html"],
    ["DESAFIO_WEBAUTHN_REQUERIDO", "../desafio-webauthn/desafio-webauthn.html"],
    ["CONFLICTO_SESION", "../conflicto-sesion/conflicto-sesion.html"],
  ]);
  for (const [codigo, destino] of casos) {
    const resultado = await ejecutarInicioSesion(respuestaJson({ codigo }));
    try {
      assert.deepEqual(resultado.entorno.navegaciones, [destino]);
      assert.equal(JSON.parse(resultado.llamadas[0].opciones.body).contrasena, "contraseña exacta segura");
    } finally {
      resultado.entorno.restaurar();
    }
  }
});

test("login mantiene el mismo error ante cuentas inexistentes, contraseña incorrecta y red", async () => {
  const respuestas = [
    respuestaJson({ codigo: "CUENTA_INEXISTENTE", mensaje: "interno" }, 401),
    respuestaJson({ codigo: "CONTRASENA_INCORRECTA", mensaje: "interno" }, 401),
    new TypeError("detalle de red"),
  ];
  const mensajes = [];
  for (const respuesta of respuestas) {
    const resultado = await ejecutarInicioSesion(respuesta);
    try {
      mensajes.push(resultado.mensaje.textContent);
      assert.equal(resultado.formulario.elements.contrasena.value, "");
    } finally {
      resultado.entorno.restaurar();
    }
  }
  assert.equal(new Set(mensajes).size, 1);
  assert.equal(mensajes[0], "No fue posible iniciar sesión con los datos proporcionados.");
});

function prepararVerificacion(entorno) {
  const estado = entorno.crearElemento("estado-verificacion");
  const correo = entorno.crearCampo("correo", { value: "persona@ejemplo.test", type: "email" });
  const formulario = entorno.crearFormulario("formulario-reenvio", [correo], "Solicitar enlace");
  return { estado, correo, ...formulario };
}

test("verificación consume una credencial una vez, limpia la URL y reenvía con mensaje genérico", async () => {
  const entorno = crearEntorno("https://servicio.test/verificacion.html?credencial=secreto-opaco");
  const { estado, formulario } = prepararVerificacion(entorno);
  const llamadas = [];
  instalarFetch(entorno, async (ruta, opciones) => {
    llamadas.push({ ruta, opciones });
    return respuestaJson({ codigo: ruta.endsWith("confirmar") ? "CORREO_VERIFICADO" : "REENVIO_VERIFICACION_RECIBIDO" });
  });
  try {
    await importarPagina("verificacion-correo");
    await completarTareas();
    assert.equal(JSON.parse(llamadas[0].opciones.body).credencial, "secreto-opaco");
    assert.equal(entorno.historial[0].includes("credencial"), false);
    assert.equal(estado.textContent, "Correo verificado. Ya puedes iniciar sesión.");

    await formulario.emitir("submit");
    assert.equal(llamadas[1].ruta, "/api/v1/verificaciones-correo/reenviar");
    assert.match(estado.textContent, /Si corresponde/u);
  } finally {
    entorno.restaurar();
  }
});

test("verificación controla enlace inválido, correo inválido, red y rate limit", async () => {
  const entorno = crearEntorno("https://servicio.test/verificacion.html?credencial=invalida");
  const { estado, correo, formulario, boton } = prepararVerificacion(entorno);
  let numeroLlamada = 0;
  instalarFetch(entorno, async () => {
    numeroLlamada += 1;
    if (numeroLlamada === 1) return respuestaJson({ codigo: "CREDENCIAL_VERIFICACION_INVALIDA" }, 400);
    return respuestaJson({ codigo: "LIMITE_SOLICITUDES" }, 429, { "retry-after": "30" });
  });
  try {
    await importarPagina("verificacion-correo");
    await completarTareas();
    assert.equal(estado.textContent, "El enlace no es válido. Solicita uno nuevo.");

    correo.value = "invalido";
    await formulario.emitir("submit");
    assert.equal(numeroLlamada, 1);
    assert.equal(correo.getAttribute("aria-invalid"), "true");

    correo.value = "persona@ejemplo.test";
    await formulario.emitir("submit");
    assert.equal(boton.disabled, true);
    assert.equal(boton.textContent, "Espera 30 s");
    assert.match(estado.textContent, /Espera e inténtalo nuevamente/u);
  } finally {
    entorno.restaurar();
  }

  const entornoRed = crearEntorno("https://servicio.test/verificacion.html");
  const { estado: estadoRed, formulario: formularioRed } = prepararVerificacion(entornoRed);
  instalarFetch(entornoRed, async () => { throw new TypeError("detalle privado de red"); });
  try {
    await importarPagina("verificacion-correo");
    await formularioRed.emitir("submit");
    assert.equal(estadoRed.textContent, "No se pudo procesar la solicitud. Espera e inténtalo nuevamente.");
    assert.doesNotMatch(estadoRed.textContent, /detalle privado/u);
  } finally {
    entornoRed.restaurar();
  }
});

test("alta WebAuthn completa opciones y credencial; cancelación y falta de soporte son recuperables", async () => {
  const entorno = crearEntorno();
  const boton = entorno.crearElemento("boton-configurar", { type: "button", textContent: "Configurar passkey" });
  entorno.crearElemento("mensaje-configuracion", { hidden: true });
  const llamadas = [];
  globalThis.navigator.credentials.create = async () => crearCredencialRegistro();
  instalarFetch(entorno, async (ruta, opciones) => {
    llamadas.push({ ruta, opciones });
    if (ruta.endsWith("opciones")) {
      return respuestaJson({ opciones: { challenge: "AQID", user: { id: "BAUG" } } });
    }
    return respuestaJson({ codigo: "WEBAUTHN_CONFIGURADO" });
  });
  try {
    await importarPagina("configuracion-webauthn");
    await boton.emitir("click");
    assert.equal(llamadas.length, 2);
    assert.equal(JSON.parse(llamadas[1].opciones.body).credencial.id, "credencial-registro");
    assert.deepEqual(entorno.navegaciones, ["../codigos-respaldo/codigos-respaldo.html"]);
  } finally {
    entorno.restaurar();
  }

  const entornoCancelado = crearEntorno();
  const botonCancelado = entornoCancelado.crearElemento("boton-configurar", { type: "button", textContent: "Configurar passkey" });
  const mensajeCancelado = entornoCancelado.crearElemento("mensaje-configuracion", { hidden: true });
  globalThis.navigator.credentials.create = async () => {
    const error = new Error("cancelada");
    error.name = "NotAllowedError";
    throw error;
  };
  instalarFetch(entornoCancelado, async () => respuestaJson({ opciones: { challenge: "AQID", user: { id: "BAUG" } } }));
  try {
    await importarPagina("configuracion-webauthn");
    await botonCancelado.emitir("click");
    assert.match(mensajeCancelado.textContent, /cancelada o excedió/u);
    assert.equal(botonCancelado.disabled, false);
  } finally {
    entornoCancelado.restaurar();
  }

  const entornoSinSoporte = crearEntorno();
  const botonSinSoporte = entornoSinSoporte.crearElemento("boton-configurar", { type: "button" });
  const mensajeSinSoporte = entornoSinSoporte.crearElemento("mensaje-configuracion", { hidden: true });
  delete globalThis.PublicKeyCredential;
  try {
    await importarPagina("configuracion-webauthn");
    assert.equal(botonSinSoporte.disabled, true);
    assert.match(mensajeSinSoporte.textContent, /no permite configurar/u);
  } finally {
    entornoSinSoporte.restaurar();
  }
});

function prepararCodigos(entorno) {
  const lista = entorno.crearElemento("lista-codigos", { hidden: true });
  const estado = entorno.crearElemento("estado-carga");
  const casilla = entorno.crearCampo("codigos_guardados", { type: "checkbox" });
  const { formulario } = entorno.crearFormulario("formulario-confirmacion", [casilla], "Confirmar y continuar");
  formulario.hidden = true;
  const mensaje = entorno.crearElemento("mensaje-codigos", { hidden: true });
  return { lista, estado, casilla, formulario, mensaje };
}

test("códigos de respaldo se presentan, exigen confirmación y se eliminan de la vista al continuar", async () => {
  const entorno = crearEntorno();
  const { lista, casilla, formulario } = prepararCodigos(entorno);
  const llamadas = [];
  instalarFetch(entorno, async (ruta, opciones) => {
    llamadas.push({ ruta, opciones });
    if (ruta.endsWith("pendientes")) return respuestaJson({ codigos: ["uno", "dos"] });
    return respuestaJson({ codigo: "AUTENTICADO" });
  });
  try {
    await importarPagina("codigos-respaldo");
    await completarTareas();
    assert.deepEqual(lista.children.map((elemento) => elemento.textContent), ["uno", "dos"]);
    assert.equal(formulario.hidden, false);

    await formulario.emitir("submit");
    assert.equal(llamadas.length, 1, "No envía sin confirmación");
    assert.equal(casilla.getAttribute("aria-invalid"), "true");

    casilla.checked = true;
    await formulario.emitir("submit");
    assert.equal(llamadas.length, 2);
    assert.equal(lista.children.length, 0);
    assert.deepEqual(entorno.navegaciones, ["../sesion/sesion.html"]);
  } finally {
    entorno.restaurar();
  }
});

test("códigos de respaldo informan respuestas vacías y fallos de confirmación", async () => {
  const entornoVacio = crearEntorno();
  const { estado, mensaje } = prepararCodigos(entornoVacio);
  instalarFetch(entornoVacio, async () => respuestaJson({ codigos: [] }));
  try {
    await importarPagina("codigos-respaldo");
    await completarTareas();
    assert.equal(estado.hidden, true);
    assert.match(mensaje.textContent, /No fue posible mostrar/u);
  } finally {
    entornoVacio.restaurar();
  }

  const entornoError = crearEntorno();
  const preparados = prepararCodigos(entornoError);
  let llamada = 0;
  instalarFetch(entornoError, async () => {
    llamada += 1;
    if (llamada === 1) return respuestaJson({ codigos: ["uno"] });
    throw new TypeError("red");
  });
  try {
    await importarPagina("codigos-respaldo");
    await completarTareas();
    preparados.casilla.checked = true;
    await preparados.formulario.emitir("submit");
    assert.match(preparados.mensaje.textContent, /No se pudo confirmar/u);
    assert.equal(preparados.lista.children.length, 1);
  } finally {
    entornoError.restaurar();
  }
});

function prepararDesafio(entorno) {
  const boton = entorno.crearElemento("boton-passkey", { type: "button", textContent: "Usar passkey" });
  const codigo = entorno.crearCampo("codigo_respaldo");
  const { formulario } = entorno.crearFormulario("formulario-respaldo", [codigo], "Verificar código");
  const mensaje = entorno.crearElemento("mensaje-desafio", { hidden: true });
  const alternativa = entorno.crearElemento("alternativa-respaldo");
  return { boton, codigo, formulario, mensaje, alternativa };
}

test("desafío WebAuthn completa una aserción y oculta respaldo durante conflicto", async () => {
  const entorno = crearEntorno("https://servicio.test/desafio.html?conflicto=1");
  const { boton, alternativa } = prepararDesafio(entorno);
  const llamadas = [];
  globalThis.navigator.credentials.get = async () => crearCredencialAutenticacion();
  instalarFetch(entorno, async (ruta, opciones) => {
    llamadas.push({ ruta, opciones });
    if (ruta.endsWith("opciones")) {
      return respuestaJson({ opciones: { challenge: "AQID", allowCredentials: [{ id: "BAUG", type: "public-key" }] } });
    }
    return respuestaJson({ codigo: "CONFLICTO_SESION_RESUELTO" });
  });
  try {
    await importarPagina("desafio-webauthn");
    assert.equal(alternativa.hidden, true);
    await boton.emitir("click");
    assert.equal(JSON.parse(llamadas[1].opciones.body).credencial.id, "credencial-acceso");
    assert.deepEqual(entorno.navegaciones, ["../sesion/sesion.html"]);
  } finally {
    entorno.restaurar();
  }
});

test("desafío controla cancelación, código de respaldo exacto y rate limit", async () => {
  const entornoCancelado = crearEntorno();
  const { boton, mensaje } = prepararDesafio(entornoCancelado);
  globalThis.navigator.credentials.get = async () => {
    const error = new Error("cancelada");
    error.name = "NotAllowedError";
    throw error;
  };
  instalarFetch(entornoCancelado, async () => respuestaJson({ opciones: { challenge: "AQID" } }));
  try {
    await importarPagina("desafio-webauthn");
    await boton.emitir("click");
    assert.match(mensaje.textContent, /cancelada o venció/u);
    assert.equal(boton.disabled, false);
  } finally {
    entornoCancelado.restaurar();
  }

  const entornoRespaldo = crearEntorno();
  const preparados = prepararDesafio(entornoRespaldo);
  preparados.codigo.value = "  codigo exacto  ";
  let cuerpoEnviado;
  instalarFetch(entornoRespaldo, async (_ruta, opciones) => {
    cuerpoEnviado = JSON.parse(opciones.body);
    return respuestaJson({ codigo: "AUTENTICADO" });
  });
  try {
    await importarPagina("desafio-webauthn");
    await preparados.formulario.emitir("submit");
    assert.equal(cuerpoEnviado.codigo_respaldo, "  codigo exacto  ");
    assert.equal(preparados.codigo.value, "");
  } finally {
    entornoRespaldo.restaurar();
  }

  const entornoLimite = crearEntorno();
  const limitados = prepararDesafio(entornoLimite);
  limitados.codigo.value = "codigo";
  instalarFetch(entornoLimite, async () => respuestaJson({ codigo: "LIMITE_SOLICITUDES" }, 429));
  try {
    await importarPagina("desafio-webauthn");
    await limitados.formulario.emitir("submit");
    assert.match(limitados.mensaje.textContent, /límite de intentos/u);
  } finally {
    entornoLimite.restaurar();
  }
});

test("conflicto presenta datos como texto y controla su vencimiento", async () => {
  const entorno = crearEntorno();
  const detalle = entorno.crearElemento("detalle-conflicto", { hidden: true });
  entorno.crearElemento("mensaje-conflicto", { hidden: true });
  const inicio = entorno.crearElemento("inicio-anterior");
  const dispositivo = entorno.crearElemento("dispositivo-anterior");
  instalarFetch(entorno, async () => respuestaJson({
    inicio_aproximado: "13:00",
    dispositivo: "<img src=x onerror=alert(1)>",
  }));
  try {
    await importarPagina("conflicto-sesion");
    await completarTareas();
    assert.equal(detalle.hidden, false);
    assert.equal(inicio.textContent, "13:00");
    assert.equal(dispositivo.textContent, "<img src=x onerror=alert(1)>");
  } finally {
    entorno.restaurar();
  }

  const entornoVencido = crearEntorno();
  entornoVencido.crearElemento("detalle-conflicto", { hidden: true });
  const mensajeVencido = entornoVencido.crearElemento("mensaje-conflicto", { hidden: true });
  entornoVencido.crearElemento("inicio-anterior");
  entornoVencido.crearElemento("dispositivo-anterior");
  instalarFetch(entornoVencido, async () => { throw new TypeError("red"); });
  try {
    await importarPagina("conflicto-sesion");
    await completarTareas();
    assert.match(mensajeVencido.textContent, /ya no está disponible o venció/u);
  } finally {
    entornoVencido.restaurar();
  }
});

function prepararSesion(entorno) {
  const mensaje = entorno.crearElemento("mensaje-sesion");
  const detalle = entorno.crearElemento("detalle-sesion", { hidden: true });
  const reingreso = entorno.crearElemento("enlace-reingreso", { hidden: true });
  const cerrar = entorno.crearElemento("boton-cerrar", { type: "button", textContent: "Cerrar sesión" });
  const correo = entorno.crearElemento("correo-cuenta");
  const vencimiento = entorno.crearElemento("vencimiento-absoluto");
  return { mensaje, detalle, reingreso, cerrar, correo, vencimiento };
}

test("sesión carga datos y el cierre positivo oculta el área autenticada", async () => {
  const entorno = crearEntorno();
  const elementos = prepararSesion(entorno);
  const llamadas = [];
  instalarFetch(entorno, async (ruta) => {
    llamadas.push(ruta);
    if (ruta.endsWith("actual")) {
      return respuestaJson({ correo: "persona@ejemplo.test", vencimiento_absoluto: "21:00" });
    }
    return respuestaJson({ codigo: "SESION_CERRADA" });
  });
  try {
    await importarPagina("sesion");
    await completarTareas();
    assert.equal(elementos.correo.textContent, "persona@ejemplo.test");
    assert.equal(elementos.detalle.hidden, false);
    await elementos.cerrar.emitir("click");
    assert.deepEqual(llamadas, ["/api/v1/sesiones/actual", "/api/v1/sesiones/cerrar"]);
    assert.equal(elementos.detalle.hidden, true);
    assert.equal(elementos.reingreso.hidden, false);
    assert.match(elementos.mensaje.textContent, /cerró correctamente/u);
  } finally {
    entorno.restaurar();
  }
});

test("sesión diferencia expiración, inactividad y revocación sin revelar excepciones", async () => {
  const casos = new Map([
    ["SESION_EXPIRADA", "límite de 8 horas"],
    ["SESION_INACTIVA", "30 minutos de inactividad"],
    ["SESION_REVOCADA", "fue revocada"],
  ]);
  for (const [codigo, texto] of casos) {
    const entorno = crearEntorno();
    const elementos = prepararSesion(entorno);
    instalarFetch(entorno, async () => respuestaJson({ codigo }, 401));
    try {
      await importarPagina("sesion");
      await completarTareas();
      assert.match(elementos.mensaje.textContent, new RegExp(texto, "u"));
      assert.equal(elementos.reingreso.hidden, false);
    } finally {
      entorno.restaurar();
    }
  }
});

test("fallo al cerrar sesión conserva una advertencia y permite reintentar", async () => {
  const entorno = crearEntorno();
  const elementos = prepararSesion(entorno);
  let llamada = 0;
  instalarFetch(entorno, async () => {
    llamada += 1;
    if (llamada === 1) return respuestaJson({ correo: "persona@ejemplo.test", vencimiento_absoluto: "21:00" });
    throw new TypeError("red");
  });
  try {
    await importarPagina("sesion");
    await completarTareas();
    await elementos.cerrar.emitir("click");
    assert.match(elementos.mensaje.textContent, /No se pudo confirmar el cierre/u);
    assert.equal(elementos.cerrar.disabled, false);
    assert.equal(elementos.detalle.hidden, false);
  } finally {
    entorno.restaurar();
  }
});

test("login bloquea una segunda activación mientras la solicitud está pendiente", async () => {
  const entorno = crearEntorno();
  const correo = entorno.crearCampo("correo", { value: "persona@ejemplo.test", type: "email" });
  const contrasena = entorno.crearCampo("contrasena", { value: "contraseña suficientemente larga", type: "password" });
  const { formulario } = entorno.crearFormulario("formulario-acceso", [correo, contrasena], "Continuar");
  entorno.crearElemento("mensaje-acceso", { hidden: true });
  let resolverSolicitud;
  let solicitudes = 0;
  instalarFetch(entorno, () => {
    solicitudes += 1;
    return new Promise((resolver) => { resolverSolicitud = resolver; });
  });
  try {
    await importarPagina("inicio-sesion");
    const primera = formulario.emitir("submit");
    const segunda = formulario.emitir("submit");
    await completarTareas();
    assert.equal(solicitudes, 1);
    resolverSolicitud(respuestaJson({ codigo: "AUTENTICADO" }));
    await Promise.all([primera, segunda]);
    assert.equal(solicitudes, 1);
  } finally {
    entorno.restaurar();
  }
});

test("reenvío de verificación bloquea una segunda activación concurrente", async () => {
  const entorno = crearEntorno("https://servicio.test/verificacion.html");
  const { formulario } = prepararVerificacion(entorno);
  let resolverSolicitud;
  let solicitudes = 0;
  instalarFetch(entorno, () => {
    solicitudes += 1;
    return new Promise((resolver) => { resolverSolicitud = resolver; });
  });
  try {
    await importarPagina("verificacion-correo");
    const primera = formulario.emitir("submit");
    const segunda = formulario.emitir("submit");
    await completarTareas();
    assert.equal(solicitudes, 1);
    resolverSolicitud(respuestaJson({ codigo: "REENVIO_VERIFICACION_RECIBIDO" }));
    await Promise.all([primera, segunda]);
    assert.equal(solicitudes, 1);
  } finally {
    entorno.restaurar();
  }
});

test("confirmación de códigos de respaldo bloquea una segunda activación concurrente", async () => {
  const entorno = crearEntorno();
  const { casilla, formulario } = prepararCodigos(entorno);
  let resolverConfirmacion;
  const solicitudes = [];
  instalarFetch(entorno, (ruta) => {
    solicitudes.push(ruta);
    if (ruta.endsWith("pendientes")) return Promise.resolve(respuestaJson({ codigos: ["uno"] }));
    return new Promise((resolver) => { resolverConfirmacion = resolver; });
  });
  try {
    await importarPagina("codigos-respaldo");
    await completarTareas();
    casilla.checked = true;
    const primera = formulario.emitir("submit");
    const segunda = formulario.emitir("submit");
    await completarTareas();
    assert.deepEqual(solicitudes, [
      "/api/v1/codigos-respaldo/pendientes",
      "/api/v1/codigos-respaldo/confirmar",
    ]);
    resolverConfirmacion(respuestaJson({ codigo: "AUTENTICADO" }));
    await Promise.all([primera, segunda]);
    assert.equal(solicitudes.filter((ruta) => ruta.endsWith("confirmar")).length, 1);
  } finally {
    entorno.restaurar();
  }
});

test("alta WebAuthn bloquea una segunda activación durante el desafío", async () => {
  const entorno = crearEntorno();
  const boton = entorno.crearElemento("boton-configurar", { type: "button", textContent: "Configurar passkey" });
  entorno.crearElemento("mensaje-configuracion", { hidden: true });
  globalThis.navigator.credentials.create = async () => crearCredencialRegistro();
  let resolverOpciones;
  const solicitudes = [];
  instalarFetch(entorno, (ruta) => {
    solicitudes.push(ruta);
    if (ruta.endsWith("opciones")) {
      return new Promise((resolver) => { resolverOpciones = resolver; });
    }
    return Promise.resolve(respuestaJson({ codigo: "WEBAUTHN_CONFIGURADO" }));
  });
  try {
    await importarPagina("configuracion-webauthn");
    const primera = boton.emitir("click");
    const segunda = boton.emitir("click");
    await completarTareas();
    assert.equal(solicitudes.length, 1);
    resolverOpciones(respuestaJson({ opciones: { challenge: "AQID", user: { id: "BAUG" } } }));
    await Promise.all([primera, segunda]);
    assert.deepEqual(solicitudes, [
      "/api/v1/webauthn/registro/opciones",
      "/api/v1/webauthn/registro/completar",
    ]);
  } finally {
    entorno.restaurar();
  }
});

test("desafío passkey bloquea una segunda activación durante la autenticación", async () => {
  const entorno = crearEntorno();
  const { boton } = prepararDesafio(entorno);
  globalThis.navigator.credentials.get = async () => crearCredencialAutenticacion();
  let resolverOpciones;
  const solicitudes = [];
  instalarFetch(entorno, (ruta) => {
    solicitudes.push(ruta);
    if (ruta.endsWith("opciones")) {
      return new Promise((resolver) => { resolverOpciones = resolver; });
    }
    return Promise.resolve(respuestaJson({ codigo: "AUTENTICADO" }));
  });
  try {
    await importarPagina("desafio-webauthn");
    const primera = boton.emitir("click");
    const segunda = boton.emitir("click");
    await completarTareas();
    assert.equal(solicitudes.length, 1);
    resolverOpciones(respuestaJson({ opciones: { challenge: "AQID" } }));
    await Promise.all([primera, segunda]);
    assert.deepEqual(solicitudes, [
      "/api/v1/webauthn/autenticacion/opciones",
      "/api/v1/webauthn/autenticacion/completar",
    ]);
  } finally {
    entorno.restaurar();
  }
});

test("desafío con código de respaldo bloquea una segunda activación concurrente", async () => {
  const entorno = crearEntorno();
  const { codigo, formulario } = prepararDesafio(entorno);
  codigo.value = "codigo-unico";
  let resolverSolicitud;
  let solicitudes = 0;
  instalarFetch(entorno, () => {
    solicitudes += 1;
    return new Promise((resolver) => { resolverSolicitud = resolver; });
  });
  try {
    await importarPagina("desafio-webauthn");
    const primera = formulario.emitir("submit");
    const segunda = formulario.emitir("submit");
    await completarTareas();
    assert.equal(solicitudes, 1);
    resolverSolicitud(respuestaJson({ codigo: "AUTENTICADO" }));
    await Promise.all([primera, segunda]);
    assert.equal(solicitudes, 1);
  } finally {
    entorno.restaurar();
  }
});

test("cierre de sesión bloquea una segunda activación mientras revoca la sesión", async () => {
  const entorno = crearEntorno();
  const { cerrar } = prepararSesion(entorno);
  let resolverCierre;
  const solicitudes = [];
  instalarFetch(entorno, (ruta) => {
    solicitudes.push(ruta);
    if (ruta.endsWith("actual")) {
      return Promise.resolve(respuestaJson({ correo: "persona@ejemplo.test", vencimiento_absoluto: "21:00" }));
    }
    return new Promise((resolver) => { resolverCierre = resolver; });
  });
  try {
    await importarPagina("sesion");
    await completarTareas();
    const primera = cerrar.emitir("click");
    const segunda = cerrar.emitir("click");
    await completarTareas();
    assert.deepEqual(solicitudes, ["/api/v1/sesiones/actual", "/api/v1/sesiones/cerrar"]);
    resolverCierre(respuestaJson({ codigo: "SESION_CERRADA" }));
    await Promise.all([primera, segunda]);
    assert.equal(solicitudes.filter((ruta) => ruta.endsWith("cerrar")).length, 1);
  } finally {
    entorno.restaurar();
  }
});

async function comprobarEstadoVerificacion(codigo, mensajeEsperado) {
  const entorno = crearEntorno("https://servicio.test/verificacion.html?credencial=opaca");
  const { estado } = prepararVerificacion(entorno);
  instalarFetch(entorno, async () => respuestaJson({ codigo }, 400));
  try {
    await importarPagina("verificacion-correo");
    await completarTareas();
    assert.equal(estado.textContent, mensajeEsperado);
    assert.equal(estado.getAttribute("role"), "alert");
    assert.equal(estado.className, "mensaje mensaje-error");
    assert.equal(entorno.historial.length, 1);
    assert.doesNotMatch(entorno.historial[0], /credencial/u);
    assert.deepEqual(entorno.navegaciones, []);
  } finally {
    entorno.restaurar();
  }
}

test("credencial de verificación vencida muestra recuperación segura sin navegar", async () => {
  await comprobarEstadoVerificacion(
    "CREDENCIAL_VERIFICACION_VENCIDA",
    "El enlace venció. Solicita uno nuevo.",
  );
});

test("credencial de verificación utilizada informa el estado sin navegar", async () => {
  await comprobarEstadoVerificacion(
    "CREDENCIAL_VERIFICACION_UTILIZADA",
    "El enlace ya fue utilizado. Puedes intentar iniciar sesión.",
  );
});
