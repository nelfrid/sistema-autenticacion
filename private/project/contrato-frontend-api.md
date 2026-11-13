# Contrato mínimo entre frontend y API

## Convenciones

- Base relativa de mismo origen: `/api/v1`.
- Solicitudes y respuestas: JSON UTF-8, excepto cuando una respuesta no necesite cuerpo.
- Las credenciales de preautenticación, sesión y renovación se administran mediante cookies seguras; nunca se devuelven a JavaScript.
- Las operaciones mutables envían `X-CSRF-Token`. El frontend obtiene el valor desde `/seguridad/csrf`, lo conserva solo en memoria y acepta su rotación mediante el mismo encabezado de respuesta.
- Toda respuesta relacionada con autenticación debe incluir `Cache-Control: no-store`.
- Los errores utilizan códigos funcionales estables en español:

```json
{
  "codigo": "CODIGO_FUNCIONAL",
  "mensaje": "Mensaje seguro para la persona usuaria.",
  "campos": {
    "nombre_campo": "Corrección necesaria."
  },
  "reintentar_en": 30
}
```

`campos` y `reintentar_en` son opcionales. Un límite de frecuencia también debe enviar `Retry-After`.

## Operaciones consumidas

| Método y ruta | Solicitud principal | Respuesta necesaria |
| --- | --- | --- |
| `GET /seguridad/csrf` | Cookie de mismo origen, sin cuerpo | `token_csrf` opaco; también puede entregarse en `X-CSRF-Token` |
| `POST /registros` | Nombre, correo, contraseña exacta, confirmación y versiones aceptadas | `REGISTRO_RECIBIDO` con mensaje anti-enumeración |
| `POST /verificaciones-correo/confirmar` | Credencial opaca | `CORREO_VERIFICADO` |
| `POST /verificaciones-correo/reenviar` | Correo | `REENVIO_VERIFICACION_RECIBIDO` anti-enumeración |
| `POST /sesiones/iniciar` | Correo y contraseña exacta | Uno de los siguientes estados de autenticación |
| `POST /webauthn/registro/opciones` | Sin datos sensibles; usa preautenticación restringida | `opciones` compatibles con `navigator.credentials.create` |
| `POST /webauthn/registro/completar` | Credencial WebAuthn serializada | `WEBAUTHN_CONFIGURADO` |
| `GET /codigos-respaldo/pendientes` | Preautenticación restringida | `codigos`, disponibles hasta confirmarlos |
| `POST /codigos-respaldo/confirmar` | Confirmación de resguardo | Establece la sesión completa y devuelve `AUTENTICADO` |
| `POST /webauthn/autenticacion/opciones` | Preautenticación restringida | `opciones` compatibles con `navigator.credentials.get` |
| `POST /webauthn/autenticacion/completar` | Aserción WebAuthn serializada | `AUTENTICADO` o `CONFLICTO_SESION_RESUELTO` |
| `POST /webauthn/autenticacion/codigo-respaldo` | Código exacto de un solo uso | `AUTENTICADO`; no se admite para resolver conflictos de sesión |
| `GET /sesiones/conflicto` | Preautenticación restringida | `inicio_aproximado` y `dispositivo`, sin datos sensibles |
| `GET /sesiones/actual` | Cookies de sesión | Correo y `vencimiento_absoluto` |
| `POST /sesiones/cerrar` | Cookies de sesión | `SESION_CERRADA` y revocación de renovación |

## Estados devueltos por el inicio de sesión

- `AUTENTICADO`
- `VERIFICACION_CORREO_PENDIENTE`
- `CONFIGURACION_WEBAUTHN_REQUERIDA`
- `DESAFIO_WEBAUTHN_REQUERIDO`
- `CONFLICTO_SESION`

Los errores de cuenta inexistente, contraseña incorrecta o estado no revelable deben converger en una respuesta genérica como `CREDENCIALES_INVALIDAS`.

## Condiciones de seguridad del servidor

- Conservar la contraseña exactamente como se recibe; no aplicar `trim`, normalización ni truncamiento.
- Aplicar 15 a 128 caracteres y comprobar contraseñas comprometidas en el servidor.
- Mantener la verificación opaca con uso único y vencimiento de 30 minutos.
- Mantener la preautenticación restringida hasta completar correo, configuración o desafío WebAuthn y códigos de respaldo.
- En un conflicto, bloquear ambas sesiones; después de WebAuthn, revocar la anterior y establecer la nueva de forma atómica.
- Aplicar 8 horas de duración absoluta, 30 minutos de inactividad y 5 minutos para el Access Token sin ampliar el límite absoluto.
- Proteger cookies con `HttpOnly`, `Secure`, alcance mínimo y una política `SameSite` adecuada.
- Validar `Origin` y aplicar la defensa CSRF acordada para operaciones con cookies.
- Rechazar tokens CSRF ausentes, vencidos o inválidos mediante códigos `CSRF_*`; una operación mutable rechazada no debe ejecutarse ni solicitarse de nuevo automáticamente.
- Definir CSP y protección contra inclusión en marcos mediante cabeceras HTTP; las etiquetas HTML son defensa complementaria.
- No registrar contraseñas, credenciales opacas, aserciones completas, códigos de respaldo ni cookies.
