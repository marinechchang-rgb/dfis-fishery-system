# S1 主站 AI 未審核候選查詢／CSV 修正紀錄

日期：2026-10-22（Asia/Taipei）。狀態：**本機實作、回歸與 Streamlit AppTest 通過；尚未部署或完成真實 PostgreSQL／Cloud 驗收。**
主執行順序依 implementation_plan.md，沿用原 Streamlit 測試站，不再擴充獨立本機使用介面。

## A. 修改檔案與理由

| 檔案 | 修改 |
| --- | --- |
| workflow_candidates.py（新增） | 純候選驗證／投影、頁面摘要、未審核 CSV、摘要 JSON；沒有 DB 或 API 寫入 |
| workflow_store.py | 新增 candidate_snapshot，兩次參數化 SELECT；依母版／批次載入保存候選，不依賴上傳檔或 session_state |
| workflow_ui.py | 第三分頁增加候選／確認模式；候選摘要、部分資料提示與下載；原確認 CSV 移成 helper，格式保留 |
| workflow_ai.py | 未知 provider 提早拒絕，避免 LocalCPU 等名稱默默進 Gemini 分支；未新增模型呼叫 |
| test_workflow_candidates.py（新增） | 19 項契約、唯讀資料存取、介面 helper 與舊確認 CSV 相容測試 |
| tools/verify_streamlit_candidates.py（新增） | 真實 Streamlit AppTest，含三分頁與模式切換；使用合成／mock，不呼叫真實服務 |
| implementation_plan.md、WORD_WORKFLOW_TEST_GUIDE.md | 更新實作、操作與待部署驗收範圍 |

## B. 使用者可見的改變（部署後才會出現）

主站第三分頁「③ 候選／已確認 CSV」：

- 選擇已發布母版版本，預設查看「AI 未審核候選」。
- 可查全部未確認批次或指定批次，不要求重新上傳原 PDF，也不必先人工確認。
- 顯示保存的頁碼、provider／model、候選列數、缺頁、失敗、非 AI 頁、格式問題及排除全 null 行的數量。
- 同時提供候選頁面摘要 JSON 及 UTF-8 BOM CSV。
- 部分失敗／缺頁時，必須勾選「了解這是部分候選」才啟用 CSV；這不是人審，不改資料狀態。
- 部分候選檔名包含 AI_UNREVIEWED_PARTIAL；完整範圍則 AI_UNREVIEWED。
- 壞 JSON、重複 JSON key、未知欄位、錯頁或非法數字等，整個所選範圍阻擋 CSV，仍可下載問題摘要。
- 切換「已確認資料」即使用原有 wf_records 讀取與 CSV 格式，不將候選混入。

重新查詢按鈕只觸發正常 Streamlit rerun；候選資料不加 session 快取，重新從保存層取得。
原人工覆核與確認 checkbox 保留，沒有由程式代勾。

## C. 來源與數值規則

- metadata 使用既有保留的 source_ 前綴，避免碰撞母版自訂欄位。
- 候選固定 source_review_status=ai_unreviewed、source_reviewed_by_human=false；忽略輸入自稱 confirmed／human-reviewed。
- source_candidate_row 是原保存 rows 的頁內索引；排除全空列後仍保留原索引，不冒充原表實體列。
- 舊資料沒有已驗證的左右區／實體列證據，source_section、source_physical_row 留空，不猜測。
- 只將保存 provider 為 Gemini／OpenAI 的成功頁列為 AI 候選；人工建檔頁單獨計數、不偽裝 AI。
  LocalCPU 等新 provider 仍未接入，不能因新增候選匯出而宣稱低成本引擎已上線。
- 0 與 null 分開；空 rows 不等於已確認空白或零漁獲。全 null 行排除並明示，不當觀測。
- 母版發佈的欄位順序保留；日期與魚名保留文字，不猜年份或標準魚名。
- 新匯出層使用 Decimal，不額外以 float 轉換造成精度損失；無法恢復之前解析／保存時已損失的精度。
- 數字字串不作字母補位或把 1,2 自動改為 12；格式不符時阻擋匯出，而非默默修造資料。
- CSV 保留 UTF-8 BOM 與公式文字防護；原已確認 CSV 欄名、檔名及生成函式不變。

## D. Schema 與 migration 影響

**無 schema 或 migration 變更。** 沿用 wf_templates、wf_uploads、wf_pages 與 wf_records。
candidate_snapshot 僅 SELECT，沒有 INSERT／UPDATE／DELETE／DDL，也不呼叫 confirm。
confirmed 批次在全選候選時排除；若指定已確認批次，提示改用確認模式。
錯母版／外來批次／不存在 ID 明確拒絕，SQL 參數化。

