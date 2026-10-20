"""Read-only PostgreSQL preflight for the current application CRUD contract."""

REQUIRED_COLUMNS = {
    'database_categories': 'name created_at',
    'fishery_logs': 'id database_type vessel_name log_date gear_type gear_properties created_at',
    'catch_records': 'id log_id species_raw_name species_standard_name weight_kg count_individual catch_properties operation_id sequence_no size_bucket remarks',
    'ports': 'id name county',
    'vessels': 'id name registration_number',
    'species': 'id chinese_name code genus species',
    'biological_parameters': 'id collection_date collection_id port vessel_name form_code species_name sex maturity total_length_mm weight_g gsi remarks created_at sample_batch_id sequence_no specimen_no species_standard_name fork_length_mm net_group net_set_no site_name total_weight_kg discard_weight_kg background_properties',
    'form_templates': 'template_code template_name_zh data_domain gear_family source_file_name is_active notes created_at',
    'import_batches': 'id database_category_code form_template_code source_channel import_status notes created_at updated_at',
    'fishery_operations': 'id legacy_log_id batch_id database_category_code form_template_code vessel_name vessel_registration_no owner_name observer_name operation_date departure_time return_time start_time end_time gear_type remarks gear_properties review_status created_at updated_at',
    'operation_locations': 'id operation_id location_role sequence_no location_name latitude longitude depth_m extra_properties created_at',
    'bio_sample_batches': 'id source_record_key form_template_code vessel_name operation_date site_name port_name net_group net_set_no total_weight_kg discard_weight_kg background_properties review_status created_at updated_at',
    'biological_measurements': 'id sample_batch_id legacy_biological_id sequence_no specimen_no species_raw_name species_standard_name fork_length_mm total_length_mm weight_g sex maturity gsi remarks measurement_properties created_at',
}

INTEGER_ID_TABLES = {'fishery_logs', 'catch_records', 'ports', 'vessels', 'species', 'biological_parameters'}


def inspect_contract(connection):
    """No DDL, records, credentials, or connection strings in the returned report."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_schema()')
        schema = cursor.fetchone()[0]
        cursor.execute("""
            SELECT table_name, column_name, udt_name, is_nullable,
                   column_default IS NOT NULL, is_identity
            FROM information_schema.columns WHERE table_schema = %s
            ORDER BY table_name, ordinal_position
        """, (schema,))
        columns = {}
        for table, name, dtype, nullable, defaulted, identity in cursor.fetchall():
            columns.setdefault(table, {})[name] = {
                'type': dtype, 'nullable': nullable == 'YES',
                'generated': bool(defaulted) or identity == 'YES',
            }
        cursor.execute("""
            SELECT t.relname, c.contype, pg_get_constraintdef(c.oid)
            FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = %s ORDER BY t.relname, c.conname
        """, (schema,))
        constraints = [list(row) for row in cursor.fetchall()]
    issues = []
    for table, names in REQUIRED_COLUMNS.items():
        actual = columns.get(table, {})
        expected = set(names.split())
        missing = sorted(expected - actual.keys())
        if missing:
            issues.append(f'{table}: missing {", ".join(missing)}')
        for name, meta in actual.items():
            if name not in expected and not meta['nullable'] and not meta['generated']:
                issues.append(f'{table}.{name}: extra required column')
            if name in expected and meta['type'] in {'uuid', 'json', 'jsonb'}:
                issues.append(f'{table}.{name}: requires adapter for {meta["type"]}')
        if table in INTEGER_ID_TABLES and 'id' in actual:
            if actual['id']['type'] not in {'int2', 'int4', 'int8'} or not actual['id']['generated']:
                issues.append(f'{table}.id: generated integer required')
    for table, key in [('database_categories', 'name'), ('form_templates', 'template_code'),
                       ('bio_sample_batches', 'source_record_key')]:
        if not any(t == table and kind in {'p', 'u'} and definition in {
            f'PRIMARY KEY ({key})', f'UNIQUE ({key})'
        } for t, kind, definition in constraints):
            issues.append(f'{table}.{key}: unique constraint required')
    return {'schema': schema, 'compatible': not issues, 'issues': issues,
            'tables': columns, 'constraints': constraints, 'integration_verified': False}
