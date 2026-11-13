import { execFileSync } from "node:child_process";
import { readFile, stat } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";

import { solicitarApi } from "../../assets/cliente-api.js";
import {
  contarCaracteres,
  validarContrasena,
  validarCorreo,
  validarNombre,
} from "../../assets/utilidades-formulario.js";
import {
  base64UrlABytes,
  bytesABase64Url,
  prepararOpcionesAutenticacion,
  prepararOpcionesRegistro,
  serializarAutenticacion,
  serializarRegistro,
} from "../../assets/webauthn.js";

const directorioFrontend = dirname(fileURLToPath(import.meta.url));
const directorioPublico = join(directorioFrontend, "..", "..");
const paginas = [
  "registro",
  "terminos",
  "privacidad",
  "verificacion-correo",
  "inicio-sesion",
  "configuracion-webauthn",
  "codigos-respaldo",
  "desafio-webauthn",
  "conflicto-sesion",
  "sesion",
];

function respuestaJson(cuerpo, estado = 200, cabeceras = {}) {
  return new Response(JSON.stringify(cuerpo), {
    status: estado,
    headers: { "content-type": "application/json", ...cabeceras },
  });
}

test("cuenta caracteres Unicode sin normalizar la contraseña", () => {
  assert.equal(contarCaracteres("á🔐 "), 3);
  assert.equal(validarContrasena("12345678901234"), "La contraseña debe contener al menos 15 caracteres.");
  assert.equal(validarContrasena("123456789012345"), "");
  assert.equal(validarContrasena(" ".repeat(15)), "");
  assert.equal(validarContrasena("a".repeat(129)), "La contraseña no puede superar 128 caracteres.");
});

test("valida nombre y correo sin reglas culturales restrictivas", () => {
  assert.equal(validarNombre("María-José O'Connor"), "");
  assert.equal(validarNombre("   "), "Introduce tu nombre completo.");
  assert.equal(validarCorreo("persona@ejemplo.test"), "");
  assert.equal(validarCorreo("persona@"), "Introduce un correo electrónico válido.");
});

test("el cliente usa /api/v1, mismo origen y conserva exactamente la contraseña", async () => {
  const contrasena = "  contraseña exacta  ";
  let solicitud;
  const fetchFalso = async (ruta, opciones) => {
    if (ruta === "/api/v1/seguridad/csrf") {
      return respuestaJson({ token_csrf: "csrf-prueba-unitaria" });
    }
    solicitud = { ruta, opciones };
    return respuestaJson({ codigo: "REGISTRO_RECIBIDO" });
  };

  const resultado = await solicitarApi("/registros", {
    metodo: "POST",
    datos: { contrasena },
  }, fetchFalso);

  assert.equal(solicitud.ruta, "/api/v1/registros");
  assert.equal(solicitud.opciones.credentials, "same-origin");
  assert.equal(solicitud.opciones.redirect, "error");
  assert.equal(solicitud.opciones.cache, "no-store");
  assert.equal(JSON.parse(solicitud.opciones.body).contrasena, contrasena);
  assert.equal(resultado.codigo, "REGISTRO_RECIBIDO");
});

test("el cliente conserva códigos funcionales y espera de límites", async () => {
  const fetchFalso = async () => respuestaJson({
    codigo: "LIMITE_SOLICITUDES",
    mensaje: "Espera antes de reintentar.",
  }, 429, { "retry-after": "12" });

  await assert.rejects(
    solicitarApi("/registros", { metodo: "POST", datos: {} }, fetchFalso),
    (error) => error.codigo === "LIMITE_SOLICITUDES" && error.reintentarEn === 12,
  );
});

test("el cliente convierte fallos de red en un error seguro", async () => {
  const fetchFalso = async () => { throw new TypeError("detalle privado de red"); };
  await assert.rejects(
    solicitarApi("/sesiones/iniciar", { metodo: "POST", datos: {} }, fetchFalso),
    (error) => error.codigo === "ERROR_DESCONOCIDO"
      && error.estado === 0
      && !error.message.includes("detalle privado"),
  );
});

test("el cliente conserva una cancelación explícita", async () => {
  const cancelacion = new Error("cancelada");
  cancelacion.name = "AbortError";
  const fetchFalso = async () => { throw cancelacion; };
  await assert.rejects(
    solicitarApi("/sesiones/actual", {}, fetchFalso),
    (error) => error === cancelacion,
  );
});

test("el cliente controla respuestas HTTP sin JSON válido", async () => {
  const fetchFalso = async () => new Response("respuesta interna", {
    status: 503,
    headers: { "content-type": "application/json" },
  });
  await assert.rejects(
    solicitarApi("/sesiones/actual", {}, fetchFalso),
    (error) => error.estado === 503 && error.codigo === "ERROR_DESCONOCIDO",
  );
});

test("convierte valores base64url de WebAuthn en ambos sentidos", () => {
  const original = Uint8Array.from([0, 1, 2, 250, 255]);
  const codificado = bytesABase64Url(original);
  assert.deepEqual(base64UrlABytes(codificado), original);
});

