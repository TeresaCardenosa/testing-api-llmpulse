"""Informe del esquema real de las respuestas de la API.

Este modulo produce docs/ESQUEMA.md, el documento de traspaso: dice que campos
devuelve /answers/{id}, de que tipo son, con que frecuencia vienen rellenos y
como de largos son. Con eso se puede disenar el NAR sin hacer una sola llamada.

REGLA DE CONFIDENCIALIDAD
El informe se versiona en git, asi que NO puede contener datos de clientes.
Solo se imprimen valores de ejemplo para campos inequivocamente tecnicos
(identificadores, fechas, booleanos, numeros, nombres de modelo) y, para las
URLs, unicamente el dominio. Todo lo demas se reporta como forma: tipo,
relleno y longitud, nunca contenido.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

#: Nombres de campo cuyo valor NUNCA se imprime (pueden identificar al cliente).
SENSITIVE_HINTS = (
    "response", "text", "content", "answer", "body", "snippet", "summary",
    "description", "title", "name", "brand", "company", "client", "prompt",
    "email", "author", "query", "keyword",
)

#: Campos tecnicos cuyo valor corto si es seguro mostrar.
SAFE_HINTS = (
    "id", "model", "status", "type", "state", "lang", "locale", "country",
    "currency", "position", "rank", "score", "sentiment", "count", "total",
    "index", "order", "version", "provider", "engine", "region",
)

MAX_EXAMPLE_CHARS = 48


def _type_name(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _leaf_name(path: str) -> str:
    return path.replace("[]", "").rsplit(".", 1)[-1].lower()


def _safe_example(path: str, value: object) -> str | None:
    """Devolver un ejemplo publicable, o None si el campo no es seguro."""
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str) or not value:
        return None
    name = _leaf_name(path)
    # Las URL se reducen al dominio: util para el NAR, sin la ruta concreta.
    if "url" in name or value.startswith(("http://", "https://")):
        if "//" in value:
            return value.split("//", 1)[1].split("/", 1)[0]
        return None
    if any(hint in name for hint in SENSITIVE_HINTS):
        return None
    # Fechas ISO: siempre seguras y muy informativas.
    if len(value) >= 10 and value[:4].isdigit() and value[4] == "-":
        return value[:MAX_EXAMPLE_CHARS]
    if any(hint == name or name.endswith("_" + hint) for hint in SAFE_HINTS):
        return value[:MAX_EXAMPLE_CHARS]
    return None


class FieldStats:
    """Acumulador de observaciones de un unico campo."""

    def __init__(self) -> None:
        self.types: set[str] = set()
        self.present = 0
        self.filled = 0
        self.lengths: list[int] = []
        self.example: str | None = None

    def observe(self, path: str, value: object) -> None:
        self.present += 1
        self.types.add(_type_name(value))
        empty = value is None or (isinstance(value, (str, list, dict)) and len(value) == 0)
        if not empty:
            self.filled += 1
        if isinstance(value, (str, list)):
            self.lengths.append(len(value))
        if self.example is None and not empty:
            self.example = _safe_example(path, value)


def _walk(node: object, stats: dict[str, FieldStats], prefix: str = "") -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else key
            stats[path].observe(path, value)
            _walk(value, stats, path)
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, (dict, list)):
                _walk(item, stats, f"{prefix}[]")


def collect(details: list[dict]) -> dict[str, FieldStats]:
    """Recorrer todas las respuestas y acumular estadisticas por campo."""
    stats: dict[str, FieldStats] = defaultdict(FieldStats)
    for detail in details:
        _walk(detail, stats)
    return dict(stats)


def _length_cell(stats: FieldStats) -> str:
    if not stats.lengths:
        return "-"
    low, high = min(stats.lengths), max(stats.lengths)
    if low == high:
        return str(low)
    return f"{low}-{high} (med. {round(mean(stats.lengths))})"


def render(stats: dict[str, FieldStats], total: int, context: dict) -> str:
    """Componer el markdown del informe de traspaso."""
    lines = [
        "# Esquema de las respuestas de LLM Pulse",
        "",
        "> Generado por `scripts/06_esquema.py` a partir de una muestra real.",
        "> **No contiene datos de clientes**: solo la forma de los campos.",
        "> Para regenerarlo, vuelve a ejecutar los scripts 05 y 06.",
        "",
        "## Muestra analizada",
        "",
        f"- Respuestas inspeccionadas: **{total}**",
        f"- Prompts distintos: **{context.get('prompts', '-')}**",
        f"- Modelos distintos: **{context.get('models', '-')}**",
        f"- Ventana temporal: **{context.get('window', '-')}**",
        "",
        "## Como leer la tabla",
        "",
        "- **Relleno**: porcentaje de respuestas donde el campo viene con valor no vacio.",
        "  Un campo al 100 % se puede dar por garantizado; por debajo, hay que tratarlo",
        "  como opcional en el codigo del NAR.",
        "- **Longitud**: numero de caracteres para cadenas, numero de elementos para listas.",
        "- **Ejemplo**: solo para campos tecnicos. Las URL aparecen reducidas al dominio.",
        "  Un guion significa que el campo se omite por confidencialidad, no que este vacio.",
        "- `sources[].url` se lee: campo `url` dentro de cada elemento de la lista `sources`.",
        "",
        "## Campos",
        "",
        "| Campo | Tipo | Relleno | Longitud | Ejemplo |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for path in sorted(stats):
        item = stats[path]
        types = "/".join(sorted(t for t in item.types if t != "null")) or "null"
        if "null" in item.types and types != "null":
            types += "?"
        pct = round(100 * item.filled / total) if total else 0
        example = (item.example or "-").replace("|", "\\|")
        lines.append(
            f"| `{path}` | {types} | {pct} % | {_length_cell(item)} | {example} |"
        )
    lines += [
        "",
        "## Notas para el desarrollo del NAR",
        "",
        "- **El texto integro esta en `response`.** El listado `/answers` lo trunca a",
        "  10.000 caracteres, por eso el script 05 hace una segunda llamada a",
        "  `/answers/{id}` por cada respuesta. No prescindas de esa llamada.",
        "- **`sources[]` es la via para atribucion y share of voice**: contiene las",
        "  referencias que el modelo cita. Comprueba arriba su relleno antes de",
        "  construir metricas que dependan de el.",
        "- **La unidad de analisis es (prompt x modelo x fecha)**, que es como esta",
        "  aplanado `data/interim/respuestas.csv`. Un mismo prompt se ejecuta contra",
        "  varios modelos: ahi es donde se compara la narrativa.",
        "- **Ojo con las fechas**: los filtros de `/answers` se refieren a cuando se",
        "  genero la respuesta; los de `/dimensions/prompts`, a cuando se creo el prompt.",
        "",
    ]
    return "\n".join(lines)


def load_cached(cache_dir: Path) -> list[dict]:
    """Leer las respuestas ya descargadas en data/raw/."""
    details = []
    for path in sorted(cache_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            print(f"  AVISO: {path.name} no es JSON legible; se omite.")
            continue
        if isinstance(payload, dict):
            details.append(payload)
    return details
