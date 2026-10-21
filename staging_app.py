"""Staging-only persistence acceptance entry point; uses the production CRUD."""
import os
import uuid
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
import database
from p0_persistence_smoke import run

st.set_page_config(page_title='DFIS staging persistence', layout='wide')

def setting(name, default=''):
    return str(st.secrets.get(name, os.environ.get(name, default)))

if setting('DFIS_ENVIRONMENT') != 'staging' or not database.REQUIRE_POSTGRES:
    st.error('此驗證頁要求 DFIS_ENVIRONMENT=staging 與 DFIS_REQUIRE_POSTGRES=true。')
    st.stop()

# Ref is public metadata; credentials remain in Streamlit Secrets only.
expected_ref = 'hmdeurstmttoiuiddyzi'
from urllib.parse import urlparse
configured_user = database.PG_USER
configured_host = database.PG_HOST
if database.DB_URL:
    parsed = urlparse(database.DB_URL)
    configured_user, configured_host = parsed.username, parsed.hostname
if not (configured_host == f'db.{expected_ref}.supabase.co' or
        configured_user == f'postgres.{expected_ref}'):
    st.error('目前連線設定不屬於指定的 dfis-staging 專案。')
    st.stop()
try:
    database.init_db()
except database.DatabaseUnavailableError as exc:
    st.error(str(exc))
    st.stop()

view=st.sidebar.radio('測試功能',['Word／PDF 新流程','P0-A 保存驗證'])
if view=='Word／PDF 新流程':
    from workflow_ui import render
    render()
    st.stop()
st.title('DFIS staging 資料保存驗證')

@st.cache_resource
def process_identity():
    return {'instance': str(uuid.uuid4()), 'pid': os.getpid(),
            'started_at': datetime.now(timezone.utc).isoformat()}

identity = process_identity()
st.success('PostgreSQL 已連線；SQLite fallback 已停用。')
st.json(identity)
st.caption('先新增測試資料，記下 marker 與 ID，再於 Cloud 管理介面 Reboot，最後以同一組 marker / ID 查詢。')
marker = st.text_input('驗證標記', value='P0-STAGING-20261020-001')
log_id = st.number_input('日誌 ID（重啟後填入）', min_value=1, step=1)
phase = None
left, right = st.columns(2)
if left.button('新增一筆 staging 測試資料'):
    phase = 'insert'
if right.button('重啟後查詢與匯出驗證'):
    phase = 'verify'
if phase:
    st.session_state.pop('p0_result', None)
    try:
        result = run(phase, marker, int(log_id))
        result['app_process'] = identity
        result['observed_at'] = datetime.now(timezone.utc).isoformat()
        st.session_state['p0_result'] = result
    except Exception as exc:
        st.error(f'驗證失敗（{type(exc).__name__}）；請檢查 staging 設定與資料庫 schema。')
if 'p0_result' in st.session_state:
    result = st.session_state['p0_result']
    st.json(result)
    detail = database.get_fishery_log_detail(result['log_id'])
    frame = pd.DataFrame(detail['catch_records'])
    st.dataframe(frame)
    st.download_button('下載驗證 CSV', frame.to_csv(index=False).encode('utf-8-sig'),
                       file_name=f"{result['marker']}.csv", mime='text/csv')
