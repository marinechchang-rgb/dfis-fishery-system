-- Additive staging migration. Existing P0-A tables/data are unchanged.
BEGIN;
CREATE TABLE wf_templates (
 id TEXT PRIMARY KEY, code TEXT NOT NULL, version INTEGER NOT NULL,
 name TEXT NOT NULL, source_name TEXT NOT NULL, source_sha TEXT NOT NULL,
 snapshot_json TEXT NOT NULL, fields_json TEXT NOT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(code,version),
 UNIQUE(code,source_sha,fields_json)
);
CREATE TABLE wf_uploads (
 id TEXT PRIMARY KEY, template_id TEXT NOT NULL REFERENCES wf_templates(id),
 filename TEXT NOT NULL, pdf_sha TEXT NOT NULL, page_count INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(template_id,pdf_sha)
);
CREATE TABLE wf_pages (
 upload_id TEXT NOT NULL REFERENCES wf_uploads(id), page_no INTEGER NOT NULL,
 status TEXT NOT NULL, result_json TEXT, provider TEXT, model TEXT,
 PRIMARY KEY(upload_id,page_no)
);
CREATE TABLE wf_records (
 id TEXT PRIMARY KEY, upload_id TEXT NOT NULL REFERENCES wf_uploads(id),
 page_no INTEGER NOT NULL, row_no INTEGER NOT NULL, values_json TEXT NOT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(upload_id,page_no,row_no)
);
CREATE INDEX wf_upload_template_idx ON wf_uploads(template_id);
CREATE INDEX wf_records_upload_idx ON wf_records(upload_id);
COMMIT;
