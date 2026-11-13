import assert from "node:assert/strict";
import test from "node:test";

let numeroCliente = 0;

function respuestaJson(cuerpo, estado = 200, cabeceras = {}) {
  return new Response(JSON.stringify(cuerpo), {
    status: estado,
    headers: { "content-type": "application/json", ...cabeceras },
  });
}

async function cargarClienteAislado() {
  numeroCliente += 1;
  const ruta = new URL(`../../assets/cliente-api.js?csrf=${numeroCliente}`, import.meta.url);
  return import(ruta.href);
}

test("CSRF obtiene el token en memoria y lo envía en una operación mutable", async () => {
  const { solicitarApi } = await cargarClienteAislado();
  const llamadas = [];
  const fetchFalso = async (ruta, opciones) => {
    llamadas.push({ ruta, opciones });
    if (ruta === "/api/v1/seguridad/csrf") {
      return respuestaJson({ token_csrf: "token-inicial" });
    }
    return respuestaJson({ codigo: "REGISTRO_RECIBIDO" });
  };

  await solicitarApi("/registros", { metodo: "POST", datos: { valor: true } }, fetchFalso);

  assert.equal(llamadas.length, 2);
  assert.equal(llamadas[0].ruta, "/api/v1/seguridad/csrf");
  assert.equal(llamadas[0].opciones.method, "GET");
  assert.equal(llamadas[1].ruta, "/api/v1/registros");
  assert.equal(llamadas[1].opciones.headers["X-CSRF-Token"], "token-inicial");
});

test("CSRF rechaza un token ausente sin ejecutar la operación mutable", async () => {
  const { solicitarApi } = await cargarClienteAislado();
  const llamadas = [];
  const fetchFalso = async (ruta, opciones) => {
    llamadas.push({ ruta, opciones });
    return respuestaJson({});
  };

  await assert.rejects(
    solicitarApi("/sesiones/cerrar", { metodo: "POST" }, fetchFalso),
    (error) => error.codigo === "CSRF_NO_DISPONIBLE",
  );
  assert.deepEqual(llamadas.map(({ ruta }) => ruta), ["/api/v1/seguridad/csrf"]);
});

test("CSRF expirado invalida memoria y no reintenta automáticamente la operación", async () => {
  const { solicitarApi } = await cargarClienteAislado();
  const llamadas = [];
  let entregasCsrf = 0;
  let mutaciones = 0;
  const fetchFalso = async (ruta, opciones) => {
    llamadas.push({ ruta, opciones });
    if (ruta === "/api/v1/seguridad/csrf") {
      entregasCsrf += 1;
      return respuestaJson({ token_csrf: `token-${entregasCsrf}` });
    }
    mutaciones += 1;
    if (mutaciones === 1) {
      return respuestaJson({ codigo: "CSRF_EXPIRADO", mensaje: "Token vencido." }, 403);
    }
    return respuestaJson({ codigo: "SESION_CERRADA" });
  };

  await assert.rejects(
    solicitarApi("/sesiones/cerrar", { metodo: "POST" }, fetchFalso),
    (error) => error.codigo === "CSRF_EXPIRADO" && error.estado === 403,
  );
  assert.equal(mutaciones, 1, "La operación rechazada no se reintenta");
  assert.equal(llamadas.length, 2);

  await solicitarApi("/sesiones/cerrar", { metodo: "POST" }, fetchFalso);
  assert.equal(entregasCsrf, 2);
  assert.equal(mutaciones, 2);
  assert.equal(llamadas[1].opciones.headers["X-CSRF-Token"], "token-1");
  assert.equal(llamadas[3].opciones.headers["X-CSRF-Token"], "token-2");
});

test("CSRF adopta una rotación segura sin solicitar otro token", async () => {
  const { solicitarApi } = await cargarClienteAislado();
  const llamadas = [];
  let mutaciones = 0;
  const fetchFalso = async (ruta, opciones) => {
    llamadas.push({ ruta, opciones });
    if (ruta === "/api/v1/seguridad/csrf") {
      return respuestaJson({ token_csrf: "token-anterior" });
    }
    mutaciones += 1;
    if (mutaciones === 1) {
      return respuestaJson(
        { codigo: "ACTUALIZADO" },
        200,
        { "x-csrf-token": "token-rotado" },
      );
    }
    return respuestaJson({ codigo: "ACTUALIZADO" });
  };

  await solicitarApi("/registros", { metodo: "POST", datos: {} }, fetchFalso);
  await solicitarApi("/verificaciones-correo/reenviar", { metodo: "POST", datos: {} }, fetchFalso);

  assert.equal(llamadas.filter(({ ruta }) => ruta === "/api/v1/seguridad/csrf").length, 1);
  assert.equal(llamadas[1].opciones.headers["X-CSRF-Token"], "token-anterior");
  assert.equal(llamadas[2].opciones.headers["X-CSRF-Token"], "token-rotado");
});

test("CSRF transforma un fallo de red sin ejecutar ni filtrar la operación", async () => {
  const { solicitarApi } = await cargarClienteAislado();
  const llamadas = [];
  const fetchFalso = async (ruta, opciones) => {
    llamadas.push({ ruta, opciones });
    throw new TypeError("detalle interno de conexión");
  };

  await assert.rejects(
    solicitarApi("/sesiones/iniciar", { metodo: "POST", datos: {} }, fetchFalso),
    (error) => error.codigo === "ERROR_DESCONOCIDO"
      && !error.message.includes("detalle interno"),
  );
  assert.deepEqual(llamadas.map(({ ruta }) => ruta), ["/api/v1/seguridad/csrf"]);
});
