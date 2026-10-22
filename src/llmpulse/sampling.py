"""Seleccion de la muestra y descarga de respuestas completas.

Criterio de muestreo: N prompts distintos del tag, con TODAS sus respuestas en
la ventana temporal. No un tope plano sobre /answers, porque las primeras 20
respuestas del listado pueden ser todas del mismo prompt en fechas distintas,
y entonces no hay nada que comparar entre modelos.

Las respuestas se cachean en data/raw/<execution_id>.json. Reejecutar no vuelve
a pedir a la API lo que ya esta descargado.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .client import LLMPulseClient, LLMPulseError

#: Tope de seguridad de respuestas a inspeccionar en el listado antes de agrupar.
SUMMARY_SCAN_LIMIT = 2000


def prompts_in_collection(prompts: list[dict], collection_id: str | None) -> list[dict]:
    """Filtrar los prompts que pertenecen a un tag.

    La API expone la pertenencia de dos formas segun el endpoint, asi que se
    comprueban ambas: `collection_ids` y la lista `tags`.
    """
    if not collection_id:
        return prompts
    selected = []
    for prompt in prompts:
        in_ids = collection_id in {str(x) for x in (prompt.get("collection_ids") or [])}
        in_tags = any(
            str(tag.get("id")) == collection_id
            for tag in prompt.get("tags", [])
            if isinstance(tag, dict)
        )
        if in_ids or in_tags:
            selected.append(prompt)
    return selected


def choose_prompts(summaries: list[dict], num_prompts: int) -> dict[str, list[dict]]:
    """Agrupar el listado por prompt y quedarse con los N mejor cubiertos.

    Se prefieren los prompts con mas respuestas: dan la comparacion entre
    modelos mas rica, que es el objetivo del experimento.
    """
    grouped: dict[str, list[dict]] = {}
    for item in summaries:
        key = str(item.get("prompt_id"))
        grouped.setdefault(key, []).append(item)
    ranked = sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return dict(ranked[:num_prompts])


def fetch_details(
    client: LLMPulseClient,
    project_id: str,
    summaries: list[dict],
    cache_dir: Path,
    max_answers: int,
) -> list[dict]:
    """Descargar el detalle completo de cada respuesta, usando cache en disco.

    La segunda llamada a /answers/{id} es imprescindible: el listado trunca el
    texto a 10.000 caracteres y el NAR necesita la respuesta integra.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    details: list[dict] = []
    seen: set[str] = set()
    for item in summaries:
        if len(details) >= max_answers:
            print(f"  Tope de seguridad alcanzado ({max_answers}); se detiene la descarga.")
            break
        execution_id = item.get("id")
        if execution_id is None:
            raise LLMPulseError("/answers: una respuesta carece de ID de ejecucion.")
        key = str(execution_id)
        if key in seen:
            continue
        seen.add(key)
        cached = cache_dir / f"{key}.json"
        if cached.exists():
            detail = json.loads(cached.read_text(encoding="utf-8"))
            origin = "cache"
        else:
            detail = client.get(f"/answers/{execution_id}", project_id=project_id)
            cached.write_text(
                json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            origin = "API"
        details.append(detail)
        text = detail.get("response") or ""
        print(
            f"  [{len(details):>3}] ejecucion={key:<12} modelo={detail.get('model', '?'):<12}"
            f" chars={len(text):<7} ({origin})"
        )
    return details


def write_manifest(
    path: Path,
    *,
    project: dict,
    collection_id: str | None,
    date_from: str,
    date_to: str,
    models: list,
    chosen: dict[str, list[dict]],
    prompts: list[dict],
    details: list[dict],
) -> None:
    """Dejar constancia de QUE se descargo y por que, para poder reproducirlo."""
    indexed = {str(p.get("id")): p for p in prompts}
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": "LLM Pulse REST API v1",
        "query": {
            "project_id": project.get("id"),
            "collection_id": collection_id,
            "from": date_from,
            "to": date_to,
            "no_result": False,
        },
        "project": project,
        "models_with_data": models,
        "sampled_prompts": [
            {
                "prompt_id": prompt_id,
                "prompt_text": indexed.get(prompt_id, {}).get("prompt_text"),
                "answers_in_window": len(items),
            }
            for prompt_id, items in chosen.items()
        ],
        "downloaded_answers": len(details),
        "execution_ids": [d.get("id") for d in details],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_flat_csv(path: Path, details: list[dict], prompts: list[dict]) -> None:
    """Tabla plana: una fila por (prompt x modelo x fecha).

    Es la unidad de analisis sobre la que operara el NAR. Contiene el texto
    integro de las respuestas, asi que vive en data/ y NO se versiona.
    """
    indexed = {str(p.get("id")): p for p in prompts}
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "execution_id",
        "prompt_id",
        "prompt_text",
        "tags",
        "model",
        "executed_at",
        "response_chars",
        "num_sources",
        "source_domains",
        "app_url",
        "response_text",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for detail in details:
            prompt_id = str(detail.get("prompt_id"))
            prompt = indexed.get(prompt_id, {})
            sources = detail.get("sources") or []
            domains = []
            for source in sources:
                if isinstance(source, dict):
                    url = str(source.get("url") or "")
                    if "//" in url:
                        domains.append(url.split("//", 1)[1].split("/", 1)[0])
            text = detail.get("response") or ""
            writer.writerow({
                "execution_id": detail.get("id"),
                "prompt_id": prompt_id,
                "prompt_text": detail.get("prompt_text") or prompt.get("prompt_text"),
                "tags": ", ".join(
                    str(t.get("name", "")) for t in prompt.get("tags", []) if isinstance(t, dict)
                ),
                "model": detail.get("model"),
                "executed_at": detail.get("executed_at"),
                "response_chars": len(text),
                "num_sources": len(sources),
                "source_domains": ", ".join(sorted(set(domains))),
                "app_url": detail.get("app_url"),
                "response_text": text,
            })
