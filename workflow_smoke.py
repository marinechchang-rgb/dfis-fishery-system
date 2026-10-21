"""Synthetic persistence probe, explicitly not an OCR benchmark."""
import json
import workflow_store as store
from word_workflow import csv_bytes,digest


def run():
    fields=[{'key':'species','label':'測試魚種','scope':'detail','type':'text'},
            {'key':'weight_kg','label':'重量 kg','scope':'detail','type':'decimal'}]
    tid=store.publish('WF_SMOKE_20261021','合成流程測試（非真實觀測）','synthetic-template.txt',
                      b'wf-smoke-template-v1',{'paragraphs':['合成資料測試'],'tables':[]},fields)
    for number in (1,2):
        uid=store.register(tid,f'synthetic-{number}.pdf',f'synthetic-pdf-{number}'.encode(),1)
        upload=next(u for u in store.uploads(tid) if u['id']==uid)
        if upload['status']!='confirmed':
            row={'species':'合成測試魚','weight_kg':number*1.25}
            store.save_page(uid,1,{'rows':[row],'warnings':'合成資料，不是 OCR'},'manual','smoke-v1')
            store.confirm(uid,[dict(row,source_page=1)],fields)
        if store.register(tid,'renamed.pdf',f'synthetic-pdf-{number}'.encode(),1)!=uid:
            raise RuntimeError('Content deduplication failed')
    rows=store.export_rows(tid)
    if len(rows)!=2 or sorted(r['weight_kg'] for r in rows)!=[1.25,2.5]:
        raise RuntimeError('Accumulation mismatch')
    return {'kind':'synthetic persistence only; not OCR','template_id':tid,
            'confirmed_uploads':2,'rows':len(rows),'backend':'postgresql' if store.database.IS_POSTGRES else 'sqlite',
            'csv_sha256':digest(csv_bytes(rows,fields))}
