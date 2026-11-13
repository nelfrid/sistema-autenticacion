import { execFileSync } from "node:child_process";
import { readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const directorioActual = dirname(fileURLToPath(import.meta.url));
const raices = [
  resolve(directorioActual, "../assets"),
  resolve(directorioActual, "../src/frontend"),
];

function encontrarJavaScript(directorio) {
  return readdirSync(directorio).flatMap((nombre) => {
    const ruta = join(directorio, nombre);
    if (statSync(ruta).isDirectory()) return encontrarJavaScript(ruta);
    return nombre.endsWith(".js") ? [ruta] : [];
  });
}

const archivos = raices.flatMap(encontrarJavaScript);
archivos.forEach((archivo) => execFileSync(process.execPath, ["--check", archivo], { stdio: "pipe" }));
console.log(`Sintaxis válida en ${archivos.length} archivos JavaScript.`);
