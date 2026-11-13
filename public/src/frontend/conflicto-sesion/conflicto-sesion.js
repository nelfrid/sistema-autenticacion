import { solicitarApi } from "../../../assets/cliente-api.js";
import { mostrarMensaje } from "../../../assets/utilidades-formulario.js";

const detalle = document.getElementById("detalle-conflicto");
const mensaje = document.getElementById("mensaje-conflicto");

async function cargarConflicto() {
  try {
    const resultado = await solicitarApi("/sesiones/conflicto");
    document.getElementById("inicio-anterior").textContent = resultado.inicio_aproximado ?? "No disponible";
    document.getElementById("dispositivo-anterior").textContent = resultado.dispositivo ?? "Información limitada";
    detalle.hidden = false;
  } catch {
    mostrarMensaje(mensaje, "El conflicto ya no está disponible o venció. Vuelve a iniciar sesión.", "error");
  }
}

cargarConflicto();
