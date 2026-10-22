"""Workflow persistence; schema installed by explicit migration, never at startup."""
import json
import uuid
import database
from word_workflow import digest, validate_fields, validate_values


def _query(sql, params=(), write=False):
    conn=database.get_db_connection()
    try:
        cur=database.get_cursor(conn); cur.execute(sql,params)
        result=[] if write else [dict(r) for r in cur.fetchall()]
        if write: conn.commit()
        return result
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


def check_schema():
    for table,cols in [('wf_templates','id,code,version,name,source_name,source_sha,snapshot_json,fields_json'),
                       ('wf_uploads','id,template_id,filename,pdf_sha,page_count,status'),
                       ('wf_pages','upload_id,page_no,status,result_json,provider,model'),
                       ('wf_records','id,upload_id,page_no,row_no,values_json')]:
        _query(f'SELECT {cols} FROM {table} LIMIT 0')


def templates():
    return _query('SELECT * FROM wf_templates ORDER BY code,version DESC')


def publish(code,name,source_name,data,snapshot,fields):
    import re
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{1,47}',code) or not name.strip():
        raise ValueError('類型代碼需為 2–48 個英數／底線，名稱不可空白。')
    fields=validate_fields(fields)
    encoded=json.dumps(fields,ensure_ascii=False,sort_keys=True)
    sha=digest(data)
    existing=_query('SELECT id FROM wf_templates WHERE code=? AND source_sha=? AND fields_json=?',(code,sha,encoded))
    if existing: return existing[0]['id']
    version=_query('SELECT COALESCE(MAX(version),0)+1 AS v FROM wf_templates WHERE code=?',(code,))[0]['v']
    tid=str(uuid.uuid4())
    _query('INSERT INTO wf_templates(id,code,version,name,source_name,source_sha,snapshot_json,fields_json) VALUES(?,?,?,?,?,?,?,?)',
           (tid,code,version,name,source_name,sha,json.dumps(snapshot,ensure_ascii=False),encoded),True)
    return tid


def register(template_id,filename,data,page_count):
    uid=str(uuid.uuid5(uuid.NAMESPACE_URL,template_id+digest(data)))
    _query('INSERT INTO wf_uploads(id,template_id,filename,pdf_sha,page_count) VALUES(?,?,?,?,?) ON CONFLICT(id) DO NOTHING',
           (uid,template_id,filename,digest(data),page_count),True)
    return uid


def uploads(template_id):
    return _query('SELECT * FROM wf_uploads WHERE template_id=? ORDER BY created_at DESC,id',(template_id,))


def pages(uid):
    return _query('SELECT * FROM wf_pages WHERE upload_id=? ORDER BY page_no',(uid,))


def save_page(uid,page_no,result,provider,model):
    conn=database.get_db_connection()
    try:
        cur=database.get_cursor(conn)
        if database.IS_POSTGRES:
            cur.execute('SELECT status FROM wf_uploads WHERE id=? FOR UPDATE',(uid,))
        else:
            cur.execute('SELECT status FROM wf_uploads WHERE id=?',(uid,))
        if cur.fetchone()['status']=='confirmed':
            raise ValueError('此批次已確認，不可覆寫。')
        cur.cursor.execute(database.query_fmt('INSERT INTO wf_pages(upload_id,page_no,status,result_json,provider,model) VALUES(?,?,?,?,?,?) ON CONFLICT(upload_id,page_no) DO UPDATE SET status=excluded.status,result_json=excluded.result_json,provider=excluded.provider,model=excluded.model'),
                    (uid,page_no,'success' if result is not None else 'failed',json.dumps(result,ensure_ascii=False),provider,model))
        cur.execute("UPDATE wf_uploads SET status='review' WHERE id=?",(uid,))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally: conn.close()


