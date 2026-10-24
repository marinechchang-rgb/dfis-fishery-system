"""Mock-only Streamlit comparison tests; no network, real credentials, or DB writes."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest
from model_comparison_ui import registry

SCRIPT = '''
import streamlit as st
from unittest.mock import patch
from types import SimpleNamespace
import model_comparison_ui as ui
from model_comparison import TEMPLATE_ID
template={'id':TEMPLATE_ID,'code':'FORM_ca51e7dd','version':1,'fields_json':'[]','snapshot_json':'{}'}
fixture=SimpleNamespace(getvalue=lambda:b'fixture') if st.session_state.get('has_pdf') else None
def once(*a): return {'status':'http_error','http_status':503}
with patch.object(st,'file_uploader',return_value=fixture), patch.object(ui,'prepare',return_value=(b'image','prompt')), patch('model_comparison.request_once',side_effect=AssertionError('unexpected network')):
    state=ui.registry()
    real_run=state.run
    with patch.object(state,'run',side_effect=lambda *a,**k:real_run(*a,send=once,**k)):
        ui.render(template)
'''


class UITests(unittest.TestCase):
    def setUp(self): registry.clear()

    def app(self, pdf=False):
        app = AppTest.from_string(SCRIPT)
        app.secrets = {'GEMINI_API_KEY':'fake-gemini', 'OPENAI_API_KEY':'fake-openai'}
        app.session_state['has_pdf'] = pdf
        app.run()
        self.assertFalse(app.exception)
        return app

    def test_no_pdf_blocks(self):
        app=self.app()
        self.assertTrue(all(b.disabled for b in app.button))

    def test_consent_blocks(self):
        app=self.app(True)
        self.assertTrue(all(b.disabled for b in app.button))

    def test_single_attempt_failure_locks(self):
        app=self.app(True)
        app.checkbox(key='cmp_consent').check().run()
        self.assertFalse(app.button(key='cmp_run_Gemini').disabled)
        app.button(key='cmp_run_Gemini').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.button(key='cmp_run_Gemini').disabled)
        self.assertFalse(app.button(key='cmp_run_OpenAI').disabled)
        app.run()
        self.assertTrue(app.button(key='cmp_run_Gemini').disabled)


if __name__=='__main__': unittest.main()
