"""Paso 4: listar los prompts del tag elegido.

    py scripts/04_prompts.py
"""

import os

import _bootstrap  # noqa: F401  (ajusta sys.path)

from llmpulse import config
from llmpulse.client import LLMPulseClient, LLMPulseError
from llmpulse.display import heading, table
from llmpulse.sampling import prompts_in_collection


def main() -> int:
    project_id = config.require(
        "LLMPULSE_PROJECT_ID", "Ejecuta antes: py scripts/02_proyectos.py <ID>"
    )
    collection_id = (os.environ.get("LLMPULSE_COLLECTION_ID") or "").strip() or None
    heading(f"Paso 4 - Prompts del proyecto {project_id}")
    try:
        client = LLMPulseClient(config.api_key())
        prompts = client.list_all("/dimensions/prompts", project_id=project_id)
    except LLMPulseError as exc:
        print(f"\nERROR: {exc}")
        return 1

    selected = prompts_in_collection(prompts, collection_id)
    scope = f"tag {collection_id}" if collection_id else "todos los tags"
    print(f"Alcance: {scope}")
    print(f"Prompts en el proyecto: {len(prompts)} | en este alcance: {len(selected)}")

    if collection_id and not selected:
        print(
            "\nAVISO: ningun prompt declara este tag en /dimensions/prompts."
            "\nPuede que la pertenencia solo se exponga al filtrar las respuestas;"
            "\nel paso 5 funcionara igualmente porque filtra /answers por collection_id."
        )

    rows = [
        {
            "id": p.get("id"),
            "prompt_text": p.get("prompt_text", ""),
            "tags": ", ".join(
                str(t.get("name", "")) for t in p.get("tags", []) if isinstance(t, dict)
            ),
        }
        for p in selected
    ]
    print()
    table(rows, ("id", "prompt_text", "tags"), (10, 70, 34))
    print("\nSiguiente: py scripts/05_muestra.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
