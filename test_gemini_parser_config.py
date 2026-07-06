import types
import unittest
from unittest.mock import patch

import gemini_parser
from fishery_schema import FisheryLogBatchSchema


class _FakeModels:
    def __init__(self):
        self.last_kwargs = None

    def generate_content(self, **kwargs):
        self.last_kwargs = kwargs
        return types.SimpleNamespace(text='{"logs": []}')


class _FakeClient:
    models = _FakeModels()

    def __init__(self, **kwargs):
        self.kwargs = kwargs


class GeminiParserConfigTests(unittest.TestCase):
    def test_gemini_uses_json_mode_without_response_schema(self):
        fake_genai = types.SimpleNamespace(Client=_FakeClient)
        fake_types = types.SimpleNamespace(
            GenerateContentConfig=lambda **kwargs: kwargs,
            Part=types.SimpleNamespace(from_bytes=lambda **kwargs: kwargs),
        )

        with patch.object(gemini_parser, "genai", fake_genai), patch.object(gemini_parser, "types", fake_types):
            result = gemini_parser.parse_document_with_gemini(
                file_bytes=b"plain text",
                file_name="sample.txt",
                mime_type="text/plain",
                api_key="test-key",
                target_database_type="刺網類漁業報表資料庫",
                model_name="gemini-2.5-flash",
            )

        self.assertIsInstance(result, FisheryLogBatchSchema)
        config = _FakeClient.models.last_kwargs["config"]
        self.assertEqual(config["response_mime_type"], "application/json")
        self.assertNotIn("response_schema", config)
        self.assertEqual(config["max_output_tokens"], 16000)

    def test_normalize_dfis_payload_wraps_and_maps_aliases(self):
        raw = [
            {
                "database_type": "刺網類漁業報表資料庫",
                "boat_name": "熊麻吉",
                "date": "2025-09-26",
                "submitter": "鄭明賢",
                "gear_properties": {"bait": "硬尾"},
                "catches": [
                    {
                        "species_raw_name": "海鯽仔",
                        "species_standard_name": "短棘鯛",
                        "count": 8,
                        "weight_kg": 3.6,
                    }
                ],
            }
        ]

        normalized = gemini_parser.normalize_dfis_payload(
            raw,
            is_bio_db=False,
            target_database_type="刺網類漁業報表資料庫",
        )

        self.assertIn("logs", normalized)
        self.assertEqual(normalized["logs"][0]["vessel_name"], "熊麻吉")
        self.assertEqual(normalized["logs"][0]["log_date"], "2025-09-26")
        self.assertEqual(normalized["logs"][0]["observer_name"], "鄭明賢")
        self.assertIn("catch_records", normalized["logs"][0])
        self.assertEqual(normalized["logs"][0]["catch_records"][0]["count_individual"], 8)


if __name__ == "__main__":
    unittest.main()
