# DFIS 執行實施計畫摘要

最後更新：2026-06-24

本文件是 DFIS 專案的執行摘要版，提供目前系統定位、正式環境策略、實施順序與里程碑。完整版本請參考 [本專案的完整規劃書.md](C:/Users/azwer/OneDrive/文件/DFIS多元漁業資訊標準及智慧化軟體系統/本專案的完整規劃書.md)。

## 1. 專案目標

DFIS（多元漁業資訊標準及智慧化系統）要完成三件事：

1. 將 PDF、DOCX、影像中的漁業資料轉成可編修的結構化資料。
2. 讓使用者在網頁上人工覆核，再寫入正式資料庫。
3. 建立可持續部署的雲端版本，支援 Gemini 與 GPT 兩條 AI 解析路徑。

## 2. 目前系統現況

目前程式已具備下列基礎能力：

- `app.py` 已提供 Streamlit 操作介面。
- 已支援 `Gemini` 與 `OpenAI` 兩種影像/文件辨識流程。
- 已有 `database.py` 可在 `SQLite` 與 `PostgreSQL` 間切換。
- 已有本機資料檔 `fishery_standard.db`。
- 已補上 `README.md`、`DEPLOYMENT.md`、`.streamlit/secrets.toml.example`。

目前主要問題不是功能完全缺失，而是以下三件事還沒整齊：

- 文件版本混雜，且部分內容已與現況不一致。
- 資料標準、資料表命名與正式環境資料架構尚未完全定版。
- 雲端部署策略尚未正式以 Supabase 為核心完成落地。

## 2.1 Demo 階段表單母版來源

目前 demo 階段的欄位設計，不再只靠抽象 schema 討論，而是直接以既有調查表單作為欄位來源母版。這些檔案將作為後續手寫 PDF 辨識的背景格式依據：

1. `台南將軍沿海場域標本船作業調查表109.03.31.docx`
2. `釣具類作業報表(擷取1頁)_114.09.16.docx`
3. `網目比較實驗室紀錄表.docx`
4. `延繩釣漁撈作業報表-高雄熊麻吉 -.docx`

這代表後續系統設計要優先服務「這些表單轉成手寫 PDF 後上傳辨識」的情境，而不是先追求所有漁業表單一次通吃。

## 3. 正式架構決策

本專案後續以以下原則執行：

- 開發環境：使用本機 `SQLite`，方便快速測試。
- 測試與正式環境：以 `Supabase PostgreSQL` 為主資料庫。
- 前端與操作介面：維持 `Streamlit`。
- 原始碼版本管理：以 `GitHub` 為唯一版本來源。
- 雲端應用部署：以 `Streamlit Community Cloud` 為第一階段方案。

## 4. Supabase 納入範圍

Supabase 在本案中的角色，第一階段先聚焦在最重要的資料層：

- 必做：`Supabase Postgres`
- 第二階段：`Supabase Storage`
- 第三階段：`Supabase Auth / RLS / 權限控管`

也就是說，現階段不要一次把 Supabase 所有功能都塞進來。先把「正式資料寫入 PostgreSQL」做穩，再逐步擴大。

## 5. 系統主流程

正式流程統一為：

1. 使用者上傳 PDF、DOCX 或影像。
2. 由使用者選擇 AI 服務：`Gemini` 或 `OpenAI`。
3. AI 解析為標準資料結構。
4. 使用者於畫面中覆核與修正。
5. 系統寫入 Supabase PostgreSQL。
6. 提供查詢、匯出與圖表分析。

其中辨識目標需明確改成：

- 原始母版為 Word / 調查表格式
- 實際 demo 上傳檔案可為列印後再手寫、掃描而成的 PDF 或影像
- Gemini / OpenAI 需扮演「表單影像辨識 + 欄位對位 + 結構化輸出」角色

## 6. 實施順序

### Phase 0：文件與標準定版

- 統一欄位命名與資料表責任
- 定義本機與雲端的資料流
- 定義 Supabase 在本案中的使用範圍
- 依四份母版表單整理出 demo 必要欄位字典

### Phase 1：資料庫層整理

- 將 `SQLite` 與 `PostgreSQL` 的 schema 行為對齊
- 補齊 migration 策略
- 釐清正式環境一律以 `DATABASE_URL` 為主

### Phase 2：AI 與資料模型整理

- 統一 Gemini 與 OpenAI 的輸出 schema
- 對齊漁撈日誌與生物資料的欄位規格
- 建立解析失敗與人工退回機制
- 將手寫 PDF / 掃描影像辨識納入測試目標

### Phase 3：Supabase 雲端化

- 建立 Supabase 專案
- 建立正式資料表
- 設定 `DATABASE_URL`
- 完成 Streamlit Cloud 與 Supabase 串接

### Phase 4：驗證與上線

- 本機測試
- 雲端測試
- 資料寫入測試
- 匯出與查詢驗證

## 7. 本輪建議先做什麼

依照現在的狀況，下一步不建議直接部署，而是依序執行：

1. 先定版規劃書與執行計畫。
2. 再把四份表單拆成 demo 欄位標準與資料表映射。
3. 接著整理 `database.py` 的正式資料結構與欄位。
4. 確認 Supabase schema 後，再進行 GitHub 推送與雲端部署。

本階段交付物：

- [FIELD_DICTIONARY.md](C:/Users/azwer/OneDrive/文件/DFIS多元漁業資訊標準及智慧化軟體系統/FIELD_DICTIONARY.md)
- [supabase_schema.sql](C:/Users/azwer/OneDrive/文件/DFIS多元漁業資訊標準及智慧化軟體系統/supabase_schema.sql)

## 8. 本輪結論

本輪的正確方向不是立刻上雲，而是先把「資料標準、資料流、Supabase 角色、實施順序」對齊。等這份規劃定版後，再開始實作與部署，整體風險會低很多。
