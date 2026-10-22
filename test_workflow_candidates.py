import copy
import csv
from decimal import Decimal
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import database
import workflow_store as store
from workflow_ai import extract_page
from workflow_candidates import build_snapshot,candidate_csv,summary_json
from word_workflow import csv_bytes as confirmed_csv

FIELDS=[{'key':'species','label':'魚種','scope':'detail','type':'text'},
        {'key':'count','label':'尾數','scope':'detail','type':'integer'},
        {'key':'weight','label':'重量','scope':'detail','type':'decimal'}]
TEMPLATE={'id':'template-A','code':'TEST','version':1,'fields_json':json.dumps(FIELDS)}


def saved_page(number=1,payload=None,provider='Gemini',status='success'):
    return {'upload_id':'upload-A','page_no':number,'status':status,'provider':provider,'model':'saved-model',
            'result_json':json.dumps(payload if payload is not None else {'rows':[{'species':'合成魚','count':0,'weight':None}],'warnings':'需確認'},ensure_ascii=False)}


def upload(pages=None,count=1,status='review'):
    return {'id':'upload-A','template_id':TEMPLATE['id'],'filename':'synthetic.pdf','pdf_sha':'synthetic-sha',
            'page_count':count,'status':status,'pages':pages if pages is not None else [saved_page()]}


