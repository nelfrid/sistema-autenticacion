"""Pruebas de contrato HTTP con una fachada backend falsa."""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any

import pytest
from fastapi.testclient import TestClient

from .aplicacion import crear_aplicacion
from .configuracion import ConfiguracionApi, ErrorConfiguracion
from .ensamblaje import ensamblar_api
from .puertos import (
    CodigoErrorFachada,
    ConflictoSesionPublico,
    CredencialesSesion,
    ErrorFachada,
    EstadoInicioSesion,
    ResultadoAutenticacion,
    ResultadoInicioSesion,
    ResultadoLimite,
    SesionPublica,
    SolicitudLimite,
    SolicitudRegistro,
)

ORIGEN = "https://api.prueba"
CONTRASENA = "contraseña segura 2026"
RUTA_RENOVACION = "/api/v1/sesiones/renovar"

# Tabla única derivada del contrato estable y de los módulos JS productivos.
CONTRATOS_FRONTEND = (
    (
        "POST",
        "/api/v1/registros",
        frozenset(
            registro
            for registro in (
                "nombre_completo",
                "correo",
                "contrasena",
                "confirmacion_contrasena",
                "aceptaciones",
            )
        ),
        "REGISTRO_RECIBIDO",
    ),
    (
        "POST",
        "/api/v1/verificaciones-correo/confirmar",
        frozenset({"credencial"}),
        "CORREO_VERIFICADO",
    ),
    (
        "POST",
        "/api/v1/verificaciones-correo/reenviar",
        frozenset({"correo"}),
        "REENVIO_VERIFICACION_RECIBIDO",
    ),
    (
        "POST",
        "/api/v1/sesiones/iniciar",
        frozenset({"correo", "contrasena"}),
        "DESAFIO_WEBAUTHN_REQUERIDO",
    ),
    ("GET", "/api/v1/sesiones/conflicto", frozenset(), "CONFLICTO_SESION"),
    ("GET", "/api/v1/sesiones/actual", frozenset(), "SESION_ACTIVA"),
    ("POST", "/api/v1/sesiones/cerrar", frozenset(), "SESION_CERRADA"),
    ("POST", "/api/v1/webauthn/registro/opciones", frozenset(), "OPCIONES_WEBAUTHN"),
    (
        "POST",
        "/api/v1/webauthn/registro/completar",
        frozenset({"credencial"}),
        "WEBAUTHN_CONFIGURADO",
    ),
    (
        "GET",
        "/api/v1/codigos-respaldo/pendientes",
        frozenset(),
        "CODIGOS_RESPALDO_PENDIENTES",
    ),
    (
        "POST",
        "/api/v1/codigos-respaldo/confirmar",
        frozenset({"codigos_guardados"}),
        "AUTENTICADO",
    ),
    (
        "POST",
        "/api/v1/webauthn/autenticacion/opciones",
        frozenset(),
        "OPCIONES_WEBAUTHN",
    ),
    (
        "POST",
        "/api/v1/webauthn/autenticacion/completar",
        frozenset({"credencial"}),
        "AUTENTICADO",
    ),
    (
        "POST",
        "/api/v1/webauthn/autenticacion/codigo-respaldo",
        frozenset({"codigo_respaldo"}),
        "AUTENTICADO",
    ),
)


