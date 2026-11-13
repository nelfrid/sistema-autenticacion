"""Ensamblaje explícito y cerrado de la API."""

from __future__ import annotations

from fastapi import FastAPI

from .aplicacion import crear_aplicacion
from .configuracion import ConfiguracionApi, ErrorConfiguracion
from .puertos import FachadaAutenticacion

METODOS_OBLIGATORIOS = (
    "consumir_limite",
    "registrar",
    "verificar_correo",
    "reenviar_verificacion",
    "iniciar_sesion",
    "opciones_alta_webauthn",
    "confirmar_alta_webauthn",
    "obtener_codigos_respaldo_pendientes",
    "confirmar_resguardo_codigos",
    "opciones_autenticacion_webauthn",
    "confirmar_autenticacion_webauthn",
    "obtener_conflicto_sesion",
    "confirmar_codigo_respaldo",
    "renovar_sesion",
    "obtener_sesion",
    "cerrar_sesion",
)


def ensamblar_api(
    fachada: FachadaAutenticacion | None,
    configuracion: ConfiguracionApi | None = None,
) -> FastAPI:
    """Falla al arrancar si falta configuración o una dependencia requerida."""

    if fachada is None:
        raise RuntimeError("falta la fachada backend obligatoria")
    faltantes = [
        metodo
        for metodo in METODOS_OBLIGATORIOS
        if not callable(getattr(fachada, metodo, None))
    ]
    if faltantes:
        raise RuntimeError(
            f"la fachada backend está incompleta: {', '.join(faltantes)}"
        )
    try:
        valores = configuracion or ConfiguracionApi.desde_entorno()
    except (ErrorConfiguracion, ValueError) as error:
        raise RuntimeError("la configuración segura de la API es inválida") from error
    return crear_aplicacion(fachada, valores)
