import os
import io
import docx
import pypdf
import google.generativeai as genai
from google.generativeai import GenerationConfig
from schema import FisheryLogBatchSchema
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
) -> FisheryLogBatchSchema:
    """
    Parses the file contents with Gemini Structured Outputs and returns a FisheryLogBatchSchema object.
    Supports PDF, Docx, and images.
    """
    if not api_key:
        raise ValueError("Gemini API Key is missing. Please set it in the sidebar or env variables.")
        
    genai.configure(api_key=api_key)
    
    # Configure generation parameters for structured outputs (batch schema)
    generation_config = GenerationConfig(
        response_mime_type="application/json",
        response_schema=FisheryLogBatchSchema,
        temperature=0.1,  # Low temperature for extraction accuracy
    )
    
    model = genai.GenerativeModel(model_name)
    
    prompt = (
        "你是一個專業的海洋漁業資訊系統解析器。請分析上傳的檔案內容，"
        "從中自動提取、分割、校正、除錯，並完全對齊 FisheryLogBatchSchema 的格式，將解析出的所有作業日誌以 logs 陣列回傳。\n\n"
        "特別注意事項（重要）：\n"
        "1. 【多重日期分拆】如果原始報表或圖片中包含多個日期、時間或不同地點的作業紀錄，"
        "請務必將其區分、並依照「每艘船每日作業」分別提取為獨立的 FisheryLogSchema 物件存入 logs 列表中。\n"
        "2. 【手寫劃除替代規則】極重要！如果手寫日誌中有將印刷字體或舊文字畫線塗改（劃除）並手寫填上新魚種的情形："
        "例如劃除 '白帶魚' 並手寫改為 '石姥'；劃除 '黃雞魚' 並手寫改為 '黃石斑'；劃除 '紅目鰱' 並手寫改為 '紅盤' 等，"
        "AI 判讀時必須完全以『劃除後新寫上去的魚種』為準，將新魚種填入原始魚種名稱 (species_raw_name)，並自動對應其標準名稱 (species_standard_name)，"
        "絕對不要填入已被劃除的舊魚種名。\n"
        "3. 【原始魚名】species_raw_name 請填入劃除後新寫上去的原樣，包含空格或簡寫手誤（例如: '石姥', '黃石斑', '紅盤'）。\n"
        "4. 【標準化名稱】species_standard_name 請對齊臺灣魚類資料庫的標準中文俗名或學名（例如: '石姥' -> '波紋唇魚', '黃石斑' -> '青石斑魚', '紅盤' -> '真鯛'）。\n"
        "5. 【重量單位】若重量原始單位為台斤、台兩、公克(g)或其他單位，請務必自動換算為公斤(kg)再填入。1台斤 = 0.6公斤。如果寫著 '20台斤' 則重量填入 12.0；若寫著 '10台斤' 則重量填入 6.0。\n"
        "6. 【資料庫分類定義】請分析日誌性質，將 database_type 設定為以下之一：'生物學參數資料庫'、'拖網類漁業報表資料庫'、'刺網類漁業報表資料庫'、'釣具類漁業報表資料庫'。如果是以一支釣、延繩釣、釣具等為主的紀錄請歸類為 '釣具類漁業報表資料庫'；若為拖網請歸為 '拖網類漁業報表資料庫'；刺網/流網歸為 '刺網類漁業報表資料庫'；若為生物學個體測量（如叉長、單尾重）請歸為 '生物學參數資料庫'。\n"
        "7. 【動態參數】請將所有與特定漁獲單尾相關的量測數據（如尾數、體長等）放入 catch_properties 中，將漁法/作業參數（如經緯度、水深、下竿時數、出進港時間等）放入 gear_properties 中。"
    )
    
    contents = []
    
    # Prepare input contents depending on MIME type
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or file_name.lower().endswith(".docx"):
        text_content = extract_docx_text(file_bytes)
        contents.append(f"文件內容如下：\n\n{text_content}\n\n")
        contents.append(prompt)
    elif mime_type == "application/pdf" or file_name.lower().endswith(".pdf"):
        try:
            pdf_part = {
                "mime_type": "application/pdf",
                "data": file_bytes
            }
            contents.append(pdf_part)
            contents.append(prompt)
        except Exception as e:
            text_content = extract_pdf_text_fallback(file_bytes)
            contents.append(f"PDF文字提取內容如下：\n\n{text_content}\n\n")
            contents.append(prompt)
    elif mime_type.startswith("image/") or file_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        image_part = {
            "mime_type": mime_type if mime_type.startswith("image/") else "image/jpeg",
            "data": file_bytes
        }
        contents.append(image_part)
        contents.append(prompt)
    else:
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
    
    # Return validated FisheryLogBatchSchema object
    return FisheryLogBatchSchema.model_validate_json(response.text)
