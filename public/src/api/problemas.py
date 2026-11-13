"""Errores HTTP uniformes según RFC 9457."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as ExcepcionHttpStarlette

from .puertos import CodigoErrorFachada, ErrorFachada


@dataclass(frozen=True, slots=True)
class ErrorCampo:
    campo: str
    codigo: str


class ProblemaHttp(Exception):
    def __init__(
        self,
        estado: int,
        codigo: str,
        titulo: str,
        detalle: str,
        *,
        errores: tuple[ErrorCampo, ...] = (),
        encabezados: dict[str, str] | None = None,
    ) -> None:
        super().__init__(codigo)
        self.estado = estado
        self.codigo = codigo
        self.titulo = titulo
        self.detalle = detalle
        self.errores = errores
        self.encabezados = encabezados or {}


def respuesta_problema(
    problema: ProblemaHttp,
    identificador_solicitud: str,
    ruta: str,
) -> JSONResponse:
    contenido: dict[str, Any] = {
        "type": f"https://errores.local/{problema.codigo.lower()}",
        "title": problema.titulo,
        "status": problema.estado,
        "detail": problema.detalle,
        "mensaje": problema.detalle,
        "instance": ruta,
        "codigo": problema.codigo,
        "idSolicitud": identificador_solicitud,
    }
    if problema.errores:
        contenido["errores"] = [
            {"campo": error.campo, "codigo": error.codigo} for error in problema.errores
        ]
        contenido["campos"] = {
            error.campo: "Revisa el valor proporcionado." for error in problema.errores
        }
    if problema.estado == 429 and "Retry-After" in problema.encabezados:
        contenido["reintentar_en"] = int(problema.encabezados["Retry-After"])
    return JSONResponse(
        status_code=problema.estado,
        content=contenido,
        media_type='application/problem+json; compatible="application/json"',
        headers=problema.encabezados,
    )


def _campo_desde_ubicacion(ubicacion: tuple[Any, ...]) -> str:
    partes = [
        str(parte) for parte in ubicacion if parte not in {"body", "query", "path"}
    ]
    return ".".join(partes) or "solicitud"


def _codigo_validacion(tipo: str) -> str:
    if tipo == "extra_forbidden":
        return "CAMPO_NO_PERMITIDO"
    if tipo in {"missing", "value_error.missing"}:
        return "CAMPO_OBLIGATORIO"
    if "json" in tipo:
        return "JSON_INVALIDO"
    if "string_too_short" in tipo:
        return "LONGITUD_MINIMA"
    if "string_too_long" in tipo:
        return "LONGITUD_MAXIMA"
    return "VALOR_INVALIDO"


def instalar_manejadores_problemas(aplicacion: FastAPI) -> None:
    @aplicacion.exception_handler(ProblemaHttp)
    async def manejar_problema(request: Request, error: ProblemaHttp) -> JSONResponse:
        return respuesta_problema(
            error,
            request.state.id_solicitud,
            request.url.path,
        )

    @aplicacion.exception_handler(RequestValidationError)
    async def manejar_validacion(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        errores = tuple(
            ErrorCampo(
                campo=_campo_desde_ubicacion(tuple(detalle.get("loc", ()))),
                codigo=_codigo_validacion(str(detalle.get("type", ""))),
            )
            for detalle in error.errors()
        )
        json_invalido = any(item.codigo == "JSON_INVALIDO" for item in errores)
        problema = ProblemaHttp(
            400 if json_invalido else 422,
            "JSON_INVALIDO" if json_invalido else "SOLICITUD_INVALIDA",
            "JSON inválido" if json_invalido else "Solicitud inválida",
            "El cuerpo no contiene JSON válido."
            if json_invalido
            else "Hay campos que requieren corrección.",
            errores=errores,
        )
        return respuesta_problema(
            problema, request.state.id_solicitud, request.url.path
        )

    @aplicacion.exception_handler(ErrorFachada)
    async def manejar_error_fachada(
        request: Request, error: ErrorFachada
    ) -> JSONResponse:
        if error.codigo in {
            CodigoErrorFachada.CREDENCIALES_INVALIDAS,
            CodigoErrorFachada.NO_AUTORIZADO,
        }:
            problema = ProblemaHttp(
                401,
                "CREDENCIALES_INVALIDAS",
                "Autenticación rechazada",
                "No fue posible completar la autenticación.",
            )
        elif error.codigo == CodigoErrorFachada.SESION_INVALIDA:
            problema = ProblemaHttp(
                401,
                "SESION_INVALIDA",
                "Sesión inválida",
                "No hay una sesión activa.",
            )
        elif error.codigo == CodigoErrorFachada.VERIFICACION_INVALIDA:
            problema = ProblemaHttp(
                400,
                "CREDENCIAL_VERIFICACION_INVALIDA",
                "Credencial inválida",
                "La credencial es inválida, expiró o ya fue utilizada.",
            )
        elif error.codigo == CodigoErrorFachada.CODIGO_RESPALDO_INVALIDO:
            problema = ProblemaHttp(
                400,
                "CODIGO_RESPALDO_INVALIDO",
                "Credencial inválida",
                "La credencial es inválida, expiró o ya fue utilizada.",
            )
        elif error.codigo == CodigoErrorFachada.FLUJO_INVALIDO:
            problema = ProblemaHttp(
                400,
                "FLUJO_INVALIDO",
                "Flujo inválido",
                "El proceso es inválido, expiró o ya fue utilizado.",
            )
        else:
            problema = ProblemaHttp(
                503,
                "SERVICIO_NO_DISPONIBLE",
                "Servicio no disponible",
                "No fue posible completar la operación.",
            )
        return respuesta_problema(
            problema, request.state.id_solicitud, request.url.path
        )

    @aplicacion.exception_handler(ExcepcionHttpStarlette)
    async def manejar_http(
        request: Request, error: ExcepcionHttpStarlette
    ) -> JSONResponse:
        problema = ProblemaHttp(
            error.status_code,
            "RECURSO_NO_DISPONIBLE",
            "Recurso no disponible",
            "La operación solicitada no está disponible.",
        )
        return respuesta_problema(
            problema, request.state.id_solicitud, request.url.path
        )

    @aplicacion.exception_handler(Exception)
    async def manejar_inesperado(request: Request, _: Exception) -> JSONResponse:
        problema = ProblemaHttp(
            500,
            "ERROR_INTERNO",
            "Error interno",
            "No fue posible completar la operación.",
        )
        return respuesta_problema(
            problema, request.state.id_solicitud, request.url.path
        )
