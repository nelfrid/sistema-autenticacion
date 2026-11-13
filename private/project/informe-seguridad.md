# Informe acumulativo de seguridad

## Alcance publicable

Reevalué el estado completo del Frontend contra los requisitos privados del proyecto y los criterios FE-01..FE-20. Revisé código productivo, rutas, cargas, estados, validaciones, WebAuthn, sesión, tratamiento de secretos, prevención de doble ejecución, ciclo CSRF de mismo origen y pruebas automatizadas.

Este informe contiene únicamente evidencia obtenida de rutas públicas del código y resultados reproducibles. API y Backend conservan solamente su estado acumulativo pendiente de corrección.

## Estado acumulativo

| Área | Criterios | Estado |
| --- | --- | --- |
| Frontend | FE-01..FE-20 | **Correcto** |
| API | API-01..API-22 | **Pendiente de corrección** |
| Backend | BE-01..BE-35 | **Pendiente de corrección** |

## Reauditoría Frontend

- Estado evaluado en el historial público: `628fba5`.
- Modalidad: inspección de solo lectura del código Frontend.
- Resultado del árbol de trabajo después de los controles: limpio y en el estado evaluado.
- Organización revisada: diez páginas con HTML, CSS, JavaScript y directorio de recursos; recursos compartidos y dependencias separados.

### Coherencia de rutas y ciclo CSRF

- Verifiqué las 15 operaciones consumidas: obtención CSRF, registro, confirmación y reenvío de correo, inicio y cierre de sesión, estado y conflicto de sesión, alta y autenticación WebAuthn y códigos de respaldo.
- No encontré operaciones contratadas ausentes ni rutas productivas fuera del contrato vigente.
- `public/assets/cliente-api.js:1-5` define una base relativa `/api/v1`, una ruta CSRF relativa y estado CSRF exclusivamente en memoria.
- `public/assets/cliente-api.js:44-53` crea todas las solicitudes con `credentials: "same-origin"`, `redirect: "error"` y `cache: "no-store"`.
- `public/assets/cliente-api.js:61-109` obtiene una sola credencial CSRF válida, controla errores y no ejecuta la mutación si la credencial no está disponible.
- `public/assets/cliente-api.js:111-163` añade `X-CSRF-Token` a `POST`, `PUT`, `PATCH` y `DELETE`, adopta rotaciones válidas, invalida el valor ante errores `CSRF_*` y no reintenta automáticamente la mutación rechazada.
- `public/src/frontend/pruebas-csrf-frontend.js:19-128` comprueba obtención y envío, ausencia de credencial, expiración sin reintento, rotación y fallo de red seguro.
- No existe persistencia del token CSRF en almacenamiento web, cookies accesibles a JavaScript ni parámetros de URL.

### Matriz FE-01..FE-20

