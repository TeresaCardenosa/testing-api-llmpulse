"""Cliente HTTP de solo lectura para la API v1 de LLM Pulse.

Trasladado desde llmpulse_probe.py sin cambios de logica. Solo realiza
peticiones GET: no modifica proyectos, prompts ni tags, y no ejecuta modelos.

Nunca envies a terceros la clave de API ni los JSON con datos de clientes.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://api.llmpulse.ai/api/v1"
PER_PAGE = 100
MAX_RETRIES = 5
TIMEOUT_SECONDS = 30


class LLMPulseError(RuntimeError):
    """Error de integracion con la API."""


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


def _tls_hint(exc: Exception) -> str:
    """Reconocer el fallo de certificado del proxy corporativo y orientar."""
    text = str(exc)
    if "CERTIFICATE_VERIFY_FAILED" in text or "certificate" in text.lower():
        return (
            "\n  La verificacion del certificado ha fallado. Si estas en una red"
            " con inspeccion TLS (p. ej. Havas), instala truststore:"
            "\n    py -m pip install -r requirements.txt"
        )
    return ""


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
                raise LLMPulseError(
                    f"{path}: no se pudo conectar con la API: {exc}{_tls_hint(exc)}"
                ) from None
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
                raise LLMPulseError(f"{path}: limite de seguridad de paginas superado.")
        return result
