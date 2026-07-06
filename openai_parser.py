"""OpenAI vision/document parser for DFIS.

The module mirrors the Gemini parser contract and returns the same Pydantic
models, so the Streamlit review and database flows remain provider-agnostic.
"""

import base64
import io
from typing import List, Union

from fishery_schema import BiologicalParameterBatch, FisheryLogBatchSchema
from gemini_parser import (
    align_payload_dates_with_filename,
    extract_docx_text,
    extract_pdf_text_fallback,
    normalize_dfis_payload,
    repair_truncated_json,
)


ParsedBatch = Union[FisheryLogBatchSchema, BiologicalParameterBatch]


GEAR_FIELD_GUIDANCE = {
    "休閒船釣漁業資料庫": (
        "gear_properties 優先擷取 submitter、start_time、end_time、"
        "start_latitude、start_longitude、end_latitude、end_longitude、"
        "grid_number、mesh_size、net_length、depth、gear_count、bait。"
    ),
    "刺網類漁業報表資料庫": (
        "gear_properties 優先擷取 departure_time、arrival_time、setting_time、"
        "hauling_time、setting_longitude、setting_latitude、operation_depth、"
        "gear_length、mesh_size。"
    ),
    "釣具類漁業報表資料庫": (
        "gear_properties 優先擷取 vessel_owner、vessel_registration、"
        "departure_time、arrival_time、total_fishing_hours、bait_type、"
        "location_1_latitude、location_1_longitude、location_1_depth、"
        "location_2_latitude、location_2_longitude、location_2_depth。"
    ),
    "拖網類漁業報表資料庫": (
        "gear_properties 優先擷取出進港時間、拖網起訖時間、作業位置、"
        "水深、網目、網長與拖網時數；原表沒有的欄位不要臆測。"
    ),
}


def _load_reference_values():
    try:
        import database

        vessels = database.get_vessels()["name"].dropna().astype(str).tolist()
        ports = database.get_ports()["name"].dropna().astype(str).tolist()
        species = database.get_species()["chinese_name"].dropna().astype(str).tolist()
        return vessels, ports, species
    except Exception:
        return [], [], []


def build_extraction_prompt(target_database_type: str) -> str:
    """Build a concise, provider-neutral extraction prompt."""
    vessels, ports, species = _load_reference_values()
    reference_block = (
        f"已核准船名：{', '.join(vessels) if vessels else '無'}\n"
        f"已核准港口：{', '.join(ports) if ports else '無'}\n"
        f"已核准魚種中文名：{', '.join(species) if species else '無'}"
    )

    common = f"""
你是 DFIS 漁業表單結構化辨識器。請完整閱讀所有頁面，輸出指定的結構化資料，
不得加入原文件沒有的事實。目標資料庫分類是「{target_database_type}」。

共同規則：
1. 多頁、左右雙欄與連續表格都必須完整擷取，不得只讀第一頁或前幾列。
2. 垂直線、同上、ditto 或空白承接上列時，將上方最近的有效值向下填入。
3. 被劃除的內容不採用，以修正後手寫值為準；無法辨識時保留最接近原貌，勿臆測。
4. 日期統一為 YYYY-MM-DD。重量換算為 kg；生物個體重量為 g；全長為 mm。
5. 同時保留原始魚名與標準魚名。標準名優先對齊核准清單；無可靠對應時沿用原名，
   不可為了填滿欄位而虛構物種。
6. 文件沒有的選填數值填 null；沒有動態屬性時填空物件 {{}}。
7. 每一筆記錄都要能獨立理解，不可在輸出中使用「同上」或省略共同欄位。

{reference_block}
""".strip()

    if target_database_type == "生物學參數資料庫":
        return common + """

請輸出 BiologicalParameterBatch。每一個體一筆 records：collection_date、collection_id、
port、vessel_name、form_code、species_name、sex、maturity、total_length_mm、weight_g、
gsi、remarks。若一頁左右各 25 筆，應完整輸出 50 筆；多頁依序合併。
"""

    gear_guidance = GEAR_FIELD_GUIDANCE.get(
        target_database_type,
        "gear_properties 應保存文件中所有可辨識的漁法與作業參數。",
    )
    return common + f"""

請輸出 FisheryLogBatchSchema。依每艘船、每個作業日期拆成 logs；每筆的 database_type
固定為「{target_database_type}」。漁獲逐列放入 catch_records，尾數放
count_individual，重量放 weight_kg，其餘單尾屬性放 catch_properties。
{gear_guidance}
"""


