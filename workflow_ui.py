"""Word template → PDF pages → review → accumulated CSV test interface."""
import io
import json
from decimal import Decimal
import pandas as pd
import streamlit as st
import workflow_store as store
from word_workflow import read_word,suggest_fields,digest,csv_bytes
from workflow_ai import extract_page
from workflow_candidates import candidate_csv,summary_json


def secret(name):
    import os
    return str(st.secrets.get(name,os.environ.get(name,'')))


def render_candidate_exports(template,batches):
    st.caption('從 Supabase 保存的頁面讀取 AI 候選，不必重傳 PDF，也不會呼叫 AI 或自動確認入庫。')
    st.warning('AI 未審核候選不是已確認資料。頁內候選序號不是原表實體列；下載不代表人工覆核完成。')
    pending={u['id']:u for u in batches if u['status']!='confirmed'}
    scope=st.selectbox('候選匯出範圍',[None]+list(pending),
        format_func=lambda uid:'全部未確認批次' if uid is None else f"{pending[uid]['filename']} · {uid[:8]}",
        key='wf_candidate_batch_'+template['id'])
    st.button('重新查詢保存的候選',key='wf_candidate_refresh_'+template['id'])
    try: snapshot=store.candidate_snapshot(template['id'],scope)
    except ValueError as exc: st.error(str(exc)); return
    except Exception:
        st.error('讀取候選資料失敗，請確認資料庫連線與工作流程資料表；不會改用本機資料。'); return
    counts=snapshot['summary']
    st.metric('AI 未審核候選列數',counts['candidate_rows'])
    st.caption(f"未確認批次 {counts['batches']}｜預期頁數 {counts['expected_pages']}｜AI 結果頁 {counts['ai_pages']}｜"
               f"缺頁 {counts['missing_pages']}｜失敗 {counts['failed_pages']}｜資料問題 {counts['invalid_pages']}｜"
               f"非 AI 頁 {counts['manual_pages']}｜排除全空列 {counts['excluded_null_rows']}")
    for notice in snapshot['notices']: st.info(notice)
    if snapshot['page_summary']: st.dataframe(pd.DataFrame(snapshot['page_summary']),hide_index=True)
    if snapshot['issues']: st.dataframe(pd.DataFrame(snapshot['issues']),hide_index=True)
    st.download_button('下載候選頁面摘要 JSON',summary_json(snapshot),
        file_name=f"{template['code']}_v{template['version']}_AI_UNREVIEWED_summary.json",mime='application/json',
        key='wf_candidate_summary_'+template['id'])
    if snapshot['blocked']:
        st.error('候選資料有格式問題，已阻擋 CSV。請依摘要處理問題頁；不能忽略壞資料後宣稱完整。'); return
    if not snapshot['rows']:
        st.info('目前沒有可匯出的 AI 候選。缺頁、人工建檔頁或沒有候選，都不代表已確認零漁獲。'); return
    display=[{key:format(value,'f') if isinstance(value,Decimal) else value for key,value in row.items()}
             for row in snapshot['rows']]
    st.dataframe(pd.DataFrame(display),hide_index=True)
    understood=True
    if snapshot['partial']:
        st.warning('所選範圍不完整。可下載已取得的候選，但請一併保存頁面摘要。')
        understood=st.checkbox('我了解這是包含缺頁、失敗或非 AI 頁的部分候選，不是完整轉錄或人工確認',
                                  key='wf_candidate_partial_'+template['id']+'_'+str(scope))
    export=candidate_csv(snapshot)
    st.download_button('下載 AI 未審核候選 CSV',export,
        file_name=f"{template['code']}_v{template['version']}_AI_UNREVIEWED"+('_PARTIAL' if snapshot['partial'] else '')+'.csv',mime='text/csv',
        disabled=not understood,key='wf_candidate_csv_'+template['id'])
    st.caption('候選 CSV SHA-256：'+digest(export))


def render_confirmed_exports(template,batches):
    batch_ids=['全部']+[u['id'] for u in batches if u['status']=='confirmed']
    batch=st.selectbox('匯出範圍',batch_ids,key='wf_export_batch')
    rows=store.export_rows(template['id'],None if batch=='全部' else batch)
    st.metric('已確認累積資料列數',len(rows))
    if rows:
        st.dataframe(pd.DataFrame(rows),hide_index=True)
        export=csv_bytes(rows,json.loads(template['fields_json']))
        st.download_button('下載累積 CSV',export,file_name=f"{template['code']}_v{template['version']}.csv",mime='text/csv')
        st.caption('CSV SHA-256：'+digest(export))


def _sync_template_export():
    st.session_state['wf_export_template']=st.session_state['wf_selected']


