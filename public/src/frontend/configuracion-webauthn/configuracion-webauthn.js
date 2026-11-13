import { solicitarApi } from "../../../assets/cliente-api.js";
import { mostrarMensaje } from "../../../assets/utilidades-formulario.js";
import {
  prepararOpcionesRegistro,
  serializarRegistro,
  webauthnDisponible,
} from "../../../assets/webauthn.js";

const boton = document.getElementById("boton-configurar");
const mensaje = document.getElementById("mensaje-configuracion");

if (!webauthnDisponible()) {
  boton.disabled = true;
  mostrarMensaje(mensaje, "Este navegador o contexto no permite configurar una passkey. Usa un navegador compatible y una conexión segura.", "error");
}

boton.addEventListener("click", async () => {
  if (boton.disabled) return;
  boton.disabled = true;
  boton.textContent = "Preparando…";
  mostrarMensaje(mensaje, "");
  try {
    const resultado = await solicitarApi("/webauthn/registro/opciones", { metodo: "POST" });
    const credencial = await navigator.credentials.create({
      publicKey: prepararOpcionesRegistro(resultado.opciones),
    });
    if (!credencial) throw new Error("No se obtuvo una credencial.");

    boton.textContent = "Completando…";
    await solicitarApi("/webauthn/registro/completar", {
      metodo: "POST",
      datos: { credencial: serializarRegistro(credencial) },
    });
    window.location.assign("../codigos-respaldo/codigos-respaldo.html");
  } catch (error) {
    const cancelado = error.name === "NotAllowedError";
    mostrarMensaje(
      mensaje,
      cancelado
        ? "La configuración fue cancelada o excedió el tiempo disponible. Puedes intentarlo otra vez."
        : "No se pudo configurar la passkey. Inténtalo nuevamente.",
      "error",
    );
    boton.disabled = false;
    boton.textContent = "Configurar passkey";
  }
});
