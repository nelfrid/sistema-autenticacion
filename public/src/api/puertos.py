"""Puertos y DTO que debe implementar el backend de autenticación."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class CodigoErrorFachada(StrEnum):
    CORREO_EXISTENTE = "correo_existente"
    CREDENCIALES_INVALIDAS = "credenciales_invalidas"
    VERIFICACION_INVALIDA = "verificacion_invalida"
    FLUJO_INVALIDO = "flujo_invalido"
    CODIGO_RESPALDO_INVALIDO = "codigo_respaldo_invalido"
    SESION_INVALIDA = "sesion_invalida"
    NO_AUTORIZADO = "no_autorizado"
    NO_DISPONIBLE = "no_disponible"


class ErrorFachada(Exception):
    """Error controlado del dominio, sin detalles internos transportables."""

    def __init__(self, codigo: CodigoErrorFachada) -> None:
        super().__init__(codigo.value)
        self.codigo = codigo


class EstadoInicioSesion(StrEnum):
    ALTA_WEBAUTHN_REQUERIDA = "alta_webauthn_requerida"
    WEBAUTHN_REQUERIDO = "webauthn_requerido"
    CONFLICTO_SESION = "conflicto_sesion"
    VERIFICACION_CORREO_PENDIENTE = "verificacion_correo_pendiente"


@dataclass(frozen=True, slots=True)
class SolicitudLimite:
    """Consumo que el backend debe resolver atómicamente en MySQL."""

    ambito: str
    clave_anonima: str
    limite: int
    ventana_segundos: int


@dataclass(frozen=True, slots=True)
class ResultadoLimite:
    permitido: bool
    reintentar_en_segundos: int = 0


@dataclass(frozen=True, slots=True)
class SolicitudRegistro:
    nombre_completo: str
    correo: str
    contrasena: str
    version_terminos: str
    version_privacidad: str


@dataclass(frozen=True, slots=True)
class ResultadoInicioSesion:
    estado: EstadoInicioSesion
    identificador_flujo: str


@dataclass(frozen=True, slots=True)
class CredencialesSesion:
    """Credenciales que la API solo transporta mediante cookies protegidas."""

    token_acceso: str
    token_renovacion: str


@dataclass(frozen=True, slots=True)
class ResultadoAutenticacion:
    credenciales: CredencialesSesion
    conflicto_resuelto: bool = False


@dataclass(frozen=True, slots=True)
class ConflictoSesionPublico:
    """Información aproximada y no identificadora de la sesión anterior."""

    inicio_aproximado: datetime
    dispositivo: str


@dataclass(frozen=True, slots=True)
class SesionPublica:
    identificador_usuario: str
    nombre_mostrado: str
    correo: str
    creada_en: datetime
    expira_en: datetime
    ultima_actividad_en: datetime
    expira_por_inactividad_en: datetime


@runtime_checkable
class FachadaAutenticacion(Protocol):
    """Contrato asíncrono que conecta HTTP con dominio y MySQL.

    ``consumir_limite`` debe usar una operación atómica respaldada por MySQL.
    ``registrar`` crea una cuenta pendiente, valida la unicidad en base de datos,
    guarda Argon2id y aceptaciones, y genera mediante outbox un enlace opaco de
    un solo uso, almacenado como hash y válido treinta minutos. El registro no
    crea sesión. ``iniciar_sesion`` identifica solo por correo, ejecuta un hash
    ficticio equivalente para cuentas inexistentes y nunca devuelve credenciales.

    ``confirmar_alta_webauthn`` configura el autenticador pero mantiene la
    preautenticación restringida. Después, ``obtener_codigos_respaldo_pendientes``
    entrega los códigos ya generados y ``confirmar_resguardo_codigos`` es la única
    operación que establece la primera sesión completa. Los códigos no deben
    regenerarse al consultar ni desaparecer hasta confirmar su resguardo.

    La implementación también aplica estados, códigos de respaldo de un solo uso,
    sesión única, ocho horas
    absolutas, treinta minutos de inactividad, JWT de cinco minutos y rotación
    con detección de reutilización del token opaco. Nunca devuelve credenciales
    antes de completar el factor requerido. El conflicto de segunda sesión solo
    se confirma con WebAuthn y conserva la sesión nueva, revocando la anterior
    atómicamente; en ese caso ``confirmar_autenticacion_webauthn`` marca
    ``conflicto_resuelto`` en el resultado. ``confirmar_codigo_respaldo`` debe
    rechazar los flujos de conflicto.
    """

    async def consumir_limite(self, solicitud: SolicitudLimite) -> ResultadoLimite: ...

    async def registrar(self, solicitud: SolicitudRegistro) -> None: ...

    async def verificar_correo(self, credencial_opaca: str) -> None: ...

    async def reenviar_verificacion(self, correo: str) -> None: ...

    async def iniciar_sesion(
        self, correo: str, contrasena: str
    ) -> ResultadoInicioSesion: ...

    async def opciones_alta_webauthn(
        self, identificador_flujo: str
    ) -> Mapping[str, Any]: ...

    async def confirmar_alta_webauthn(
        self,
        identificador_flujo: str,
        respuesta: Mapping[str, Any],
    ) -> None: ...

    async def obtener_codigos_respaldo_pendientes(
        self,
        identificador_flujo: str,
    ) -> tuple[str, ...]:
        """Devuelve la misma emisión pendiente, sin crear sesión ni regenerarla."""
        ...

    async def confirmar_resguardo_codigos(
        self,
        identificador_flujo: str,
    ) -> ResultadoAutenticacion:
        """Consume la fase pendiente y establece la primera sesión completa."""
        ...

    async def opciones_autenticacion_webauthn(
        self,
        identificador_flujo: str,
    ) -> Mapping[str, Any]: ...

    async def confirmar_autenticacion_webauthn(
        self,
        identificador_flujo: str,
        respuesta: Mapping[str, Any],
    ) -> ResultadoAutenticacion: ...

    async def obtener_conflicto_sesion(
        self,
        identificador_flujo: str,
    ) -> ConflictoSesionPublico:
        """Expone solo inicio aproximado y descripción limitada del dispositivo."""
        ...

    async def confirmar_codigo_respaldo(
        self,
        identificador_flujo: str,
        codigo: str,
    ) -> ResultadoAutenticacion: ...

    async def renovar_sesion(self, token_renovacion: str) -> CredencialesSesion: ...

    async def obtener_sesion(self, token_acceso: str) -> SesionPublica: ...

    async def cerrar_sesion(
        self,
        token_acceso: str | None,
        token_renovacion: str | None,
    ) -> None: ...
