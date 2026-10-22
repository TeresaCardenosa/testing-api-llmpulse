"""Carga de configuracion y arreglo de TLS corporativo.

Importar este modulo tiene dos efectos, en este orden:

1. Habilita la verificacion TLS contra el almacen de certificados del sistema,
   si `truststore` esta instalado. Hace falta en redes con inspeccion TLS
   (la de Havas intercepta llmpulse.ai y firma con una autoridad privada que
   OpenSSL no conoce). Si no esta instalado no pasa nada: fuera de esas redes
   la verificacion normal funciona.
2. Vuelca las variables de `.env` al entorno del proceso, sin pisar las que ya
   vengan definidas desde fuera.

Solo biblioteca estandar: no hace falta `pip install` para usar el repositorio.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Raiz del repositorio: .../src/llmpulse/config.py -> subir tres niveles.
ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"
DATA_RAW = ROOT / "data" / "raw"
DATA_INTERIM = ROOT / "data" / "interim"
DOCS = ROOT / "docs"

#: True si la verificacion se delego en el almacen del sistema.
SYSTEM_TRUST_ENABLED = False


def _enable_system_trust() -> None:
    """Delegar la verificacion TLS en el almacen de certificados del sistema."""
    global SYSTEM_TRUST_ENABLED
    try:
        import truststore
    except ImportError:
        return  # Sin proxy corporativo no hace falta; ver requirements.txt.
    truststore.inject_into_ssl()
    SYSTEM_TRUST_ENABLED = True


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def load_env(path: Path | None = None) -> dict[str, str]:
    """Leer un .env sencillo y exportarlo al entorno.

    El entorno manda: una variable ya definida fuera no se sobreescribe, para
    poder lanzar un script puntual con otro valor sin tocar el fichero.
    """
    target = path or ENV_PATH
    loaded: dict[str, str] = {}
    if not target.exists():
        return loaded
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        loaded[key] = _unquote(value)
        if key not in os.environ:
            os.environ[key] = loaded[key]
    return loaded


def set_env_value(key: str, value: str, path: Path | None = None) -> None:
    """Fijar una clave en .env conservando el resto del fichero.

    Lo usan los scripts 02 y 03 para recordar el proyecto y el tag elegidos.
    Reescribe la linea si la clave existe y la anade al final si no, sin tocar
    comentarios ni orden. Tambien actualiza el entorno del proceso actual.
    """
    target = path or ENV_PATH
    lines = target.read_text(encoding="utf-8").splitlines() if target.exists() else []
    replaced = False
    for index, raw_line in enumerate(lines):
        stripped = raw_line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.partition("=")[0].strip() == key:
            lines[index] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        target.chmod(0o600)
    except OSError:
        pass  # Segun el sistema de archivos puede no admitirse.
    os.environ[key] = value


def require(key: str, hint: str) -> str:
    """Leer una variable obligatoria o salir con un mensaje util."""
    value = (os.environ.get(key) or "").strip()
    if not value:
        print(f"ERROR: falta {key} en .env\n  -> {hint}", file=sys.stderr)
        raise SystemExit(1)
    return value


def api_key() -> str:
    return require(
        "LLMPULSE_API_KEY",
        "Copia .env.example a .env y pon tu clave en LLMPULSE_API_KEY.",
    )


_enable_system_trust()
load_env()