def render_new_template():
    word=st.file_uploader('新增 Word 母版（DOCX；DOC 請另存為 DOCX）',type=['docx','doc'],key='wf_word')
    if not word: return
    try:
        data=word.getvalue(); snapshot=read_word(data,word.name)
        form_key=digest(data)
        with st.expander('檢視擷取的 Word 結構（請核對未遺漏欄位）'): st.json(snapshot)
        code=st.text_input('類型代碼，例如 LONG_LINE 或 QUESTIONNAIRE',value='FORM_'+form_key[:8],key='wf_code_'+form_key)
        name=st.text_input('類型名稱',value=word.name.rsplit('.',1)[0],key='wf_name_'+form_key)
        st.caption('header 為共用表頭，detail 為一組重複明細。請刪除說明段落等非欄位內容；欄位 code 將成為 CSV 欄名。同類型新版本請沿用類型代碼，既有版本不會被覆寫。')
        draft=st.data_editor(pd.DataFrame(suggest_fields(snapshot)),num_rows='dynamic',hide_index=True,
            key='wf_fields_'+form_key,column_config={
                'scope':st.column_config.SelectboxColumn(options=['header','detail'],required=True),
                'type':st.column_config.SelectboxColumn(options=['text','integer','decimal'],required=True)})
        approved=st.checkbox('我已核對欄位、單位、左右欄順序，且本母版只有一組重複明細',key='wf_template_approved_'+form_key)
        if st.button('儲存為樣板（發布版本）',disabled=not approved):
            tid=store.publish(code,name,word.name,data,snapshot,draft.fillna('').to_dict('records'))
            st.session_state['wf_template_pending_id']=tid
            st.rerun()
    except ValueError as exc: st.error(str(exc))
    except Exception: st.error('Word 讀取或發布失敗，請確認格式、欄位及資料庫設定。')


