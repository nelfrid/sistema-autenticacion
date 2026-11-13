import { solicitarApi } from "../../../assets/cliente-api.js";
import { mostrarMensaje } from "../../../assets/utilidades-formulario.js";

const mensaje = document.getElementById("mensaje-sesion");
const detalle = document.getElementById("detalle-sesion");
const enlaceReingreso = document.getElementById("enlace-reingreso");
const botonCerrar = document.getElementById("boton-cerrar");

function mostrarSesionFinalizada(texto) {
  detalle.hidden = true;
  enlaceReingreso.hidden = false;
  mostrarMensaje(mensaje, texto, "aviso");
}

async function cargarSesion() {
  try {
    const resultado = await solicitarApi("/sesiones/actual");
    document.getElementById("correo-cuenta").textContent = resultado.correo;
    document.getElementById("vencimiento-absoluto").textContent = resultado.vencimiento_absoluto;
    detalle.hidden = false;
    mostrarMensaje(mensaje, "La sesión está activa.", "exito");
  } catch (error) {
    const textos = {
      SESION_EXPIRADA: "La sesión alcanzó su límite de 8 horas.",
      SESION_INACTIVA: "La sesión terminó después de 30 minutos de inactividad.",
      SESION_REVOCADA: "La sesión fue revocada.",
    };
    mostrarSesionFinalizada(textos[error.codigo] ?? "No hay una sesión activa.");
  }
}

botonCerrar.addEventListener("click", async () => {
  if (botonCerrar.disabled) return;
  botonCerrar.disabled = true;
  botonCerrar.textContent = "Cerrando…";
  try {
    await solicitarApi("/sesiones/cerrar", { metodo: "POST" });
    mostrarSesionFinalizada("La sesión se cerró correctamente.");
  } catch {
    mostrarMensaje(mensaje, "No se pudo confirmar el cierre. No continúes usando este dispositivo hasta verificar el estado de la sesión.", "error");
    botonCerrar.disabled = false;
    botonCerrar.textContent = "Cerrar sesión";
  }
});

cargarSesion();
