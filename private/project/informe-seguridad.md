# Informe acumulativo de seguridad

## Alcance publicable

Reevalué el estado completo del Frontend contra los criterios FE-01..FE-20. Revisé código productivo, rutas, cargas, estados, validaciones, WebAuthn, sesión, tratamiento de secretos, prevención de doble ejecución, ciclo CSRF de mismo origen y pruebas automatizadas.

Este informe contiene únicamente evidencia obtenida de rutas públicas del código y resultados reproducibles. Backend conserva solamente su estado acumulativo pendiente de corrección.

## Estado acumulativo

| Área | Criterios | Estado |
| --- | --- | --- |
| Frontend | FE-01..FE-20 | **Correcto** |
| API | API-01..API-22 | **Correcto** |
| Backend | BE-01..BE-35 | **Pendiente de corrección** |

## Reauditoría Frontend

- Modalidad: inspección de solo lectura del código Frontend.
- Resultado del árbol de trabajo después de los controles: limpio.
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

FE-01..FE-20 cumplen los criterios evaluados.

## Auditoría API

Revisé íntegramente la capa HTTP y la contrasté en solo lectura con el Frontend publicado. Evalué rutas, cargas, estados, errores, HTTPS, normalización, límites, CSRF, cookies, preautenticación, WebAuthn, códigos de respaldo, sesión, renovación, concurrencia y fallos cerrados.

### Alineación con el Frontend publicado

- Extraje las operaciones usadas por los módulos JavaScript productivos y las comparé con las rutas FastAPI.
- El Frontend consume 14 operaciones funcionales; las 14 existen con el mismo método y ruta.
- La API expone además `GET /api/v1/seguridad/csrf`, requerido por el cliente HTTP, y `POST /api/v1/sesiones/renovar`, reservado para la renovación de sesión.
- Los cuerpos coinciden en registro, verificación, reenvío, login, WebAuthn, confirmación de códigos y código de respaldo (`public/src/api/esquemas.py:55-145`; `public/src/api/test_api_autenticacion.py:35-110,372-393`).
- Los códigos de registro, correo, login, WebAuthn, códigos, conflicto, sesión y cierre coinciden con los estados consumidos por el Frontend (`public/src/api/aplicacion.py:45-50,188-499`).
- Los problemas usan `application/problem+json`, incluyen `mensaje`, `codigo`, `campos` y `reintentar_en` cuando corresponde, y mantienen una indicación compatible con el lector JSON del Frontend (`public/src/api/problemas.py:42-71`).
- La configuración de passkey no crea sesión: primero confirma WebAuthn, después entrega los códigos pendientes y solo la confirmación de resguardo establece credenciales (`public/src/api/aplicacion.py:313-361`).
- El conflicto de sesión se resuelve mediante WebAuthn; el contrato del puerto rechaza el código de respaldo en ese estado (`public/src/api/puertos.py:119-127,166-188`; prueba HTTP en `public/src/api/test_api_autenticacion.py:616-643`).

### Matriz API-01..API-22

