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
    if case=='navigation' or case.startswith('library_'):
        import workflow_ui
        batch_view={key:value for key,value in batch.items() if key!='pages'}
        second=dict(template,id='synthetic-template-second',code='SECOND',name='合成樣板乙',version=2)
        library=[] if case=='library_empty' else [template,second]
        real_upload=st.file_uploader
        real_read_word=workflow_ui.read_word
        if case=='library_publish':
            if 'fixture_library' not in st.session_state: st.session_state['fixture_library']=[]
            library=st.session_state['fixture_library']
        def mock_upload(label,*args,**kwargs):
            if case=='library_publish' and label.startswith('新增 Word'):
                from types import SimpleNamespace
                return SimpleNamespace(name='synthetic.docx',getvalue=lambda:b'synthetic Word fixture')
            return real_upload(label,*args,**kwargs)
        def mock_read_word(*args):
            if case=='library_publish': return {'paragraphs':['魚種','尾數'],'tables':[]}
            return real_read_word(*args)
        def publish_fixture(*args):
            if case!='library_publish': forbidden()
            st.session_state['fixture_publish_calls']=st.session_state.get('fixture_publish_calls',0)+1
            library.append(template)
            return template['id']
        def saved_snapshot(tid,upload_id=None):
            selected=next(t for t in library if t['id']==tid)
            st.session_state['fixture_candidate_template']=tid
            return build_snapshot(selected,[dict(batch,template_id=tid)])
        with (patch.object(store,'check_schema',return_value=None),
              patch.object(store,'templates',side_effect=lambda:list(library)),
              patch.object(store,'publish',side_effect=publish_fixture),
              patch('streamlit.file_uploader',side_effect=mock_upload),
              patch.object(workflow_ui,'read_word',side_effect=mock_read_word),
              patch.object(store,'uploads',return_value=[batch_view]),
              patch.object(store,'candidate_snapshot',side_effect=saved_snapshot),
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
        self.assertEqual(app.radio(key='wf_export_mode').value,'AI 未審核候選')
        self.assertIn('下載 AI 未審核候選 CSV',self.downloads(app))
        app.radio(key='wf_export_mode').set_value('已確認資料'); app.run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(set(self.downloads(app)),{'下載累積 CSV'})

    def test_saved_templates_default_to_selection_without_word_upload(self):
        app=self.app('library_saved')
        self.assertEqual(app.radio(key='wf_template_mode').value,'使用已儲存樣板')
        self.assertEqual(app.selectbox(key='wf_selected').value,'synthetic-template')
        self.assertFalse(any('Word' in node.proto.label for node in app.get('file_uploader')))
        app.run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(app.selectbox(key='wf_selected').value,'synthetic-template')

    def test_switch_saved_template_routes_pdf_and_export_to_same_version(self):
        app=self.app('library_saved')
        app.selectbox(key='wf_selected').set_value('synthetic-template-second'); app.run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(app.selectbox(key='wf_export_template').value,'synthetic-template-second')
        self.assertEqual(app.session_state['fixture_candidate_template'],'synthetic-template-second')
        self.assertTrue(any('合成樣板乙' in node.value and '步驟①' in node.value for node in app.info))
        self.assertTrue(any(node.key=='wf_pdfs_synthetic-template-second' for node in app.get('file_uploader')))

    def test_add_template_mode_exposes_word_upload_only_when_requested(self):
        app=self.app('library_saved')
        app.radio(key='wf_template_mode').set_value('新增 Word 母版／版本'); app.run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertTrue(any(node.key=='wf_word' for node in app.get('file_uploader')))
        app.radio(key='wf_template_mode').set_value('使用已儲存樣板'); app.run()
        self.assertFalse(any(node.key=='wf_word' for node in app.get('file_uploader')))

    def test_first_visit_without_templates_exposes_first_word_upload(self):
        app=self.app('library_empty')
        self.assertTrue(any(node.key=='wf_word' for node in app.get('file_uploader')))
        self.assertEqual(len(app.selectbox),0)
        self.assertTrue(any('尚無樣板' in node.value for node in app.info))

    def test_published_template_pending_id_activates_saved_template(self):
        app=AppTest.from_string(SCRIPT,default_timeout=30)
        app.session_state['case']='library_saved'
        app.session_state['wf_template_pending_id']='synthetic-template-second'
        app.session_state['wf_template_mode']='新增 Word 母版／版本'
        app.run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(app.selectbox(key='wf_selected').value,'synthetic-template-second')
        self.assertEqual(app.selectbox(key='wf_export_template').value,'synthetic-template-second')
        self.assertEqual(app.radio(key='wf_template_mode').value,'使用已儲存樣板')
        self.assertFalse(any(node.key=='wf_word' for node in app.get('file_uploader')))

    def test_new_session_reloads_library_without_reuploading_word(self):
        app=self.app('library_saved')
        fresh=self.app('library_saved')
        self.assertEqual(app.selectbox(key='wf_selected').options,fresh.selectbox(key='wf_selected').options)
        self.assertFalse(any(node.key=='wf_word' for node in fresh.get('file_uploader')))

    def test_save_template_button_publishes_once_then_selects_saved_template(self):
        app=self.app('library_publish')
        save=next(b for b in app.button if b.label=='儲存為樣板（發布版本）')
        self.assertTrue(save.disabled)
        app.checkbox[0].check(); app.run()
        next(b for b in app.button if b.label=='儲存為樣板（發布版本）').click(); app.run()
        self.assertEqual(len(app.exception),0,str(app.exception))
        self.assertEqual(app.session_state['fixture_publish_calls'],1)
        self.assertEqual(app.selectbox(key='wf_selected').value,'synthetic-template')
        self.assertEqual(app.radio(key='wf_template_mode').value,'使用已儲存樣板')
        app.run()
        self.assertEqual(app.session_state['fixture_publish_calls'],1)


if __name__=='__main__':
    print('Streamlit AppTest runtime: '+streamlit.__version__,flush=True)
    unittest.main(verbosity=2)
