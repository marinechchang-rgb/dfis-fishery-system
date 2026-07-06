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
        return types.SimpleNamespace(output_text=self.parsed)


class _FakeOpenAIClient:
    responses = _FakeResponses('{"logs": []}')

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

    def test_openai_parser_normalizes_alias_fields(self):
        fake_module = types.SimpleNamespace(OpenAI=_FakeOpenAIClient)
        _FakeOpenAIClient.responses = _FakeResponses(
            """{
                "logs": [
                    {
                        "ship_name": "熊麻吉",
                        "date": "2025-09-26",
                        "fishing_method": "一支釣",
                        "catch_records": [
                            {
                                "original_name": "海鯽仔",
                                "standard_name": "短棘鯛",
                                "catch_properties": {"count": 8, "weight_kg": 3.6}
                            }
                        ]
                    }
                ]
            }"""
        )
        with patch.dict(sys.modules, {"openai": fake_module}):
            result = openai_parser.parse_document_with_openai(
                file_bytes=b"test document",
                file_name="sample.txt",
                mime_type="text/plain",
                api_key="test-key",
                target_database_type="?箇雯憿?璆剖銵刻??澈",
                model_name="gpt-4.1-mini",
            )

        self.assertEqual(result.logs[0].vessel_name, "熊麻吉")
        self.assertEqual(result.logs[0].gear_type, "一支釣")
        self.assertEqual(result.logs[0].catch_records[0].species_raw_name, "海鯽仔")
        self.assertEqual(result.logs[0].catch_records[0].species_standard_name, "短棘鯛")
        self.assertEqual(result.logs[0].catch_records[0].count_individual, 8)
        self.assertEqual(result.logs[0].catch_records[0].weight_kg, 3.6)


if __name__ == "__main__":
    unittest.main()