候選 helper 的唯讀界線不表示整個舊 App 都不寫入：原 Word 發布、PDF 上傳註冊及確認按鈕仍有各自既有寫入用途。
S1 的「不用重新上傳」路徑已在 AppTest 驗證不需要 PDF 輸入，也沒有 AI 或確認呼叫。
沒有操作使用者的 fishery_standard.db、真實 Supabase 或既有 Cloud Secrets。

## E. 實際測試結果

### 完整回歸

主 runtime Python 3.12.14：**125 項 unittest discover 通過**，原 106＋新增 19。

```powershell
& 'C:\Users\azwer\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover
```

新增測試涵蓋：

- 0/null、來源 metadata、人審旗標、沒有實體格位時留空、不改輸入物件。
- 缺頁／失敗頁的部分狀態與 CSV 警示、人工頁排除、未知 provider 阻擋且不呼叫 SDK。
- 壞 JSON／重複 key／NaN／超範圍指數、未知欄位與非法值、整頁驗證原子性。
- 全 null 行排除與保留索引、空候選不冒充空白、越界／重複／外來頁、欄位 metadata 碰撞。
- BOM、公式防護、Decimal 精度、禁止匯出偽造人審旗標。
- 兩批候選重新連線查詢、真正以 SQLite mode=ro 連線及 SQL trace 驗證只執行 SELECT；前後 dump 相同。
- 確認後候選排除、原確認 CSV 資料不變、錯母版／不存在 ID／SQL 注入字串拒絕。
- 合成 UI helper 的無檔案／無 API／不確認下載、部分候選 acknowledgement、壞頁只允許摘要及舊 CSV bytes 一致。

SQLite 僅為獨立暫存測試 fixture，不是 App fallback，也不冒稱 PostgreSQL 測試。

### 真實 Streamlit AppTest

既有專案 .venv：Python 3.14.5、Streamlit 1.58.0，**5 項 AppTest 全通過**：

1. 完整 AI 候選不需人審 checkbox，即有可用 CSV 下載元件。
2. 部分候選先 disabled，明確理解提示後 rerun 可啟用，仍是未審核。
3. 保存 JSON 壞掉只提供摘要下載，不提供候選 CSV。
4. 舊已確認 CSV 入口獨立保留。
5. 完整 Word／PDF／匯出三分頁在沒有重新上傳 PDF 時可顯示候選，並成功切回確認模式。

```powershell
& '.\.venv\Scripts\python.exe' tools/verify_streamlit_candidates.py
```

AppTest 執行的是實際 Streamlit 元件與 rerun，但替代 store 與模型呼叫；不是瀏覽器點選、實際 HTTP 下載、
真實 PostgreSQL、Cloud Reboot 或目前線上 Streamlit 套件版本的證明。
初次導覽 fixture 缺少原母版顯示欄位，補齊 name／source_name 後重跑全通過，沒有為配合 fixture 修改既有母版顯示契約。
執行時有 AppTest bare-mode ScriptRunContext 警告，沒有 app exception。

## F. 尚未完成的線上驗收

- 原站最新部署 commit、可登入狀態與指定 Supabase 環境尚未在本輪重新核對。
- 未 commit／push／部署，新入口目前只在本機工作區程式內。
- 未做真實 PostgreSQL 候選查詢、Cloud Reboot、瀏覽器下載檔 byte/hash 比較。
- S2 低成本結果包／worker 仍未接入；主站 provider 能力未擴張。
- 原本未確認候選的 upsert／多 run 版本問題仍需 S2 保護設計，不在 S1 悄悄覆寫。
- 沒有驗收真實手寫品質、漏列率、日期／魚名正確率或獨立樣本泛化。

## G. 接續順序

先唯讀核對原私人 staging 的版本、環境與現存母版／批次，再依授權選檔部署 S1。
部署後以已保存候選驗證查詢／CSV，核對確認資料未改；如需新增測試資料，另限定合成批次。
候選保存／重啟／實際下載列為 S3/S4 證據，不能沿用舊 P0-A 或本機 AppTest 代替。

低成本 OCR 結果契約與執行位置維持下一個獨立工作包；不把本次候選 CSV 改動說成 CPU 引擎已在 Cloud 運行。

建議 commit message：feat: add read-only unreviewed candidate export to staging workflow