def render():
    st.title('多元漁業資訊標準及智慧化軟體系統v1')
    st.caption('手寫紙本PDF檔案智慧轉譯小幫手')
    st.info('本版支援 DOCX 文字／表格母版，以及一組重複明細。日期、單位與複選保留原文；原始 Word／PDF 不長期保存，請自行保留。尚未驗收真實手寫辨識準確率。')
    try: store.check_schema()
    except Exception:
        st.error('工作流程資料表尚未就緒，請由管理者套用 migration 002。啟動不會自動建表。'); return
    templates=store.templates()
    by_id={t['id']:t for t in templates}
    pending=st.session_state.pop('wf_template_pending_id',None)
    if pending in by_id:
        st.session_state['wf_selected']=pending
        st.session_state['wf_export_template']=pending
        st.session_state['wf_template_mode']='使用已儲存樣板'
        st.success('樣板版本已保存並自動選取；後續可直接上傳對應 PDF，無需重傳 Word。')
    tab1,tab2,tab3=st.tabs(['① 選取／新增樣板','② PDF 辨識與覆核','③ 候選／已確認 CSV'])
    with tab1:
        if templates:
            st.info('Word 只需在首次建置或新增版本時上傳，核對欄位並儲存為樣板。已儲存的欄位與版本會保留在資料庫，後續直接選用；原始 Word 請自行留存。')
            tid=st.selectbox('選取已儲存樣板',list(by_id),
                format_func=lambda k:f"{by_id[k]['name']} · {by_id[k]['code']} v{by_id[k]['version']}",
                key='wf_selected',on_change=_sync_template_export)
            st.caption('目前選取：'+by_id[tid]['name']+f" v{by_id[tid]['version']}。請在步驟②上傳對應的 PDF。")
            mode=st.radio('樣板操作',['使用已儲存樣板','新增 Word 母版／版本'],key='wf_template_mode',horizontal=True)
            with st.expander('檢視已儲存樣板清單'):
                st.dataframe(pd.DataFrame(templates)[['code','version','name','source_name']],hide_index=True)
        else:
            mode='新增 Word 母版／版本'
            st.info('尚無樣板。請先上傳一次 Word 母版，核對欄位並儲存為樣板；之後即可直接選用。')
        if mode=='新增 Word 母版／版本': render_new_template()
        with st.expander('測試環境資料保存自測'):
            st.caption('新增兩批明確標示的合成資料，驗證母版、去重、累積及 CSV；不呼叫 AI，也不代表辨識準確率通過。')
            if st.button('執行合成資料保存測試'):
                try:
                    from workflow_smoke import run
                    st.json(run())
                except Exception as exc: st.error('保存測試失敗：'+type(exc).__name__)
    if not templates:
        with tab2: st.info('請先在步驟①發布母版。')
        return
    with tab2:
        st.info(f"目前樣板：{by_id[tid]['name']} · {by_id[tid]['code']} v{by_id[tid]['version']}；如需更換，請至步驟①選取已儲存樣板。")
        template=by_id[tid]; fields=json.loads(template['fields_json'])
        provider=st.selectbox('辨識方式',['Gemini','OpenAI','人工建檔'],key='wf_provider')
        model='manual'; key=''
        if provider!='人工建檔':
            model=st.text_input('模型名稱',value='gemini-2.5-flash' if provider=='Gemini' else 'gpt-4.1-mini',key='wf_model_'+provider)
            key=st.text_input(provider+' API Key',type='password',value=secret('GEMINI_API_KEY' if provider=='Gemini' else 'OPENAI_API_KEY'),key='wf_key_'+provider)
        pdfs=st.file_uploader('可持續追加不同的手寫 PDF（單檔上限 20 MB／40 頁）',type=['pdf'],accept_multiple_files=True,key='wf_pdfs_'+tid)
        consent=st.checkbox('執行 AI 時，同意將所選 PDF 頁面與 Word 母版文字送至所選 API 服務辨識',key='wf_consent')
        for pdf_file in pdfs:
            try:
                import pypdfium2 as pdfium
                content=pdf_file.getvalue()
                if len(content)>20*1024*1024: raise ValueError('PDF 超過 20 MB。')
                pdf=pdfium.PdfDocument(content)
                if not 1<=len(pdf)<=40:
                    pdf.close(); raise ValueError('每份 PDF 需為 1–40 頁。')
                uid=store.register(tid,pdf_file.name,content,len(pdf))
                upload=next(u for u in store.uploads(tid) if u['id']==uid)
                with st.expander(f"{pdf_file.name}｜{len(pdf)} 頁｜{upload['status']}｜{uid[:8]}",expanded=True):
                    if upload['status']=='confirmed':
                        st.success('相同內容已確認入庫，不會重複新增。')
                    else:
                        existing={p['page_no']:p for p in store.pages(uid)}
                        st.caption('成功頁會保存為待覆核結果；重試只處理未完成頁。已確認資料不可覆寫。')
                        if st.button('開始／重試未完成頁',key='wf_run_'+uid,disabled=provider!='人工建檔' and (not key or not consent)):
                            progress=st.progress(0.0)
                            for number in range(1,len(pdf)+1):
                                if existing.get(number,{}).get('status')!='success':
                                    page=pdf[number-1]
                                    try:
                                        if provider=='人工建檔':
                                            result={'rows':[{f['key']:None for f in fields}],'warnings':'人工建檔，請逐頁填入實際資料；此列不是 AI 辨識成果。'}
                                        else:
                                            bitmap=page.render(scale=2)
                                            try:
                                                image=bitmap.to_pil(); out=io.BytesIO(); image.save(out,format='JPEG',quality=90)
                                                result=extract_page(out.getvalue(),template,number,provider,model,key)
                                            finally: bitmap.close()
                                        store.save_page(uid,number,result,provider,model)
                                    except Exception as exc:
                                        store.save_page(uid,number,None,provider,model)
                                        status=getattr(exc,'status_code',None)
                                        st.warning(f'第 {number} 頁未成功（{type(exc).__name__}'+(f' / {status}' if status else '')+'），請重試或改人工建檔。')
                                    finally: page.close()
                                progress.progress(number/len(pdf))
                        pages=store.pages(uid)
                        st.dataframe(pd.DataFrame([{'頁碼':p['page_no'],'狀態':p['status'],'模型':p['model']} for p in pages]),hide_index=True)
                        reviewed=[]
                        for p in pages:
                            if p['status']=='success':
                                result=json.loads(p['result_json'])
                                if result['warnings']: st.warning(f"第 {p['page_no']} 頁：{result['warnings']}")
                                reviewed.extend(dict(r,source_page=p['page_no']) for r in result['rows'])
                        preview=st.number_input('原始 PDF 頁面預覽',1,len(pdf),key='wf_preview_'+uid)
                        page=pdf[int(preview)-1]; bitmap=page.render(scale=1)
                        try: st.image(bitmap.to_pil(),caption=f'原始第 {preview} 頁')
                        finally: bitmap.close(); page.close()
                        if reviewed:
                            st.caption('下表每列是一筆明細或一份問卷。可增加／刪除列；source_page 請填正確來源頁碼。')
                            editor_key='wf_review_'+uid+'_'+digest(json.dumps(pages,default=str).encode())[:12]
                            edited=st.data_editor(pd.DataFrame(reviewed),num_rows='dynamic',hide_index=True,key=editor_key)
                            approve=st.checkbox('我已對照所有原頁並確認表格數值與列數',key='wf_confirm_check_'+uid)
                            all_pages=len(pages)==len(pdf) and all(p['status']=='success' for p in pages)
                            if st.button('確認入庫並累積保存',key='wf_save_'+uid,disabled=not approve or not all_pages):
                                rows=edited.astype(object).where(pd.notna(edited),None).to_dict('records')
                                if store.confirm(uid,rows,fields): st.success(f'已保存 {len(rows)} 列；後續 PDF 會繼續累積。')
                                else: st.info('此批次已保存，不會重複新增。')
                pdf.close()
            except ValueError as exc: st.error(f'{pdf_file.name}：{exc}')
            except Exception: st.error(f'{pdf_file.name}：處理失敗，請重新上傳或確認資料庫設定。')
    with tab3:
        export_tid=st.selectbox('要查詢／匯出的母版版本',list(by_id),format_func=lambda k:f"{by_id[k]['name']} v{by_id[k]['version']}",key='wf_export_template')
        batches=store.uploads(export_tid)
        st.dataframe(pd.DataFrame(batches),hide_index=True)
        mode=st.radio('資料模式',['AI 未審核候選','已確認資料'],key='wf_export_mode',horizontal=True)
        if mode=='AI 未審核候選': render_candidate_exports(by_id[export_tid],batches)
        else: render_confirmed_exports(by_id[export_tid],batches)