| Criterio | Resultado | Evidencia pública |
| --- | --- | --- |
| API-01 | **Correcto** | `public/src/api/configuracion.py:36-52` exige un origen HTTPS sin opción para desactivarlo. `public/src/api/seguridad_http.py:97-111,161-178` valida el destino efectivo y rechaza transporte no seguro, incluido el informado por un proxy confiable. |
| API-02 | **Correcto** | El nombre se normaliza a NFC antes de aplicar el máximo de 150 caracteres (`public/src/api/esquemas.py:33-48`). Las 14 rutas y sus cuerpos coinciden con el Frontend (`public/src/api/test_api_autenticacion.py:35-110,372-448`). |
| API-03 | **Correcto** | Todos los cuerpos heredan configuración estricta y prohíben campos adicionales (`public/src/api/esquemas.py:51-145`); las pruebas rechazan atributos internos y envolturas WebAuthn incorrectas. |
| API-04 | **Correcto** | Registro exige confirmación exacta de contraseña, exactamente dos aceptaciones y las versiones vigentes (`public/src/api/esquemas.py:55-72`; `public/src/api/aplicacion.py:192-225`). |
| API-05 | **Correcto** | El middleware limita cuerpo y frecuencia global antes del endpoint; las operaciones sensibles añaden límites por correo, flujo o token (`public/src/api/seguridad_http.py:198-268`; `public/src/api/aplicacion.py:85-119`). |
| API-06 | **Correcto** | Registro duplicado y reenvío inexistente convergen en respuestas aceptadas, y login usa un único error de credenciales (`public/src/api/aplicacion.py:216-233,275-287`; `public/src/api/problemas.py:129-142`). |
| API-07 | **Correcto** | Validación, dominio, HTTP y excepciones inesperadas se convierten en problemas RFC 9457 sin trazas ni detalles internos. El cuerpo conserva extensiones consumibles por el cliente (`public/src/api/problemas.py:42-71,95-206`). |
| API-08 | **Correcto** | Confirmación y reenvío validan esquema, CSRF y límites; la credencial opaca se entrega al backend sin exponer detalles (`public/src/api/aplicacion.py:235-287`). |
| API-09 | **Correcto** | El inicio de sesión devuelve solo un estado restringido y una cookie de flujo; no emite credenciales completas después de la contraseña (`public/src/api/aplicacion.py:289-311`; `public/src/api/puertos.py:63-67`). |
| API-10 | **Correcto** | Las credenciales solo se guardan después de confirmar códigos de alta, WebAuthn de autenticación o un código de respaldo permitido (`public/src/api/aplicacion.py:146-163,352-415`). |
| API-11 | **Correcto** | La API no confía en declaraciones del token: entrega la cookie de acceso al puerto obligatorio de validación y solo publica una sesión devuelta por éste (`public/src/api/aplicacion.py:450-461`; `public/src/api/puertos.py:190-198`). |
| API-12 | **Correcto** | La ausencia de cookie de acceso produce sesión inválida; los rechazos del backend se traducen a un error cerrado sin ruta alternativa (`public/src/api/aplicacion.py:450-455`; `public/src/api/problemas.py:143-149`). |
| API-13 | **Correcto** | Renovación exige cookie, CSRF y límite específico, y solo emite nuevas cookies después de que el backend complete la rotación (`public/src/api/aplicacion.py:428-448`). |
| API-14 | **Correcto** | La prueba concurrente presenta seis renovaciones del mismo token y verifica exactamente un `204` y cinco rechazos `401` (`public/src/api/test_api_autenticacion.py:712-737`). |
| API-15 | **Correcto** | Cookies CSRF, flujo, acceso y renovación usan `Secure`, `HttpOnly`, `SameSite=Strict`, carecen de `Domain` y tienen duraciones limitadas (`public/src/api/seguridad_http.py:294-380`). |
| API-16 | **Correcto** | La capa HTTP emite acceso y renovación conjuntamente solo después de un resultado completo; no existe una ruta de emisión parcial (`public/src/api/aplicacion.py:146-163,428-448`). |
| API-17 | **Correcto** | Rotación, reutilización y revocación son operaciones obligatorias del puerto backend; un rechazo no genera credenciales (`public/src/api/puertos.py:104-127,190-198`; `public/src/api/problemas.py:129-180`). |
| API-18 | **Correcto** | La cookie de renovación tiene exactamente `Path=/api/v1/sesiones/renovar` al emitirse y eliminarse (`public/src/api/seguridad_http.py:27-30,355-397`). |
| API-19 | **Correcto** | Unicidad, sesión única y atomicidad permanecen en el puerto backend obligatorio; la API no contiene rutas permisivas que omitan esas operaciones (`public/src/api/puertos.py:102-128`; `public/src/api/ensamblaje.py:11-52`). |
| API-20 | **Correcto** | Encabezados reenviados solo se consideran cuando la conexión directa pertenece a una red configurada como confiable; las claves de límite se anonimizan con HMAC (`public/src/api/seguridad_http.py:60-118`). |
| API-21 | **Correcto** | Fallos de limitación, fachada, configuración, ensamblaje y cierre producen respuestas cerradas sin conceder acceso ni filtrar excepciones (`public/src/api/seguridad_http.py:134-159,240-268`; `public/src/api/problemas.py:129-206`; `public/src/api/ensamblaje.py:31-52`). |
| API-22 | **Correcto** | La suite cubre rutas, cuerpos, estados, validaciones, CSRF, cookies, concurrencia de límites y renovación, y excepciones de todas las fases (`public/src/api/test_api_autenticacion.py:372-960`). |

### CSRF y cookies

- `GET /api/v1/seguridad/csrf` entrega el token firmado en `X-CSRF-Token` y establece una cookie protegida (`public/src/api/aplicacion.py:188-190`; `public/src/api/seguridad_http.py:294-316`).
- Toda mutación funcional llama a la validación CSRF antes de delegar al backend (`public/src/api/aplicacion.py:143-144,192-499`).
- La validación compara en tiempo constante cookie, valor del encabezado y firma HMAC (`public/src/api/seguridad_http.py:318-340`).
- El middleware exige `Origin` en mutaciones y rechaza orígenes distintos (`public/src/api/seguridad_http.py:180-196`).
- Después de completar autenticación se rotan las credenciales y el token CSRF; los errores mantienen formato consumible por el Frontend (`public/src/api/aplicacion.py:146-163`; `public/src/api/problemas.py:42-71`).
- La cookie de renovación no se envía a registro, verificación, login, WebAuthn, códigos, estado ni cierre por su ruta exacta (`public/src/api/seguridad_http.py:27-30,365-397`).

### Pruebas y controles ejecutados

1. `python -m pytest -p no:cacheprovider -q public/src/api`, con escritura de bytecode desactivada:
   - Total: 31.
   - Correctas: 31.
   - Fallidas: 0.
   - Advertencias: 1 deprecación externa del complemento asíncrono bajo Python 3.14.
2. `python -m ruff check public/src/api`:
   - Resultado: correcto, sin hallazgos.
3. `python -m ruff format --check public/src/api`:
   - Resultado: 9 archivos ya formateados.
4. `python -m compileall -q public/src/api`, con `PYTHONPYCACHEPREFIX` fuera del árbol:
   - Resultado: correcto.
5. `git diff --check HEAD^ HEAD`:
   - Resultado: correcto, sin salida.
6. Comparación automática con los módulos productivos del Frontend publicado:
   - Rutas funcionales consumidas: 14.
   - Métodos o rutas ausentes: 0.
   - Ruta CSRF: presente.
   - Ruta explícita de renovación: presente.
7. Versiones del entorno:
   - Python `3.14.5`.
   - pytest `8.4.2`.
   - Ruff `0.14.5`.
8. Verificación posterior:
   - Los árboles de API y Frontend continuaron limpios.

### Veredicto final de API

**Correcto.**

API-01..API-22 cumplen los criterios evaluados. Backend permanece pendiente de corrección.
