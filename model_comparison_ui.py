"""Staging-only, process-memory diagnostic; never calls workflow_store writes."""
import streamlit as st
from model_comparison import Comparison, MODELS, prepare, export


@st.cache_resource
def registry():
    return Comparison()


def render(template):
    st.subheader('隔離模型比較｜第 5 頁限定')
    st.warning('只供本輪兩模型各一次比較，不寫入既有候選或確認資料。結果僅暫存於目前伺服器程序；請下載留存。重啟會清除結果與單次鎖，請勿藉重啟重測。')
    st.caption('版本 CMP-1 · 固定模型、相同影像與提示；無自動重試、無替代模型。請勿在公開或多人共用環境執行。')
    pdf = st.file_uploader('比較用第 5 頁獨立 PDF 副本', type=['pdf'], key='cmp_pdf')
    inputs = None
    if pdf:
        try:
            inputs = prepare(pdf.getvalue(), template)
            st.success('已核對指定單頁副本及樣板，兩模型共用同一份 JPEG 與提示。')
        except Exception:
            st.error('副本或樣板不符，或無法渲染；未呼叫 API。')
    consent = st.checkbox('同意僅將此第 5 頁影像及樣板文字送至下列兩家 API，各測一次，可能產生費用', key='cmp_consent')
    state = registry()
    for provider, model in MODELS.items():
        st.markdown('#### ' + provider + ' · ' + model)
        secret_name = 'GEMINI_API_KEY' if provider == 'Gemini' else 'OPENAI_API_KEY'
        import os
        key = st.text_input(provider + ' 比較用 API Key', type='password',
            value=st.session_state.get('wf_key_' + provider) or st.secrets.get(secret_name, os.environ.get(secret_name, '')),
            key='cmp_key_' + provider)
        record = state.results.get(provider)
        if st.button('單次測試 ' + model, key='cmp_run_' + provider,
                     disabled=not inputs or not consent or not key.strip() or record is not None):
            with st.spinner('單次請求中；請勿重啟或另開測試程序。'):
                record = state.run(provider, *inputs, template, key)
            st.rerun()
        if record:
            st.write('狀態：' + record['status'])
            st.json({k: v for k, v in record.items() if k not in {'raw', 'parsed'}})
            if record.get('parsed'):
                st.dataframe(record['parsed']['rows'], hide_index=True)
                st.write(record['parsed'].get('warnings', ''))
            if record['status'] != 'started':
                artifact = export(record)
                st.download_button('下載 ' + provider + ' 比較結果 JSON', artifact,
                    file_name='CMP_P005_' + model + '.json', mime='application/json', key='cmp_download_' + provider)
            st.info('本模型已使用本程序唯一測試機會；不提供重試或確認入庫。')
