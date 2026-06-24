# DFIS Demo 欄位字典與表單映射

最後更新：2026-06-24

本文件定義 DFIS demo 階段的欄位字典，直接以目前指定的 4 份母版表單為欄位來源。目的不是一次涵蓋所有漁業表單，而是先建立「手寫 PDF / 掃描影像 → AI 辨識 → 結構化資料 → Supabase」所需的第一版標準。

## 1. 適用表單

| 表單代碼 | 表單名稱 | 資料領域 | 主要用途 |
| --- | --- | --- | --- |
| `TN_COASTAL_GILLNET_001` | 台南將軍沿海場域標本船作業調查表109.03.31 | 漁撈日誌 | 沿海網具作業與漁獲紀錄 |
| `SW_HOOK_001` | 釣具類作業報表(擷取1頁)_114.09.16 | 漁撈日誌 | 西南海域釣具類作業紀錄 |
| `TW_LONGLINE_001` | 延繩釣漁撈作業報表-高雄熊麻吉 - | 漁撈日誌 | 延繩釣 / 一支釣 / 曳繩釣混合表單 |
| `BIO_MESH_001` | 網目比較實驗室紀錄表 | 生物學資料 | 個體量測與網次背景紀錄 |

## 2. 欄位分類原則

欄位分成 4 類：

1. 固定主欄位：所有同類資料都盡量落在固定資料庫欄位。
2. 作業背景欄位：會因漁法或表單不同而變動，優先放入 `gear_properties` 或 `background_properties`。
3. 漁獲明細欄位：一筆作業下可重複出現多筆，進 `catch_records`。
4. 生物量測欄位：一批樣本下有多個個體，進 `biological_measurements`。

## 3. 資料表映射總覽

| 資料類型 | 目標資料表 | 說明 |
| --- | --- | --- |
| 匯入批次 | `import_batches` | 一次上傳或一次解析任務 |
| 原始檔案 | `source_documents` | PDF、DOCX、影像原件 |
| AI 解析紀錄 | `ai_extraction_runs` | Gemini / OpenAI 執行結果 |
| 漁撈作業主檔 | `fishery_operations` | 一份作業日誌的主資料 |
| 作業位置 | `operation_locations` | 起訖點、地點1、地點2、下網點等 |
| 漁獲明細 | `catch_records` | 魚種、重量、尾數等 |
| 生物學樣本批次 | `bio_sample_batches` | 一張生物量測表的背景資料 |
| 生物學個體明細 | `biological_measurements` | 每尾魚或每個樣本的量測值 |

## 4. 漁撈日誌固定主欄位

| 欄位鍵值 | 中文名稱 | 型別 | 必填 | 目標資料表.欄位 | 備註 |
| --- | --- | --- | --- | --- | --- |
| `form_template_code` | 表單代碼 | text | 是 | `fishery_operations.form_template_code` | 對應母版 |
| `database_category_code` | 資料庫類型代碼 | text | 是 | `fishery_operations.database_category_code` | 例如沿近海、生物學 |
| `vessel_name` | 船名 | text | 否 | `fishery_operations.vessel_name` | 若表單無則可空 |
| `vessel_registration_no` | 船編 | text | 否 | `fishery_operations.vessel_registration_no` | 西南海域表有 |
| `owner_name` | 船主 | text | 否 | `fishery_operations.owner_name` | 西南海域表有 |
| `observer_name` | 填表人/調查人 | text | 否 | `fishery_operations.observer_name` | 延繩釣表有 |
| `operation_date` | 作業日期 | date | 是 | `fishery_operations.operation_date` | 可由年月日組成 |
| `departure_time` | 出港時間 | time | 否 | `fishery_operations.departure_time` | |
| `return_time` | 進港時間 | time | 否 | `fishery_operations.return_time` | |
| `start_time` | 作業開始時間 | time | 否 | `fishery_operations.start_time` | 如下網、起始作業 |
| `end_time` | 作業結束時間 | time | 否 | `fishery_operations.end_time` | 如起網、結束作業 |
| `gear_type` | 漁法主類型 | text | 是 | `fishery_operations.gear_type` | 刺網、延繩釣、曳繩釣、一支釣、釣具類 |
| `remarks` | 備註 | text | 否 | `fishery_operations.remarks` | |

## 5. 位置欄位字典

所有經緯度、水深、地點資訊一律標準化到 `operation_locations`。

| 欄位鍵值 | 中文名稱 | 型別 | 目標欄位 | 範例 location_role |
| --- | --- | --- | --- | --- |
| `location_name` | 地點名稱 | text | `operation_locations.location_name` | `spot_1`, `spot_2` |
| `latitude` | 緯度 | numeric | `operation_locations.latitude` | `set_point`, `start_point` |
| `longitude` | 經度 | numeric | `operation_locations.longitude` | `set_point`, `start_point` |
| `depth_m` | 水深(公尺) | numeric | `operation_locations.depth_m` | `spot_1`, `spot_2`, `set_point` |
| `location_role` | 位置角色 | text | `operation_locations.location_role` | `set_point`, `haul_point`, `start_point`, `end_point` |
| `sequence_no` | 順序 | integer | `operation_locations.sequence_no` | 地點1、地點2用 |

