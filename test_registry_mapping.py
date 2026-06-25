import unittest

from dfis_registry import (
    infer_bio_template_code,
    infer_database_category_code,
    infer_form_template_code,
)


class RegistryMappingTests(unittest.TestCase):
    def test_infer_database_category_code(self):
        self.assertEqual(infer_database_category_code("生物學資料庫"), "BIOLOGY_SAMPLE")
        self.assertEqual(infer_database_category_code("沿近海漁業資料庫"), "COASTAL_FISHERY")

    def test_infer_form_template_code_from_gillnet_properties(self):
        payload = {
            "gear_type": "gillnet",
            "gear_properties": {
                "mesh_size_inch": 4.5,
                "net_length_m": 1200,
            },
        }
        self.assertEqual(infer_form_template_code(payload), "TN_COASTAL_GILLNET_001")

    def test_infer_form_template_code_from_longline_properties(self):
        payload = {
            "gear_type": "longline",
            "gear_properties": {
                "gear_count_hooks": 1200,
                "bait_types": ["beltfish"],
            },
        }
        self.assertEqual(infer_form_template_code(payload), "TW_LONGLINE_001")

    def test_infer_bio_template_code(self):
        record = {
            "fork_length_mm": 210.5,
            "net_group": "inner_net",
        }
        self.assertEqual(infer_bio_template_code(record), "BIO_MESH_001")


if __name__ == "__main__":
    unittest.main()