class CandidateContracts(unittest.TestCase):
    def test_unreviewed_zero_null_provenance_and_no_input_mutation(self):
        source=[upload()]; before=copy.deepcopy(source)
        snapshot=build_snapshot(TEMPLATE,source); row=snapshot['rows'][0]
        self.assertEqual(row['count'],0); self.assertIsNone(row['weight'])
        self.assertFalse(row['source_reviewed_by_human'])
        self.assertEqual(row['source_review_status'],'ai_unreviewed')
        self.assertIsNone(row['source_physical_row']); self.assertIsNone(row['source_section'])
        self.assertEqual(row['source_candidate_row'],1)
        self.assertEqual(row['source_provider'],'Gemini'); self.assertEqual(row['source_model'],'saved-model')
        self.assertEqual(source,before)

    def test_partial_missing_failed_and_csv_warning(self):
        snapshot=build_snapshot(TEMPLATE,[upload([saved_page(),saved_page(2,status='failed')],count=3)])
        self.assertTrue(snapshot['partial']); self.assertFalse(snapshot['blocked'])
        self.assertEqual([p['status'] for p in snapshot['page_summary']],['ai_unreviewed','failed','missing'])
        self.assertIn('所選範圍不完整',snapshot['rows'][0]['source_warnings'])
        self.assertIn('missing_pages',summary_json(snapshot).decode('utf8'))

    def test_confirmed_excluded_and_cross_template_rejected(self):
        snapshot=build_snapshot(TEMPLATE,[upload(status='confirmed')])
        self.assertEqual(snapshot['rows'],[]); self.assertEqual(snapshot['summary']['excluded_confirmed_batches'],1)
        bad=upload(); bad['template_id']='other'
        with self.assertRaises(ValueError): build_snapshot(TEMPLATE,[bad])

    def test_manual_not_labeled_ai(self):
        snapshot=build_snapshot(TEMPLATE,[upload([saved_page(provider='人工建檔')])])
        self.assertEqual(snapshot['rows'],[]); self.assertEqual(snapshot['summary']['manual_pages'],1)

    def test_unknown_provider_blocks_not_gemini_fallback(self):
        snapshot=build_snapshot(TEMPLATE,[upload([saved_page(provider='LocalCPU')])])
        self.assertTrue(snapshot['blocked'])
        with self.assertRaises(ValueError): candidate_csv(snapshot)
        with self.assertRaises(ValueError): extract_page(b'synthetic',{},1,'LocalCPU','model','unused')

    def test_bad_json_duplicate_keys_and_nonfinite_block_csv(self):
        for raw in ('{','null','{"rows":[],"rows":[]}',
                    '{"rows":[{"weight":NaN}]}','{"rows":[{"weight":1e999}]}'):
            p=saved_page(); p['result_json']=raw
            snapshot=build_snapshot(TEMPLATE,[upload([p])])
            self.assertTrue(snapshot['blocked'],raw)
            with self.assertRaises(ValueError): candidate_csv(snapshot)

    def test_page_row_validation_atomic_no_partial_valid_row_leak(self):
        for bad in ({'unknown':1},{'count':True},{'count':1.5},{'weight':'1,2'},{'species':[]},
                    {'source_review_status':'confirmed'}):
            snapshot=build_snapshot(TEMPLATE,[upload([saved_page(payload={'rows':[{'species':'有效合成列'},bad]})])])
            self.assertTrue(snapshot['blocked']); self.assertEqual(snapshot['rows'],[])

    def test_null_placeholder_not_observation_and_index_not_renumbered(self):
        snapshot=build_snapshot(TEMPLATE,[upload([saved_page(payload={'rows':[{}, {'species':'合成魚'}]})])])
        self.assertEqual(snapshot['summary']['excluded_null_rows'],1)
        self.assertEqual(snapshot['rows'][0]['source_candidate_row'],2)
        self.assertIn('排除全 null',snapshot['rows'][0]['source_warnings'])

    def test_empty_candidates_not_confirmed_blank(self):
        snapshot=build_snapshot(TEMPLATE,[upload([saved_page(payload={'rows':[]})])])
        self.assertFalse(snapshot['blocked']); self.assertEqual(snapshot['summary']['no_candidate_pages'],1)
        self.assertFalse(snapshot['quality_accepted']); self.assertIn('不代表已確認空白',''.join(snapshot['notices']))

    def test_duplicate_out_of_range_or_foreign_page_blocked(self):
        foreign=saved_page(); foreign['upload_id']='other'
        for pages in ([saved_page(),saved_page()],[saved_page(2)],[foreign]):
            self.assertTrue(build_snapshot(TEMPLATE,[upload(pages)])['blocked'])

    def test_reserved_columns_and_invalid_fields_rejected(self):
        for definitions in ({'bad':1},[1],FIELDS+[{'key':'source_review_status','label':'狀態','scope':'detail','type':'text'}]):
            template=dict(TEMPLATE,fields_json=json.dumps(definitions))
            with self.assertRaises(ValueError): build_snapshot(template,[])

    def test_csv_bom_precision_formula_and_false_approval_ignored(self):
        page=saved_page(payload={'rows':[{'species':'=危險公式','count':0,'weight':'0.12345678901234567890'}],
                                 'reviewed_by_human':True,'status':'confirmed'})
        snapshot=build_snapshot(TEMPLATE,[upload([page])])
        self.assertEqual(snapshot['rows'][0]['weight'],Decimal('0.12345678901234567890'))
        data=candidate_csv(snapshot); self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
        row=next(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
        self.assertEqual(row['species'],"'=危險公式")
        self.assertEqual(row['weight'],'0.12345678901234567890')
        self.assertEqual(row['source_reviewed_by_human'],'False')
        snapshot['rows'][0]['source_reviewed_by_human']=True
        with self.assertRaises(ValueError): candidate_csv(snapshot)


class CandidateStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='candidate-test-',dir=Path.cwd())
        self.path=Path(self.temp.name)/'test.sqlite'
        def connect():
            conn=sqlite3.connect(self.path); conn.row_factory=sqlite3.Row
            conn.execute('PRAGMA foreign_keys=ON'); return conn
        self.connect=connect
        conn=connect(); conn.executescript(Path('migrations/002_word_workflow.sql').read_text(encoding='utf8')); conn.close()
        self.patches=[patch.object(database,'get_db_connection',connect),patch.object(database,'IS_POSTGRES',False)]
        for p in self.patches: p.start()
        self.tid=store.publish('CANDIDATE_TEST','合成測試','synthetic.docx',b'synthetic',{},FIELDS)

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()

    def test_two_batches_reopen_readonly_snapshot_no_confirmation(self):
        for n in (1,2):
            uid=store.register(self.tid,str(n)+'.pdf',str(n).encode(),2)
            store.save_page(uid,1,{'rows':[{'species':'合成魚','count':0}],'warnings':''},'Gemini','saved-model')
        conn=self.connect(); before='\n'.join(conn.iterdump()); conn.close()
        queries=[]
        def read_only():
            conn=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True); conn.row_factory=sqlite3.Row
            conn.set_trace_callback(queries.append); return conn
        with patch.object(database,'get_db_connection',read_only):
            snapshot=store.candidate_snapshot(self.tid)
        self.assertEqual(snapshot['summary']['candidate_rows'],2)
        self.assertEqual(snapshot['summary']['missing_pages'],2)
        self.assertTrue(all(q.lstrip().upper().startswith('SELECT') for q in queries))
        conn=self.connect(); after='\n'.join(conn.iterdump()); conn.close(); self.assertEqual(before,after)
        self.assertEqual(store.export_rows(self.tid),[])

    def test_confirmed_mode_unchanged_and_candidate_excludes(self):
        uid=store.register(self.tid,'synthetic.pdf',b'synthetic',1)
        store.save_page(uid,1,{'rows':[{'species':'合成魚','count':0}],'warnings':''},'OpenAI','saved-model')
        self.assertEqual(len(store.candidate_snapshot(self.tid)['rows']),1)
        store.confirm(uid,[{'source_page':1,'species':'合成魚','count':0}],FIELDS)
        self.assertEqual(store.candidate_snapshot(self.tid)['rows'],[])
        with self.assertRaises(ValueError): store.candidate_snapshot(self.tid,uid)
        self.assertEqual(len(store.export_rows(self.tid)),1)

    def test_scope_and_missing_template_and_empty_batch(self):
        uid=store.register(self.tid,'empty.pdf',b'empty',1)
        snapshot=store.candidate_snapshot(self.tid,uid)
        self.assertEqual(snapshot['summary']['missing_pages'],1)
        with self.assertRaises(ValueError): store.candidate_snapshot('missing')
        other=store.publish('OTHER','另一合成','b.docx',b'other',{},FIELDS)
        with self.assertRaises(ValueError): store.candidate_snapshot(other,uid)
        with self.assertRaises(ValueError): store.candidate_snapshot(self.tid,"' OR 1=1 --")


