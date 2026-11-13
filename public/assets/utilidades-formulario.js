const EXPRESION_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/u;
const EXPRESION_CONTROL = /[\u0000-\u001F\u007F]/u;

export function contarCaracteres(valor) {
  return Array.from(valor).length;
}

export function validarNombre(nombre) {
  if (!nombre || !nombre.trim()) return "Introduce tu nombre completo.";
  if (contarCaracteres(nombre.trim()) > 150) return "El nombre no puede superar 150 caracteres.";
  if (EXPRESION_CONTROL.test(nombre)) return "El nombre contiene caracteres no permitidos.";
  return "";
}

export function validarCorreo(correo) {
  if (!correo) return "Introduce tu correo electrónico.";
  if (contarCaracteres(correo) > 254 || !EXPRESION_CORREO.test(correo)) {
    return "Introduce un correo electrónico válido.";
  }
  return "";
}

export function validarContrasena(contrasena) {
  const longitud = contarCaracteres(contrasena);
  if (longitud < 15) return "La contraseña debe contener al menos 15 caracteres.";
  if (longitud > 128) return "La contraseña no puede superar 128 caracteres.";
  return "";
}

export function escribirErrorCampo(campo, mensaje) {
  const identificadorError = campo.getAttribute("aria-describedby")?.split(" ")
    .find((identificador) => identificador.startsWith("error-"));
  const salida = identificadorError ? document.getElementById(identificadorError) : null;
  campo.setAttribute("aria-invalid", mensaje ? "true" : "false");
  if (salida) salida.textContent = mensaje;
}

export function limpiarErrores(formulario) {
  formulario.querySelectorAll("[aria-invalid]").forEach((campo) => campo.setAttribute("aria-invalid", "false"));
  formulario.querySelectorAll(".error-campo").forEach((salida) => { salida.textContent = ""; });
}

export function mostrarErroresApi(formulario, campos = {}) {
  Object.entries(campos).forEach(([nombre, mensaje]) => {
    const campo = formulario.elements.namedItem(nombre);
    if (campo instanceof HTMLElement) escribirErrorCampo(campo, String(mensaje));
  });
}

export function establecerEnvio(formulario, enCurso, textoEnCurso = "Procesando…") {
  const boton = formulario.querySelector('button[type="submit"]');
  formulario.setAttribute("aria-busy", String(enCurso));
  formulario.querySelectorAll("button, input").forEach((control) => { control.disabled = enCurso; });
  if (!boton) return;
  if (enCurso) {
    boton.dataset.textoAnterior = boton.textContent;
    boton.textContent = textoEnCurso;
  } else if (boton.dataset.textoAnterior) {
    boton.textContent = boton.dataset.textoAnterior;
    delete boton.dataset.textoAnterior;
  }
}

export function mostrarMensaje(elemento, mensaje, tipo = "error") {
  elemento.textContent = mensaje;
  elemento.className = `mensaje mensaje-${tipo}`;
  elemento.setAttribute("role", tipo === "error" ? "alert" : "status");
  elemento.hidden = !mensaje;
}

export function activarAlternadoresContrasena(contenedor = document) {
  contenedor.querySelectorAll("[data-alternar-contrasena]").forEach((boton) => {
    boton.addEventListener("click", () => {
      const campo = document.getElementById(boton.dataset.alternarContrasena);
      if (!campo) return;
      const visible = campo.type === "text";
      campo.type = visible ? "password" : "text";
      boton.textContent = visible ? "Mostrar" : "Ocultar";
      boton.setAttribute("aria-pressed", String(!visible));
    });
  });
}

export function iniciarCuentaRegresiva(boton, segundos) {
  let restantes = segundos;
  const textoOriginal = boton.textContent;
  boton.disabled = true;
  boton.textContent = `Espera ${restantes} s`;
  const intervalo = window.setInterval(() => {
    restantes -= 1;
    if (restantes <= 0) {
      window.clearInterval(intervalo);
      boton.disabled = false;
      boton.textContent = textoOriginal;
      return;
    }
    boton.textContent = `Espera ${restantes} s`;
  }, 1000);
}
