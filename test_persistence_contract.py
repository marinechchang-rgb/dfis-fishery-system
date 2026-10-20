import unittest
from unittest.mock import MagicMock
from persistence_contract import inspect_contract


class PreflightTests(unittest.TestCase):
    def inspect(self, rows, constraints=()):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ('public',)
        cursor.fetchall.side_effect = [rows, constraints]
        report = inspect_contract(conn)
        self.assertTrue(all(call.args[0].strip().startswith('SELECT')
                            for call in cursor.execute.call_args_list))
        return report

    def test_empty_project_rejected_without_migration(self):
        report = self.inspect([])
        self.assertFalse(report['compatible'])
        self.assertTrue(any('fishery_logs' in issue for issue in report['issues']))

    def test_target_uuid_schema_requires_explicit_adapter(self):
        report = self.inspect([
            ('catch_records', 'id', 'uuid', 'NO', True, 'NO'),
            ('catch_records', 'operation_id', 'uuid', 'NO', False, 'NO'),
            ('fishery_operations', 'form_template_id', 'uuid', 'NO', False, 'NO'),
        ])
        self.assertFalse(report['compatible'])
        self.assertIn('catch_records.id: requires adapter for uuid', report['issues'])
        self.assertIn('fishery_operations.form_template_id: extra required column', report['issues'])


if __name__ == '__main__':
    unittest.main()