test("prepara y serializa registro WebAuthn", () => {
  const opciones = prepararOpcionesRegistro({
    challenge: "AQID",
    user: { id: "BAUG", name: "persona@ejemplo.test", displayName: "Persona" },
    excludeCredentials: [{ id: "BwgJ", type: "public-key" }],
  });
  assert.deepEqual(Array.from(opciones.challenge), [1, 2, 3]);
  assert.deepEqual(Array.from(opciones.user.id), [4, 5, 6]);

  const serializado = serializarRegistro({
    id: "credencial",
    rawId: Uint8Array.from([1, 2]).buffer,
    type: "public-key",
    response: {
      attestationObject: Uint8Array.from([3]).buffer,
      clientDataJSON: Uint8Array.from([4]).buffer,
      getTransports: () => ["internal"],
    },
  });
  assert.equal(serializado.rawId, "AQI");
  assert.deepEqual(serializado.response.transports, ["internal"]);
});

test("prepara y serializa autenticación WebAuthn", () => {
  const opciones = prepararOpcionesAutenticacion({
    challenge: "AQID",
    allowCredentials: [{ id: "BAUG", type: "public-key" }],
  });
  assert.deepEqual(Array.from(opciones.allowCredentials[0].id), [4, 5, 6]);

  const serializado = serializarAutenticacion({
    id: "credencial",
    rawId: Uint8Array.from([1]).buffer,
    type: "public-key",
    response: {
      authenticatorData: Uint8Array.from([2]).buffer,
      clientDataJSON: Uint8Array.from([3]).buffer,
      signature: Uint8Array.from([4]).buffer,
      userHandle: null,
    },
  });
  assert.equal(serializado.response.signature, "BA");
  assert.equal(serializado.response.userHandle, null);
});

test("cada página conserva HTML, CSS, JavaScript y assets", async () => {
  for (const pagina of paginas) {
    const directorio = join(directorioFrontend, pagina);
    await stat(join(directorio, `${pagina}.html`));
    await stat(join(directorio, `${pagina}.css`));
    await stat(join(directorio, `${pagina}.js`));
    assert.ok((await stat(join(directorio, "assets"))).isDirectory());
  }
});

test("los recursos y enlaces locales de las páginas existen", async () => {
  const archivosHtml = [
    join(directorioPublico, "..", "index.html"),
    ...paginas.map((pagina) => join(directorioFrontend, pagina, `${pagina}.html`)),
  ];
  for (const archivoHtml of archivosHtml) {
    const contenido = await readFile(archivoHtml, "utf8");
    const referencias = [...contenido.matchAll(/(?:href|src)="([^"#?]+)(?:\?[^"#]*)?"/gu)]
      .map((coincidencia) => coincidencia[1])
      .filter((referencia) => !referencia.startsWith("/"));
    for (const referencia of referencias) {
      await stat(resolve(dirname(archivoHtml), referencia));
    }
  }
});

test("las páginas conservan navegación y estructura accesibles", async () => {
  const archivosHtml = paginas.map((pagina) => join(directorioFrontend, pagina, `${pagina}.html`));
  for (const archivoHtml of archivosHtml) {
    const contenido = await readFile(archivoHtml, "utf8");
    assert.match(contenido, /<html lang="es">/u);
    assert.match(contenido, /class="salto-contenido" href="#contenido"/u);
    assert.match(contenido, /<main id="contenido"/u);
    assert.equal((contenido.match(/<h1\b/gu) ?? []).length, 1);
    assert.doesNotMatch(contenido, /<button(?![^>]*\btype=)[^>]*>/gu);

    const identificadoresEntrada = [...contenido.matchAll(/<input[^>]+id="([^"]+)"/gu)]
      .map((coincidencia) => coincidencia[1]);
    identificadoresEntrada.forEach((identificador) => {
      assert.match(contenido, new RegExp(`<label[^>]+for="${identificador}"`, "u"));
    });
  }
});

test("los formularios sensibles anuncian errores y permiten gestores de contraseña", async () => {
  const registro = await readFile(join(directorioFrontend, "registro", "registro.html"), "utf8");
  const acceso = await readFile(join(directorioFrontend, "inicio-sesion", "inicio-sesion.html"), "utf8");
  assert.match(registro, /autocomplete="new-password"/u);
  assert.match(acceso, /autocomplete="current-password"/u);
  assert.match(registro, /data-alternar-contrasena="contrasena" aria-pressed="false"/u);
  assert.match(acceso, /data-alternar-contrasena="contrasena" aria-pressed="false"/u);
  assert.match(registro, /aria-live="polite"/u);
  assert.match(acceso, /aria-live="assertive"/u);
});

test("el frontend no utiliza almacenamiento web para secretos", async () => {
  const archivos = [
    join(directorioPublico, "assets", "cliente-api.js"),
    join(directorioPublico, "assets", "utilidades-formulario.js"),
    join(directorioPublico, "assets", "webauthn.js"),
    ...paginas.map((pagina) => join(directorioFrontend, pagina, `${pagina}.js`)),
  ];
  for (const archivo of archivos) {
    const contenido = await readFile(archivo, "utf8");
    assert.doesNotMatch(contenido, /(?:local|session)Storage/u);
  }
});

test("todos los módulos JavaScript tienen sintaxis válida", () => {
  const archivos = [
    join(directorioPublico, "assets", "cliente-api.js"),
    join(directorioPublico, "assets", "utilidades-formulario.js"),
    join(directorioPublico, "assets", "webauthn.js"),
    ...paginas.map((pagina) => join(directorioFrontend, pagina, `${pagina}.js`)),
  ];
  for (const archivo of archivos) {
    execFileSync(process.execPath, ["--check", archivo], { stdio: "pipe" });
  }
});
