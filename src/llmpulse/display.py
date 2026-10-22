"""Utilidades de impresion por pantalla compartidas por los scripts."""

from __future__ import annotations


def table(rows: list[dict], columns: tuple[str, ...], widths: tuple[int, ...]) -> None:
    """Imprimir una tabla de ancho fijo, recortando los valores largos."""
    if not rows:
        print("  (ningun registro)")
        return
    print("  " + "  ".join(c.ljust(w) for c, w in zip(columns, widths)))
    print("  " + "  ".join("-" * w for w in widths))
    for row in rows:
        cells = []
        for col, width in zip(columns, widths):
            raw = row.get(col, "")
            val = " ".join(str(raw if raw is not None else "").split())
            cells.append((val[: width - 1] + "\u2026") if len(val) > width else val.ljust(width))
        print("  " + "  ".join(cells))


def heading(text: str) -> None:
    print(f"\n{text}")
    print("=" * len(text))
