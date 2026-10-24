# 隔離模型比較入口 CMP-1

日期：2026-10-24。使用者已授權新增並部署於原 dfis-v1-lab staging；僅限指定第 5 頁與既有樣板，各模型一次。

## 範圍與資料流

- 步驟④「隔離模型比較」，僅在 DFIS_ENVIRONMENT=staging 啟用。
- 僅接受原第 5 頁的已驗證單頁副本 hash，以及指定樣板 ID；不重新發布樣板、不改原 PDF。
- 同一 JPEG（PDFium scale=2、JPEG quality=90）與原流程提示，兩模型輸入 hash 必須相同。
- 固定 Gemini `gemini-3.1-flash-lite`、OpenAI `gpt-6-luna`，不接受其他模型、不靜默替換。
- 正確年份 2025 僅作使用者提供的事後判讀基準，未注入提示。
- 直接官方 HTTPS REST，一次 POST、transport retries=0、follow_redirects=false、trust_env=false；無 SDK 重試或應用重試迴圈。
- 發送前以程序共用 lock claim 每模型，失敗、逾時、不完整／JSON 解析錯誤都保留且不可重試。HTTP 失敗只存狀態碼，不存可能包含敏感資訊的例外字串／錯誤本文。
- 結果與 usage、耗時、模型、來源 hash、原頁／副本頁映射可下載 JSON。API key 僅在密碼元件／請求標頭，不寫入結果或 repository。

## Schema 與風險

- 不讀寫 wf_pages／wf_records，不呼叫 register/save_page/confirm，無 schema／migration／Auth／RLS／Storage 改動。
- 比較結果與每模型單次鎖僅存伺服器程序記憶體，透過 Streamlit cache_resource 跨 rerun／同程序 session 共用。
- **重啟／重新部署會清除結果與鎖**；這不是持久化評測 ledger，也不能保證跨重啟 exactly-once。不得藉重啟再次消費原有授權。
- 僅在私人測試站使用；同程序有權進入該站者可見比較結果。本版沒有新增使用者隔離或 Auth。
- 若伺服器在請求後回應前中斷，可能已有費用而無下載證據；不得因無結果就自行重試。
- 單次 transport 不代表服務商內部運算一次；費用以供應商 usage／帳單為準。
- 不把 HTTP success、JSON 可解析或年份正確當作整頁 OCR 品質通過；仍需比較左右欄列數、魚名、尾數與重量。

## 本機驗證

- unittest discover：136 項通過（包含新增 11 項）；首次有 4 項既有 localhost HTTP 測試遭沙箱阻擋，經授權在沙箱外重跑全部通過。
- 新增 Streamlit 比較 AppTest：3 項通過，涵蓋無檔／無同意阻擋、單次失敗鎖與 rerun 不再發送。
- 既有 Streamlit 樣板／候選測試 12 項、PDF 步驟測試 11 項通過；均為合成資料／fake API，非新模型品質驗收。
- 本機安裝 httpx 0.28.1 用於 mock transport 測試；requirements 新增 httpx>=0.28.0。
- 測試不使用真實 key、不呼叫付費 API。線上驗證與真實測試結果另於下方記錄。

## 發布檔案

model_comparison.py、model_comparison_ui.py、workflow_ui.py、requirements.txt、test_model_comparison.py、tools/verify_streamlit_comparison.py、本文件。
不提交私人 PDF／CSV／截圖、Secrets、其他 dirty 文件或實驗；main 不變。

## 線上驗證

待選檔提交、推送及 Cloud 發布後實際檢查；此段尚不宣告已部署或雙模型實測完成。
