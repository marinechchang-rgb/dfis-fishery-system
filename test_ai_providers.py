import sys
import types
import unittest
from unittest.mock import patch

import openai_parser
from fishery_schema import FisheryLogBatchSchema


class _FakeResponses:
    def __init__(self, parsed):
        self.parsed = parsed
        self.last_request = None

    def create(self, **kwargs):
        self.last_request = kwargs
        return types.SimpleNamespace(output_text='{"logs": []}')


class _FakeOpenAIClient:
    responses = _FakeResponses(FisheryLogBatchSchema(logs=[]))

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs


class AIProviderTests(unittest.TestCase):
    def test_openai_parser_returns_shared_schema(self):
        fake_module = types.SimpleNamespace(OpenAI=_FakeOpenAIClient)
        with patch.dict(sys.modules, {"openai": fake_module}):
            result = openai_parser.parse_document_with_openai(
                file_bytes=b"test document",
                file_name="sample.txt",
                mime_type="text/plain",
                api_key="test-key",
                target_database_type="刺網類漁業報表資料庫",
                model_name="gpt-4.1-mini",
            )

        self.assertIsInstance(result, FisheryLogBatchSchema)
        request = _FakeOpenAIClient.responses.last_request
        self.assertEqual(request["model"], "gpt-4.1-mini")
        self.assertEqual(request["text"]["format"]["type"], "json_object")
        self.assertIn("刺網類漁業報表資料庫", request["input"][0]["content"])

    def test_image_content_uses_data_url(self):
        content = openai_parser.build_document_content(
            b"image-bytes",
            "sample.jpg",
            "image/jpeg",
        )
        self.assertEqual(content[0]["type"], "input_image")
        self.assertTrue(content[0]["image_url"].startswith("data:image/jpeg;base64,"))


if __name__ == "__main__":
    unittest.main()
