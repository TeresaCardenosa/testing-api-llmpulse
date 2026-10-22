"""Pruebas locales sin credenciales ni conexion a LLM Pulse.

    py -m unittest discover -s tests -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llmpulse import schema  # noqa: E402
from llmpulse.config import load_env, set_env_value  # noqa: E402
from llmpulse.sampling import (  # noqa: E402
    choose_prompts,
    fetch_details,
    prompts_in_collection,
    write_flat_csv,
)

PROMPTS = [
    {"id": 501, "prompt_text": "Pregunta A", "collection_ids": [7],
     "tags": [{"id": 7, "name": "Sostenibilidad"}]},
    {"id": 502, "prompt_text": "Pregunta B", "collection_ids": [],
     "tags": [{"id": 7, "name": "Sostenibilidad"}]},
    {"id": 503, "prompt_text": "Pregunta C", "collection_ids": [9], "tags": []},
]


class FakeClient:
    """Cliente simulado que cuenta las llamadas realizadas."""

    def __init__(self):
        self.calls = []

    def get(self, path, **query):
        self.calls.append(path)
        execution_id = int(path.rsplit("/", 1)[-1])
        return {
            "id": execution_id,
            "prompt_id": 501 if execution_id < 2000 else 502,
            "prompt_text": "Pregunta A",
            "model": "chatgpt",
            "executed_at": "2026-10-15T12:00:00Z",
            # Mas de 10.000 caracteres: por eso existe la segunda llamada.
            "response": "Respuesta completa. " * 700,
            "sources": [{"url": "https://example.org/articulo", "title": "Titular"}],
            "app_url": "https://llmpulse.ai/app/answer/1",
        }


class PromptSelectionTests(unittest.TestCase):
    def test_collection_membership_via_ids_or_tags(self):
        """La pertenencia al tag se expone de dos formas; valen las dos."""
        selected = prompts_in_collection(PROMPTS, "7")
        self.assertEqual({p["id"] for p in selected}, {501, 502})

    def test_no_collection_returns_everything(self):
        self.assertEqual(len(prompts_in_collection(PROMPTS, None)), 3)

    def test_chooses_best_covered_prompts(self):
        """Se priorizan los prompts con mas respuestas, no el orden del listado."""
        summaries = (
            [{"id": i, "prompt_id": 501} for i in range(3)]
            + [{"id": 100 + i, "prompt_id": 502} for i in range(5)]
            + [{"id": 200 + i, "prompt_id": 503} for i in range(1)]
        )
        chosen = choose_prompts(summaries, 2)
        self.assertEqual(list(chosen), ["502", "501"])
        self.assertEqual(len(chosen["502"]), 5)

    def test_sample_is_not_a_flat_cap(self):
        """Con 4 prompts pedidos y 4 disponibles, entran los 4."""
        summaries = [{"id": i, "prompt_id": 500 + (i % 4)} for i in range(40)]
        self.assertEqual(len(choose_prompts(summaries, 4)), 4)


class FetchTests(unittest.TestCase):
    def test_full_text_and_cache(self):
        client = FakeClient()
        summaries = [{"id": 1001}, {"id": 1002}]
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder)
            details = fetch_details(client, "123", summaries, cache, max_answers=40)
            self.assertEqual(len(details), 2)
            self.assertGreater(len(details[0]["response"]), 10000)
            self.assertEqual(len(client.calls), 2)

            # Segunda pasada: todo desde cache, sin tocar la API.
            again = fetch_details(client, "123", summaries, cache, max_answers=40)
            self.assertEqual(len(again), 2)
            self.assertEqual(len(client.calls), 2, "la cache deberia evitar nuevas llamadas")

    def test_max_answers_is_a_safety_cap(self):
        client = FakeClient()
        summaries = [{"id": 1000 + i} for i in range(10)]
        with tempfile.TemporaryDirectory() as folder:
            details = fetch_details(client, "123", summaries, Path(folder), max_answers=3)
        self.assertEqual(len(details), 3)

    def test_duplicates_are_skipped(self):
        client = FakeClient()
        summaries = [{"id": 1001}, {"id": 1001}, {"id": 1002}]
        with tempfile.TemporaryDirectory() as folder:
            details = fetch_details(client, "123", summaries, Path(folder), max_answers=40)
        self.assertEqual(len(details), 2)


class FlatTableTests(unittest.TestCase):
    def test_one_row_per_answer_with_domains(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as folder:
            details = fetch_details(
                client, "123", [{"id": 1001}], Path(folder), max_answers=40
            )
            csv_path = Path(folder) / "respuestas.csv"
            write_flat_csv(csv_path, details, PROMPTS)
            content = csv_path.read_text(encoding="utf-8-sig")
        self.assertIn("example.org", content)
        self.assertIn("chatgpt", content)
        self.assertEqual(len(content.splitlines()[0].split(",")), 11)


class SchemaReportTests(unittest.TestCase):
    """El informe se versiona: no puede llevar contenido de cliente."""

    def test_sensitive_fields_have_no_example(self):
        for path, value in [
            ("response", "Texto confidencial del cliente"),
            ("prompt_text", "Que marca es mejor"),
            ("brand_name", "Cliente SA"),
            ("sources[].title", "Titular del articulo"),
        ]:
            with self.subTest(path=path):
                self.assertIsNone(schema._safe_example(path, value))

    def test_technical_fields_keep_an_example(self):
        self.assertEqual(schema._safe_example("model", "chatgpt"), "chatgpt")
        self.assertEqual(schema._safe_example("id", 1001), "1001")
        self.assertEqual(
            schema._safe_example("executed_at", "2026-10-15T12:00:00Z"),
            "2026-10-15T12:00:00Z",
        )

    def test_urls_are_reduced_to_domain(self):
        self.assertEqual(
            schema._safe_example("sources[].url", "https://example.org/ruta/privada"),
            "example.org",
        )

    def test_report_excludes_response_text(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as folder:
            details = fetch_details(
                client, "123", [{"id": 1001}, {"id": 2002}], Path(folder), max_answers=40
            )
        stats = schema.collect(details)
        report = schema.render(stats, len(details), {"prompts": 2, "models": 1})
        self.assertIn("`response`", report, "el campo debe aparecer en la tabla")
        self.assertNotIn("Respuesta completa.", report, "pero nunca su contenido")
        self.assertNotIn("Titular", report)
        self.assertIn("example.org", report)

    def test_fill_rate_detects_optional_fields(self):
        details = [
            {"a": 1, "b": "x"},
            {"a": 2, "b": None},
            {"a": 3, "b": ""},
        ]
        stats = schema.collect(details)
        report = schema.render(stats, 3, {})
        self.assertIn("| `a` | int | 100 % |", report)
        self.assertIn("| `b` | str? | 33 % |", report)


class EnvFileTests(unittest.TestCase):
    def test_parse_and_preserve_comments(self):
        with tempfile.TemporaryDirectory() as folder:
            env = Path(folder) / ".env"
            env.write_text(
                "# comentario\nLLMPULSE_API_KEY='secreta'\nVACIO=\n", encoding="utf-8"
            )
            values = load_env(env)
            self.assertEqual(values["LLMPULSE_API_KEY"], "secreta")
            self.assertEqual(values["VACIO"], "")

            set_env_value("LLMPULSE_PROJECT_ID", "123", env)
            set_env_value("LLMPULSE_API_KEY", "otra", env)
            text = env.read_text(encoding="utf-8")
            self.assertIn("# comentario", text, "los comentarios se conservan")
            self.assertIn("LLMPULSE_PROJECT_ID=123", text)
            self.assertIn("LLMPULSE_API_KEY=otra", text)
            self.assertEqual(text.count("LLMPULSE_API_KEY"), 1, "no se duplica la clave")

    def test_missing_file_is_not_an_error(self):
        self.assertEqual(load_env(Path("no_existe_este_fichero.env")), {})


if __name__ == "__main__":
    unittest.main()
