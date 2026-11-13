export function base64UrlABytes(valor) {
  const base64 = valor.replace(/-/gu, "+").replace(/_/gu, "/");
  const relleno = "=".repeat((4 - (base64.length % 4)) % 4);
  const binario = globalThis.atob(base64 + relleno);
  return Uint8Array.from(binario, (caracter) => caracter.charCodeAt(0));
}

export function bytesABase64Url(valor) {
  const bytes = new Uint8Array(valor);
  let binario = "";
  bytes.forEach((byte) => { binario += String.fromCharCode(byte); });
  return globalThis.btoa(binario).replace(/\+/gu, "-").replace(/\//gu, "_").replace(/=+$/gu, "");
}

export function prepararOpcionesRegistro(opciones) {
  return {
    ...opciones,
    challenge: base64UrlABytes(opciones.challenge),
    user: { ...opciones.user, id: base64UrlABytes(opciones.user.id) },
    excludeCredentials: (opciones.excludeCredentials ?? []).map((credencial) => ({
      ...credencial,
      id: base64UrlABytes(credencial.id),
    })),
  };
}

export function prepararOpcionesAutenticacion(opciones) {
  return {
    ...opciones,
    challenge: base64UrlABytes(opciones.challenge),
    allowCredentials: (opciones.allowCredentials ?? []).map((credencial) => ({
      ...credencial,
      id: base64UrlABytes(credencial.id),
    })),
  };
}

export function serializarRegistro(credencial) {
  return {
    id: credencial.id,
    rawId: bytesABase64Url(credencial.rawId),
    type: credencial.type,
    response: {
      attestationObject: bytesABase64Url(credencial.response.attestationObject),
      clientDataJSON: bytesABase64Url(credencial.response.clientDataJSON),
      transports: credencial.response.getTransports?.() ?? [],
    },
    clientExtensionResults: credencial.getClientExtensionResults?.() ?? {},
  };
}

export function serializarAutenticacion(credencial) {
  return {
    id: credencial.id,
    rawId: bytesABase64Url(credencial.rawId),
    type: credencial.type,
    response: {
      authenticatorData: bytesABase64Url(credencial.response.authenticatorData),
      clientDataJSON: bytesABase64Url(credencial.response.clientDataJSON),
      signature: bytesABase64Url(credencial.response.signature),
      userHandle: credencial.response.userHandle
        ? bytesABase64Url(credencial.response.userHandle)
        : null,
    },
    clientExtensionResults: credencial.getClientExtensionResults?.() ?? {},
  };
}

export function webauthnDisponible() {
  return Boolean(globalThis.PublicKeyCredential && globalThis.navigator?.credentials);
}
