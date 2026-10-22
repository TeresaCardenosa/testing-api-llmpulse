"""Paso 5: descargar la muestra de respuestas completas.

Selecciona N prompts del tag y descarga TODAS sus respuestas dentro de la
ventana temporal, cacheando cada una en data/raw/. Reejecutar no vuelve a
pedir a la API lo que ya esta descargado.

    py scripts/05_muestra.py
"""

import os
import re
from datetime import date

import _bootstrap  # noqa: F401  (ajusta sys.path)

from llmpulse import config
from llmpulse.client import LLMPulseClient, LLMPulseError
from llmpulse.display import heading
from llmpulse.sampling import (
    SUMMARY_SCAN_LIMIT,
    choose_prompts,
    fetch_details,
    parse_num_prompts,
    write_flat_csv,
    write_manifest,
)


def _valid_date(value: str, label: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise LLMPulseError(f"{label} debe tener formato AAAA-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise LLMPulseError(f"{label} no es una fecha valida.") from None


def main() -> int:
    project_id = config.require(
        "LLMPULSE_PROJECT_ID", "Ejecuta antes: py scripts/02_proyectos.py <ID>"
    )
    date_from = config.require("LLMPULSE_FROM", "Pon la fecha inicial en .env (AAAA-MM-DD).")
    date_to = config.require("LLMPULSE_TO", "Pon la fecha final en .env (AAAA-MM-DD).")
    collection_id = (os.environ.get("LLMPULSE_COLLECTION_ID") or "").strip() or None
    max_answers = int(os.environ.get("LLMPULSE_MAX_ANSWERS", "40") or 40)

    heading("Paso 5 - Descarga de la muestra")
    try:
        if _valid_date(date_from, "LLMPULSE_FROM") > _valid_date(date_to, "LLMPULSE_TO"):
            raise LLMPulseError("LLMPULSE_FROM debe ser anterior o igual a LLMPULSE_TO.")
        num_prompts = parse_num_prompts(os.environ.get("LLMPULSE_NUM_PROMPTS"))

        client = LLMPulseClient(config.api_key())
        project = client.get(f"/dimensions/projects/{project_id}")
        models = client.get("/dimensions/models", project_id=project_id).get("models", [])
        prompts = client.list_all("/dimensions/prompts", project_id=project_id)

        print(f"Proyecto {project_id} | tag {collection_id or 'todos'} | {date_from} a {date_to}")
        objetivo = "TODOS los prompts" if num_prompts is None else f"{num_prompts} prompts distintos"
        print(f"Objetivo: {objetivo} (tope de seguridad: {max_answers} respuestas)")

        # Se pide el listado y se agrupa por prompt en local, en vez de filtrar por
        # prompt_id en la API: asi no dependemos de un parametro no documentado.
        print("\nConsultando el listado de respuestas...")
        summaries = client.list_all(
            "/answers",
            max_items=SUMMARY_SCAN_LIMIT,
            project_id=project_id,
            collection_id=collection_id,
            **{"from": date_from, "to": date_to, "no_result": "false"},
        )
        print(f"Respuestas reales en la ventana: {len(summaries)}")
        if not summaries:
            print(
                "\nNo hay respuestas en esta ventana."
                "\n  1. La cadencia es SEMANAL: comprueba que la ventana cubra una"
                "\n     semana entera. Una ventana de uno o dos dias puede no incluir"
                "\n     ningun dia de ejecucion y devolver cero sin que nada falle."
                "\n  2. Revisa el ID de tag."
                "\n  3. Comprueba que existan ejecuciones en ese periodo."
            )
            return 1

        chosen = choose_prompts(summaries, num_prompts)
        indexed = {str(p.get("id")): p for p in prompts}
        print(f"\nPrompts seleccionados ({len(chosen)}):")
        for prompt_id, items in chosen.items():
            text = indexed.get(prompt_id, {}).get("prompt_text") or "(texto no disponible)"
            preview = " ".join(str(text).split())[:70]
            print(f"  prompt {prompt_id:<10} {len(items):>3} respuestas  {preview}")

        flat = [item for items in chosen.values() for item in items]
        print(f"\nDescargando el detalle completo de {len(flat)} respuestas...")
        details = fetch_details(client, project_id, flat, config.DATA_RAW, max_answers)
    except LLMPulseError as exc:
        print(f"\nERROR: {exc}")
        return 1

    manifest = config.DATA_INTERIM / "muestra.json"
    csv_path = config.DATA_INTERIM / "respuestas.csv"
    write_manifest(
        manifest,
        project=project,
        collection_id=collection_id,
        date_from=date_from,
        date_to=date_to,
        models=models,
        chosen=chosen,
        prompts=prompts,
        details=details,
    )
    write_flat_csv(csv_path, details, prompts)

    print(f"\nRespuestas descargadas: {len(details)}")
    print(f"  cache    : {config.DATA_RAW}")
    print(f"  manifiesto: {manifest}")
    print(f"  tabla    : {csv_path}")
    print("\nATENCION: data/ contiene informacion confidencial y no se versiona.")
    print("\nSiguiente: py scripts/06_esquema.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
