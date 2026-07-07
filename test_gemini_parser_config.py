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
    def test_call_with_retry_retries_transient_provider_errors(self):
        attempts = {"count": 0}

        def flaky_call():
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RuntimeError("503 UNAVAILABLE: high demand")
            return "ok"

        with patch("gemini_parser.time.sleep", return_value=None):
            result = gemini_parser._call_with_retry(flaky_call, max_attempts=3, base_delay_seconds=0)

        self.assertEqual(result, "ok")
        self.assertEqual(attempts["count"], 3)

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


    def test_normalize_dfis_payload_promotes_numbers_from_catch_properties(self):
        raw = {
            "logs": [
                {
                    "ship_name": "熊麻吉",
                    "date": "2025-09-27",
                    "fishing_method": "一支釣",
                    "catch_records": [
                        {
                            "original_name": "海鯽仔",
                            "standard_name": "短棘鯛",
                            "catch_properties": {"count": 11, "weight_kg": 5.8},
                        }
                    ],
                }
            ]
        }

        normalized = gemini_parser.normalize_dfis_payload(
            raw,
            is_bio_db=False,
            target_database_type="?箇雯憿?璆剖銵刻??澈",
        )

        catch = normalized["logs"][0]["catch_records"][0]
        self.assertEqual(normalized["logs"][0]["vessel_name"], "熊麻吉")
        self.assertEqual(normalized["logs"][0]["gear_type"], "一支釣")
        self.assertEqual(catch["species_raw_name"], "海鯽仔")
        self.assertEqual(catch["species_standard_name"], "短棘鯛")
        self.assertEqual(catch["count_individual"], 11)
        self.assertEqual(catch["weight_kg"], 5.8)

    def test_normalize_dfis_payload_promotes_string_zero_values(self):
        raw = {
            "logs": [
                {
                    "ship": "熊麻吉",
                    "day": "2025-09-27",
                    "fishing_method": "一支釣",
                    "catch_records": [
                        {
                            "original_name": "赤鯮",
                            "standard_name": "黃齒牙鯛",
                            "weight_kg": "0",
                            "count_individual": "0",
                            "catch_properties": {"count": 5, "weight_kg": 1.2},
                        }
                    ],
                }
            ]
        }

        normalized = gemini_parser.normalize_dfis_payload(
            raw,
            is_bio_db=False,
            target_database_type="?箇雯憿?璆剖銵刻??澈",
        )

        catch = normalized["logs"][0]["catch_records"][0]
        self.assertEqual(normalized["logs"][0]["vessel_name"], "熊麻吉")
        self.assertEqual(normalized["logs"][0]["log_date"], "2025-09-27")
        self.assertEqual(catch["count_individual"], 5)
        self.assertEqual(catch["weight_kg"], 1.2)

    def test_normalize_dfis_payload_unwraps_page_data_wrapper(self):
        raw = {
            "logs": [
                {
                    "page_number": 25,
                    "data": {
                        "ship_name": "熊麻吉",
                        "work_date": "2025-10-10",
                        "fishing_method": "一支釣",
                    },
                    "catch_records": [],
                }
            ]
        }

        normalized = gemini_parser.normalize_dfis_payload(
            raw,
            is_bio_db=False,
            target_database_type="?箇雯憿?璆剖銵刻??澈",
        )

        self.assertEqual(normalized["logs"][0]["vessel_name"], "熊麻吉")
        self.assertEqual(normalized["logs"][0]["log_date"], "2025-10-10")
        self.assertEqual(normalized["logs"][0]["gear_type"], "一支釣")

    def test_normalize_dfis_payload_drops_empty_shell_logs(self):
        raw = {
            "logs": [
                {
                    "database_type": "休閒船釣漁業資料庫",
                    "catch_records": [],
                },
                {
                    "ship_name": "熊麻吉",
                    "work_date": "2025-10-10",
                    "fishing_method": "一支釣",
                    "catch_records": [],
                },
            ]
        }

        normalized = gemini_parser.normalize_dfis_payload(
            raw,
            is_bio_db=False,
            target_database_type="休閒船釣漁業資料庫",
        )

        self.assertEqual(len(normalized["logs"]), 1)
        self.assertEqual(normalized["logs"][0]["vessel_name"], "熊麻吉")

    def test_merge_fishery_logs_merges_same_day_records(self):
        merged = gemini_parser._merge_fishery_logs(
            [
                {
                    "vessel_name": "熊麻吉",
                    "log_date": "2025-10-10",
                    "gear_type": "一支釣",
                    "database_type": "休閒船釣漁業資料庫",
                    "gear_properties": {"start_time": "06:00"},
                    "catch_records": [{"species_raw_name": "赤鯮"}],
                },
                {
                    "vessel_name": "熊麻吉",
                    "log_date": "2025-10-10",
                    "gear_type": "一支釣",
                    "database_type": "休閒船釣漁業資料庫",
                    "gear_properties": {"end_time": "14:30"},
                    "catch_records": [{"species_raw_name": "海鯽仔"}],
                },
            ]
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(len(merged[0]["catch_records"]), 2)
        self.assertEqual(merged[0]["gear_properties"]["start_time"], "06:00")
        self.assertEqual(merged[0]["gear_properties"]["end_time"], "14:30")

    def test_align_payload_dates_with_filename_uses_roc_year(self):
        parsed = {
            "logs": [
                {
                    "vessel_name": "test-vessel",
                    "log_date": "2021-10-12",
                    "gear_type": "一支釣",
                    "catch_records": [],
                }
            ]
        }

        aligned = gemini_parser.align_payload_dates_with_filename(
            parsed,
            file_name="?獄??-114-休閒船釣-一支釣.pdf",
            is_bio_db=False,
        )

        self.assertEqual(aligned["logs"][0]["log_date"], "2025-10-12")

    def test_complete_biological_required_fields_backfills_required_values(self):
        parsed = {
            "records": [
                {
                    "collection_date": "2025-08-07",
                    "species_name": "白帶魚",
                    "gsi": None,
                }
            ]
        }

        completed = gemini_parser.complete_biological_required_fields(
            parsed,
            file_name="20250807中芸拖網生物學參數.pdf",
        )

        record = completed["records"][0]
        self.assertEqual(record["collection_id"], "BIO-001")
        self.assertEqual(record["port"], "中芸")
        self.assertEqual(record["vessel_name"], "待人工確認")
        self.assertEqual(record["form_code"], "20250807中芸拖網生物學參數")

    def test_complete_biological_required_fields_uses_aliases_when_present(self):
        parsed = {
            "records": [
                {
                    "collection_date": "2025-08-07",
                    "specimen_no": "12",
                    "port_name": "中芸",
                    "ship_name": "海洋1號",
                    "form_template_code": "1017",
                    "species_standard_name": "白帶魚",
                }
            ]
        }

        completed = gemini_parser.complete_biological_required_fields(
            parsed,
            file_name="20250807中芸拖網生物學參數.pdf",
        )

        record = completed["records"][0]
        self.assertEqual(record["collection_id"], "12")
        self.assertEqual(record["port"], "中芸")
        self.assertEqual(record["vessel_name"], "海洋1號")
        self.assertEqual(record["form_code"], "1017")
        self.assertEqual(record["species_name"], "白帶魚")

    def test_stitch_fragmented_fishery_logs_inherits_previous_context(self):
        stitched = gemini_parser._stitch_fragmented_fishery_logs(
            [
                {
                    "vessel_name": "test-vessel",
                    "log_date": "2025-10-12",
                    "gear_type": "一支釣",
                    "database_type": "休閒船釣漁業資料庫",
                    "gear_properties": {"start_time": "06:00"},
                    "catch_records": [],
                },
                {
                    "catch_records": [
                        {
                            "species_raw_name": "鰹魚",
                            "species_standard_name": "正鰹",
                            "count_individual": 10,
                            "weight_kg": 28.0,
                            "catch_properties": {},
                        }
                    ]
                },
            ]
        )

        self.assertEqual(stitched[1]["vessel_name"], "test-vessel")
        self.assertEqual(stitched[1]["log_date"], "2025-10-12")
        self.assertEqual(stitched[1]["gear_type"], "一支釣")

    def test_normalize_dfis_payload_keeps_continuation_page_catches(self):
        raw = {
            "logs": [
                {
                    "ship_name": "test-vessel",
                    "work_date": "2025-10-12",
                    "fishing_method": "一支釣",
                    "gear_properties": {"start_time": "06:00"},
                    "catch_records": [],
                },
                {
                    "catch_records": [
                        {
                            "original_name": "鰹魚",
                            "standard_name": "正鰹",
                            "count": 10,
                            "weight_kg": 28.0,
                        }
                    ]
                },
            ]
        }

        normalized = gemini_parser.normalize_dfis_payload(
            raw,
            is_bio_db=False,
            target_database_type="休閒船釣漁業資料庫",
        )

        self.assertEqual(len(normalized["logs"]), 2)
        self.assertEqual(normalized["logs"][1]["vessel_name"], "test-vessel")
        self.assertEqual(normalized["logs"][1]["log_date"], "2025-10-12")
        self.assertEqual(normalized["logs"][1]["catch_records"][0]["species_standard_name"], "正鰹")


if __name__ == "__main__":
    unittest.main()