class FachadaFalsa:
    def __init__(self) -> None:
        self.registros: list[SolicitudRegistro] = []
        self.limites: list[SolicitudLimite] = []
        self.fallos: set[str] = set()
        self.error_registro: CodigoErrorFachada | None = None
        self.error_login: CodigoErrorFachada | None = None
        self.ambito_rechazado: str | None = None
        self.limite_concurrente: tuple[str, int] | None = None
        self.consumos: dict[str, int] = {}
        self.bloqueo_limites = Lock()
        self.detectar_reutilizacion = False
        self.renovaciones_consumidas: set[str] = set()
        self.bloqueo_renovaciones = Lock()
        self.flujo = EstadoInicioSesion.WEBAUTHN_REQUERIDO
        self.alta_confirmada = False
        self.cierres: list[tuple[str | None, str | None]] = []

    def fallar(self, operacion: str) -> None:
        if operacion in self.fallos:
            raise RuntimeError(f"detalle interno de {operacion}")

    async def consumir_limite(self, solicitud: SolicitudLimite) -> ResultadoLimite:
        self.fallar("limite")
        self.limites.append(solicitud)
        if self.limite_concurrente and solicitud.ambito == self.limite_concurrente[0]:
            with self.bloqueo_limites:
                consumos = self.consumos.get(solicitud.ambito, 0) + 1
                self.consumos[solicitud.ambito] = consumos
            return ResultadoLimite(consumos <= self.limite_concurrente[1], 37)
        return ResultadoLimite(solicitud.ambito != self.ambito_rechazado, 37)

    async def registrar(self, solicitud: SolicitudRegistro) -> None:
        self.fallar("registro")
        if self.error_registro:
            raise ErrorFachada(self.error_registro)
        self.registros.append(solicitud)

    async def verificar_correo(self, credencial_opaca: str) -> None:
        self.fallar("verificacion")
        if credencial_opaca.startswith("x"):
            raise ErrorFachada(CodigoErrorFachada.VERIFICACION_INVALIDA)

    async def reenviar_verificacion(self, correo: str) -> None:
        self.fallar("reenvio")
        if correo.startswith("inexistente"):
            raise ErrorFachada(CodigoErrorFachada.CREDENCIALES_INVALIDAS)

    async def iniciar_sesion(
        self, correo: str, contrasena: str
    ) -> ResultadoInicioSesion:
        self.fallar("inicio")
        if self.error_login:
            raise ErrorFachada(self.error_login)
        return ResultadoInicioSesion(self.flujo, "flujo-opaco-123")

    async def opciones_alta_webauthn(
        self, identificador_flujo: str
    ) -> Mapping[str, Any]:
        self.fallar("opciones_alta")
        return {
            "challenge": "cmV0by1hbHRh",
            "rp": {"name": "Demo"},
            "user": {"id": "dXN1YXJpby0x", "name": "angela@example.com"},
        }

    async def confirmar_alta_webauthn(
        self,
        identificador_flujo: str,
        respuesta: Mapping[str, Any],
    ) -> None:
        self.fallar("confirmacion_alta")
        self.alta_confirmada = True

    async def obtener_codigos_respaldo_pendientes(
        self,
        identificador_flujo: str,
    ) -> tuple[str, ...]:
        self.fallar("codigos_pendientes")
        if not self.alta_confirmada:
            raise ErrorFachada(CodigoErrorFachada.FLUJO_INVALIDO)
        return ("RESPALDO-1", "RESPALDO-2")

    async def confirmar_resguardo_codigos(
        self,
        identificador_flujo: str,
    ) -> ResultadoAutenticacion:
        self.fallar("confirmacion_codigos")
        if not self.alta_confirmada:
            raise ErrorFachada(CodigoErrorFachada.FLUJO_INVALIDO)
        return ResultadoAutenticacion(CredencialesSesion("jwt-alta", "renovacion-alta"))

    async def opciones_autenticacion_webauthn(
        self,
        identificador_flujo: str,
    ) -> Mapping[str, Any]:
        self.fallar("opciones_autenticacion")
        return {
            "challenge": "cmV0by1hdXRo",
            "allowCredentials": [{"id": "Y3JlZGVuY2lhbA", "type": "public-key"}],
        }

    async def confirmar_autenticacion_webauthn(
        self,
        identificador_flujo: str,
        respuesta: Mapping[str, Any],
    ) -> ResultadoAutenticacion:
        self.fallar("confirmacion_autenticacion")
        return ResultadoAutenticacion(
            CredencialesSesion("jwt-acceso", "renovacion-opaca"),
            conflicto_resuelto=self.flujo == EstadoInicioSesion.CONFLICTO_SESION,
        )

    async def obtener_conflicto_sesion(
        self,
        identificador_flujo: str,
    ) -> ConflictoSesionPublico:
        self.fallar("conflicto")
        return ConflictoSesionPublico(
            datetime(2026, 11, 13, 10, 30, tzinfo=UTC), "Navegador anterior"
        )

    async def confirmar_codigo_respaldo(
        self,
        identificador_flujo: str,
        codigo: str,
    ) -> ResultadoAutenticacion:
        self.fallar("codigo_respaldo")
        if self.flujo == EstadoInicioSesion.CONFLICTO_SESION:
            raise ErrorFachada(CodigoErrorFachada.NO_AUTORIZADO)
        if codigo == "INVALIDO-0":
            raise ErrorFachada(CodigoErrorFachada.CODIGO_RESPALDO_INVALIDO)
        return ResultadoAutenticacion(
            CredencialesSesion("jwt-codigo", "renovacion-codigo")
        )

    async def renovar_sesion(self, token_renovacion: str) -> CredencialesSesion:
        self.fallar("renovacion")
        if self.detectar_reutilizacion:
            with self.bloqueo_renovaciones:
                if token_renovacion in self.renovaciones_consumidas:
                    raise ErrorFachada(CodigoErrorFachada.SESION_INVALIDA)
                self.renovaciones_consumidas.add(token_renovacion)
        return CredencialesSesion("jwt-rotado", "renovacion-rotada")

    async def obtener_sesion(self, token_acceso: str) -> SesionPublica:
        self.fallar("sesion")
        ahora = datetime.now(UTC)
        return SesionPublica(
            identificador_usuario="usuario-1",
            nombre_mostrado="Ángela O'Connor",
            correo="angela@example.com",
            creada_en=ahora,
            expira_en=ahora + timedelta(hours=8),
            ultima_actividad_en=ahora,
            expira_por_inactividad_en=ahora + timedelta(minutes=30),
        )

    async def cerrar_sesion(
        self,
        token_acceso: str | None,
        token_renovacion: str | None,
    ) -> None:
        self.fallar("cierre")
        self.cierres.append((token_acceso, token_renovacion))


