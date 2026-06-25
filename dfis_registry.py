from typing import Any, Dict


FORM_TEMPLATE_NAMES = {
    "TN_COASTAL_GILLNET_001": "台南將軍沿海場域標本船作業調查表109.03.31",
    "SW_HOOK_001": "釣具類作業報表(擷取1頁)_114.09.16",
    "TW_LONGLINE_001": "延繩釣漁撈作業報表-高雄熊麻吉 -",
    "BIO_MESH_001": "網目比較實驗室紀錄表",
}


def infer_database_category_code(database_type: str) -> str:
    text = (database_type or "").strip()
    if "生物" in text or "實驗" in text:
        return "BIOLOGY_SAMPLE"
    return "COASTAL_FISHERY"


def infer_form_template_code(log_data: Dict[str, Any]) -> str:
    explicit = (log_data.get("form_template_code") or "").strip()
    if explicit:
        return explicit

    gear_type = (log_data.get("gear_type") or "").strip()
    gear_props = log_data.get("gear_properties") or {}

    if any(key in gear_props for key in ("net_set_time", "net_haul_time", "mesh_size_inch", "net_length_m", "net_length_nmi")):
        return "TN_COASTAL_GILLNET_001"
    if any(key in gear_props for key in ("gear_count_hooks", "gear_count_baskets", "bait_types", "gear_subtype_flags")):
        return "TW_LONGLINE_001"
    if any(key in gear_props for key in ("total_hook_hours",)) or log_data.get("owner_name") or log_data.get("vessel_registration_no"):
        return "SW_HOOK_001"

    if any(keyword in gear_type for keyword in ("延繩", "一支釣", "曳繩")):
        return "TW_LONGLINE_001"
    if any(keyword in gear_type for keyword in ("釣",)):
        return "SW_HOOK_001"
    return "TN_COASTAL_GILLNET_001"


def infer_bio_template_code(record: Dict[str, Any]) -> str:
    explicit = (record.get("form_template_code") or "").strip()
    if explicit:
        return explicit
    if (
        record.get("fork_length_mm") is not None
        or record.get("net_group")
        or record.get("net_set_no")
        or record.get("total_weight_kg") is not None
        or record.get("discard_weight_kg") is not None
    ):
        return "BIO_MESH_001"
    return "BIO_MESH_001"
