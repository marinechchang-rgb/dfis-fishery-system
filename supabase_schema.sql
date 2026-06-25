create extension if not exists pgcrypto;

create table if not exists database_categories (
    id uuid primary key default gen_random_uuid(),
    category_code text not null unique,
    category_name_zh text not null,
    description text,
    created_at timestamptz not null default now()
);

create table if not exists form_templates (
    id uuid primary key default gen_random_uuid(),
    template_code text not null unique,
    template_name_zh text not null,
    data_domain text not null check (data_domain in ('fishery', 'biology')),
    gear_family text,
    source_file_name text,
    version_no text default '1.0',
    is_active boolean not null default true,
    notes text,
    created_at timestamptz not null default now()
);

create table if not exists vessels (
    id uuid primary key default gen_random_uuid(),
    vessel_name text not null,
    registration_no text,
    owner_name text,
    unique (vessel_name, registration_no)
);

create table if not exists ports (
    id uuid primary key default gen_random_uuid(),
    port_name text not null unique,
    county_name text
);

create table if not exists species_catalog (
    id uuid primary key default gen_random_uuid(),
    standard_name_zh text not null unique,
    scientific_name text,
    fao_code text,
    taxon_rank text,
    aliases jsonb not null default '[]'::jsonb,
    notes text
);