@pytest.fixture
def configuracion() -> ConfiguracionApi:
    return ConfiguracionApi(
        origen_publico=ORIGEN,
        secreto_csrf=b"csrf-primario-independiente-1234567890",
        secreto_limitacion=b"limite-secundario-independiente-12345",
    )


@pytest.fixture
def fachada() -> FachadaFalsa:
    return FachadaFalsa()


@pytest.fixture
def cliente(fachada: FachadaFalsa, configuracion: ConfiguracionApi) -> TestClient:
    return crear_cliente(fachada, configuracion)


def crear_cliente(fachada: FachadaFalsa, configuracion: ConfiguracionApi) -> TestClient:
    return TestClient(
        crear_aplicacion(fachada, configuracion),
        base_url=ORIGEN,
        client=("127.0.0.1", 50_000),
    )


def preparar_csrf(cliente: TestClient) -> dict[str, str]:
    respuesta = cliente.get("/api/v1/seguridad/csrf")
    assert respuesta.status_code == 204
    assert "__Secure-csrf=" in respuesta.headers["set-cookie"]
    return {"Origin": ORIGEN, "X-CSRF-Token": respuesta.headers["x-csrf-token"]}


def registro_valido() -> dict[str, Any]:
    return {
        "nombre_completo": "Ángela O'Connor",
        "correo": "angela@example.com",
        "contrasena": CONTRASENA,
        "confirmacion_contrasena": CONTRASENA,
        "aceptaciones": ["terminos-demo-1.0", "privacidad-demo-1.0"],
    }


def credencial_registro() -> dict[str, Any]:
    return {
        "id": "credencial-1",
        "rawId": "Y3JlZGVuY2lhbA",
        "type": "public-key",
        "response": {
            "clientDataJSON": "Y2xpZW50",
            "attestationObject": "YXR0ZXN0YXRpb24",
            "transports": ["internal"],
        },
        "clientExtensionResults": {},
    }


def credencial_autenticacion() -> dict[str, Any]:
    return {
        "id": "credencial-1",
        "rawId": "Y3JlZGVuY2lhbA",
        "type": "public-key",
        "response": {
            "clientDataJSON": "Y2xpZW50",
            "authenticatorData": "YXV0aA",
            "signature": "ZmlybWE",
            "userHandle": None,
        },
        "clientExtensionResults": {},
    }


def iniciar_flujo(cliente: TestClient, encabezados: dict[str, str]) -> Any:
    respuesta = cliente.post(
        "/api/v1/sesiones/iniciar",
        headers=encabezados,
        json={"correo": "angela@example.com", "contrasena": CONTRASENA},
    )
    assert respuesta.status_code == 202
    return respuesta


def autenticar_webauthn(cliente: TestClient, encabezados: dict[str, str]) -> Any:
    iniciar_flujo(cliente, encabezados)
    return cliente.post(
        "/api/v1/webauthn/autenticacion/completar",
        headers=encabezados,
        json={"credencial": credencial_autenticacion()},
    )


def test_tabla_unica_cubre_las_catorce_rutas_productivas(
    fachada: FachadaFalsa,
    configuracion: ConfiguracionApi,
) -> None:
    aplicacion = crear_aplicacion(fachada, configuracion)
    rutas = {
        (metodo, ruta.path): ruta
        for ruta in aplicacion.routes
        for metodo in (ruta.methods or set())
    }
    esperadas = {(metodo, ruta) for metodo, ruta, _, _ in CONTRATOS_FRONTEND}
    assert len(CONTRATOS_FRONTEND) == 14
    assert esperadas <= set(rutas)
    assert not any(ruta.startswith("/api/v1/autenticacion") for _, ruta in rutas)
    for metodo, ruta, carga, _ in CONTRATOS_FRONTEND:
        parametros_cuerpo = rutas[(metodo, ruta)].dependant.body_params
        campos = (
            frozenset(parametros_cuerpo[0].type_.model_fields)
            if parametros_cuerpo
            else frozenset()
        )
        assert campos == carga, f"carga divergente para {metodo} {ruta}"