## 6. 漁具動態欄位字典

這些欄位放入 `fishery_operations.gear_properties` JSONB。

| 欄位鍵值 | 中文名稱 | 型別 | 適用表單 | 備註 |
| --- | --- | --- | --- | --- |
| `net_set_time` | 下網時間 | time | `TN_COASTAL_GILLNET_001` | |
| `net_haul_time` | 起網時間 | time | `TN_COASTAL_GILLNET_001` | |
| `operation_depth_fathom` | 作業深度(噚) | numeric | `TN_COASTAL_GILLNET_001` | 原表單有米/噚雙單位 |
| `net_length_m` | 網具長度(公尺) | numeric | `TN_COASTAL_GILLNET_001` | |
| `net_length_nmi` | 網具長度(浬) | numeric | `TN_COASTAL_GILLNET_001` | |
| `mesh_size_inch` | 網目尺寸(吋) | numeric | `TN_COASTAL_GILLNET_001` | |
| `total_hook_hours` | 總下竿時數 | numeric | `SW_HOOK_001` | |
| `gear_count_hooks` | 漁具數(鉤) | numeric | `TW_LONGLINE_001` | |
| `gear_count_baskets` | 漁具數(筐) | numeric | `TW_LONGLINE_001` | |
| `bait_types` | 餌料類型 | text[] | `TW_LONGLINE_001` | 白帶魚、硬尾、煙仔魚、其他 |
| `gear_subtype_flags` | 表單內勾選的漁法 | jsonb | `TW_LONGLINE_001` | 流刺網、曳繩釣、延繩釣、一支釣 |
| `net_depth_text` | 網具深度描述 | text | `TW_LONGLINE_001` | 原表單文字補充 |

## 7. 漁獲明細欄位字典

這些欄位放入 `catch_records`。

| 欄位鍵值 | 中文名稱 | 型別 | 必填 | 目標欄位 | 備註 |
| --- | --- | --- | --- | --- | --- |
| `species_raw_name` | 原始魚種名稱 | text | 是 | `catch_records.species_raw_name` | AI 直接讀到的名稱 |
| `species_standard_name` | 標準魚種名稱 | text | 否 | `catch_records.species_standard_name` | 經人工或規則標準化 |
| `count_individual` | 尾數 | integer | 否 | `catch_records.count_individual` | |
| `weight_kg` | 重量(公斤) | numeric | 否 | `catch_records.weight_kg` | |
| `size_bucket` | 尺寸分級 | text | 否 | `catch_records.size_bucket` | 大 / 中 / 小 |
| `catch_notes` | 明細備註 | text | 否 | `catch_records.remarks` | |
| `catch_properties` | 動態欄位 | jsonb | 否 | `catch_records.catch_properties` | 其他不固定欄位 |

### 7.1 漁獲表單特例

`SW_HOOK_001` 額外需要支援：

- `size_bucket = large | medium | small`
- 大中小對應文字仍保留原值，例如 `1斤以上`、`半斤~1斤`、`半斤以下`

建議放法：

- 主欄位：`size_bucket`
- 補充欄位：`catch_properties.size_bucket_label`

## 8. 生物學樣本批次欄位字典

這些欄位放入 `bio_sample_batches`。

| 欄位鍵值 | 中文名稱 | 型別 | 必填 | 目標欄位 | 備註 |
| --- | --- | --- | --- | --- | --- |
| `form_template_code` | 表單代碼 | text | 是 | `bio_sample_batches.form_template_code` | |
| `vessel_name` | 船名 | text | 否 | `bio_sample_batches.vessel_name` | |
| `operation_date` | 作業/量測日期 | date | 否 | `bio_sample_batches.operation_date` | |
| `site_name` | 作業地點 | text | 否 | `bio_sample_batches.site_name` | |
| `net_group` | 內網/外網 | text | 否 | `bio_sample_batches.net_group` | |
| `net_set_no` | 第幾網 | text | 否 | `bio_sample_batches.net_set_no` | 可保留文字格式 |
| `total_weight_kg` | 總重量 | numeric | 否 | `bio_sample_batches.total_weight_kg` | |
| `discard_weight_kg` | 拋棄重量 | numeric | 否 | `bio_sample_batches.discard_weight_kg` | |
| `background_properties` | 其他背景欄位 | jsonb | 否 | `bio_sample_batches.background_properties` | |

## 9. 生物學個體量測欄位字典