| Criterio | Resultado | Evidencia pública |
| --- | --- | --- |
| FE-01 | **Correcto** | El código productivo es funcional, legible y necesario. No contiene bloques residuales sin uso; los documentos legales usan controles de impresión funcionales en `public/src/frontend/terminos/terminos.js:1-8` y `public/src/frontend/privacidad/privacidad.js:1-8`. |
| FE-02 | **Correcto** | El formulario declara nombre, correo, contraseña, confirmación y aceptaciones obligatorias en `public/src/frontend/registro/registro.html:23-71`; todos se validan en `registro.js:21-37`. |
| FE-03 | **Correcto** | `public/assets/utilidades-formulario.js:4-13` rechaza nombres vacíos, espacios solos, exceso de longitud y controles sin excluir tildes, espacios, guiones o apóstrofos. |
| FE-04 | **Correcto** | `public/assets/utilidades-formulario.js:15-21` valida estructura y longitud del correo, no solo la presencia del símbolo de arroba. |
| FE-05 | **Correcto** | `public/src/frontend/registro/registro.html:38-44` y `public/assets/utilidades-formulario.js:23-27` aplican 15 a 128 caracteres, permiten espacios y pegado y no exigen reglas de composición. |
| FE-06 | **Correcto** | Registro y login conservan la contraseña exacta, sin recorte, normalización ni truncamiento (`public/src/frontend/registro/registro.js:23-29,58-60`; `public/src/frontend/inicio-sesion/inicio-sesion.js:27-30,40-43`). |
| FE-07 | **Correcto** | La confirmación es obligatoria, se compara exactamente y solo se envía para validar el registro (`public/src/frontend/registro/registro.html:47-53`; `registro.js:23-31,54-62`). |
| FE-08 | **Correcto** | Términos y privacidad se presentan por separado, sin selección previa y con documentos consultables (`public/src/frontend/registro/registro.html:57-68`). |
| FE-09 | **Correcto** | `public/assets/utilidades-formulario.js:50-62` deshabilita controles durante cada envío. Las pruebas independientes de doble activación están en `public/src/frontend/pruebas-comportamiento-frontend.js:279-310,798-986`. |
| FE-10 | **Correcto** | Registro y reenvío usan mensajes anti-enumeración; login unifica cuenta inexistente, contraseña incorrecta y fallo de red (`public/src/frontend/registro/registro.js:64-75`; `public/src/frontend/verificacion-correo/verificacion-correo.js:55-61`; `public/src/frontend/inicio-sesion/inicio-sesion.js:47-53`). |
| FE-11 | **Correcto** | La credencial se elimina de la URL antes de usarse y se distinguen los estados vencida, utilizada e inválida sin activar la cuenta (`public/src/frontend/verificacion-correo/verificacion-correo.js:13-67`; pruebas en `pruebas-comportamiento-frontend.js:415-477,988-1018`). |
| FE-12 | **Correcto** | Login valida formato y presencia antes de enviar y enruta únicamente estados funcionales recibidos del servidor (`public/src/frontend/inicio-sesion/inicio-sesion.js:15-46`). |
| FE-13 | **Correcto** | No se usa almacenamiento web para credenciales; la contraseña permanece en memoria transitoria y se vacía después de un fallo (`public/src/frontend/inicio-sesion/inicio-sesion.js:47-53`; comprobación en `public/src/frontend/pruebas-frontend.js:234-245`). |
| FE-14 | **Correcto** | Los fallos de identificación no revelan si falló la cuenta o la contraseña (`public/src/frontend/inicio-sesion/inicio-sesion.js:47-53`; prueba en `pruebas-comportamiento-frontend.js:388-406`). |
| FE-15 | **Correcto** | Solo los estados autenticados abren la sesión; correo, configuración WebAuthn, desafío y conflicto permanecen en flujos restringidos (`public/src/frontend/inicio-sesion/inicio-sesion.js:15-46`; `public/src/frontend/desafio-webauthn/desafio-webauthn.js:22-27`). |
| FE-16 | **Correcto** | El Frontend no utiliza identificadores de dispositivo ni `User-Agent` como autenticadores; la información de conflicto se trata únicamente como texto (`public/src/frontend/conflicto-sesion/conflicto-sesion.js:7-15`). |
| FE-17 | **Correcto** | Estado, vencimiento, inactividad y revocación se obtienen del servidor y no del reloj del navegador (`public/src/frontend/sesion/sesion.js:15-29`). |
| FE-18 | **Correcto** | El cliente usa cookies de mismo origen sin exponerlas a JavaScript, no almacena tokens de sesión y aplica el ciclo CSRF en memoria a todas las mutaciones (`public/assets/cliente-api.js:1-5,44-53,61-163`). Las páginas incluyen CSP complementaria. |
| FE-19 | **Correcto** | Los datos dinámicos se insertan con `textContent` o nodos creados. No encontré `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval` ni `new Function` en el JavaScript público. |
| FE-20 | **Correcto** | La suite ejecuta 46 pruebas unitarias, estructurales, positivas, negativas y de excepción. Incluye siete controles independientes de doble activación, los estados de verificación vencida y utilizada y cinco pruebas dedicadas al ciclo CSRF (`public/src/frontend/pruebas-comportamiento-frontend.js:798-1018`; `public/src/frontend/pruebas-csrf-frontend.js:19-128`). |

### Pruebas y controles ejecutados

1. `npm run pruebas:frontend`, desde `public/dependencies`:
   - Total: 46.
   - Correctas: 46.
   - Fallidas: 0.
   - Omitidas: 0.
   - Resultado: correcto.
2. `npm run lint:frontend`, desde `public/dependencies`:
   - Resultado: sintaxis válida en 16 archivos JavaScript.
3. `git diff --check HEAD^ HEAD`:
   - Resultado: correcto, sin salida.
4. Verificación de rutas productivas:
   - Operaciones consumidas: 15.
   - Operaciones ausentes: 0.
   - Rutas fuera del contrato: 0.
5. Búsqueda de patrones sensibles en JavaScript público:
   - Sin almacenamiento web, lectura de cookies, sumideros HTML dinámicos, ejecución dinámica de código ni registros de consola productivos.
6. Versiones del entorno:
   - Node.js `v24.15.0`.
   - npm `11.12.1`.

### Veredicto final de Frontend

**Correcto.**

FE-01..FE-20 cumplen los requisitos evaluados. No asigno un nuevo veredicto a API ni Backend; ambas áreas permanecen pendientes de corrección.