def test_https_es_ineludible_en_configuracion_y_proxy() -> None:
    argumentos = {
        "secreto_csrf": b"csrf-primario-independiente-1234567890",
        "secreto_limitacion": b"limite-secundario-independiente-12345",
    }
    with pytest.raises(ErrorConfiguracion, match="HTTPS"):
        ConfiguracionApi(origen_publico="http://api.prueba", **argumentos)
    with pytest.raises(TypeError):
        ConfiguracionApi(origen_publico=ORIGEN, exigir_https=False, **argumentos)  # type: ignore[call-arg]
    with pytest.raises(ErrorConfiguracion, match="HTTPS"):
        ConfiguracionApi.desde_entorno(
            {
                "API_ORIGEN_PUBLICO": "http://api.prueba",
                "API_SECRETO_CSRF": "csrf-primario-independiente-1234567890",
                "API_SECRETO_LIMITACION": "limite-secundario-independiente-12345",
                "API_EXIGIR_HTTPS": "false",
            }
        )

    configuracion = ConfiguracionApi(
        origen_publico=ORIGEN,
        proxies_confiables=("127.0.0.1/32",),
        **argumentos,
    )
    cliente = TestClient(
        crear_aplicacion(FachadaFalsa(), configuracion),
        base_url="http://api.prueba",
        client=("127.0.0.1", 50_000),
    )
    respuesta = cliente.get(
        "/api/v1/seguridad/csrf",
        headers={"X-Forwarded-Proto": "http", "X-Forwarded-Host": "api.prueba"},
    )
    assert respuesta.status_code == 400


def test_registro_alinea_payload_normaliza_nfc_y_no_enumera(
    cliente: TestClient,
    fachada: FachadaFalsa,
) -> None:
    encabezados = preparar_csrf(cliente)
    datos = registro_valido()
    datos["nombre_completo"] = "e\u0301" * 150
    datos["contrasena"] = " 1234567890123 "
    datos["confirmacion_contrasena"] = " 1234567890123 "
    nueva = cliente.post("/api/v1/registros", headers=encabezados, json=datos)
    fachada.error_registro = CodigoErrorFachada.CORREO_EXISTENTE
    duplicada = cliente.post("/api/v1/registros", headers=encabezados, json=datos)
    assert nueva.status_code == duplicada.status_code == 202
    assert nueva.json()["codigo"] == duplicada.json()["codigo"] == "REGISTRO_RECIBIDO"
    assert nueva.json()["mensaje"] == duplicada.json()["mensaje"]
    assert fachada.registros[0].nombre_completo == "é" * 150
    assert fachada.registros[0].contrasena == " 1234567890123 "


@pytest.mark.parametrize(
    "cambio",
    [
        {"nombre_completo": "e\u0301" * 151},
        {"confirmacion_contrasena": "otra contraseña suficientemente larga"},
        {"aceptaciones": ["terminos-demo-1.0", "otra"]},
        {"rol": "administrador"},
    ],
)
def test_registro_rechaza_limites_aceptaciones_y_campos_internos(
    cliente: TestClient,
    cambio: dict[str, Any],
) -> None:
    datos = registro_valido()
    datos.update(cambio)
    respuesta = cliente.post(
        "/api/v1/registros",
        headers=preparar_csrf(cliente),
        json=datos,
    )
    assert respuesta.status_code == 422
    assert "mensaje" in respuesta.json()


def test_verificacion_y_reenvio_respetan_codigos_y_anti_enumeracion(
    cliente: TestClient,
) -> None:
    encabezados = preparar_csrf(cliente)
    verificada = cliente.post(
        "/api/v1/verificaciones-correo/confirmar",
        headers=encabezados,
        json={"credencial": "a" * 32},
    )
    invalida = cliente.post(
        "/api/v1/verificaciones-correo/confirmar",
        headers=encabezados,
        json={"credencial": "x" * 32},
    )
    existente = cliente.post(
        "/api/v1/verificaciones-correo/reenviar",
        headers=encabezados,
        json={"correo": "angela@example.com"},
    )
    inexistente = cliente.post(
        "/api/v1/verificaciones-correo/reenviar",
        headers=encabezados,
        json={"correo": "inexistente@example.com"},
    )
    assert verificada.json()["codigo"] == "CORREO_VERIFICADO"
    assert invalida.json()["codigo"] == "CREDENCIAL_VERIFICACION_INVALIDA"
    assert existente.status_code == inexistente.status_code == 202
    assert existente.json()["codigo"] == inexistente.json()["codigo"]
    assert existente.json()["mensaje"] == inexistente.json()["mensaje"]


