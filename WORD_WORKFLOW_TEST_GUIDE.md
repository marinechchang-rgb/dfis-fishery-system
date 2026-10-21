# Word 母版 PDF 建檔測試版

日期：2026-10-21。入口：https://dfis-v1-lab.streamlit.app/（私人 staging）。
側欄選 Word／PDF 新流程；舊 P0-A 驗證仍可切換。

## 使用方式

1. 在 Word 母版頁上傳含文字／表格的 DOCX。舊 DOC 請先用 Word 另存 DOCX。
2. 確認候選欄位，填寫類型代碼與名稱；header 是共用表頭、detail 是一組重複明細。
3. 核對欄位後勾選確認，發布版本。相同 Word 與欄位不重複發布；更改會建立新版本。
4. PDF 頁選對應母版及模型，輸入 API key，確認 API 傳送同意，再上傳一份或多份 PDF。
5. 開始辨識。每頁狀態會存入 Supabase，可重試未成功頁。也可選人工建檔，不呼叫 API。
6. 對照原頁預覽修正表格，補足來源頁，刪除空白占位列；確認所有頁後保存。
7. 累積資料頁可查看同母版版本歷次資料，按批次或全部匯出 UTF-8 BOM CSV。
8. 同 PDF 即使改名再上傳，不會重複確認入庫；其他內容的 PDF 會繼續累積。

## 本版範圍與限制

- 原始 Word／PDF 不長期保存；保存的是母版文字／表格快照、欄位、文件 hash、逐頁結果與已確認資料。
- 一個母版支援共用表頭加一組重複明細；多組明細 CSV ZIP 尚未實作。
- 型別為 text、integer、decimal。日期、座標、單位及複選保留原文，尚不自動轉換成標準單位／日期。
- 同一份 PDF 的跨頁共同表頭尚不自動承接，請逐頁覆核補齊；每列來源頁保留，source_row 為確認後序號，並非原表實體列定位。
- 新資料存入四張獨立 wf_* 表，JSON 為 TEXT，ID 為文字 UUID；未雙寫舊 fishery_logs／生物學資料表。
- 結構快照尚未涵蓋影像型 Word、所有文字方塊與視覺版面，母版確認不可省略。
- Gemini／OpenAI API 程式已接入；真實手寫 PDF 準確率與使用者 API 額度仍需實際樣本驗收。
- 只有測試環境部署，正式 main App 未變更。無 Auth、RLS 或 Storage 新增。

## Migration

migrations/002_word_workflow.sql：只新增 wf_templates、wf_uploads、wf_pages、wf_records 與索引，
不修改 P0-A 表、不刪除既有資料、不在 App 啟動時 migration。只可執行一次；正式環境套用前需另行驗收。

## 驗證

本機 unittest discover：41 項通過（原有 34 + 新增 7）。
新增測試涵蓋 DOCX 欄位讀取、DOC 拒絕、未知欄位、零與缺值、截斷 JSON 拒絕、CSV BOM 與公式文字、
母版版本與內容去重、缺頁阻擋、交易 rollback、空白占位列拒絕，以及兩批資料累積後重新連線查詢。
不將 mock／合成測試稱為真實 OCR 驗收。

### 2026-10-21 雲端實測紀錄

- 部署程式：`5d8b7b4`，branch `codex/dfis-v1`，入口 `staging_app.py`；新版三分頁已實際開啟。
- Supabase staging 已執行 migration 002，四張 wf_* 表就緒；舊表與正式 App 未修改。
- 透過 App 的合成保存測試按鈕建立一個母版、兩批資料、兩筆明細，backend 回報 `postgresql`。
- 母版 ID：`5b2633ea-2ad2-4f77-b127-1419f7c7b83c`；重量分別為 1.25、2.5。
- 同內容改名再登錄回傳相同批次 ID；不重複入庫。
- 保存後實際執行 Manage app → Reboot app。Cloud 紀錄顯示 UTC 03:21:55 重新啟動、03:22:10 新 server 啟動。
- 重啟後未再次執行寫入自測，直接於「③ 累積資料與 CSV」查得原母版、兩批及兩筆明細。
- 重啟前後 CSV 產生位元組的 SHA-256 均為 `d6e27878222b2990a7060fb12116429c823af788714b0971e765996f8e3b47d2`。
- 本次確認下載按鈕與 CSV 產生結果；尚未取得本次瀏覽器實際下載檔進行獨立位元組校驗。
- 截圖：[雲端重啟後資料](evidence/word_workflow_cloud_20261021.png)；結構證據：[JSON](evidence/word_workflow_20261021.json)。
- 使用者提供的兩份 DOCX 在本機均可擷取到 1 張表格、5 個非空段落及 10 個建議欄位；不等於每一欄均已人工驗收。
- 瀏覽器自動上傳受擴充功能本機檔案權限阻擋，沒有修改權限；實際 Word 上傳發布、手寫 PDF 雙模型及人工覆核 UI 全流程仍需使用者測試。

### 下一輪測試重點

1. 手動上傳自己的 DOCX，確認建議欄位、header/detail 與數值型別後發布（不要拿合成母版辨識正式表單）。
2. 先用一頁清楚的手寫 PDF，比對原頁與辨識列數；API key 僅填網頁密碼欄或 Streamlit Secrets。
3. 分別跑 Gemini、OpenAI，記錄遺漏列、數值、日期原文及每頁狀態；本版不自動修正年份或換算單位。
4. 確認後上傳第二份 PDF，檢查累積列數、同檔去重，再下載 CSV 以 Excel 核對中文及數值。
5. 尚未驗收前只使用去識別測試資料；勿將私人 staging 改為公開。正式環境 migration、權限及備份另案驗收。

OpenAI 影像輸入的實作依據：[官方影像與視覺文件](https://developers.openai.com/api/docs/guides/images-vision)。