def confirm(uid,rows,fields):
    if not rows: raise ValueError('沒有資料，不能確認入庫。')
    conn=database.get_db_connection()
    try:
        cur=database.get_cursor(conn)
        cur.execute('SELECT * FROM wf_uploads WHERE id=?'+(' FOR UPDATE' if database.IS_POSTGRES else ''),(uid,))
        upload=cur.fetchone()
        if upload['status']=='confirmed': return False
        cur.execute("SELECT page_no FROM wf_pages WHERE upload_id=? AND status='success'",(uid,))
        if {r['page_no'] for r in cur.fetchall()}!=set(range(1,upload['page_count']+1)):
            raise ValueError('仍有未完成頁，請重試失敗頁。')
        for index,row in enumerate(rows,1):
            page=int(row['source_page'])
            if not 1<=page<=upload['page_count']: raise ValueError('來源頁碼超出範圍。')
            values=validate_values({f['key']:row.get(f['key']) for f in fields},fields)
            if all(v is None for v in values.values()):
                raise ValueError('空白占位列不能入庫，請填寫實際資料或刪除該列。')
            cur.execute('INSERT INTO wf_records(id,upload_id,page_no,row_no,values_json) VALUES(?,?,?,?,?)',
                        (str(uuid.uuid4()),uid,page,index,json.dumps(values,ensure_ascii=False)))
        cur.execute("UPDATE wf_uploads SET status='confirmed' WHERE id=?",(uid,))
        conn.commit(); return True
    except Exception:
        conn.rollback(); raise
    finally: conn.close()


def export_rows(template_id,upload_id=None):
    rows=_query('SELECT r.*,u.filename,t.code,t.version FROM wf_records r JOIN wf_uploads u ON u.id=r.upload_id JOIN wf_templates t ON t.id=u.template_id WHERE t.id=?'+(' AND u.id=?' if upload_id else '')+' ORDER BY u.created_at,u.id,r.page_no,r.row_no',
                (template_id,upload_id) if upload_id else (template_id,))
    return [dict(json.loads(r['values_json']),source_filename=r['filename'],source_upload_id=r['upload_id'],
                 source_template_code=r['code'],source_template_version=r['version'],source_page=r['page_no'],source_row=r['row_no']) for r in rows]


def candidate_snapshot(template_id,upload_id=None):
    """SELECT-only saved AI candidates, independent of uploaded files/session state."""
    from workflow_candidates import build_snapshot
    templates_found=_query('SELECT id,code,version,fields_json FROM wf_templates WHERE id=?',(template_id,))
    if len(templates_found)!=1: raise ValueError('找不到所選母版版本。')
    records=_query('SELECT u.id AS upload_id,u.template_id,u.filename,u.pdf_sha,u.page_count,u.status AS upload_status,'
        'p.page_no,p.status AS page_status,p.result_json,p.provider,p.model '
        'FROM wf_uploads u LEFT JOIN wf_pages p ON p.upload_id=u.id WHERE u.template_id=?'+
        (' AND u.id=?' if upload_id is not None else '')+' ORDER BY u.created_at,u.id,p.page_no',
        (template_id,upload_id) if upload_id is not None else (template_id,))
    if upload_id is not None and not records: raise ValueError('批次不屬於所選母版或不存在。')
    grouped={}
    for record in records:
        uid=record['upload_id']
        if uid not in grouped:
            grouped[uid]={'id':uid,'template_id':record['template_id'],'filename':record['filename'],
                'pdf_sha':record['pdf_sha'],'page_count':record['page_count'],'status':record['upload_status'],'pages':[]}
        if record['page_no'] is not None:
            grouped[uid]['pages'].append({'upload_id':uid,'page_no':record['page_no'],'status':record['page_status'],
                'result_json':record['result_json'],'provider':record['provider'],'model':record['model']})
    if upload_id is not None and grouped[upload_id]['status']=='confirmed':
        raise ValueError('此批次已確認，請使用已確認資料匯出。')
    return build_snapshot(templates_found[0],list(grouped.values()))
