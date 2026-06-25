# DFIS 多元漁業資訊標準及智慧化系統

DFIS 將 PDF、DOCX 與掃描影像中的漁撈日誌或生物學參數，透過 Gemini 或 OpenAI 視覺模型轉為結構化資料，再由人員覆核後存入 SQLite 或 PostgreSQL。

## 主要功能

- Gemini／OpenAI AI 辨識服務切換
- PDF、DOCX、PNG、JPG、WEBP 文件解析
- 漁獲與生物學參數人工覆核
- 魚種、船隻、港口與資料分類管理
- SQLite 本機開發與 PostgreSQL 雲端資料庫
- 統計圖表與 CSV 匯出

## 本機啟動

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

API 金鑰可使用環境變數：

```powershell
$env:GEMINI_API_KEY="..."
$env:OPENAI_API_KEY="sk-..."
```

也可以建立不納入 Git 的 `.streamlit/secrets.toml`，格式請參考 `.streamlit/secrets.toml.example`。

## 雲端部署

本專案可直接部署至 Streamlit Community Cloud。部署與 Secrets 設定請參考 [DEPLOYMENT.md](DEPLOYMENT.md)。正式用途應設定 PostgreSQL `DATABASE_URL`；Community Cloud 的本機 SQLite 不保證永久保存。

## 專案規劃

完整現況、風險、目標架構與開發里程碑請參考 [本專案的完整規劃書.md](本專案的完整規劃書.md)。
