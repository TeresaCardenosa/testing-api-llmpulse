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
    # Los dominios identifican al cliente y a sus competidores vigilados.
    # Para un repositorio publico eso es informacion comercial confidencial,
    # asi que tampoco se publican, ni siquiera reducidos a host.
    "url", "domain", "host", "merchant",
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
    if any(hint in name for hint in SENSITIVE_HINTS):
        return None
    if value.startswith(("http://", "https://")) or "/" in value:
        return None  # Valor con forma de URL aunque el campo no se llame asi.
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


def _parent(path: str) -> str:
    """Contenedor en el que vive un campo: 'sources[].url' -> 'sources[]'."""
    return path.rsplit(".", 1)[0] if "." in path else ""


def _walk(
    node: object,
    stats: dict[str, FieldStats],
    containers: dict[str, int],
    prefix: str = "",
) -> None:
    if isinstance(node, dict):
        # Contar el contenedor: es el denominador del relleno de sus campos.
        containers[prefix] = containers.get(prefix, 0) + 1
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else key
            stats[path].observe(path, value)
            _walk(value, stats, containers, path)
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, (dict, list)):
                _walk(item, stats, containers, f"{prefix}[]")


def collect(details: list[dict]) -> tuple[dict[str, FieldStats], dict[str, int]]:
    """Recorrer las respuestas y acumular estadisticas por campo.

    Devuelve tambien cuantas veces se vio cada contenedor. Hace falta porque el
    relleno de un campo anidado NO se mide sobre el numero de respuestas: un
    campo dentro de sources[] puede observarse 300 veces en 20 respuestas, y
    dividir entre 20 daria porcentajes por encima del 100 %.
    """
    stats: dict[str, FieldStats] = defaultdict(FieldStats)
    containers: dict[str, int] = {}
    for detail in details:
        _walk(detail, stats, containers)
    return dict(stats), containers


def _length_cell(stats: FieldStats) -> str:
    if not stats.lengths:
        return "-"
    low, high = min(stats.lengths), max(stats.lengths)
    if low == high:
        return str(low)
    return f"{low}-{high} (med. {round(mean(stats.lengths))})"


def render(
    stats: dict[str, FieldStats],
    containers: dict[str, int],
    total: int,
    context: dict,
) -> str:
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
        "- **Relleno**: porcentaje de veces que el campo viene con valor no vacio,",
        "  medido sobre la **base** indicada en la columna siguiente. Un campo al 100 %",
        "  se puede dar por garantizado; por debajo, hay que tratarlo como opcional.",
        "- **Base**: cuantas veces podia aparecer el campo. Para los de primer nivel es el",
        "  numero de respuestas. Para los anidados es el numero de elementos de la lista que",
        f"  los contiene: `sources[].url` se mide sobre todas las fuentes de las {total}",
        "  respuestas, no sobre las respuestas.",
        "- **Longitud**: numero de caracteres para cadenas, numero de elementos para listas.",
        "- **Ejemplo**: solo para campos tecnicos (ids, fechas, numeros, modelos). Un guion",
        "  significa que se omite por confidencialidad, no que este vacio. **Las URL y los",
        "  dominios no se publican**: identifican al cliente y a sus competidores.",
        "- `sources[].url` se lee: campo `url` dentro de cada elemento de la lista `sources`.",
        "",
        "## Campos",
        "",
        "| Campo | Tipo | Relleno | Base | Longitud | Ejemplo |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for path in sorted(stats):
        item = stats[path]
        types = "/".join(sorted(t for t in item.types if t != "null")) or "null"
        if "null" in item.types and types != "null":
            types += "?"
        base = containers.get(_parent(path)) or total
        pct = round(100 * item.filled / base) if base else 0
        example = (item.example or "-").replace("|", "\\|")
        lines.append(
            f"| `{path}` | {types} | {pct} % | {base} | {_length_cell(item)} | {example} |"
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
        "- **La cadencia de ejecucion es semanal**, no diaria. Mira la distribucion de",
        "  `executed_at` en la muestra para confirmar en que dia cae. Cualquier ventana",
        "  temporal mas corta que una semana puede devolver cero respuestas.",
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
