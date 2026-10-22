"""Real Streamlit AppTest with synthetic store fixtures; no network/DB/API."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import streamlit
from streamlit.testing.v1 import AppTest


SCRIPT='''
import json
import streamlit as st
from unittest.mock import patch
import workflow_store as store
from workflow_ui import render_candidate_exports,render_confirmed_exports
from workflow_candidates import build_snapshot

fields=[{'key':'species','label':'魚種','scope':'detail','type':'text'},
        {'key':'count','label':'尾數','scope':'detail','type':'integer'},
        {'key':'weight','label':'重量','scope':'detail','type':'decimal'}]
template={'id':'synthetic-template','code':'SYNTHETIC','version':1,'fields_json':json.dumps(fields),
          'name':'合成測試母版','source_name':'synthetic.docx'}
case=st.session_state.get('case','complete')
page={'upload_id':'synthetic-upload','page_no':1,'status':'success','provider':'Gemini','model':'synthetic-model',
      'result_json':json.dumps({'rows':[{'species':'合成魚','count':0,'weight':None}],'warnings':''})}
if case=='invalid': page['result_json']='{'
batch={'id':'synthetic-upload','template_id':template['id'],'filename':'synthetic.pdf','pdf_sha':'synthetic-sha',
       'page_count':2 if case=='partial' else 1,'status':'review','pages':[page]}
def forbidden(*args,**kw): raise AssertionError('must not confirm or call AI')
with patch.object(store,'confirm',side_effect=forbidden), patch('workflow_ui.extract_page',side_effect=forbidden):
    if case=='navigation':
        import workflow_ui
        batch_view={key:value for key,value in batch.items() if key!='pages'}
        with (patch.object(store,'check_schema',return_value=None),
              patch.object(store,'templates',return_value=[template]),
              patch.object(store,'uploads',return_value=[batch_view]),
              patch.object(store,'candidate_snapshot',return_value=build_snapshot(template,[batch])),
              patch.object(store,'export_rows',return_value=[{'species':'合成已確認魚','count':0}]),
              patch('workflow_ui.secret',return_value='')):
            workflow_ui.render()
    elif case=='confirmed':
        with patch.object(store,'export_rows',return_value=[{'species':'合成已確認魚','count':0}]):
            render_confirmed_exports(template,[])
    else:
        with patch.object(store,'candidate_snapshot',return_value=build_snapshot(template,[batch])):
            render_candidate_exports(template,[batch])
'''


class RealStreamlitCandidates(unittest.TestCase):
    def app(self,case):
        app=AppTest.from_string(SCRIPT,default_timeout=30)
        app.session_state['case']=case
        app.run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        return app

    def downloads(self,app):
        return {node.proto.label:node.proto for node in app.get('download_button')}

    def test_complete_ai_csv_without_human_checkbox(self):
        app=self.app('complete')
        self.assertEqual(len(app.checkbox),0)
        self.assertFalse(self.downloads(app)['下載 AI 未審核候選 CSV'].disabled)
        self.assertEqual(app.metric[0].value,'1')
        self.assertEqual(len(app.get('file_uploader')),0)

    def test_partial_download_ack_and_rerun(self):
        app=self.app('partial')
        self.assertTrue(self.downloads(app)['下載 AI 未審核候選 CSV'].disabled)
        app.checkbox[0].check(); app.run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertFalse(self.downloads(app)['下載 AI 未審核候選 CSV'].disabled)

    def test_bad_saved_json_only_summary_download(self):
        app=self.app('invalid')
        self.assertEqual(set(self.downloads(app)),{'下載候選頁面摘要 JSON'})
        self.assertGreater(len(app.error),0)

    def test_confirmed_download_still_separate(self):
        app=self.app('confirmed')
        self.assertEqual(set(self.downloads(app)),{'下載累積 CSV'})
        self.assertEqual(len(app.checkbox),0)

    def test_full_workflow_navigation_switches_without_pdf_reupload(self):
        app=self.app('navigation')
        self.assertEqual(app.title[0].value,'多元漁業資訊標準及智慧化軟體系統v1')
        self.assertEqual(app.caption[0].value,'手寫紙本PDF檔案智慧轉譯小幫手')
        self.assertEqual(app.radio[0].value,'AI 未審核候選')
        self.assertIn('下載 AI 未審核候選 CSV',self.downloads(app))
        app.radio[0].set_value('已確認資料'); app.run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(set(self.downloads(app)),{'下載累積 CSV'})


if __name__=='__main__':
    print('Streamlit AppTest runtime: '+streamlit.__version__,flush=True)
    unittest.main(verbosity=2)