@pytest.mark.parametrize(
    ("estado", "codigo"),
    [
        (
            EstadoInicioSesion.ALTA_WEBAUTHN_REQUERIDA,
            "CONFIGURACION_WEBAUTHN_REQUERIDA",
        ),
        (EstadoInicioSesion.WEBAUTHN_REQUERIDO, "DESAFIO_WEBAUTHN_REQUERIDO"),
        (EstadoInicioSesion.CONFLICTO_SESION, "CONFLICTO_SESION"),
        (
            EstadoInicioSesion.VERIFICACION_CORREO_PENDIENTE,
            "VERIFICACION_CORREO_PENDIENTE",
        ),
    ],
)
def test_inicio_sesion_devuelve_estados_consumidos_por_interfaz(
    cliente: TestClient,
    fachada: FachadaFalsa,
    estado: EstadoInicioSesion,
    codigo: str,
) -> None:
    fachada.flujo = estado
    respuesta = iniciar_flujo(cliente, preparar_csrf(cliente))
    assert respuesta.json()["codigo"] == codigo
    assert "__Secure-flujo-autenticacion=" in respuesta.headers["set-cookie"]
    assert "__Secure-acceso=" not in respuesta.headers["set-cookie"]


def test_inicio_sesion_no_enumera_credenciales(
    cliente: TestClient,
    fachada: FachadaFalsa,
) -> None:
    fachada.error_login = CodigoErrorFachada.CREDENCIALES_INVALIDAS
    encabezados = preparar_csrf(cliente)
    respuestas = [
        cliente.post(
            "/api/v1/sesiones/iniciar",
            headers=encabezados,
            json={"correo": correo, "contrasena": CONTRASENA},
        )
        for correo in ("existente@example.com", "inexistente@example.com")
    ]
    assert [respuesta.status_code for respuesta in respuestas] == [401, 401]
    assert {respuesta.json()["codigo"] for respuesta in respuestas} == {
        "CREDENCIALES_INVALIDAS"
    }
    assert {respuesta.json()["mensaje"] for respuesta in respuestas} == {
        "No fue posible completar la autenticación."
    }


def test_alta_webauthn_mantiene_restriccion_hasta_confirmar_codigos(
    cliente: TestClient,
    fachada: FachadaFalsa,
) -> None:
    fachada.flujo = EstadoInicioSesion.ALTA_WEBAUTHN_REQUERIDA
    encabezados = preparar_csrf(cliente)
    iniciar_flujo(cliente, encabezados)
    opciones = cliente.post(
        "/api/v1/webauthn/registro/opciones",
        headers=encabezados,
    )
    completar = cliente.post(
        "/api/v1/webauthn/registro/completar",
        headers=encabezados,
        json={"credencial": credencial_registro()},
    )
    pendientes = cliente.get("/api/v1/codigos-respaldo/pendientes")
    confirmar = cliente.post(
        "/api/v1/codigos-respaldo/confirmar",
        headers=encabezados,
        json={"codigos_guardados": True},
    )
    assert opciones.json()["opciones"]["challenge"] == "cmV0by1hbHRh"
    assert completar.json()["codigo"] == "WEBAUTHN_CONFIGURADO"
    assert "__Secure-acceso=" not in completar.headers.get("set-cookie", "")
    assert pendientes.json()["codigos"] == ["RESPALDO-1", "RESPALDO-2"]
    assert confirmar.json()["codigo"] == "AUTENTICADO"
    assert "__Secure-acceso=" in confirmar.headers["set-cookie"]


def test_autenticacion_webauthn_alinea_envoltura_opciones_y_cookies(
    cliente: TestClient,
) -> None:
    encabezados = preparar_csrf(cliente)
    iniciar_flujo(cliente, encabezados)
    opciones = cliente.post(
        "/api/v1/webauthn/autenticacion/opciones",
        headers=encabezados,
    )
    completar = cliente.post(
        "/api/v1/webauthn/autenticacion/completar",
        headers=encabezados,
        json={"credencial": credencial_autenticacion()},
    )
    assert opciones.json()["opciones"]["challenge"] == "cmV0by1hdXRo"
    assert completar.json()["codigo"] == "AUTENTICADO"
    assert "jwt-acceso" not in completar.text
    cookies = completar.headers.get_list("set-cookie")
    acceso = next(valor for valor in cookies if "__Secure-acceso=" in valor)
    renovacion = next(valor for valor in cookies if "__Secure-renovacion=" in valor)
    for cookie in (acceso, renovacion):
        assert "HttpOnly" in cookie
        assert "Secure" in cookie
        assert "SameSite=strict" in cookie
        assert "Domain=" not in cookie
    assert "Path=/api/v1" in acceso
    assert "Path=/api/v1/sesiones/renovar" in renovacion


