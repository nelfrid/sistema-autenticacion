"""Esquemas estrictos de entrada de la API."""

from __future__ import annotations

import unicodedata
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

TextoCorto = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=256)
]
Contrasena = Annotated[
    str,
    StringConstraints(
        strict=True, min_length=15, max_length=128, strip_whitespace=False
    ),
]
Base64Url = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=12_000)
]


def _normalizar_nombre(valor: Any) -> Any:
    if not isinstance(valor, str):
        return valor
    normalizado = unicodedata.normalize("NFC", valor)
    if not normalizado.strip():
        raise ValueError("no puede contener únicamente espacios")
    if any(unicodedata.category(caracter) == "Cc" for caracter in normalizado):
        raise ValueError("contiene caracteres de control")
    return normalizado


Nombre = Annotated[
    str,
    BeforeValidator(_normalizar_nombre),
    StringConstraints(strict=True, min_length=1, max_length=150),
]


class EsquemaEstricto(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", populate_by_name=True)


class RegistroEntrada(EsquemaEstricto):
    nombre_completo: Nombre
    correo: EmailStr
    contrasena: Contrasena
    confirmacion_contrasena: Annotated[
        str,
        StringConstraints(strict=True, min_length=15, max_length=128),
    ]
    aceptaciones: list[
        Annotated[str, StringConstraints(strict=True, min_length=1, max_length=64)]
    ] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validar_confirmacion(self) -> RegistroEntrada:
        # La contraseña se compara tal como llegó: no se recorta ni normaliza.
        if self.contrasena != self.confirmacion_contrasena:
            raise ValueError("las contraseñas no coinciden")
        return self


class VerificacionCorreoEntrada(EsquemaEstricto):
    credencial: Annotated[
        str, StringConstraints(strict=True, min_length=32, max_length=512)
    ]


class ReenvioVerificacionEntrada(EsquemaEstricto):
    correo: EmailStr


class InicioSesionEntrada(EsquemaEstricto):
    correo: EmailStr
    contrasena: Contrasena


class RespuestaAtestacionWebAuthn(EsquemaEstricto):
    client_data_json: Base64Url = Field(alias="clientDataJSON")
    attestation_object: Base64Url = Field(alias="attestationObject")
    transports: list[str] = Field(default_factory=list, max_length=16)


class RegistroWebAuthnEntrada(EsquemaEstricto):
    identificador: TextoCorto = Field(alias="id")
    identificador_crudo: Base64Url = Field(alias="rawId")
    tipo: Literal["public-key"] = Field(alias="type")
    respuesta: RespuestaAtestacionWebAuthn = Field(alias="response")
    extensiones_cliente: dict[str, Any] = Field(
        default_factory=dict, alias="clientExtensionResults"
    )


class CompletarRegistroWebAuthnEntrada(EsquemaEstricto):
    credencial: RegistroWebAuthnEntrada


class RespuestaAsercionWebAuthn(EsquemaEstricto):
    client_data_json: Base64Url = Field(alias="clientDataJSON")
    authenticator_data: Base64Url = Field(alias="authenticatorData")
    firma: Base64Url = Field(alias="signature")
    identificador_usuario: Base64Url | None = Field(default=None, alias="userHandle")


class AutenticacionWebAuthnEntrada(EsquemaEstricto):
    identificador: TextoCorto = Field(alias="id")
    identificador_crudo: Base64Url = Field(alias="rawId")
    tipo: Literal["public-key"] = Field(alias="type")
    respuesta: RespuestaAsercionWebAuthn = Field(alias="response")
    extensiones_cliente: dict[str, Any] = Field(
        default_factory=dict, alias="clientExtensionResults"
    )


class CompletarAutenticacionWebAuthnEntrada(EsquemaEstricto):
    credencial: AutenticacionWebAuthnEntrada


class CodigoRespaldoEntrada(EsquemaEstricto):
    codigo_respaldo: Annotated[
        str, StringConstraints(strict=True, min_length=8, max_length=128)
    ]


class ConfirmacionCodigosRespaldoEntrada(EsquemaEstricto):
    codigos_guardados: bool

    @field_validator("codigos_guardados", mode="before")
    @classmethod
    def exigir_confirmacion_explicita(cls, valor: Any) -> bool:
        if type(valor) is not bool or valor is not True:
            raise ValueError("debe confirmarse explícitamente")
        return valor
