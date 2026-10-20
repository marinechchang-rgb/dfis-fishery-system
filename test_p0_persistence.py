import unittest
import sys
from unittest.mock import patch, MagicMock

import database


class PersistenceSafetyTests(unittest.TestCase):
    def test_failed_postgres_never_opens_sqlite_or_changes_backend(self):
        driver = MagicMock()
        driver.connect.side_effect = RuntimeError('sensitive diagnostic')
        with patch.object(database, 'IS_POSTGRES', True), \
             patch.object(database, 'DB_URL', None), \
             patch.dict(sys.modules, {'psycopg2': driver, 'psycopg2.extras': driver.extras}), \
             patch('sqlite3.connect') as local:
            for _ in range(2):
                with self.assertRaises(database.DatabaseUnavailableError) as result:
                    database.get_db_connection()
                self.assertNotIn('sensitive diagnostic', str(result.exception))
                self.assertTrue(database.IS_POSTGRES)
            local.assert_not_called()

    def test_required_postgres_without_configuration_stops(self):
        with patch.object(database, 'IS_POSTGRES', False), \
             patch.object(database, 'REQUIRE_POSTGRES', True), \
             patch('sqlite3.connect') as local:
            with self.assertRaises(database.DatabaseUnavailableError):
                database.get_db_connection()
            local.assert_not_called()

    def test_postgres_requires_tls(self):
        driver = MagicMock()
        with patch.object(database, 'IS_POSTGRES', True), \
             patch.object(database, 'DB_URL', None), \
             patch.dict(sys.modules, {'psycopg2': driver, 'psycopg2.extras': driver.extras}):
            self.assertIs(database.get_db_connection(), driver.connect.return_value)
            self.assertEqual(driver.connect.call_args.kwargs['sslmode'], 'require')

    def test_incompatible_schema_stops_before_ddl(self):
        connection = MagicMock()
        cursor = MagicMock()
        with patch.object(database, 'IS_POSTGRES', True), \
             patch.object(database, 'get_db_connection', return_value=connection), \
             patch.object(database, 'get_cursor', return_value=cursor), \
             patch.object(database, 'inspect_contract', return_value={'compatible': False}):
            with self.assertRaises(database.DatabaseUnavailableError):
                database.init_db()
            cursor.execute.assert_not_called()
            connection.close.assert_called_once()

    def test_compatible_postgres_startup_never_initializes_or_seeds(self):
        connection = MagicMock()
        with patch.object(database, 'IS_POSTGRES', True), \
             patch.object(database, 'get_db_connection', return_value=connection), \
             patch.object(database, 'inspect_contract', return_value={'compatible': True}), \
             patch.object(database, '_legacy_init_db') as legacy:
            database.init_db()
            legacy.assert_not_called()
            connection.close.assert_called_once()

    def test_preflight_failure_closes_connection_and_hides_diagnostics(self):
        connection = MagicMock()
        with patch.object(database, 'IS_POSTGRES', True), \
             patch.object(database, 'get_db_connection', return_value=connection), \
             patch.object(database, 'inspect_contract', side_effect=RuntimeError('sensitive diagnostic')):
            with self.assertRaises(database.DatabaseUnavailableError) as result:
                database.init_db()
            self.assertNotIn('sensitive diagnostic', str(result.exception))
            connection.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
