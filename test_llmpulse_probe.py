"""Pruebas locales sin credenciales ni conexión a LLMPulse."""
import json
import tempfile
import unittest
from pathlib import Path

from llmpulse_probe import LLMPulseClient, LLMPulseError, extract, _valid_date


class FakeClient:
    def __init__(self):
        self.paths = []

    def get(self, path, **query):
        self.paths.append((path, query))
        if path == '/dimensions/projects/123':
            return {'id': 123, 'name': 'Empresa demo'}
        if path == '/dimensions/collections':
            return {'collections': [{'id': 7, 'name': 'Sostenibilidad'}]}
        if path == '/dimensions/models':
            return {'models': ['chatgpt', 'gemini']}
        if path == '/answers/1001':
            return {'id': 1001, 'prompt_id': 501, 'prompt_text': '¿Sostenibilidad?',
                    'model': 'chatgpt', 'executed_at': '2026-10-15T12:00:00Z',
                    'response': 'Respuesta completa. ' * 3000,
                    'sources': [{'url': 'https://example.org'}], 'app_url': 'https://llmpulse.ai/app/...'}
        raise AssertionError(f'GET inesperado: {path} {query}')

    def list_all(self, path, **kwargs):
        self.paths.append((path, kwargs))
        if path == '/dimensions/prompts':
            return [{'id': 501, 'prompt_text': '¿Sostenibilidad?',
                     'collection_ids': [7], 'tags': [{'id': 7, 'name': 'Sostenibilidad'}]}]
        if path == '/answers':
            assert kwargs['no_result'] == 'false'
            assert kwargs['max_items'] == 10
            return [{'id': 1001, 'prompt_id': 501, 'model': 'chatgpt'}]
        raise AssertionError(f'LIST inesperado: {path} {kwargs}')


class ExtractTests(unittest.TestCase):
    def test_export_includes_complete_text_and_sources(self):
        client = FakeClient()
        with tempfile.TemporaryDirectory() as folder:
            target = extract(client, '123', '7', '2026-10-12', '2026-10-18', 10, Path(folder))
            self.assertTrue(target.exists())
            payload = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(payload['query']['exported_answers'], 1)
            self.assertEqual(payload['answers'][0]['source_execution_id'], 1001)
            self.assertTrue(len(payload['answers'][0]['response_text']) > 10000)
            self.assertEqual(payload['answers'][0]['tags'][0]['id'], 7)
            self.assertEqual(payload['answers'][0]['sources'][0]['url'], 'https://example.org')
            self.assertEqual(payload['answers'][0]['raw_detail']['id'], 1001)
            self.assertIn(('/answers/1001', {'project_id': '123'}), client.paths)
            self.assertNotIn('api_key', payload)

    def test_bad_collection_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(LLMPulseError):
                extract(FakeClient(), '123', '999', '2026-10-12', '2026-10-18', 10, Path(folder))

    def test_date_validation(self):
        self.assertEqual(_valid_date('2026-10-19', 'FROM').isoformat(), '2026-10-19')
        with self.assertRaises(LLMPulseError):
            _valid_date('19-10-2026', 'FROM')


if __name__ == '__main__':
    unittest.main()