def test_conflicto_consulta_detalle_y_se_resuelve_por_webauthn(
    cliente: TestClient,
    fachada: FachadaFalsa,
) -> None:
    fachada.flujo = EstadoInicioSesion.CONFLICTO_SESION
    encabezados = preparar_csrf(cliente)
    iniciar_flujo(cliente, encabezados)
    conflicto = cliente.get("/api/v1/sesiones/conflicto")
    opciones = cliente.post(
        "/api/v1/webauthn/autenticacion/opciones",
        headers=encabezados,
    )
    respaldo = cliente.post(
        "/api/v1/webauthn/autenticacion/codigo-respaldo",
        headers=encabezados,
        json={"codigo_respaldo": "RESPALDO-1"},
    )
    completar = cliente.post(
        "/api/v1/webauthn/autenticacion/completar",
        headers=encabezados,
        json={"credencial": credencial_autenticacion()},
    )
    assert conflicto.json()["inicio_aproximado"] == "2026-11-13T10:30+00:00"
    assert conflicto.json()["dispositivo"] == "Navegador anterior"
    assert opciones.status_code == 200
    assert completar.json()["codigo"] == "CONFLICTO_SESION_RESUELTO"
    assert respaldo.status_code == 401


def test_codigo_respaldo_autentica_y_rechaza_reutilizacion(cliente: TestClient) -> None:
    encabezados = preparar_csrf(cliente)
    iniciar_flujo(cliente, encabezados)
    valido = cliente.post(
        "/api/v1/webauthn/autenticacion/codigo-respaldo",
        headers=encabezados,
        json={"codigo_respaldo": "RESPALDO-1"},
    )
    cliente.cookies.clear()
    encabezados = preparar_csrf(cliente)
    iniciar_flujo(cliente, encabezados)
    invalido = cliente.post(
        "/api/v1/webauthn/autenticacion/codigo-respaldo",
        headers=encabezados,
        json={"codigo_respaldo": "INVALIDO-0"},
    )
    assert valido.json()["codigo"] == "AUTENTICADO"
    assert invalido.json()["codigo"] == "CODIGO_RESPALDO_INVALIDO"


def test_webauthn_rechaza_formato_y_campos_internos(cliente: TestClient) -> None:
    encabezados = preparar_csrf(cliente)
    iniciar_flujo(cliente, encabezados)
    credencial = credencial_autenticacion()
    credencial["rol"] = "administrador"
    extra = cliente.post(
        "/api/v1/webauthn/autenticacion/completar",
        headers=encabezados,
        json={"credencial": credencial},
    )
    sin_envoltura = cliente.post(
        "/api/v1/webauthn/autenticacion/completar",
        headers=encabezados,
        json=credencial_autenticacion(),
    )
    assert extra.status_code == sin_envoltura.status_code == 422
    assert extra.json()["campos"]["credencial.rol"] == "Revisa el valor proporcionado."


def test_sesion_actual_cierre_y_cookie_refresh_de_alcance_exacto(
    cliente: TestClient,
    fachada: FachadaFalsa,
) -> None:
    encabezados = preparar_csrf(cliente)
    autenticacion = autenticar_webauthn(cliente, encabezados)
    encabezados["X-CSRF-Token"] = autenticacion.headers["x-csrf-token"]
    estado = cliente.get("/api/v1/sesiones/actual")
    cierre = cliente.post("/api/v1/sesiones/cerrar", headers=encabezados)
    assert estado.json()["correo"] == "angela@example.com"
    assert "vencimiento_absoluto" in estado.json()
    assert cierre.json()["codigo"] == "SESION_CERRADA"
    assert fachada.cierres[-1][1] is None
    assert "__Secure-renovacion=" in cierre.headers["set-cookie"]
    assert "Path=/api/v1/sesiones/renovar" in cierre.headers["set-cookie"]


