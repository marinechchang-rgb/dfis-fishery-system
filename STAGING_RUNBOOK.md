# DFIS P0-A staging 操作紀錄

日期：2026-10-20。依 implementation_plan.md 的 P0-A 優先順序執行。

## 環境與範圍

- 工作分支：codex/dfis-v1；起點 HEAD：3d362963e0bc703628c7db40bdd43cedef05f7ed。
- Supabase：dfis-staging，project ref：hmdeurstmttoiuiddyzi；Tokyo。
- 獨立新專案；正式 dfis-fishery-system 未執行 migration。
- Data API 關閉。此次沒有 Auth、RLS、Storage、parser 或 UI 重構工作。
- 不在 repository 保存密碼、token 或實際 DATABASE_URL。

## Schema 決策與影響

現行 CRUD 使用整數 legacy ID 與 TEXT UUID shadow ID、TEXT JSON、文字日期。
supabase_schema.sql 的 UUID / JSONB 目標結構仍需後續明確 adapter/migration。
P0-A 使用 migrations/001_staging_legacy_contract.sql，在已確認空白的 staging public schema
建立與目前 CRUD 相容的 15 張表，另補 8 個 FK 及查詢索引。
只 seed 五項分類及四項母版，不新增歷史漁撈或生物學示例紀錄。
SQL 有 transaction 與既存應用表阻擋條件；不得在非空環境重跑。
沒有 DROP、資料轉型、搬移或清空。

PostgreSQL init_db 改成唯讀 schema contract 檢查；不再於啟動時建表或 seed。
schema 不符或連線失敗會停止，不會改用 SQLite。
SQLite 開發初始化維持原行為，不能據此宣告雲端保存通過。

## 部署與設定

先部署 codex/dfis-v1 / staging_app.py，將 Streamlit Cloud App 設為僅測試人員可存取。
在該 App 的 Secrets 設定以下非機密開關：

```toml
DFIS_ENVIRONMENT = "staging"
DFIS_REQUIRE_POSTGRES = true
```

連線設定請從 Supabase Connect 的 Session pooler 複製 host、port、database、user，
使用 PGHOST、PGPORT、PGDATABASE、PGUSER、PGPASSWORD 欄位存入該 App Secrets。
PGPASSWORD 由使用者親自填入；不要貼入對話、SQL 編輯器或任何追蹤檔。
既有正式 App 的 Secrets 不搬入 staging。

## 驗收步驟

1. staging_app.py 先要求 PostgreSQL 與指定 staging project ref，並檢查實際 schema。
2. 新增唯一 P0-STAGING- 標記的合成日誌，使用 database.save_fishery_log 真實 CRUD。
3. 記錄 marker、log ID、CSV SHA-256、App instance / PID / started_at。
4. 在 Streamlit Cloud 管理介面執行 Reboot，記錄操作時間。
5. 重啟後填入同 marker / ID 查詢，驗證重量 1.25 kg、尾數 3 與中文魚名。
6. 確認 instance 已改變，下載 CSV，核對其內容與 SHA-256。
7. Supabase 唯讀查詢同 ID 與關聯明細，交叉確認資料來自 PostgreSQL。

p0_persistence_smoke.py 的 cloud_restart_verified 固定 false；需結合實際 Cloud reboot
與前後結果，才可人工將 P0-A 驗收紀錄列為完成。

## 目前證據與未完成事項

- Supabase Healthy；建表前 public 查詢回傳 0 表。
- staging 建表 SQL 執行顯示 Success. No rows returned。
- 本機 unittest discover：34 項通過（含唯讀 contract / fail-closed 測試）。
- 暫存 SQLite 執行既有 test_database.run_tests：分類、日誌、統計、參數及生物資料 CRUD 通過；
  最後 JSON repair 舊斷言失敗（實際保留第二個可修復物件，預期只保留第一個）。整份手動套件不能列為通過。
  該 parser 斷言不在 P0-A 範圍，此次未修改。測試未操作原有 fishery_standard.db。
- 雲端唯讀核對：15 表、5 分類、4 母版、0 日誌、0 生物學紀錄、8 FK。
- Cloud 部署、實際 Secrets 連線、insert / reboot / query / CSV：待執行。
- P0-A 與 v1 尚未完成，不進入 P0-B / P1。

## 尚存風險

- 本次相容結構不是最終 UUID schema，後續統一欄位需另行設計及驗證。
- 既有 biological sample batch conflict / shadow cleanup 路徑尚需 PostgreSQL 實測。
- Supabase Free 專案可能因閒置暫停；正式服務可用性尚未驗收。
- 部署版本若仍使用 main，不能代表本分支的 persistence 修正已上線。

建議 commit message：feat: add fail-closed Supabase staging persistence verification
