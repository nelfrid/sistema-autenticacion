import { solicitarApi } from "../../../assets/cliente-api.js";
import {
  establecerEnvio,
  escribirErrorCampo,
  iniciarCuentaRegresiva,
  mostrarMensaje,
  validarCorreo,
} from "../../../assets/utilidades-formulario.js";

const estado = document.getElementById("estado-verificacion");
const formulario = document.getElementById("formulario-reenvio");

async function verificarCredencial() {
  const direccion = new URL(window.location.href);
  const credencial = direccion.searchParams.get("credencial");
  if (!credencial) return;

  direccion.searchParams.delete("credencial");
  window.history.replaceState(null, "", `${direccion.pathname}${direccion.search}${direccion.hash}`);
  mostrarMensaje(estado, "Comprobando el enlace…", "aviso");
  try {
    await solicitarApi("/verificaciones-correo/confirmar", {
      metodo: "POST",
      datos: { credencial },
    });
    mostrarMensaje(estado, "Correo verificado. Ya puedes iniciar sesión.", "exito");
  } catch (error) {
    const mensajes = {
      CREDENCIAL_VERIFICACION_VENCIDA: "El enlace venció. Solicita uno nuevo.",
      CREDENCIAL_VERIFICACION_UTILIZADA: "El enlace ya fue utilizado. Puedes intentar iniciar sesión.",
      CREDENCIAL_VERIFICACION_INVALIDA: "El enlace no es válido. Solicita uno nuevo.",
    };
    mostrarMensaje(estado, mensajes[error.codigo] ?? "No se pudo verificar el enlace.", "error");
  }
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (formulario.getAttribute("aria-busy") === "true") return;
  const correo = formulario.elements.correo.value;
  const errorCorreo = validarCorreo(correo);
  escribirErrorCampo(formulario.elements.correo, errorCorreo);
  if (errorCorreo) {
    formulario.elements.correo.focus();
    return;
  }

  let espera = null;
  establecerEnvio(formulario, true, "Solicitando…");
  try {
    await solicitarApi("/verificaciones-correo/reenviar", {
      metodo: "POST",
      datos: { correo },
    });
    formulario.reset();
    mostrarMensaje(estado, "Si corresponde, enviaremos un enlace nuevo. Revisa también el correo no deseado.", "exito");
  } catch (error) {
    if (error.estado === 429 && error.reintentarEn !== null) {
      espera = error.reintentarEn;
    }
    mostrarMensaje(estado, "No se pudo procesar la solicitud. Espera e inténtalo nuevamente.", "error");
  } finally {
    establecerEnvio(formulario, false);
    if (espera !== null) {
      iniciarCuentaRegresiva(formulario.querySelector('button[type="submit"]'), espera);
    }
  }
});

verificarCredencial();
