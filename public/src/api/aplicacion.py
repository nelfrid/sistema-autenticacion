"""Aplicación FastAPI y contratos HTTP de autenticación."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request, Response, status

from .configuracion import ConfiguracionApi
from .esquemas import (
    CodigoRespaldoEntrada,
    CompletarAutenticacionWebAuthnEntrada,
    CompletarRegistroWebAuthnEntrada,
    ConfirmacionCodigosRespaldoEntrada,
    InicioSesionEntrada,
    ReenvioVerificacionEntrada,
    RegistroEntrada,
    VerificacionCorreoEntrada,
)
from .problemas import ProblemaHttp, instalar_manejadores_problemas, respuesta_problema
from .puertos import (
    CodigoErrorFachada,
    ErrorFachada,
    EstadoInicioSesion,
    FachadaAutenticacion,
    ResultadoAutenticacion,
    SolicitudLimite,
    SolicitudRegistro,
)
from .seguridad_http import (
    NOMBRE_COOKIE_ACCESO,
    NOMBRE_COOKIE_FLUJO,
    NOMBRE_COOKIE_RENOVACION,
    GestorCsrf,
    MiddlewareSeguridadHttp,
    _direccion_cliente,
    clave_anonima,
    eliminar_credenciales,
    guardar_credenciales,
    guardar_flujo,
)


CODIGOS_INICIO_SESION = {
    EstadoInicioSesion.ALTA_WEBAUTHN_REQUERIDA: "CONFIGURACION_WEBAUTHN_REQUERIDA",
    EstadoInicioSesion.WEBAUTHN_REQUERIDO: "DESAFIO_WEBAUTHN_REQUERIDO",
    EstadoInicioSesion.CONFLICTO_SESION: "CONFLICTO_SESION",
    EstadoInicioSesion.VERIFICACION_CORREO_PENDIENTE: "VERIFICACION_CORREO_PENDIENTE",
}


def _exigir_flujo(request: Request) -> str:
    identificador = request.cookies.get(NOMBRE_COOKIE_FLUJO, "")
    if not identificador:
        raise ProblemaHttp(
            400,
            "FLUJO_INVALIDO",
            "Flujo inválido",
            "El proceso es inválido, expiró o ya fue utilizado.",
        )
    return identificador


def _serializar_webauthn(valor: Any) -> Any:
    """Copia defensiva que limita la fachada a valores JSON."""

    if isinstance(valor, Mapping):
        return {
            str(clave): _serializar_webauthn(contenido)
            for clave, contenido in valor.items()
        }
    if isinstance(valor, (list, tuple)):
        return [_serializar_webauthn(contenido) for contenido in valor]
    if isinstance(valor, (str, int, float, bool)) or valor is None:
        return valor
    raise ProblemaHttp(
        503,
        "RESPUESTA_BACKEND_INVALIDA",
        "Servicio no disponible",
        "No fue posible preparar el desafío de autenticación.",
    )


async def _consumir_limite(
    request: Request,
    fachada: FachadaAutenticacion,
    configuracion: ConfiguracionApi,
    *,
    ambito: str,
    factor: str,
    limite: int,
    ventana: int,
) -> None:
    direccion = _direccion_cliente(request, configuracion)
    try:
        resultado = await fachada.consumir_limite(
            SolicitudLimite(
                ambito=ambito,
                clave_anonima=clave_anonima(configuracion, direccion, factor),
                limite=limite,
                ventana_segundos=ventana,
            )
        )
    except Exception as error:
        raise ProblemaHttp(
            503,
            "LIMITACION_NO_DISPONIBLE",
            "Servicio no disponible",
            "No fue posible validar la frecuencia de la solicitud.",
        ) from error
    if not resultado.permitido:
        raise ProblemaHttp(
            429,
            "LIMITE_EXCEDIDO",
            "Demasiadas solicitudes",
            "Inténtalo de nuevo más tarde.",
            encabezados={"Retry-After": str(max(1, resultado.reintentar_en_segundos))},
        )


def crear_aplicacion(
    fachada: FachadaAutenticacion,
    configuracion: ConfiguracionApi,
) -> FastAPI:
    """Construye la API; no existe una fachada implícita ni permisiva."""

    aplicacion = FastAPI(
        title="API de autenticación",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    gestor_csrf = GestorCsrf(configuracion)
    instalar_manejadores_problemas(aplicacion)
    aplicacion.add_middleware(
        MiddlewareSeguridadHttp,
        configuracion=configuracion,
        fachada=fachada,
    )

    def validar_csrf(request: Request) -> None:
        gestor_csrf.validar(request)

    def completar_autenticacion(
        response: Response,
        resultado: ResultadoAutenticacion,
    ) -> dict[str, str]:
        guardar_credenciales(
            response,
            resultado.credenciales.token_acceso,
            resultado.credenciales.token_renovacion,
        )
        gestor_csrf.emitir(response)
        return {
            "codigo": (
                "CONFLICTO_SESION_RESUELTO"
                if resultado.conflicto_resuelto
                else "AUTENTICADO"
            ),
            "mensaje": "La autenticación se completó correctamente.",
        }

    async def obtener_opciones(
        request: Request,
        operacion: Any,
        *,
        ambito: str,
    ) -> dict[str, Any]:
        validar_csrf(request)
        identificador_flujo = _exigir_flujo(request)
        await _consumir_limite(
            request,
            fachada,
            configuracion,
            ambito=ambito,
            factor=identificador_flujo,
            limite=10,
            ventana=15 * 60,
        )
        opciones = await operacion(identificador_flujo)
        return {
            "codigo": "OPCIONES_WEBAUTHN",
            "opciones": _serializar_webauthn(opciones),
        }

    @aplicacion.get("/api/v1/seguridad/csrf", status_code=status.HTTP_204_NO_CONTENT)
    async def obtener_csrf(response: Response) -> None:
        gestor_csrf.emitir(response)

    @aplicacion.post("/api/v1/registros", status_code=status.HTTP_202_ACCEPTED)
    async def registrar(datos: RegistroEntrada, request: Request) -> dict[str, str]:
        validar_csrf(request)
        versiones_requeridas = {
            configuracion.version_terminos,
            configuracion.version_privacidad,
        }
        if set(datos.aceptaciones) != versiones_requeridas:
            raise ProblemaHttp(
                422,
                "ACEPTACIONES_INVALIDAS",
                "Aceptaciones inválidas",
                "Deben aceptarse las versiones vigentes de términos y privacidad.",
            )
        correo = str(datos.correo)
        await _consumir_limite(
            request,
            fachada,
            configuracion,
            ambito="registro_correo",
            factor=correo,
            limite=3,
            ventana=60 * 60,
        )
        try:
            await fachada.registrar(
                SolicitudRegistro(
                    nombre_completo=datos.nombre_completo,
                    correo=correo,
                    contrasena=datos.contrasena,
                    version_terminos=configuracion.version_terminos,
                    version_privacidad=configuracion.version_privacidad,
                )
            )
        except ErrorFachada as error:
            if error.codigo != CodigoErrorFachada.CORREO_EXISTENTE:
                raise
        return {
            "codigo": "REGISTRO_RECIBIDO",
            "mensaje": "Si la información puede utilizarse, recibirás instrucciones para continuar.",
            "id_solicitud": request.state.id_solicitud,
        }

    @aplicacion.post("/api/v1/verificaciones-correo/confirmar")
    async def verificar_correo(
        datos: VerificacionCorreoEntrada,
        request: Request,
    ) -> dict[str, str]:
        validar_csrf(request)
        await _consumir_limite(
            request,
            fachada,
            configuracion,
            ambito="verificacion_correo",
            factor=datos.credencial,
            limite=10,
            ventana=15 * 60,
        )
        await fachada.verificar_correo(datos.credencial)
        return {
            "codigo": "CORREO_VERIFICADO",
            "mensaje": "El correo se verificó correctamente.",
        }

    @aplicacion.post(
        "/api/v1/verificaciones-correo/reenviar",
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def reenviar_verificacion(
        datos: ReenvioVerificacionEntrada,
        request: Request,
    ) -> dict[str, str]:
        validar_csrf(request)
        correo = str(datos.correo)
        await _consumir_limite(
            request,
            fachada,
            configuracion,
            ambito="reenvio_verificacion",
            factor=correo,
            limite=3,
            ventana=60 * 60,
        )
        try:
            await fachada.reenviar_verificacion(correo)
        except ErrorFachada as error:
            if error.codigo not in {
                CodigoErrorFachada.CREDENCIALES_INVALIDAS,
                CodigoErrorFachada.VERIFICACION_INVALIDA,
            }:
                raise
        return {
            "codigo": "REENVIO_VERIFICACION_RECIBIDO",
            "mensaje": "Si corresponde, recibirás un enlace nuevo.",
            "id_solicitud": request.state.id_solicitud,
        }

    @aplicacion.post("/api/v1/sesiones/iniciar", status_code=status.HTTP_202_ACCEPTED)
    async def iniciar_sesion(
        datos: InicioSesionEntrada,
        request: Request,
        response: Response,
    ) -> dict[str, str]:
        validar_csrf(request)
        correo = str(datos.correo)
        await _consumir_limite(
            request,
            fachada,
            configuracion,
            ambito="inicio_sesion",
            factor=correo,
            limite=10,
            ventana=15 * 60,
        )
        resultado = await fachada.iniciar_sesion(correo, datos.contrasena)
        guardar_flujo(response, resultado.identificador_flujo)
        return {
            "codigo": CODIGOS_INICIO_SESION[resultado.estado],
            "mensaje": "Se requiere completar el proceso de autenticación.",
        }

    @aplicacion.post("/api/v1/webauthn/registro/opciones")
    async def opciones_registro_webauthn(request: Request) -> dict[str, Any]:
        return await obtener_opciones(
            request,
            fachada.opciones_alta_webauthn,
            ambito="opciones_registro_webauthn",
        )

    @aplicacion.post("/api/v1/webauthn/registro/completar")
    async def completar_registro_webauthn(
        datos: CompletarRegistroWebAuthnEntrada,
        request: Request,
    ) -> dict[str, str]:
        validar_csrf(request)
        identificador_flujo = _exigir_flujo(request)
        await _consumir_limite(
            request,
            fachada,
            configuracion,
            ambito="confirmacion_registro_webauthn",
            factor=identificador_flujo,
            limite=5,
            ventana=15 * 60,
        )
        await fachada.confirmar_alta_webauthn(
            identificador_flujo,
            datos.credencial.model_dump(by_alias=True),
        )
        return {
            "codigo": "WEBAUTHN_CONFIGURADO",
            "mensaje": "La passkey se configuró correctamente.",
        }

    @aplicacion.get("/api/v1/codigos-respaldo/pendientes")
    async def obtener_codigos_respaldo(request: Request) -> dict[str, Any]:
        identificador_flujo = _exigir_flujo(request)
        codigos = await fachada.obtener_codigos_respaldo_pendientes(identificador_flujo)
        return {"codigo": "CODIGOS_RESPALDO_PENDIENTES", "codigos": list(codigos)}

    @aplicacion.post("/api/v1/codigos-respaldo/confirmar")
    async def confirmar_codigos_respaldo(
        _: ConfirmacionCodigosRespaldoEntrada,
        request: Request,
        response: Response,
    ) -> dict[str, str]:
        validar_csrf(request)
        identificador_flujo = _exigir_flujo(request)
        resultado = await fachada.confirmar_resguardo_codigos(identificador_flujo)
        return completar_autenticacion(response, resultado)

    @aplicacion.post("/api/v1/webauthn/autenticacion/opciones")
    async def opciones_autenticacion_webauthn(request: Request) -> dict[str, Any]:
        return await obtener_opciones(
            request,
            fachada.opciones_autenticacion_webauthn,
            ambito="opciones_autenticacion_webauthn",
        )

    @aplicacion.post("/api/v1/webauthn/autenticacion/completar")
    async def completar_autenticacion_webauthn(
        datos: CompletarAutenticacionWebAuthnEntrada,
        request: Request,
        response: Response,
    ) -> dict[str, str]:
        validar_csrf(request)
        identificador_flujo = _exigir_flujo(request)
        await _consumir_limite(
            request,
            fachada,
            configuracion,
            ambito="confirmacion_autenticacion_webauthn",
            factor=identificador_flujo,
            limite=5,
            ventana=15 * 60,
        )
        resultado = await fachada.confirmar_autenticacion_webauthn(
            identificador_flujo,
            datos.credencial.model_dump(by_alias=True),
        )
        return completar_autenticacion(response, resultado)

    @aplicacion.post("/api/v1/webauthn/autenticacion/codigo-respaldo")
    async def autenticar_codigo_respaldo(
        datos: CodigoRespaldoEntrada,
        request: Request,
        response: Response,
    ) -> dict[str, str]:
        validar_csrf(request)
        identificador_flujo = _exigir_flujo(request)
        await _consumir_limite(
            request,
            fachada,
            configuracion,
            ambito="codigo_respaldo",
            factor=identificador_flujo,
            limite=5,
            ventana=15 * 60,
        )
        resultado = await fachada.confirmar_codigo_respaldo(
            identificador_flujo,
            datos.codigo_respaldo,
        )
        return completar_autenticacion(response, resultado)

    @aplicacion.get("/api/v1/sesiones/conflicto")
    async def obtener_conflicto_sesion(request: Request) -> dict[str, str]:
        conflicto = await fachada.obtener_conflicto_sesion(_exigir_flujo(request))
        return {
            "codigo": "CONFLICTO_SESION",
            "inicio_aproximado": conflicto.inicio_aproximado.isoformat(
                timespec="minutes"
            ),
            "dispositivo": conflicto.dispositivo,
        }

    @aplicacion.post("/api/v1/sesiones/renovar", status_code=status.HTTP_204_NO_CONTENT)
    async def renovar_sesion(request: Request, response: Response) -> None:
        validar_csrf(request)
        token = request.cookies.get(NOMBRE_COOKIE_RENOVACION, "")
        if not token:
            raise ErrorFachada(CodigoErrorFachada.SESION_INVALIDA)
        await _consumir_limite(
            request,
            fachada,
            configuracion,
            ambito="renovacion_sesion",
            factor=token,
            limite=30,
            ventana=5 * 60,
        )
        credenciales = await fachada.renovar_sesion(token)
        guardar_credenciales(
            response,
            credenciales.token_acceso,
            credenciales.token_renovacion,
        )

    @aplicacion.get("/api/v1/sesiones/actual")
    async def obtener_sesion(request: Request) -> dict[str, Any]:
        token = request.cookies.get(NOMBRE_COOKIE_ACCESO, "")
        if not token:
            raise ErrorFachada(CodigoErrorFachada.SESION_INVALIDA)
        sesion = await fachada.obtener_sesion(token)
        return {
            "codigo": "SESION_ACTIVA",
            "correo": sesion.correo,
            "vencimiento_absoluto": sesion.expira_en.isoformat(),
            "vencimiento_inactividad": sesion.expira_por_inactividad_en.isoformat(),
        }

    @aplicacion.post("/api/v1/sesiones/cerrar", response_model=None)
    async def cerrar_sesion(
        request: Request,
        response: Response,
    ) -> dict[str, str] | Response:
        validar_csrf(request)
        acceso = request.cookies.get(NOMBRE_COOKIE_ACCESO)
        await _consumir_limite(
            request,
            fachada,
            configuracion,
            ambito="cierre_sesion",
            factor=acceso or "sin_sesion",
            limite=20,
            ventana=60,
        )
        try:
            await fachada.cerrar_sesion(acceso, None)
        except Exception:  # noqa: BLE001 -- el cierre debe borrar cookies incluso ante fallo interno.
            problema = respuesta_problema(
                ProblemaHttp(
                    500,
                    "ERROR_INTERNO",
                    "Error interno",
                    "No fue posible completar la operación.",
                ),
                request.state.id_solicitud,
                request.url.path,
            )
            eliminar_credenciales(problema)
            return problema
        else:
            eliminar_credenciales(response)
        return {
            "codigo": "SESION_CERRADA",
            "mensaje": "La sesión se cerró correctamente.",
        }

    return aplicacion
