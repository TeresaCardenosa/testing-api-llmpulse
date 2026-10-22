#!/usr/bin/env python3
"""Explorador / extractor en modo solo lectura para LLM Pulse API v1.

Python 3.10+; exclusivamente librería estándar.

Ejemplos:
  LLMPULSE_API_KEY=... python3 llmpulse_probe.py discover
  LLMPULSE_API_KEY=... LLMPULSE_PROJECT_ID=123 python3 llmpulse_probe.py discover
  LLMPULSE_API_KEY=... LLMPULSE_PROJECT_ID=123 LLMPULSE_COLLECTION_ID=7 \
    LLMPULSE_FROM=2026-10-12 LLMPULSE_TO=2026-10-18 \
    python3 llmpulse_probe.py extract

Solo realiza peticiones GET. Nunca envíes a terceros la clave de API ni los JSON
que contengan información potencialmente confidencial de tus clientes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://api.llmpulse.ai/api/v1"
PER_PAGE = 100
MAX_RETRIES = 5
TIMEOUT_SECONDS = 30


class LLMPulseError(RuntimeError):
    """Error de integración con la API."""


def _retry_seconds(header: str | None, attempt: int) -> float:
    """Retry-After puede expresar segundos o una fecha HTTP."""
    if header:
        try:
            return min(max(float(header), 0), 60)
        except ValueError:
            try:
                until = parsedate_to_datetime(header)
                return min(max((until - datetime.now(timezone.utc)).total_seconds(), 0), 60)
            except (ValueError, TypeError, OverflowError):
                pass
    return min(2**attempt, 60)


def _error_info(body: bytes) -> tuple[str, str, str]:
    try:
        parsed = json.loads(body.decode("utf-8"))
        if not isinstance(parsed, dict):
            return "HTTP_ERROR", "Respuesta de error inesperada", "-"
        err = parsed.get("error") or {}
        if not isinstance(err, dict):
            err = {}
        return (
            str(err.get("code", "HTTP_ERROR")),
            str(err.get("message", "Sin detalles")),
            str(parsed.get("request_id", "-")),
        )
    except (UnicodeDecodeError, ValueError):
        return "HTTP_ERROR", "Respuesta no JSON", "-"


class LLMPulseClient:
    def __init__(self, api_key: str):
        if not api_key or not api_key.strip():
            raise LLMPulseError("Falta LLMPULSE_API_KEY en las variables de entorno.")
        self.api_key = api_key.strip()

    def get(self, path: str, **query: object) -> dict:
        """GET con reintentos para 429, 5xx y fallos de red transitorios."""
        encoded = urlencode({k: v for k, v in query.items() if v is not None and v != ""})
        url = f"{API_URL}{path}" + (f"?{encoded}" if encoded else "")
        request = Request(
            url,
            method="GET",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
                "User-Agent": "LLMPulse-Narrative-Explorer-Python/1.0",
            },
        )
        for attempt in range(MAX_RETRIES):
            try:
                with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise LLMPulseError(f"{path}: la API no ha devuelto un objeto JSON.")
                    return payload
            except HTTPError as exc:
                code, message, request_id = _error_info(exc.read())
                if exc.code == 429 or exc.code >= 500:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(_retry_seconds(exc.headers.get("Retry-After"), attempt))
                        continue
                raise LLMPulseError(
                    f"{path}: HTTP {exc.code} / {code}: {message}. request_id={request_id}"
                ) from None
            except (URLError, TimeoutError, ConnectionError) as exc:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(_retry_seconds(None, attempt))
                    continue
                raise LLMPulseError(f"{path}: no se pudo conectar con la API: {exc}") from None
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise LLMPulseError(f"{path}: respuesta JSON ilegible: {exc}") from None
        raise LLMPulseError(f"{path}: se agotaron los reintentos.")

    def list_all(self, path: str, *, max_items: int | None = None, **filters: object) -> list[dict]:
        """Pagina un listado {data, total, page, per_page} sin exceder max_items."""
        result: list[dict] = []
        page = 1
        while max_items is None or len(result) < max_items:
            payload = self.get(path, page=page, per_page=PER_PAGE, **filters)
            items = payload.get("data")
            if not isinstance(items, list):
                raise LLMPulseError(f"{path}: falta el array 'data' en el listado; revisar esquema.")
            if any(not isinstance(x, dict) for x in items):
                raise LLMPulseError(f"{path}: el listado contiene elementos no JSON-objeto.")
            available = items if max_items is None else items[: max_items - len(result)]
            result.extend(available)
            try:
                total = int(payload["total"]) if payload.get("total") is not None else None
            except (TypeError, ValueError):
                total = None
            if not items or len(items) < PER_PAGE or (total is not None and page * PER_PAGE >= total):
                break
            page += 1
            if page > 100000:
                raise LLMPulseError(f"{path}: límite de seguridad de páginas superado.")
        return result


def _table(rows: list[dict], columns: tuple[str, ...], widths: tuple[int, ...]) -> None:
    if not rows:
        print("  (ningún registro)")
        return
    print("  " + "  ".join(c.ljust(w) for c, w in zip(columns, widths)))
    print("  " + "  ".join("-" * w for w in widths))
    for row in rows:
        cells = []
        for col, width in zip(columns, widths):
            raw = row.get(col, "")
            val = " ".join(str(raw if raw is not None else "").split())
            cells.append((val[: width - 1] + "…") if len(val) > width else val.ljust(width))
        print("  " + "  ".join(cells))


def discover(client: LLMPulseClient, project_id: str | None) -> None:
    """Descubrir proyectos; opcionalmente consultar tags, modelos y prompts."""
    ping = client.get("/ping")
    print(f"Conexión correcta: ok={ping.get('ok')} | request_id={ping.get('request_id', '-')}")
    projects = client.get("/dimensions/projects").get("projects", [])
    if not isinstance(projects, list):
        raise LLMPulseError("La lista de proyectos no tiene la estructura esperada.")
    print("\nPROYECTOS:")
    _table(projects, ("id", "name", "brand_name"), (9, 38, 35))
    if not project_id:
        print("\nSiguiente paso: define LLMPULSE_PROJECT_ID y vuelve a ejecutar discover.")
        return

    project = client.get(f"/dimensions/projects/{project_id}")
    collections = client.get("/dimensions/collections", project_id=project_id).get("collections", [])
    models = client.get("/dimensions/models", project_id=project_id).get("models", [])
    prompts = client.list_all("/dimensions/prompts", project_id=project_id)
    print(f"\nPROYECTO: {project.get('name', '-')} (ID {project.get('id', project_id)})")
    print(f"MODELOS CON DATOS: {', '.join(map(str, models)) if models else '(ninguno)'}")
    print("\nTAGS / COLECCIONES:")
    _table(collections, ("id", "name"), (10, 60))
    print(f"\nPROMPTS ({len(prompts)}):")
    shown = []
    for p in prompts:
        shown.append({
            "id": p.get("id"),
            "prompt_text": p.get("prompt_text", ""),
            "tags": ", ".join(t.get("name", "") for t in p.get("tags", []) if isinstance(t, dict)),
        })
    _table(shown, ("id", "prompt_text", "tags"), (10, 72, 40))
    print("\nNo se han guardado archivos. Para descargar una muestra, ejecuta extract.")


def _slug(value: object) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", str(value))


def extract(
    client: LLMPulseClient,
    project_id: str,
    collection_id: str | None,
    date_from: str,
    date_to: str,
    max_answers: int,
    output_dir: Path,
) -> Path:
    """Descarga el catálogo y el detalle COMPLETO de hasta max_answers."""
    project = client.get(f"/dimensions/projects/{project_id}")
    collections = client.get("/dimensions/collections", project_id=project_id).get("collections", [])
    models = client.get("/dimensions/models", project_id=project_id).get("models", [])
    prompts = client.list_all("/dimensions/prompts", project_id=project_id)
    if collection_id and not any(str(c.get("id")) == collection_id for c in collections):
        raise LLMPulseError(f"El tag {collection_id} no figura entre los del proyecto {project_id}.")

    summaries = client.list_all(
        "/answers",
        max_items=max_answers,
        project_id=project_id,
        collection_id=collection_id,
        **{"from": date_from, "to": date_to, "no_result": "false"},
    )
    print(f"Respuestas reales seleccionadas: {len(summaries)} (máximo {max_answers}).")
    indexed_prompts = {str(p.get("id")): p for p in prompts}
    answers = []
    seen = set()
    for index, item in enumerate(summaries, start=1):
        execution_id = item.get("id")
        if execution_id is None:
            raise LLMPulseError("/answers: una respuesta carece de ID de ejecución.")
        if str(execution_id) in seen:
            continue
        seen.add(str(execution_id))
        detail = client.get(f"/answers/{execution_id}", project_id=project_id)
        prompt_id = detail.get("prompt_id", item.get("prompt_id"))
        prompt = indexed_prompts.get(str(prompt_id), {})
        answers.append({
            "source_execution_id": detail.get("id", execution_id),
            "prompt_id": prompt_id,
            "prompt_text": detail.get("prompt_text", item.get("prompt_text")),
            "model": detail.get("model", item.get("model")),
            "executed_at": detail.get("executed_at", item.get("executed_at")),
            "response_text": detail.get("response"),
            "tags": prompt.get("tags", []),
            "sources": detail.get("sources", []),
            "app_url": detail.get("app_url", item.get("app_url")),
            "raw_detail": detail,
        })
        print(f"[{index}/{len(summaries)}] ejecución={execution_id} | modelo={detail.get('model', '?')}")

    selected_prompts = prompts
    if collection_id:
        selected_prompts = [
            p for p in prompts
            if collection_id in {str(x) for x in (p.get("collection_ids") or [])}
            or any(str(t.get("id")) == collection_id for t in p.get("tags", []) if isinstance(t, dict))
        ]

    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": "LLM Pulse REST API v1",
        "query": {
            "project_id": project_id,
            "collection_id": collection_id,
            "from": date_from,
            "to": date_to,
            "no_result": False,
            "max_answers": max_answers,
            "exported_answers": len(answers),
        },
        "project": project,
        "collections": collections,
        "models": models,
        "prompts": selected_prompts,
        "answers": answers,
    }
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    filename = (
        f"llmpulse_project_{_slug(project_id)}_tag_{_slug(collection_id or 'all')}_"
        f"{_slug(date_from)}_{_slug(date_to)}.json"
    )
    target = output_dir / filename
    # Igual que la versión anterior: la misma combinación de filtros actualiza el archivo.
    # El archivo almacena el JSON bruto del detalle para futura auditoría.
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    try:
        target.chmod(0o600)
    except OSError:
        pass  # Según el sistema de archivos, puede que no admita estos permisos.
    print(f"\nArchivo guardado en: {target}")
    print("ATENCIÓN: el JSON puede contener información confidencial del cliente.")
    if len(answers) == max_answers:
        print("Nota: has alcanzado el límite de la muestra. Sube LLMPULSE_MAX_ANSWERS si lo necesitas.")
    return target


def _valid_date(value: str, label: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise LLMPulseError(f"{label} debe tener formato AAAA-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise LLMPulseError(f"{label} no es una fecha válida.") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Explorar proyectos LLMPulse o extraer respuestas completas (solo lectura)."
    )
    parser.add_argument("mode", choices=["discover", "extract"], nargs="?", default="discover")
    args = parser.parse_args(argv)
    project_id = os.environ.get("LLMPULSE_PROJECT_ID")
    collection_id = os.environ.get("LLMPULSE_COLLECTION_ID")

    try:
        client = LLMPulseClient(os.environ.get("LLMPULSE_API_KEY", ""))
        if args.mode == "discover":
            discover(client, project_id)
            return 0
        date_from = os.environ.get("LLMPULSE_FROM")
        date_to = os.environ.get("LLMPULSE_TO")
        if not project_id or not date_from or not date_to:
            raise LLMPulseError(
                "Para extract define LLMPULSE_PROJECT_ID, LLMPULSE_FROM y LLMPULSE_TO."
            )
        start = _valid_date(date_from, "LLMPULSE_FROM")
        end = _valid_date(date_to, "LLMPULSE_TO")
        if start > end:
            raise LLMPulseError("LLMPULSE_FROM debe ser anterior o igual a LLMPULSE_TO.")
        try:
            max_answers = int(os.environ.get("LLMPULSE_MAX_ANSWERS", "10"))
        except ValueError:
            raise LLMPulseError("LLMPULSE_MAX_ANSWERS debe ser un número entero.") from None
        if not 1 <= max_answers <= 10000:
            raise LLMPulseError("LLMPULSE_MAX_ANSWERS debe estar entre 1 y 10000.")
        output_dir = Path(os.environ.get("LLMPULSE_OUTPUT_DIR") or Path(__file__).resolve().parent / "llmpulse_output")
        extract(client, project_id, collection_id, date_from, date_to, max_answers, output_dir)
        return 0
    except LLMPulseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