def _image_content(file_bytes: bytes, mime_type: str) -> dict:
    encoded = base64.b64encode(file_bytes).decode("ascii")
    return {
        "type": "input_image",
        "image_url": f"data:{mime_type};base64,{encoded}",
        "detail": "high",
    }


def build_document_content(
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
) -> List[dict]:
    """Convert a supported document into OpenAI Responses API content."""
    lowered_name = file_name.lower()

    if (
        mime_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or lowered_name.endswith(".docx")
    ):
        text = extract_docx_text(file_bytes)
        return [{"type": "input_text", "text": f"DOCX 文件內容：\n\n{text}"}]

    if mime_type == "application/pdf" or lowered_name.endswith(".pdf"):
        try:
            import pypdfium2 as pdfium

            pdf = pdfium.PdfDocument(file_bytes)
            pages = []
            for page_number, page in enumerate(pdf, start=1):
                image = page.render(scale=2).to_pil()
                image_bytes = io.BytesIO()
                image.save(image_bytes, format="JPEG", quality=88)
                pages.append(
                    {
                        "type": "input_text",
                        "text": f"以下影像為 PDF 第 {page_number} 頁。",
                    }
                )
                pages.append(_image_content(image_bytes.getvalue(), "image/jpeg"))
            if not pages:
                raise ValueError("PDF 沒有可解析的頁面。")
            return pages
        except Exception:
            text = extract_pdf_text_fallback(file_bytes)
            if not text.strip():
                raise ValueError("PDF 影像渲染與文字擷取皆失敗。")
            return [{"type": "input_text", "text": f"PDF 文字內容：\n\n{text}"}]

    if mime_type.startswith("image/") or lowered_name.endswith(
        (".png", ".jpg", ".jpeg", ".webp")
    ):
        normalized_mime = mime_type if mime_type.startswith("image/") else "image/jpeg"
        return [_image_content(file_bytes, normalized_mime)]

    text = file_bytes.decode("utf-8", errors="ignore")
    if not text.strip():
        raise ValueError(f"OpenAI 不支援或無法讀取此檔案格式：{file_name}")
    return [{"type": "input_text", "text": text}]


def parse_document_with_openai(
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
    api_key: str,
    target_database_type: str,
    model_name: str = "gpt-4.1-mini",
) -> ParsedBatch:
    """Parse a DFIS source document with OpenAI vision and JSON mode."""
    if not api_key:
        raise ValueError("缺少 OpenAI API 金鑰，請在系統設定或 OPENAI_API_KEY 中提供。")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("尚未安裝 openai 套件，請重新安裝 requirements.txt。") from exc

    schema = (
        BiologicalParameterBatch
        if target_database_type == "生物學參數資料庫"
        else FisheryLogBatchSchema
    )
    is_bio_db = target_database_type == "生物學參數資料庫"
    prompt = build_extraction_prompt(target_database_type)
    document_content = build_document_content(file_bytes, file_name, mime_type)
    client = OpenAI(api_key=api_key, timeout=180.0, max_retries=2)

    response = client.responses.create(
        model=model_name,
        input=[
            {
                "role": "system",
                "content": (
                    f"{prompt}\n\n"
                    "請只輸出一個合法 JSON 物件，不要輸出 Markdown、說明文字、程式碼區塊或額外註解。"
                ),
            },
            {"role": "user", "content": document_content},
        ],
        text={
            "format": {
                "type": "json_object",
            }
        },
        max_output_tokens=16000,
    )

    raw_text = getattr(response, "output_text", "")
    if not raw_text:
        raise ValueError("OpenAI 未回傳可解析資料；請確認模型支援影像與結構化輸出。")

    import json

    repaired = repair_truncated_json(raw_text)
    parsed_dict = json.loads(repaired)
    parsed_dict = normalize_dfis_payload(
        parsed_dict,
        is_bio_db=(target_database_type == "?摮詨??貉??澈"),
        target_database_type=target_database_type,
    )
    parsed_dict = align_payload_dates_with_filename(
        parsed_dict,
        file_name=file_name,
        is_bio_db=is_bio_db,
    )
    return schema.model_validate(parsed_dict)
