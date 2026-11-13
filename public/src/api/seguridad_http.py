"""Controles HTTP, CSRF, cookies y limitación de frecuencia."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import secrets
import uuid
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlsplit

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as RespuestaStarlette

from .configuracion import ConfiguracionApi
from .problemas import ProblemaHttp, respuesta_problema
from .puertos import FachadaAutenticacion, SolicitudLimite

NOMBRE_COOKIE_CSRF = "__Secure-csrf"
NOMBRE_COOKIE_ACCESO = "__Secure-acceso"
NOMBRE_COOKIE_RENOVACION = "__Secure-renovacion"
NOMBRE_COOKIE_FLUJO = "__Secure-flujo-autenticacion"

RUTA_API = "/api/v1"
RUTA_FLUJO = "/api/v1"
RUTA_COOKIE_RENOVACION = "/api/v1/sesiones/renovar"


def _problema(
    request: Request,
    estado: int,
    codigo: str,
    titulo: str,
    detalle: str,
    *,
    encabezados: dict[str, str] | None = None,
) -> RespuestaStarlette:
    return respuesta_problema(
        ProblemaHttp(estado, codigo, titulo, detalle, encabezados=encabezados),
        request.state.id_solicitud,
        request.url.path,
    )


def _origen_canonico(valor: str) -> str | None:
    try:
        partes = urlsplit(valor)
    except ValueError:
        return None
    if partes.scheme not in {"http", "https"} or not partes.netloc:
        return None
    if partes.path not in {"", "/"} or partes.query or partes.fragment:
        return None
    return f"{partes.scheme.lower()}://{partes.netloc.lower()}"


def _direccion_cliente(request: Request, configuracion: ConfiguracionApi) -> str:
    directa = request.client.host if request.client else ""
    try:
        ipaddress.ip_address(directa)
    except ValueError as error:
        raise ProblemaHttp(
            400,
            "DIRECCION_INVALIDA",
            "Solicitud inválida",
            "No fue posible determinar el origen de la solicitud.",
        ) from error

    if not configuracion.es_proxy_confiable(directa):
        return directa

    cadena = request.headers.get("x-forwarded-for", "")
    if not cadena:
        return directa
    direcciones = [parte.strip() for parte in cadena.split(",") if parte.strip()]
    direcciones.append(directa)
    try:
        for direccion in direcciones:
            ipaddress.ip_address(direccion)
    except ValueError as error:
        raise ProblemaHttp(
            400,
            "DIRECCION_INVALIDA",
            "Solicitud inválida",
            "No fue posible determinar el origen de la solicitud.",
        ) from error

    for direccion in reversed(direcciones):
        if not configuracion.es_proxy_confiable(direccion):
            return direccion
    return direcciones[0]


def _origen_efectivo(request: Request, configuracion: ConfiguracionApi) -> str | None:
    directa = request.client.host if request.client else ""
    proxy_confiable = configuracion.es_proxy_confiable(directa)
    esquema = request.url.scheme
    host = request.headers.get("host", "")
    if proxy_confiable:
        protocolos = request.headers.get("x-forwarded-proto", "")
        hosts = request.headers.get("x-forwarded-host", "")
        if protocolos:
            esquema = protocolos.split(",")[-1].strip().lower()
        if hosts:
            host = hosts.split(",")[-1].strip().lower()
    if esquema not in {"http", "https"} or not host:
        return None
    return f"{esquema.lower()}://{host.lower()}"


def clave_anonima(configuracion: ConfiguracionApi, *partes: str) -> str:
    contenido = "\x1f".join(partes).encode("utf-8")
    return hmac.new(
        configuracion.secreto_limitacion, contenido, hashlib.sha256
    ).hexdigest()


class MiddlewareSeguridadHttp(BaseHTTPMiddleware):
    """Aplica controles antes de que FastAPI interprete el cuerpo."""

    def __init__(
        self,
        aplicacion: Any,
        configuracion: ConfiguracionApi,
        fachada: FachadaAutenticacion,
    ) -> None:
        super().__init__(aplicacion)
        self.configuracion = configuracion
        self.fachada = fachada

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[RespuestaStarlette]],
    ) -> RespuestaStarlette:
        request.state.id_solicitud = str(uuid.uuid4())
        respuesta: RespuestaStarlette
        try:
            respuesta_temprana = await self._validar(request)
            respuesta = respuesta_temprana or await call_next(request)
        except ProblemaHttp as error:
            respuesta = respuesta_problema(
                error,
                request.state.id_solicitud,
                request.url.path,
            )
        except Exception:  # noqa: BLE001 -- la frontera HTTP no expone excepciones internas.
            respuesta = _problema(
                request,
                500,
                "ERROR_INTERNO",
                "Error interno",
                "No fue posible procesar la solicitud.",
            )
        self._agregar_encabezados(request, respuesta)
        return respuesta

    async def _validar(self, request: Request) -> RespuestaStarlette | None:
        origen_efectivo = _origen_efectivo(request, self.configuracion)
        if origen_efectivo != self.configuracion.origen_normalizado:
            return _problema(
                request,
                400,
                "DESTINO_INVALIDO",
                "Solicitud inválida",
                "El destino de la solicitud no es válido.",
            )
        if not origen_efectivo.startswith("https://"):
            return _problema(
                request,
                400,
                "HTTPS_REQUERIDO",
                "HTTPS requerido",
                "La solicitud requiere una conexión segura.",
            )

        origen = request.headers.get("origin")
        if origen and _origen_canonico(origen) != self.configuracion.origen_normalizado:
            return _problema(
                request,
                403,
                "ORIGEN_RECHAZADO",
                "Origen rechazado",
                "El origen de la solicitud no está autorizado.",
            )
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not origen:
            return _problema(
                request,
                403,
                "ORIGEN_REQUERIDO",
                "Origen requerido",
                "No fue posible validar el origen de la solicitud.",
            )

        longitud = request.headers.get("content-length")
        if longitud:
            try:
                if int(longitud) > self.configuracion.limite_cuerpo_bytes:
                    return _problema(
                        request,
                        413,
                        "CUERPO_DEMASIADO_GRANDE",
                        "Solicitud demasiado grande",
                        "El cuerpo supera el tamaño permitido.",
                    )
            except ValueError:
                return _problema(
                    request,
                    400,
                    "LONGITUD_INVALIDA",
                    "Solicitud inválida",
                    "La longitud declarada no es válida.",
                )

        cuerpo = await request.body()
        if len(cuerpo) > self.configuracion.limite_cuerpo_bytes:
            return _problema(
                request,
                413,
                "CUERPO_DEMASIADO_GRANDE",
                "Solicitud demasiado grande",
                "El cuerpo supera el tamaño permitido.",
            )
        if cuerpo:
            contenido = (
                request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            )
            if contenido != "application/json":
                return _problema(
                    request,
                    415,
                    "FORMATO_NO_ADMITIDO",
                    "Formato no admitido",
                    "El cuerpo debe usar application/json.",
                )

        if request.url.path.startswith(RUTA_API):
            direccion = _direccion_cliente(request, self.configuracion)
            try:
                resultado = await self.fachada.consumir_limite(
                    SolicitudLimite(
                        ambito="http_global",
                        clave_anonima=clave_anonima(self.configuracion, direccion),
                        limite=self.configuracion.limite_global,
                        ventana_segundos=self.configuracion.ventana_global_segundos,
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
                segundos = max(1, resultado.reintentar_en_segundos)
                return _problema(
                    request,
                    429,
                    "LIMITE_EXCEDIDO",
                    "Demasiadas solicitudes",
                    "Inténtalo de nuevo más tarde.",
                    encabezados={"Retry-After": str(segundos)},
                )
        return None

    def _agregar_encabezados(
        self, request: Request, respuesta: RespuestaStarlette
    ) -> None:
        respuesta.headers["X-Request-ID"] = request.state.id_solicitud
        respuesta.headers["Cache-Control"] = "no-store"
        respuesta.headers["Pragma"] = "no-cache"
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        respuesta.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        respuesta.headers["Content-Security-Policy"] = (
            "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
            "form-action 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; connect-src 'self'"
        )
        respuesta.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        respuesta.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        respuesta.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )


class GestorCsrf:
    def __init__(self, configuracion: ConfiguracionApi) -> None:
        self.configuracion = configuracion

    def emitir(self, respuesta: Response) -> str:
        valor_cookie = secrets.token_urlsafe(32)
        firma = hmac.new(
            self.configuracion.secreto_csrf,
            valor_cookie.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        token = f"{valor_cookie}.{firma}"
        respuesta.set_cookie(
            NOMBRE_COOKIE_CSRF,
            valor_cookie,
            max_age=8 * 60 * 60,
            path=RUTA_API,
            secure=True,
            httponly=True,
            samesite="strict",
        )
        respuesta.headers["X-CSRF-Token"] = token
        return token

    def validar(self, request: Request) -> None:
        valor_cookie = request.cookies.get(NOMBRE_COOKIE_CSRF, "")
        token = request.headers.get("x-csrf-token", "")
        try:
            valor_encabezado, firma = token.rsplit(".", 1)
        except ValueError:
            valor_encabezado, firma = "", ""
        firma_esperada = hmac.new(
            self.configuracion.secreto_csrf,
            valor_cookie.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not (
            valor_cookie
            and hmac.compare_digest(valor_cookie, valor_encabezado)
            and hmac.compare_digest(firma, firma_esperada)
        ):
            raise ProblemaHttp(
                403,
                "CSRF_INVALIDO",
                "Validación CSRF rechazada",
                "No fue posible validar la solicitud.",
            )


def guardar_flujo(respuesta: Response, identificador: str) -> None:
    respuesta.set_cookie(
        NOMBRE_COOKIE_FLUJO,
        identificador,
        max_age=5 * 60,
        path=RUTA_FLUJO,
        secure=True,
        httponly=True,
        samesite="strict",
    )


def guardar_credenciales(respuesta: Response, acceso: str, renovacion: str) -> None:
    respuesta.set_cookie(
        NOMBRE_COOKIE_ACCESO,
        acceso,
        max_age=5 * 60,
        path=RUTA_API,
        secure=True,
        httponly=True,
        samesite="strict",
    )
    respuesta.set_cookie(
        NOMBRE_COOKIE_RENOVACION,
        renovacion,
        max_age=8 * 60 * 60,
        path=RUTA_COOKIE_RENOVACION,
        secure=True,
        httponly=True,
        samesite="strict",
    )
    respuesta.delete_cookie(
        NOMBRE_COOKIE_FLUJO,
        path=RUTA_FLUJO,
        secure=True,
        httponly=True,
        samesite="strict",
    )


def eliminar_credenciales(respuesta: Response) -> None:
    respuesta.delete_cookie(
        NOMBRE_COOKIE_ACCESO,
        path=RUTA_API,
        secure=True,
        httponly=True,
        samesite="strict",
    )
    respuesta.delete_cookie(
        NOMBRE_COOKIE_RENOVACION,
        path=RUTA_COOKIE_RENOVACION,
        secure=True,
        httponly=True,
        samesite="strict",
    )
    respuesta.delete_cookie(
        NOMBRE_COOKIE_FLUJO,
        path=RUTA_FLUJO,
        secure=True,
        httponly=True,
        samesite="strict",
    )
