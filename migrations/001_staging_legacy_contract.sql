-- P0-A staging bootstrap; current CRUD-compatible schema, NOT the target UUID migration.
-- Only run in the NEW dfis-staging project after reviewing its empty public schema.
-- Transaction fails if any application table already exists. No DROP or data conversion.
BEGIN;
SET LOCAL search_path = public;
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM information_schema.tables
  WHERE table_schema='public' AND table_name IN
  ('database_categories','fishery_logs','catch_records','ports','vessels','species',
   'biological_parameters','form_templates','import_batches','ai_extraction_runs',
   'fishery_operations','operation_locations','bio_sample_batches',
   'biological_measurements','field_definitions')) THEN
  RAISE EXCEPTION 'Staging bootstrap requires an empty application schema';
 END IF;
END $$;
CREATE TABLE database_categories (
                name TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

CREATE TABLE fishery_logs (
                id SERIAL PRIMARY KEY,
                database_type TEXT DEFAULT '拖網類漁業報表資料庫',
                vessel_name TEXT NOT NULL,
                log_date TEXT NOT NULL,
                gear_type TEXT NOT NULL,
                gear_properties TEXT, -- JSON string
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

CREATE TABLE catch_records (
                id SERIAL PRIMARY KEY,
                log_id INTEGER NOT NULL,
                species_raw_name TEXT NOT NULL,
                species_standard_name TEXT NOT NULL,
                weight_kg REAL,
                count_individual INTEGER,
                catch_properties TEXT
            );

ALTER TABLE catch_records ADD COLUMN IF NOT EXISTS operation_id TEXT;

ALTER TABLE catch_records ADD COLUMN IF NOT EXISTS sequence_no INTEGER;

ALTER TABLE catch_records ADD COLUMN IF NOT EXISTS size_bucket TEXT;

ALTER TABLE catch_records ADD COLUMN IF NOT EXISTS remarks TEXT;

CREATE TABLE ports (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                county TEXT NOT NULL
            );

CREATE TABLE vessels (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                registration_number TEXT
            );

CREATE TABLE species (
                id SERIAL PRIMARY KEY,
                chinese_name TEXT NOT NULL UNIQUE,
                code TEXT,
                genus TEXT,
                species TEXT
            );

CREATE TABLE biological_parameters (
                id SERIAL PRIMARY KEY,
                collection_date TEXT NOT NULL,
                collection_id TEXT NOT NULL,
                port TEXT NOT NULL,
                vessel_name TEXT NOT NULL,
                form_code TEXT NOT NULL,
                species_name TEXT NOT NULL,
                sex TEXT,
                maturity TEXT,
                total_length_mm REAL,
                weight_g REAL,
                gsi REAL,
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS sample_batch_id TEXT;

ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS sequence_no INTEGER;

ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS specimen_no TEXT;

ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS species_standard_name TEXT;

ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS fork_length_mm REAL;

ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS net_group TEXT;

ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS net_set_no TEXT;

ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS site_name TEXT;

ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS total_weight_kg REAL;

ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS discard_weight_kg REAL;

ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS background_properties TEXT;

CREATE TABLE form_templates (
            template_code TEXT PRIMARY KEY,
            template_name_zh TEXT NOT NULL,
            data_domain TEXT NOT NULL,
            gear_family TEXT,
            source_file_name TEXT,
            is_active INTEGER DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE import_batches (
            id TEXT PRIMARY KEY,
            database_category_code TEXT,
            form_template_code TEXT,
            source_channel TEXT DEFAULT 'upload',
            import_status TEXT DEFAULT 'saved',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE ai_extraction_runs (
            id TEXT PRIMARY KEY,
            batch_id TEXT,
            provider_name TEXT,
            model_name TEXT,
            prompt_version TEXT,
            schema_version TEXT,
            run_status TEXT DEFAULT 'success',
            raw_response TEXT,
            normalized_payload TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE fishery_operations (
            id TEXT PRIMARY KEY,
            legacy_log_id INTEGER UNIQUE,
            batch_id TEXT,
            database_category_code TEXT,
            form_template_code TEXT,
            vessel_name TEXT,
            vessel_registration_no TEXT,
            owner_name TEXT,
            observer_name TEXT,
            operation_date TEXT NOT NULL,
            departure_time TEXT,
            return_time TEXT,
            start_time TEXT,
            end_time TEXT,
            gear_type TEXT NOT NULL,
            remarks TEXT,
            gear_properties TEXT,
            review_status TEXT DEFAULT 'needs_review',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE operation_locations (
            id TEXT PRIMARY KEY,
            operation_id TEXT NOT NULL,
            location_role TEXT NOT NULL,
            sequence_no INTEGER,
            location_name TEXT,
            latitude REAL,
            longitude REAL,
            depth_m REAL,
            extra_properties TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE bio_sample_batches (
            id TEXT PRIMARY KEY,
            source_record_key TEXT UNIQUE,
            form_template_code TEXT,
            vessel_name TEXT,
            operation_date TEXT,
            site_name TEXT,
            port_name TEXT,
            net_group TEXT,
            net_set_no TEXT,
            total_weight_kg REAL,
            discard_weight_kg REAL,
            background_properties TEXT,
            review_status TEXT DEFAULT 'needs_review',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE biological_measurements (
            id TEXT PRIMARY KEY,
            sample_batch_id TEXT NOT NULL,
            legacy_biological_id INTEGER,
            sequence_no INTEGER,
            specimen_no TEXT,
            species_raw_name TEXT,
            species_standard_name TEXT,
            fork_length_mm REAL,
            total_length_mm REAL,
            weight_g REAL,
            sex TEXT,
            maturity TEXT,
            gsi REAL,
            remarks TEXT,
            measurement_properties TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE field_definitions (
            id TEXT PRIMARY KEY,
            form_template_code TEXT,
            field_key TEXT NOT NULL,
            field_scope TEXT NOT NULL,
            label_zh TEXT NOT NULL,
            data_type TEXT NOT NULL,
            unit_name TEXT,
            is_required INTEGER DEFAULT 0,
            target_table TEXT NOT NULL,
            target_column TEXT,
            json_path TEXT,
            notes TEXT
        );

-- Relationships missing from legacy PostgreSQL initialization.
ALTER TABLE fishery_logs ADD FOREIGN KEY (database_type) REFERENCES database_categories(name);
ALTER TABLE fishery_operations ADD FOREIGN KEY (legacy_log_id) REFERENCES fishery_logs(id) ON DELETE CASCADE;
ALTER TABLE fishery_operations ADD FOREIGN KEY (batch_id) REFERENCES import_batches(id);
ALTER TABLE catch_records ADD FOREIGN KEY (log_id) REFERENCES fishery_logs(id) ON DELETE CASCADE;
ALTER TABLE catch_records ADD FOREIGN KEY (operation_id) REFERENCES fishery_operations(id) ON DELETE CASCADE;
ALTER TABLE operation_locations ADD FOREIGN KEY (operation_id) REFERENCES fishery_operations(id) ON DELETE CASCADE;
ALTER TABLE biological_measurements ADD FOREIGN KEY (sample_batch_id) REFERENCES bio_sample_batches(id);
ALTER TABLE biological_measurements ADD FOREIGN KEY (legacy_biological_id) REFERENCES biological_parameters(id) ON DELETE CASCADE;
CREATE INDEX catch_records_log_idx ON catch_records(log_id);
CREATE INDEX catch_records_operation_idx ON catch_records(operation_id);
CREATE INDEX operation_locations_operation_idx ON operation_locations(operation_id);
CREATE INDEX biological_measurements_legacy_idx ON biological_measurements(legacy_biological_id);

INSERT INTO database_categories(name) VALUES ('生物學參數資料庫'), ('拖網類漁業報表資料庫'), ('刺網類漁業報表資料庫'), ('釣具類漁業報表資料庫'), ('休閒船釣漁業資料庫');
INSERT INTO form_templates(template_code,template_name_zh,data_domain,gear_family,source_file_name,notes) VALUES
('TN_COASTAL_GILLNET_001','台南將軍沿海場域標本船作業調查表109.03.31','fishery','gillnet','台南將軍沿海場域標本船作業調查表109.03.31.docx','沿海網具作業調查母版'),
('SW_HOOK_001','釣具類作業報表(擷取1頁)_114.09.16','fishery','hook_and_line','釣具類作業報表(擷取1頁)_114.09.16.docx','西南海域釣具類作業母版'),
('TW_LONGLINE_001','延繩釣漁撈作業報表-高雄熊麻吉 -','fishery','longline','延繩釣漁撈作業報表-高雄熊麻吉 -.docx','延繩釣與一支釣混合母版'),
('BIO_MESH_001','網目比較實驗室紀錄表','biology','lab_measurement','網目比較實驗室紀錄表.docx','生物學量測母版');
COMMIT;
