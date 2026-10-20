"""Read-only schema metadata report. Does not initialize or migrate the database."""
import json
import database
from persistence_contract import inspect_contract


def main():
    if not database.IS_POSTGRES:
        print(json.dumps({'status': 'failed', 'reason': 'PostgreSQL required'}))
        return 1
    try:
        conn = database.get_db_connection()
        try:
            report = inspect_contract(conn)
        finally:
            conn.close()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['compatible'] else 2
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