class FakeStreamlit:
    def __init__(self,ack=False): self.calls=[]; self.ack=ack
    def __getattr__(self,name):
        def call(*args,**kw):
            self.calls.append((name,args,kw))
            if name=='selectbox': return args[1][0]
            if name=='checkbox': return self.ack
            return None
        return call


class CandidateUITests(unittest.TestCase):
    def load_ui(self,fake):
        spec=importlib.util.spec_from_file_location('candidate_ui_test',Path('workflow_ui.py'))
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'streamlit':fake}): spec.loader.exec_module(module)
        return module

    def test_download_without_confirmation_or_upload_or_api(self):
        fake=FakeStreamlit(); ui=self.load_ui(fake)
        snapshot=build_snapshot(TEMPLATE,[upload()])
        with (patch.object(ui.store,'candidate_snapshot',return_value=snapshot) as query,
             patch.object(ui.store,'confirm',side_effect=AssertionError('must not confirm')),
             patch.object(ui,'extract_page',side_effect=AssertionError('must not call API'))):
            ui.render_candidate_exports(TEMPLATE,[upload()])
        query.assert_called_once_with(TEMPLATE['id'],None)
        downloads=[c for c in fake.calls if c[0]=='download_button' and c[1][0]=='下載 AI 未審核候選 CSV']
        self.assertEqual(len(downloads),1); self.assertFalse(downloads[0][2]['disabled'])
        self.assertFalse(any(c[0]=='file_uploader' for c in fake.calls))

    def test_partial_ack_is_not_human_review(self):
        for ack in (False,True):
            fake=FakeStreamlit(ack); ui=self.load_ui(fake)
            snapshot=build_snapshot(TEMPLATE,[upload(count=2)])
            with patch.object(ui.store,'candidate_snapshot',return_value=snapshot):
                ui.render_candidate_exports(TEMPLATE,[upload(count=2)])
            download=next(c for c in fake.calls if c[0]=='download_button' and c[1][0]=='下載 AI 未審核候選 CSV')
            self.assertEqual(download[2]['disabled'],not ack)
            self.assertIn('_PARTIAL.csv',download[2]['file_name'])
            self.assertIn(b'ai_unreviewed',download[1][1])

    def test_invalid_blocks_csv_but_summary_available(self):
        fake=FakeStreamlit(); ui=self.load_ui(fake)
        bad=saved_page(); bad['result_json']='{'
        with patch.object(ui.store,'candidate_snapshot',return_value=build_snapshot(TEMPLATE,[upload([bad])])):
            ui.render_candidate_exports(TEMPLATE,[upload([bad])])
        labels=[c[1][0] for c in fake.calls if c[0]=='download_button']
        self.assertEqual(labels,['下載候選頁面摘要 JSON'])

    def test_old_confirmed_csv_same_bytes(self):
        fake=FakeStreamlit(); ui=self.load_ui(fake)
        rows=[{'species':'合成魚','count':0,'source_page':1,'source_row':1}]
        with patch.object(ui.store,'export_rows',return_value=rows): ui.render_confirmed_exports(TEMPLATE,[])
        download=next(c for c in fake.calls if c[0]=='download_button')
        self.assertEqual(download[1][1],confirmed_csv(rows,FIELDS))
        self.assertEqual(download[2]['file_name'],'TEST_v1.csv')


if __name__=='__main__': unittest.main()
