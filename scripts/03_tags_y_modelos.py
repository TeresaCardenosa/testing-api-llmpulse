"""Paso 3: ver los tags y los modelos con datos del proyecto, y elegir tag.

Los modelos que salen aqui son los que tienen respuestas en el proyecto, no
todos los que soporta LLM Pulse.

    py scripts/03_tags_y_modelos.py       -> lista tags y modelos
    py scripts/03_tags_y_modelos.py 7     -> ademas fija LLMPULSE_COLLECTION_ID
"""

import os
import sys

import _bootstrap  # noqa: F401

from llmpulse import config
from llmpulse.client import LLMPulseClient, LLMPulseError
from llmpulse.display import heading, table


def main(argv: list[str]) -> int:
    project_id = config.require(
        "LLMPULSE_PROJECT_ID", "Ejecuta antes: py scripts/02_proyectos.py <ID>"
    )
    heading(f"Paso 3 - Tags y modelos del proyecto {project_id}")
    try:
        client = LLMPulseClient(config.api_key())
        project = client.get(f"/dimensions/projects/{project_id}")
        collections = client.get(
            "/dimensions/collections", project_id=project_id
        ).get("collections", [])
        models = client.get("/dimensions/models", project_id=project_id).get("models", [])
    except LLMPulseError as exc:
        print(f"\nERROR: {exc}")
        return 1

    print(f"Proyecto: {project.get('name', '-')} (ID {project.get('id', project_id)})")
    print(f"\nMODELOS CON DATOS ({len(models)}): {', '.join(map(str, models)) or '(ninguno)'}")

    print("\nTAGS / COLLECTIONS:")
    table(collections, ("id", "name"), (10, 60))

    if not argv:
        actual = os.environ.get("LLMPULSE_COLLECTION_ID", "")
        print(f"\nTag fijado ahora mismo: {actual or '(ninguno: se usarian todos)'}")
        print("Para elegir uno:  py scripts/03_tags_y_modelos.py <ID>")
        return 0

    chosen = argv[0].strip()
    if not any(str(c.get("id")) == chosen for c in collections):
        print(f"\nERROR: el tag {chosen} no pertenece al proyecto {project_id}.")
        return 1
    config.set_env_value("LLMPULSE_COLLECTION_ID", chosen)
    print(f"\nGuardado LLMPULSE_COLLECTION_ID={chosen} en .env")
    print("Siguiente: py scripts/04_prompts.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