這些欄位放入 `biological_measurements`。

| 欄位鍵值 | 中文名稱 | 型別 | 必填 | 目標欄位 |
| --- | --- | --- | --- | --- |
| `sequence_no` | 編號 | integer | 否 | `biological_measurements.sequence_no` |
| `specimen_no` | 樣本編號 | text | 否 | `biological_measurements.specimen_no` |
| `species_raw_name` | 原始魚種名稱 | text | 否 | `biological_measurements.species_raw_name` |
| `species_standard_name` | 標準魚種名稱 | text | 否 | `biological_measurements.species_standard_name` |
| `fork_length_mm` | 尾叉長(mm) | numeric | 否 | `biological_measurements.fork_length_mm` |
| `total_length_mm` | 全長(mm) | numeric | 否 | `biological_measurements.total_length_mm` |
| `weight_g` | 全重(g) | numeric | 否 | `biological_measurements.weight_g` |
| `sex` | 性別 | text | 否 | `biological_measurements.sex` |
| `maturity` | 成熟度 | text | 否 | `biological_measurements.maturity` |
| `gsi` | 生殖腺指數 | numeric | 否 | `biological_measurements.gsi` |
| `remarks` | 備註 | text | 否 | `biological_measurements.remarks` |

## 10. 表單到資料結構映射

### 10.1 台南將軍沿海場域標本船作業調查表

| 表單欄位 | 寫入位置 |
| --- | --- |
| 日期 | `fishery_operations.operation_date` |
| 出港/進港時間 | `fishery_operations.departure_time`, `fishery_operations.return_time` |
| 下網/起網時間 | `gear_properties.net_set_time`, `gear_properties.net_haul_time` |
| 下網經緯度 | `operation_locations` with `location_role = set_point` |
| 作業深度 | `operation_locations.depth_m` 或 `gear_properties.operation_depth_fathom` |
| 網具長度 | `gear_properties.net_length_m`, `gear_properties.net_length_nmi` |
| 網目 | `gear_properties.mesh_size_inch` |
| 漁獲種類/重量/尾數 | `catch_records` |

### 10.2 西南海域釣具類作業報表

| 表單欄位 | 寫入位置 |
| --- | --- |
| 船名/船編/船主 | `fishery_operations.vessel_name`, `vessel_registration_no`, `owner_name` |
| 日期 | `fishery_operations.operation_date` |
| 出港/進港時間 | `departure_time`, `return_time` |
| 總下竿時數 | `gear_properties.total_hook_hours` |
| 地點1/地點2 | `operation_locations` with `spot_1`, `spot_2` |
| 水深 | `operation_locations.depth_m` |
| 魚種/尾數/重量 | `catch_records` |
| 備註 | `catch_records.remarks` 或 `fishery_operations.remarks` |
| 大中小分級 | `catch_records.size_bucket` |

### 10.3 延繩釣漁撈作業報表

| 表單欄位 | 寫入位置 |
| --- | --- |
| 船名 | `fishery_operations.vessel_name` |
| 填表人 | `fishery_operations.observer_name` |
| 作業日期 | `fishery_operations.operation_date` |
| 作業時間/結束時間 | `start_time`, `end_time` |
| 作業經緯度/結束經緯度 | `operation_locations` with `start_point`, `end_point` |
| 漁法與漁具數 | `fishery_operations.gear_type` + `gear_properties` |
| 餌料 | `gear_properties.bait_types` |
| 漁獲魚種及數量 | `catch_records` |

### 10.4 網目比較實驗室紀錄表

| 表單欄位 | 寫入位置 |
| --- | --- |
| 日期 | `bio_sample_batches.operation_date` |
| 第幾網 | `bio_sample_batches.net_set_no` |
| 作業地點 | `bio_sample_batches.site_name` |
| 內網/外網 | `bio_sample_batches.net_group` |
| 總重量/拋棄重量 | `bio_sample_batches.total_weight_kg`, `discard_weight_kg` |
| 編號/魚種/尾叉長/全重 | `biological_measurements` |

## 11. AI 輸出要求

為了支援手寫 PDF / 掃描影像辨識，AI 輸出需要遵守：

1. 先辨識表單屬於哪一個 `form_template_code`。
2. 再依該表單的欄位字典輸出。
3. 無法確定的值保留空值，不可亂猜。
4. 原始辨識值需保留在 `species_raw_name` 或 JSON 補充欄位。
5. 同一表單內的重複明細要拆成多筆 `catch_records` 或 `biological_measurements`。

## 12. 下一步實作建議

本欄位字典定版後，下一步建議直接做三件事：

1. 依本字典建立 Supabase schema。
2. 將 `database.py` 由舊表結構逐步轉向新表結構。
3. 讓 Gemini / OpenAI parser 依 `form_template_code` 套用不同 prompt 與欄位映射。
