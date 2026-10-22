"""Paso 2: listar los proyectos y elegir uno.

    py scripts/02_proyectos.py            -> solo lista
    py scripts/02_proyectos.py 123        -> ademas fija LLMPULSE_PROJECT_ID en .env
"""

import os
import sys

import _bootstrap  # noqa: F401

from llmpulse import config
from llmpulse.client import LLMPulseClient, LLMPulseError
from llmpulse.display import heading, table


def main(argv: list[str]) -> int:
    heading("Paso 2 - Proyectos disponibles")
    try:
        client = LLMPulseClient(config.api_key())
        projects = client.get("/dimensions/projects").get("projects", [])
    except LLMPulseError as exc:
        print(f"\nERROR: {exc}")
        return 1
    if not isinstance(projects, list):
        print("\nERROR: la lista de proyectos no tiene la estructura esperada.")
        return 1

    table(projects, ("id", "name", "brand_name"), (9, 38, 35))

    if not argv:
        actual = os.environ.get("LLMPULSE_PROJECT_ID", "")
        print(f"\nProyecto fijado ahora mismo: {actual or '(ninguno)'}")
        print("Para elegir uno:  py scripts/02_proyectos.py <ID>")
        return 0

    chosen = argv[0].strip()
    if not any(str(p.get("id")) == chosen for p in projects):
        print(f"\nERROR: el proyecto {chosen} no figura entre los accesibles con tu clave.")
        return 1
    config.set_env_value("LLMPULSE_PROJECT_ID", chosen)
    print(f"\nGuardado LLMPULSE_PROJECT_ID={chosen} en .env")
    print("Siguiente: py scripts/03_tags_y_modelos.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