def test_renovacion_rota_solo_en_ruta_explicita(cliente: TestClient) -> None:
    encabezados = preparar_csrf(cliente)
    autenticacion = autenticar_webauthn(cliente, encabezados)
    encabezados["X-CSRF-Token"] = autenticacion.headers["x-csrf-token"]
    respuesta = cliente.post(RUTA_RENOVACION, headers=encabezados)
    assert respuesta.status_code == 204
    cookies = respuesta.headers.get_list("set-cookie")
    renovacion = next(valor for valor in cookies if "__Secure-renovacion=" in valor)
    assert "Path=/api/v1/sesiones/renovar" in renovacion


def test_renovaciones_concurrentes_consumen_token_una_vez(
    fachada: FachadaFalsa,
    configuracion: ConfiguracionApi,
) -> None:
    fachada.detectar_reutilizacion = True
    aplicacion = crear_aplicacion(fachada, configuracion)

    def renovar(_: int) -> int:
        cliente = TestClient(
            aplicacion,
            base_url=ORIGEN,
            client=("127.0.0.1", 50_000),
        )
        encabezados = preparar_csrf(cliente)
        cliente.cookies.set(
            "__Secure-renovacion",
            "renovacion-compartida",
            domain="api.prueba",
            path=RUTA_RENOVACION,
        )
        return cliente.post(RUTA_RENOVACION, headers=encabezados).status_code

    with ThreadPoolExecutor(max_workers=6) as ejecutor:
        estados = list(ejecutor.map(renovar, range(6)))
    assert estados.count(204) == 1
    assert estados.count(401) == 5


def test_csrf_origen_rotacion_y_error_compatible_con_cliente(
    cliente: TestClient,
) -> None:
    sin_csrf = cliente.post(
        "/api/v1/registros",
        headers={"Origin": ORIGEN},
        json=registro_valido(),
    )
    encabezados = preparar_csrf(cliente)
    cruzado = cliente.post(
        "/api/v1/registros",
        headers={**encabezados, "Origin": "https://atacante.example"},
        json=registro_valido(),
    )
    autenticacion = autenticar_webauthn(cliente, encabezados)
    assert sin_csrf.status_code == cruzado.status_code == 403
    assert sin_csrf.headers["content-type"].startswith("application/problem+json")
    assert "application/json" in sin_csrf.headers["content-type"]
    assert sin_csrf.json()["mensaje"] == sin_csrf.json()["detail"]
    assert autenticacion.headers["x-csrf-token"] != encabezados["X-CSRF-Token"]


def test_limites_de_cuerpo_formato_y_frecuencia_exponen_reintento(
    cliente: TestClient,
    fachada: FachadaFalsa,
) -> None:
    encabezados = preparar_csrf(cliente)
    grande = cliente.post(
        "/api/v1/registros",
        headers=encabezados,
        content=b"x" * (16 * 1024 + 1),
    )
    texto = cliente.post(
        "/api/v1/registros",
        headers={**encabezados, "Content-Type": "text/plain"},
        content=b"contenido",
    )
    fachada.ambito_rechazado = "registro_correo"
    limitado = cliente.post(
        "/api/v1/registros",
        headers=encabezados,
        json=registro_valido(),
    )
    assert grande.status_code == 413
    assert texto.status_code == 415
    assert limitado.status_code == 429
    assert limitado.headers["retry-after"] == "37"
    assert limitado.json()["reintentar_en"] == 37


def test_rate_limit_concurrente_respeta_presupuesto_atomico(
    fachada: FachadaFalsa,
    configuracion: ConfiguracionApi,
) -> None:
    fachada.limite_concurrente = ("registro_correo", 3)
    aplicacion = crear_aplicacion(fachada, configuracion)

    def registrar(_: int) -> int:
        cliente = TestClient(
            aplicacion,
            base_url=ORIGEN,
            client=("127.0.0.1", 50_000),
        )
        return cliente.post(
            "/api/v1/registros",
            headers=preparar_csrf(cliente),
            json=registro_valido(),
        ).status_code

    with ThreadPoolExecutor(max_workers=8) as ejecutor:
        estados = list(ejecutor.map(registrar, range(8)))
    assert estados.count(202) == 3
    assert estados.count(429) == 5
    assert len(fachada.registros) == 3


@pytest.mark.parametrize(
    ("operacion", "preparar", "metodo", "ruta", "datos"),
    [
        ("registro", None, "POST", "/api/v1/registros", registro_valido()),
        (
            "verificacion",
            None,
            "POST",
            "/api/v1/verificaciones-correo/confirmar",
            {"credencial": "a" * 32},
        ),
        (
            "reenvio",
            None,
            "POST",
            "/api/v1/verificaciones-correo/reenviar",
            {"correo": "angela@example.com"},
        ),
        (
            "inicio",
            None,
            "POST",
            "/api/v1/sesiones/iniciar",
            {"correo": "angela@example.com", "contrasena": CONTRASENA},
        ),
    ],
)
def test_fallos_de_fachada_no_exponen_detalles(
    cliente: TestClient,
    fachada: FachadaFalsa,
    operacion: str,
    preparar: Any,
    metodo: str,
    ruta: str,
    datos: dict[str, Any],
) -> None:
    del preparar
    fachada.fallos.add(operacion)
    respuesta = cliente.request(
        metodo,
        ruta,
        headers=preparar_csrf(cliente),
        json=datos,
    )
    assert respuesta.status_code == 500
    assert "detalle interno" not in respuesta.text


