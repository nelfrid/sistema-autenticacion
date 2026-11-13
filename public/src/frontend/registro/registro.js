import { solicitarApi } from "../../../assets/cliente-api.js";
import {
  activarAlternadoresContrasena,
  establecerEnvio,
  escribirErrorCampo,
  limpiarErrores,
  mostrarErroresApi,
  mostrarMensaje,
  validarContrasena,
  validarCorreo,
  validarNombre,
} from "../../../assets/utilidades-formulario.js";

const VERSION_TERMINOS = "terminos-demo-1.0";
const VERSION_PRIVACIDAD = "privacidad-demo-1.0";
const formulario = document.getElementById("formulario-registro");
const mensaje = document.getElementById("mensaje-registro");

activarAlternadoresContrasena(formulario);

function validarFormulario() {
  const datos = new FormData(formulario);
  const contrasena = datos.get("contrasena");
  const confirmacion = datos.get("confirmacion_contrasena");
  const errores = {
    nombre_completo: validarNombre(datos.get("nombre_completo")),
    correo: validarCorreo(datos.get("correo")),
    contrasena: validarContrasena(contrasena),
    confirmacion_contrasena: contrasena === confirmacion ? "" : "Las contraseñas no coinciden.",
    acepta_terminos: datos.get("acepta_terminos") ? "" : "Debes aceptar los términos.",
    acepta_privacidad: datos.get("acepta_privacidad") ? "" : "Debes aceptar el aviso de privacidad.",
  };

  Object.entries(errores).forEach(([nombre, error]) => {
    escribirErrorCampo(formulario.elements.namedItem(nombre), error);
  });
  return !Object.values(errores).some(Boolean);
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (formulario.getAttribute("aria-busy") === "true") return;
  limpiarErrores(formulario);
  mostrarMensaje(mensaje, "");
  if (!validarFormulario()) {
    mostrarMensaje(mensaje, "Revisa los campos indicados.", "error");
    formulario.querySelector('[aria-invalid="true"]')?.focus();
    return;
  }

  const datos = new FormData(formulario);
  establecerEnvio(formulario, true, "Creando cuenta…");
  try {
    await solicitarApi("/registros", {
      metodo: "POST",
      datos: {
        nombre_completo: datos.get("nombre_completo").trim(),
        correo: datos.get("correo"),
        contrasena: datos.get("contrasena"),
        confirmacion_contrasena: datos.get("confirmacion_contrasena"),
        aceptaciones: [VERSION_TERMINOS, VERSION_PRIVACIDAD],
      },
    });
    formulario.reset();
    mostrarMensaje(
      mensaje,
      "Si la solicitud puede procesarse, recibirás un enlace de verificación. Revisa también el correo no deseado.",
      "exito",
    );
  } catch (error) {
    mostrarErroresApi(formulario, error.campos);
    const texto = error.estado === 429
      ? "Se alcanzó el límite de solicitudes. Espera antes de intentarlo nuevamente."
      : "No se pudo completar la solicitud. Revisa los datos o inténtalo más tarde.";
    mostrarMensaje(mensaje, texto, "error");
  } finally {
    establecerEnvio(formulario, false);
  }
});