create table if not exists import_batches (
    id uuid primary key default gen_random_uuid(),
    database_category_id uuid references database_categories(id),
    form_template_id uuid references form_templates(id),
    source_channel text not null default 'upload',
    import_status text not null default 'uploaded'
        check (import_status in ('uploaded', 'parsed', 'needs_review', 'approved', 'saved', 'failed')),
    uploaded_by text,
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists source_documents (
    id uuid primary key default gen_random_uuid(),
    batch_id uuid not null references import_batches(id) on delete cascade,
    original_filename text not null,
    mime_type text,
    sha256_hash text,
    page_count integer,
    storage_path text,
    extracted_text text,
    created_at timestamptz not null default now()
);

create table if not exists ai_extraction_runs (
    id uuid primary key default gen_random_uuid(),
    batch_id uuid not null references import_batches(id) on delete cascade,
    provider_name text not null check (provider_name in ('gemini', 'openai')),
    model_name text not null,
    prompt_version text,
    schema_version text,
    run_status text not null default 'success'
        check (run_status in ('success', 'partial', 'failed')),
    raw_response jsonb,
    normalized_payload jsonb,
    error_message text,
    created_at timestamptz not null default now()
);

create table if not exists fishery_operations (
    id uuid primary key default gen_random_uuid(),
    batch_id uuid not null references import_batches(id) on delete cascade,
    database_category_id uuid references database_categories(id),
    form_template_id uuid not null references form_templates(id),
    vessel_id uuid references vessels(id),
    vessel_name text,
    vessel_registration_no text,
    owner_name text,
    observer_name text,
    operation_date date not null,
    departure_time time,
    return_time time,
    start_time time,
    end_time time,
    gear_type text not null,
    remarks text,
    gear_properties jsonb not null default '{}'::jsonb,
    review_status text not null default 'needs_review'
        check (review_status in ('needs_review', 'approved', 'rejected')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists operation_locations (
    id uuid primary key default gen_random_uuid(),
    operation_id uuid not null references fishery_operations(id) on delete cascade,
    location_role text not null,
    sequence_no integer,
    location_name text,
    latitude numeric(10, 6),
    longitude numeric(10, 6),
    depth_m numeric(10, 2),
    extra_properties jsonb not null default '{}'::jsonb
);

create table if not exists catch_records (
    id uuid primary key default gen_random_uuid(),
    operation_id uuid not null references fishery_operations(id) on delete cascade,
    sequence_no integer,
    species_catalog_id uuid references species_catalog(id),
    species_raw_name text not null,
    species_standard_name text,
    size_bucket text,
    count_individual integer,
    weight_kg numeric(12, 3),
    remarks text,
    catch_properties jsonb not null default '{}'::jsonb
);

create table if not exists bio_sample_batches (
    id uuid primary key default gen_random_uuid(),
    batch_id uuid not null references import_batches(id) on delete cascade,
    form_template_id uuid not null references form_templates(id),
    vessel_id uuid references vessels(id),
    vessel_name text,
    operation_date date,
    site_name text,
    port_id uuid references ports(id),
    port_name text,
    net_group text,
    net_set_no text,
    total_weight_kg numeric(12, 3),
    discard_weight_kg numeric(12, 3),
    background_properties jsonb not null default '{}'::jsonb,
    review_status text not null default 'needs_review'
        check (review_status in ('needs_review', 'approved', 'rejected')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists biological_measurements (
    id uuid primary key default gen_random_uuid(),
    sample_batch_id uuid not null references bio_sample_batches(id) on delete cascade,
    sequence_no integer,
    specimen_no text,
    species_catalog_id uuid references species_catalog(id),
    species_raw_name text,
    species_standard_name text,
    fork_length_mm numeric(10, 2),
    total_length_mm numeric(10, 2),
    weight_g numeric(12, 3),
    sex text,
    maturity text,
    gsi numeric(10, 4),
    remarks text,
    measurement_properties jsonb not null default '{}'::jsonb
);

create table if not exists field_definitions (
    id uuid primary key default gen_random_uuid(),
    form_template_id uuid references form_templates(id),
    field_key text not null,
    field_scope text not null check (field_scope in ('operation', 'location', 'gear', 'catch', 'bio_batch', 'bio_measurement')),
    label_zh text not null,
    data_type text not null,
    unit_name text,
    is_required boolean not null default false,
    target_table text not null,
    target_column text,
    json_path text,
    notes text
);

create index if not exists idx_import_batches_status on import_batches(import_status);
create index if not exists idx_source_documents_batch_id on source_documents(batch_id);
create index if not exists idx_ai_extraction_runs_batch_id on ai_extraction_runs(batch_id);
create index if not exists idx_fishery_operations_batch_id on fishery_operations(batch_id);
create index if not exists idx_operation_locations_operation_id on operation_locations(operation_id);
create index if not exists idx_catch_records_operation_id on catch_records(operation_id);
create index if not exists idx_bio_sample_batches_batch_id on bio_sample_batches(batch_id);
create index if not exists idx_biological_measurements_batch_id on biological_measurements(sample_batch_id);
create index if not exists idx_catch_records_species_raw_name on catch_records(species_raw_name);
create index if not exists idx_biological_measurements_species_raw_name on biological_measurements(species_raw_name);

insert into database_categories (category_code, category_name_zh, description)
values
    ('COASTAL_FISHERY', '沿近海漁業資料庫', '漁撈作業與漁獲資料'),
    ('BIOLOGY_SAMPLE', '生物學資料庫', '個體量測與樣本背景資料')
on conflict (category_code) do nothing;

insert into form_templates (template_code, template_name_zh, data_domain, gear_family, source_file_name, notes)
values
    ('TN_COASTAL_GILLNET_001', '台南將軍沿海場域標本船作業調查表109.03.31', 'fishery', 'gillnet', '台南將軍沿海場域標本船作業調查表109.03.31.docx', '沿海網具作業調查母版'),
    ('SW_HOOK_001', '釣具類作業報表(擷取1頁)_114.09.16', 'fishery', 'hook_and_line', '釣具類作業報表(擷取1頁)_114.09.16.docx', '西南海域釣具類作業母版'),
    ('TW_LONGLINE_001', '延繩釣漁撈作業報表-高雄熊麻吉 -', 'fishery', 'longline', '延繩釣漁撈作業報表-高雄熊麻吉 -.docx', '延繩釣與一支釣混合母版'),
    ('BIO_MESH_001', '網目比較實驗室紀錄表', 'biology', 'lab_measurement', '網目比較實驗室紀錄表.docx', '生物學量測母版')
on conflict (template_code) do nothing;
