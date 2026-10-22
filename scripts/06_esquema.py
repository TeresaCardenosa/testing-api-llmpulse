"""Paso 6: generar docs/ESQUEMA.md a partir de las respuestas descargadas.

No llama a la API: lee lo que haya en data/raw/. El documento resultante SI se
versiona, porque contiene solo la forma de los campos, nunca su contenido.

    py scripts/06_esquema.py
"""

import json

import _bootstrap  # noqa: F401  (ajusta sys.path)

from llmpulse import config, schema
from llmpulse.display import heading


def main() -> int:
    heading("Paso 6 - Informe de esquema")
    details = schema.load_cached(config.DATA_RAW)
    if not details:
        print(f"No hay respuestas en {config.DATA_RAW}.")
        print("Ejecuta antes: py scripts/05_muestra.py")
        return 1

    models = {d.get("model") for d in details if d.get("model")}
    context = {"models": len(models)}
    manifest_path = config.DATA_INTERIM / "muestra.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            query = manifest.get("query", {})
            context["prompts"] = len(manifest.get("sampled_prompts") or [])
            context["window"] = f"{query.get('from', '?')} a {query.get('to', '?')}"
        except (ValueError, UnicodeDecodeError):
            print("  AVISO: el manifiesto no es legible; se omite su contexto.")

    stats, containers = schema.collect(details)
    config.DOCS.mkdir(parents=True, exist_ok=True)
    target = config.DOCS / "ESQUEMA.md"
    target.write_text(
        schema.render(stats, containers, len(details), context), encoding="utf-8"
    )

    print(f"Respuestas inspeccionadas: {len(details)}")
    print(f"Modelos distintos: {len(models)}")
    print(f"Campos distintos encontrados: {len(stats)}")
    print(f"\nInforme escrito en: {target}")
    print("Este fichero SI se versiona. Revisalo antes de subirlo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
