"""Configuración cerrada y validada de la capa HTTP."""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit


class ErrorConfiguracion(ValueError):
    """Indica que la API no puede iniciarse de forma segura."""


@dataclass(frozen=True, slots=True)
class ConfiguracionApi:
    """Valores de seguridad necesarios para construir la aplicación."""

    origen_publico: str
    secreto_csrf: bytes
    secreto_limitacion: bytes
    proxies_confiables: tuple[str, ...] = ()
    limite_cuerpo_bytes: int = 16 * 1024
    version_terminos: str = "terminos-demo-1.0"
    version_privacidad: str = "privacidad-demo-1.0"
    limite_global: int = 120
    ventana_global_segundos: int = 60
    _redes_confiables: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
        field(
            init=False,
            repr=False,
        )
    )

    def __post_init__(self) -> None:
        origen = urlsplit(self.origen_publico)
        if origen.scheme != "https" or not origen.netloc:
            raise ErrorConfiguracion(
                "API_ORIGEN_PUBLICO debe ser un origen HTTPS válido"
            )
        if (
            origen.path not in {"", "/"}
            or origen.query
            or origen.fragment
            or origen.username
        ):
            raise ErrorConfiguracion(
                "API_ORIGEN_PUBLICO no puede contener ruta, credenciales ni consulta"
            )
        if self.origen_publico.endswith("/"):
            raise ErrorConfiguracion("el origen público no debe terminar en barra")
        if len(self.secreto_csrf) < 32 or len(self.secreto_limitacion) < 32:
            raise ErrorConfiguracion(
                "los secretos HTTP deben contener al menos 32 bytes"
            )
        if self.secreto_csrf == self.secreto_limitacion:
            raise ErrorConfiguracion(
                "CSRF y limitación requieren secretos independientes"
            )
        if not 1024 <= self.limite_cuerpo_bytes <= 1024 * 1024:
            raise ErrorConfiguracion(
                "el límite de cuerpo está fuera del intervalo seguro"
            )
        if self.limite_global <= 0 or self.ventana_global_segundos <= 0:
            raise ErrorConfiguracion("la limitación global debe ser positiva")

        redes: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        for valor in self.proxies_confiables:
            try:
                redes.append(ipaddress.ip_network(valor, strict=False))
            except ValueError as error:
                raise ErrorConfiguracion(
                    f"proxy confiable inválido: {valor}"
                ) from error
        object.__setattr__(self, "_redes_confiables", tuple(redes))

    @property
    def origen_normalizado(self) -> str:
        return self.origen_publico.lower()

    def es_proxy_confiable(self, direccion: str) -> bool:
        try:
            ip = ipaddress.ip_address(direccion)
        except ValueError:
            return False
        return any(ip in red for red in self._redes_confiables)

    @classmethod
    def desde_entorno(
        cls, entorno: Mapping[str, str] | None = None
    ) -> ConfiguracionApi:
        valores = os.environ if entorno is None else entorno

        def requerido(nombre: str) -> str:
            valor = valores.get(nombre, "")
            if not valor:
                raise ErrorConfiguracion(f"falta la variable obligatoria {nombre}")
            return valor

        proxies = tuple(
            parte.strip()
            for parte in valores.get("API_PROXIES_CONFIABLES", "").split(",")
            if parte.strip()
        )
        return cls(
            origen_publico=requerido("API_ORIGEN_PUBLICO"),
            secreto_csrf=requerido("API_SECRETO_CSRF").encode("utf-8"),
            secreto_limitacion=requerido("API_SECRETO_LIMITACION").encode("utf-8"),
            proxies_confiables=proxies,
            limite_cuerpo_bytes=int(
                valores.get("API_LIMITE_CUERPO_BYTES", str(16 * 1024))
            ),
            version_terminos=valores.get("API_VERSION_TERMINOS", "terminos-demo-1.0"),
            version_privacidad=valores.get(
                "API_VERSION_PRIVACIDAD", "privacidad-demo-1.0"
            ),
        )
