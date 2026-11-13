import { solicitarApi } from "../../../assets/cliente-api.js";
import {
  activarAlternadoresContrasena,
  establecerEnvio,
  escribirErrorCampo,
  mostrarMensaje,
  validarContrasena,
  validarCorreo,
} from "../../../assets/utilidades-formulario.js";

const formulario = document.getElementById("formulario-acceso");
const mensaje = document.getElementById("mensaje-acceso");
activarAlternadoresContrasena(formulario);

const destinos = {
  AUTENTICADO: "../sesion/sesion.html",
  VERIFICACION_CORREO_PENDIENTE: "../verificacion-correo/verificacion-correo.html",
  CONFIGURACION_WEBAUTHN_REQUERIDA: "../configuracion-webauthn/configuracion-webauthn.html",
  DESAFIO_WEBAUTHN_REQUERIDO: "../desafio-webauthn/desafio-webauthn.html",
  CONFLICTO_SESION: "../conflicto-sesion/conflicto-sesion.html",
};

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (formulario.getAttribute("aria-busy") === "true") return;
  mostrarMensaje(mensaje, "");
  const correo = formulario.elements.correo.value;
  const contrasena = formulario.elements.contrasena.value;
  const errorCorreo = validarCorreo(correo);
  const errorContrasena = contrasena ? validarContrasena(contrasena) : "Introduce tu contraseña.";
  escribirErrorCampo(formulario.elements.correo, errorCorreo);
  escribirErrorCampo(formulario.elements.contrasena, errorContrasena);
  if (errorCorreo || errorContrasena) {
    formulario.querySelector('[aria-invalid="true"]')?.focus();
    return;
  }

  establecerEnvio(formulario, true, "Comprobando…");
  try {
    const resultado = await solicitarApi("/sesiones/iniciar", {
      metodo: "POST",
      datos: { correo, contrasena },
    });
    const destino = destinos[resultado.codigo];
    if (!destino) throw new Error("Respuesta de autenticación no reconocida.");
    window.location.assign(destino);
  } catch (error) {
    const texto = error.estado === 429
      ? "Se alcanzó el límite de intentos. Espera antes de continuar."
      : "No fue posible iniciar sesión con los datos proporcionados.";
    mostrarMensaje(mensaje, texto, "error");
    formulario.elements.contrasena.value = "";
    formulario.elements.contrasena.focus();
  } finally {
    establecerEnvio(formulario, false);
  }
});
