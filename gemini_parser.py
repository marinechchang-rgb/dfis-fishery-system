import os
import io
import docx
import pypdf
import google.generativeai as genai
from google.generativeai import GenerationConfig
from schema import FisheryLogSchema
from typing import Tuple, Dict, Any, Optional

def extract_docx_text(file_bytes: bytes) -> str:
    """Extracts both paragraph text and table data from a DOCX file."""
    doc = docx.Document(io.BytesIO(file_bytes))
    lines = []
    
    # Extract paragraphs
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            lines.append(paragraph.text)
            
    # Extract tables
    for table in doc.tables:
        lines.append("\n--- Table Data ---")
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            # De-duplicate adjacent identical cells (common in merged cells)
            cleaned_cells = []
            for cell in cells:
                if not cleaned_cells or cleaned_cells[-1] != cell:
                    cleaned_cells.append(cell)
            lines.append(" | ".join(cleaned_cells))
        lines.append("------------------\n")
        
    return "\n".join(lines)

def extract_pdf_text_fallback(file_bytes: bytes) -> str:
    """Extracts text from PDF as a fallback mechanism."""
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    text = []
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text()
        if page_text:
            text.append(f"--- Page {i+1} ---\n{page_text}")
    return "\n".join(text)

def parse_document_with_gemini(
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
    api_key: str,
    model_name: str = "gemini-1.5-pro"
) -> FisheryLogSchema:
    """
    Parses the file contents with Gemini Structured Outputs and returns a FisheryLogSchema object.
    Supports PDF, Docx, and images.
    """
    if not api_key:
        raise ValueError("Gemini API Key is missing. Please set it in the sidebar or env variables.")
        
    genai.configure(api_key=api_key)
    
    # Configure generation parameters for structured outputs
    generation_config = GenerationConfig(
        response_mime_type="application/json",
        response_schema=FisheryLogSchema,
        temperature=0.1,  # Low temperature for extraction accuracy
    )
    
    model = genai.GenerativeModel(model_name)
    
    prompt = (
        "你是一個專業的海洋漁業資訊系統解析器。請分析上傳的檔案內容，"
        "從中自動提取、校正、除錯，並完全對齊 FisheryLogSchema 的格式。\n"
        "注意事項：\n"
        "1. 原始魚名 (species_raw_name) 請填入檔案中記錄的原樣，包含空格或錯字（如: '什 臭肚', '如志')。\n"
        "2. 標準化中文名 (species_standard_name) 請對齊臺灣魚類資料庫的標準俗稱或學名（如: '臭肚魚', '加志')。\n"
        "3. 若重量原始單位為公克(g)，請除以1000自動換算為公斤(kg)。\n"
        "4. 作業日期 (log_date) 請統一轉換為標準的 YYYY-MM-DD 格式。\n"
        "5. 請將所有與特定漁獲單獨相關的量測數據（如叉長、總重、單價、規格等）放入 catch_properties Dict 中。\n"
        "6. 請將與漁具/漁法作業相關的參數放入 gear_properties Dict 中。"
    )
    
    contents = []
    
    # Prepare input contents depending on MIME type
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or file_name.lower().endswith(".docx"):
        # Word documents must be converted to text
        text_content = extract_docx_text(file_bytes)
        contents.append(f"文件內容如下：\n\n{text_content}\n\n")
        contents.append(prompt)
    elif mime_type == "application/pdf" or file_name.lower().endswith(".pdf"):
        # For PDFs, try to upload/send bytes directly as Gemini natively supports PDF.
        # Fallback to text extraction if PDF bytes sending fails.
        try:
            pdf_part = {
                "mime_type": "application/pdf",
                "data": file_bytes
            }
            contents.append(pdf_part)
            contents.append(prompt)
        except Exception as e:
            # Fallback
            text_content = extract_pdf_text_fallback(file_bytes)
            contents.append(f"PDF文字提取內容如下：\n\n{text_content}\n\n")
            contents.append(prompt)
    elif mime_type.startswith("image/") or file_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        # Image bytes
        image_part = {
            "mime_type": mime_type if mime_type.startswith("image/") else "image/jpeg",
            "data": file_bytes
        }
        contents.append(image_part)
        contents.append(prompt)
    else:
        # Generic fallback to text
        try:
            text_content = file_bytes.decode("utf-8", errors="ignore")
            contents.append(f"文件內容如下：\n\n{text_content}\n\n")
            contents.append(prompt)
        except Exception as e:
            raise ValueError(f"不支援的檔案格式，且無法以文字方式讀取: {file_name}")

    # Generate content using Gemini
    response = model.generate_content(
        contents,
        generation_config=generation_config
    )
    
    # Return validated FisheryLogSchema object
    return FisheryLogSchema.model_validate_json(response.text)
