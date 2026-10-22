"""Paso 1: comprobar que la clave y la conectividad funcionan.

    py scripts/01_ping.py
"""

import _bootstrap  # noqa: F401  (ajusta sys.path)

from llmpulse import config
from llmpulse.client import LLMPulseClient, LLMPulseError
from llmpulse.display import heading


def main() -> int:
    heading("Paso 1 - Comprobacion de conexion")
    print(f"Verificacion TLS via almacen del sistema: {config.SYSTEM_TRUST_ENABLED}")
    if not config.SYSTEM_TRUST_ENABLED:
        print("  (si estas en una red con inspeccion TLS, instala requirements.txt)")
    try:
        client = LLMPulseClient(config.api_key())
        ping = client.get("/ping")
    except LLMPulseError as exc:
        print(f"\nERROR: {exc}")
        return 1
    print(f"\nConexion correcta: ok={ping.get('ok')} | request_id={ping.get('request_id', '-')}")
    print("\nSiguiente: py scripts/02_proyectos.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