def test_fallos_en_fases_restringidas_y_sesion_fallan_cerrados(
    cliente: TestClient,
    fachada: FachadaFalsa,
) -> None:
    encabezados = preparar_csrf(cliente)
    iniciar_flujo(cliente, encabezados)
    fachada.fallos.add("opciones_autenticacion")
    opciones = cliente.post(
        "/api/v1/webauthn/autenticacion/opciones",
        headers=encabezados,
    )
    fachada.fallos.clear()
    autenticacion = cliente.post(
        "/api/v1/webauthn/autenticacion/completar",
        headers=encabezados,
        json={"credencial": credencial_autenticacion()},
    )
    encabezados["X-CSRF-Token"] = autenticacion.headers["x-csrf-token"]
    fachada.fallos.add("sesion")
    sesion = cliente.get("/api/v1/sesiones/actual")
    fachada.fallos = {"renovacion"}
    renovacion = cliente.post(RUTA_RENOVACION, headers=encabezados)
    fachada.fallos = {"cierre"}
    cierre = cliente.post("/api/v1/sesiones/cerrar", headers=encabezados)
    assert [
        opciones.status_code,
        sesion.status_code,
        renovacion.status_code,
        cierre.status_code,
    ] == [500, 500, 500, 500]
    assert "__Secure-acceso=" in cierre.headers["set-cookie"]


def test_fallos_de_fachada_cubren_alta_codigos_conflicto_y_factores(
    cliente: TestClient,
    fachada: FachadaFalsa,
) -> None:
    fachada.flujo = EstadoInicioSesion.ALTA_WEBAUTHN_REQUERIDA
    encabezados = preparar_csrf(cliente)
    iniciar_flujo(cliente, encabezados)

    fachada.fallos = {"confirmacion_alta"}
    alta_fallida = cliente.post(
        "/api/v1/webauthn/registro/completar",
        headers=encabezados,
        json={"credencial": credencial_registro()},
    )
    fachada.fallos.clear()
    cliente.post(
        "/api/v1/webauthn/registro/completar",
        headers=encabezados,
        json={"credencial": credencial_registro()},
    )
    fachada.fallos = {"codigos_pendientes"}
    pendientes_fallidos = cliente.get("/api/v1/codigos-respaldo/pendientes")
    fachada.fallos = {"confirmacion_codigos"}
    codigos_fallidos = cliente.post(
        "/api/v1/codigos-respaldo/confirmar",
        headers=encabezados,
        json={"codigos_guardados": True},
    )

    fachada.flujo = EstadoInicioSesion.WEBAUTHN_REQUERIDO
    fachada.fallos.clear()
    iniciar_flujo(cliente, encabezados)
    fachada.fallos = {"confirmacion_autenticacion"}
    autenticacion_fallida = cliente.post(
        "/api/v1/webauthn/autenticacion/completar",
        headers=encabezados,
        json={"credencial": credencial_autenticacion()},
    )
    fachada.fallos = {"codigo_respaldo"}
    respaldo_fallido = cliente.post(
        "/api/v1/webauthn/autenticacion/codigo-respaldo",
        headers=encabezados,
        json={"codigo_respaldo": "RESPALDO-1"},
    )
    fachada.fallos = {"conflicto"}
    conflicto_fallido = cliente.get("/api/v1/sesiones/conflicto")

    respuestas = (
        alta_fallida,
        pendientes_fallidos,
        codigos_fallidos,
        autenticacion_fallida,
        respaldo_fallido,
        conflicto_fallido,
    )
    assert all(respuesta.status_code == 500 for respuesta in respuestas)
    assert all("detalle interno" not in respuesta.text for respuesta in respuestas)


def test_ensamblaje_falla_cerrado(configuracion: ConfiguracionApi) -> None:
    with pytest.raises(RuntimeError, match="fachada"):
        ensamblar_api(None, configuracion)
    with pytest.raises(RuntimeError, match="incompleta"):
        ensamblar_api(object(), configuracion)  # type: ignore[arg-type]
