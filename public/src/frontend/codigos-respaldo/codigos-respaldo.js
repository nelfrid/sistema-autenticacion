import { solicitarApi } from "../../../assets/cliente-api.js";
import {
  establecerEnvio,
  escribirErrorCampo,
  mostrarMensaje,
} from "../../../assets/utilidades-formulario.js";

const lista = document.getElementById("lista-codigos");
const estadoCarga = document.getElementById("estado-carga");
const formulario = document.getElementById("formulario-confirmacion");
const mensaje = document.getElementById("mensaje-codigos");

async function cargarCodigos() {
  try {
    const resultado = await solicitarApi("/codigos-respaldo/pendientes");
    if (!Array.isArray(resultado.codigos) || resultado.codigos.length === 0) {
      throw new Error("No hay códigos disponibles.");
    }
    resultado.codigos.forEach((codigo) => {
      const elemento = document.createElement("li");
      elemento.className = "solo-lectura-segura";
      elemento.textContent = codigo;
      lista.append(elemento);
    });
    estadoCarga.hidden = true;
    lista.hidden = false;
    formulario.hidden = false;
  } catch {
    estadoCarga.hidden = true;
    mostrarMensaje(mensaje, "No fue posible mostrar los códigos. Vuelve a iniciar sesión para reanudar la configuración.", "error");
  }
}

formulario.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  if (formulario.getAttribute("aria-busy") === "true") return;
  const casilla = formulario.elements.codigos_guardados;
  const error = casilla.checked ? "" : "Confirma que guardaste los códigos.";
  escribirErrorCampo(casilla, error);
  if (error) {
    casilla.focus();
    return;
  }

  establecerEnvio(formulario, true, "Confirmando…");
  try {
    await solicitarApi("/codigos-respaldo/confirmar", {
      metodo: "POST",
      datos: { codigos_guardados: true },
    });
    lista.replaceChildren();
    window.location.assign("../sesion/sesion.html");
  } catch {
    mostrarMensaje(mensaje, "No se pudo confirmar el resguardo. Los códigos siguen visibles; inténtalo nuevamente.", "error");
  } finally {
    establecerEnvio(formulario, false);
  }
});

cargarCodigos();
