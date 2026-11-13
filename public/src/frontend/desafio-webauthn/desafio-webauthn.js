import { solicitarApi } from "../../../assets/cliente-api.js";
import {
  establecerEnvio,
  escribirErrorCampo,
  mostrarMensaje,
} from "../../../assets/utilidades-formulario.js";
import {
  prepararOpcionesAutenticacion,
  serializarAutenticacion,
  webauthnDisponible,
} from "../../../assets/webauthn.js";

const botonPasskey = document.getElementById("boton-passkey");
const formularioRespaldo = document.getElementById("formulario-respaldo");
const mensaje = document.getElementById("mensaje-desafio");
const esConflictoSesion = new URL(window.location.href).searchParams.get("conflicto") === "1";

if (esConflictoSesion) {
  document.getElementById("alternativa-respaldo").hidden = true;
}

function completarAcceso(resultado) {
  if (["AUTENTICADO", "CONFLICTO_SESION_RESUELTO"].includes(resultado.codigo)) {
    window.location.assign("../sesion/sesion.html");
    return;
  }
  throw new Error("Resultado de verificación no reconocido.");
}

if (!webauthnDisponible()) {
  botonPasskey.disabled = true;
  mostrarMensaje(mensaje, "Este navegador no permite usar passkeys. Utiliza un código de respaldo o un navegador compatible.", "error");
}

botonPasskey.addEventListener("click", async () => {
  if (botonPasskey.disabled) return;
  botonPasskey.disabled = true;
  botonPasskey.textContent = "Preparando…";
  mostrarMensaje(mensaje, "");
  try {
    const resultado = await solicitarApi("/webauthn/autenticacion/opciones", { metodo: "POST" });
    const credencial = await navigator.credentials.get({
      publicKey: prepararOpcionesAutenticacion(resultado.opciones),
    });
    if (!credencial) throw new Error("No se obtuvo una credencial.");
    botonPasskey.textContent = "Verificando…";
    const verificacion = await solicitarApi("/webauthn/autenticacion/completar", {
      metodo: "POST",
      datos: { credencial: serializarAutenticacion(credencial) },
    });
    completarAcceso(verificacion);
  } catch (error) {
    const cancelado = error.name === "NotAllowedError";
    mostrarMensaje(
      mensaje,
      cancelado
        ? "La verificación fue cancelada o venció. Puedes intentarlo otra vez."
        : "No fue posible verificar la passkey.",
      "error",
    );
    botonPasskey.disabled = false;
    botonPasskey.textContent = "Usar passkey";
  }
});

formularioRespaldo.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (formularioRespaldo.getAttribute("aria-busy") === "true") return;
  const campo = formularioRespaldo.elements.codigo_respaldo;
  const error = campo.value ? "" : "Introduce un código de respaldo.";
  escribirErrorCampo(campo, error);
  if (error) {
    campo.focus();
    return;
  }

  establecerEnvio(formularioRespaldo, true, "Verificando…");
  try {
    const resultado = await solicitarApi("/webauthn/autenticacion/codigo-respaldo", {
      metodo: "POST",
      datos: { codigo_respaldo: campo.value },
    });
    campo.value = "";
    completarAcceso(resultado);
  } catch (errorApi) {
    campo.value = "";
    const texto = errorApi.estado === 429
      ? "Se alcanzó el límite de intentos. Vuelve a iniciar sesión más tarde."
      : "El código no es válido o ya fue utilizado.";
    mostrarMensaje(mensaje, texto, "error");
    campo.focus();
  } finally {
    establecerEnvio(formularioRespaldo, false);
  }
});
