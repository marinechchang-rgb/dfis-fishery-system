"""Explicit staging insert/verify probe. Never initializes or migrates schema.

Run insert, restart the deployed application, then run verify with the printed ID.
This CLI proves database persistence only; Cloud restart evidence is separate.
"""
import argparse
import hashlib
import io
import json
import uuid

import pandas as pd
import database


def run(phase, marker, log_id=None):
    if not database.IS_POSTGRES:
        raise database.DatabaseUnavailableError('Smoke test requires PostgreSQL.')
    if not marker.startswith('P0-STAGING-'):
        raise ValueError('Marker must start with P0-STAGING-.')
    connection = database.get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database(), current_schema(), pg_backend_pid()')
            db_name, schema_name, backend_pid = cursor.fetchone()
    finally:
        connection.close()
    if phase == 'insert':
        log_id = database.save_fishery_log({
            'database_type': '休閒船釣漁業資料庫',
            'vessel_name': marker,
            'log_date': '2026-09-17',
            'gear_type': '一支釣',
            'gear_properties': {'p0_staging_marker': marker},
            'catch_records': [{
                'species_raw_name': 'P0測試魚',
                'species_standard_name': 'P0測試魚',
                'weight_kg': 1.25, 'count_individual': 3,
                'catch_properties': {},
            }],
        })
    if log_id is None:
        raise ValueError('verify requires --log-id')
    # Clear Streamlit data cache so the query must reach the database.
    database.clear_db_cache()
    detail = database.get_fishery_log_detail(log_id)
    if detail['vessel_name'] != marker:
        raise AssertionError('Marker mismatch')
    records = detail['catch_records']
    if len(records) != 1 or float(records[0]['weight_kg']) != 1.25 or int(records[0]['count_individual']) != 3:
        raise AssertionError('Catch payload mismatch')
    csv_bytes = pd.DataFrame(records).to_csv(index=False).encode('utf-8-sig')
    decoded = pd.read_csv(io.BytesIO(csv_bytes))
    if decoded.iloc[0]['species_raw_name'] != 'P0測試魚':
        raise AssertionError('CSV round-trip mismatch')
    return {'phase': phase, 'marker': marker, 'log_id': log_id,
            'backend': 'postgresql', 'database': db_name, 'schema': schema_name,
            'probe_backend_pid': backend_pid, 'sqlite_fallback': False,
            'csv_sha256': hashlib.sha256(csv_bytes).hexdigest(),
            'cloud_restart_verified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['insert', 'verify'])
    parser.add_argument('--marker', default='P0-STAGING-' + uuid.uuid4().hex)
    parser.add_argument('--log-id', type=int)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.phase, args.marker, args.log_id), ensure_ascii=True))
    except Exception as exc:
        # Driver diagnostics may contain connection information; do not print them.
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__,
                          'cloud_restart_verified': False}))
        raise SystemExit(1)
