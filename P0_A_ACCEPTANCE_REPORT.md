# P0-A Supabase staging persistence 驗收報告

日期：2026-10-21（Asia/Taipei）。狀態：P0-A staging persistence 驗收通過。
通過範圍：Streamlit Cloud → Supabase PostgreSQL → 日誌 insert → Cloud Reboot → query → 實際 CSV 匯出。
此結論不代表正式環境已切換、全部 CRUD 已覆蓋或 DFIS v1 已完成。

唯一執行優先順序依據為 implementation_plan.md。此次只進行 P0-A，未更動 parser、Auth、RLS、Storage。

## A. 修改檔案

| 檔案 | 用途 |
| --- | --- |
| database.py | PostgreSQL 連線與啟動保護、局部 SQL 相容處理 |
| app.py | 啟動失敗停止與實際後端狀態提示 |
| persistence_contract.py | 唯讀核對 CRUD 欄位、型別及必要唯一鍵 |
| db_diagnostics.py | 不含憑證的 schema metadata 診斷 |
| migrations/001_staging_legacy_contract.sql | 空白 staging 專用交易式建表 |
| p0_persistence_smoke.py | 以實際 CRUD 執行 insert / verify 與 CSV 回讀 |
| staging_app.py | 限定指定 staging 專案的 Cloud 驗證入口 |
| test_p0_persistence.py / test_persistence_contract.py | 連線與 schema 保護測試 |
| STAGING_RUNBOOK.md | 環境、操作、限制與接續方式 |
| evidence/p0_a_20261021.json | 重啟前後及 Supabase 交叉核對資料 |
| evidence/P0-STAGING-20261021-VERIFY01.csv | 使用者下載的實際 CSV，逐位元組保存 |
| .gitattributes | 停用 evidence CSV 的 Git 換行轉換，保留原始雜湊 |

## B. 修改理由

PostgreSQL 設定後連線失敗必須停止，避免雲端誤存 SQLite。啟動時僅執行唯讀 schema 檢查，
不再自動 ALTER / CREATE / seed。移除全域 pandas monkeypatch，避免重載後遞迴或影響其他模組。
測試 App 僅允許 dfis-staging 的連線設定，並要求 staging 與 require-postgres 開關。

## C. Schema 影響

新 staging public schema 為現行 CRUD 相容結構：6 張整數 ID 業務表、文字主鍵分類及母版、
TEXT UUID shadow 表；日期與 JSON 仍為 TEXT。15 張表、8 個外鍵、5 分類與4母版。
完整欄位在 migration；差異盤點在 P0_A_PERSISTENCE_AUDIT.md。
supabase_schema.sql 的最終 UUID / JSONB 結構尚未套用；此 staging 不等於完成最終資料標準轉換。

## D. Migration 影響

只在獨立新專案 hmdeurstmttoiuiddyzi 執行，事前 public 查詢為空。
建表交易會拒絕已有應用表的環境；無 DROP、搬移、轉型或清除。
新增日誌、漁獲及 shadow 關聯所需 FK / 索引；分類與母版之外不 seed 業務資料。
正式專案未執行 migration。Data API 維持關閉；staging App 已設為私人。

## E. 測試結果

- unittest discover：34 項通過；含連線失敗不 fallback、TLS、缺設定停止、schema 不符不 migration、錯誤隱去憑證。
- py_compile 與 git diff --check 通過。
- 最終離線證據一致性檢查通過：原始下載檔與歸檔位元組一致、CSV 雜湊對應兩次雲端結果、
  insert / reboot / query 時序成立、App instance / PID 已改變，且實際 CSV 數值與關聯值正確。
  可用 `Get-FileHash -Algorithm SHA256 evidence/P0-STAGING-20261021-VERIFY01.csv` 重現檔案雜湊。
- 既有 test_database.run_tests 在獨立暫存 SQLite 執行：分類、日誌、統計、參數及生物資料 CRUD 通過。
  最後 JSON repair 舊斷言失敗，整份手動套件不列為全通過。該斷言未在 P0-A 修改。
- 34 項不是完整 PostgreSQL CRUD 覆蓋；真實 PostgreSQL 證據為下節 Cloud 日誌閉環。

## F. Persistence smoke test

| 項目 | 證據 / 結果 |
| --- | --- |
| Cloud App | https://dfis-v1-lab.streamlit.app/，codex/dfis-v1 / staging_app.py，Python 3.12 |
| insert | 2026-10-21 09:19:41，log ID=1，marker P0-STAGING-20261021-VERIFY01 |
| insert 程序 | PID 248，instance c2159a9a-96fe-4ebd-b315-f19e1663f609 |
| 實際重啟 | Cloud 管理介面 Reboot，09:31:22 disconnect、09:31:27 provisioning |
| 新程序 | PID 292，instance 0b39961b-fcd3-4f14-90d7-1aa95bb67440 |
| query | 09:33:39，同 marker / ID，P0測試魚、1.25 kg、3 尾 |
| PostgreSQL | 前後 backend=postgresql、schema=public；probe PID 94562 → 95399 |
| SQLite fallback | 前後 false；重新查詢前清除資料快取 |
| Supabase 交叉核對 | SQL JOIN 查到同筆日誌、漁獲、operation 與 import batch |
| CSV 產生與回讀 | 前後 SHA-256 相同；中文魚名及數值通過 |
| 實際下載 CSV | 使用者保存後獨立校驗通過：220 bytes、UTF-8 BOM、1 列、11 欄；SHA-256 完全一致 |

CSV 預期 SHA-256：c6ab382d208910428dd577551ba1e0fb2e85aa0dd32b67e6a692c68f9548bded。
原始下載位於 202610測試/P0-STAGING-20261021-VERIFY01.csv；已將完全相同位元組歸檔至 evidence。
另外核對 id=1、log_id=1、兩個中文魚名欄位、重量 1.25、尾數 3、sequence_no=1、
operation_id=52efc1c7-ffc6-4f5f-9971-62e7cd359bf5 與空白選填欄位。
p0_persistence_smoke.py 的 cloud_restart_verified 刻意固定 false，CLI 不自行聲稱觀察到 Cloud 重啟；
本報告的重啟結論來自實際管理操作、Cloud log 與前後程序識別共同佐證。

## G. 尚存風險

1. 本次只驗收合成漁撈日誌的 staging 閉環；不等同所有表單與業務流程皆已驗證。
2. 生物資料 batch conflict / shadow cleanup 等 PostgreSQL CRUD 尚需額外覆蓋。
3. 正式 App 仍部署 main，staging 成果不代表正式環境已切換。
4. Free 服務有休眠與暫停風險；此次重啟曾遇套件下載暫時失敗，由平台 pip fallback 復原。
5. UUID / JSONB 目標結構、parser 辨識品質與雙模型正式樣本驗收仍屬後續工作，v1 尚未完成。

## H. Commit

已提交實作：3adb6f0 feat: add fail-closed Supabase staging persistence verification。
已提交環境紀錄：73746e1 docs: record staging bootstrap and Cloud deployment status。
中間證據提交：1f93e59 docs: record Cloud reboot persistence evidence and CSV acceptance status。
最終驗收建議 commit message：docs: accept P0-A staging persistence with verified CSV artifact。
