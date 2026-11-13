export function activarImpresion(documento = document, ventana = window) {
  const boton = documento.getElementById("boton-imprimir");
  if (!boton) return false;
  boton.addEventListener("click", () => ventana.print());
  return true;
}

if (typeof document !== "undefined") activarImpresion();
