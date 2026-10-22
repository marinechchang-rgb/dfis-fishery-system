"""Read-only projections of stored AI candidates. Never confirm or mutate data."""
import csv
from decimal import Decimal,InvalidOperation
import io
import json
import re

from word_workflow import validate_fields

AI_PROVIDERS=frozenset({'Gemini','OpenAI'})
MANUAL_PROVIDERS=frozenset({'manual','人工建檔'})
META=['source_filename','source_upload_id','source_pdf_sha256','source_template_code',
      'source_template_version','source_page','source_page_status','source_candidate_row',
      'source_section','source_physical_row','source_provider','source_model',
      'source_review_status','source_reviewed_by_human','source_warnings']


def _object(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('JSON 有重複欄位。')
        result[key]=value
    return result


def _constant(value): raise ValueError('JSON 不可包含非有限數值。')


def strict_json(raw):
    return json.loads(raw,parse_float=Decimal,parse_constant=_constant,object_pairs_hook=_object)


def values(row,fields):
    if not isinstance(row,dict) or set(row)-{f['key'] for f in fields}:
        raise ValueError('候選含未知欄位或資料列格式不符。')
    result={}
    for field in fields:
        key=field['key']; value=row.get(key)
        if value is None or value=='': result[key]=None; continue
        if field['type']=='text':
            if not isinstance(value,str): raise ValueError('候選文字欄位型別不符。')
            result[key]=value; continue
        if isinstance(value,bool) or not isinstance(value,(str,int,float,Decimal)):
            raise ValueError('候選數字型別不符。')
        text=str(value).strip()
        # Do not turn OCR "1,2" into 12 or silently repair letters.
        if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',text):
            raise ValueError('候選數值格式不符。')
        if len(text)>100: raise ValueError('候選數值過長。')
        try: number=Decimal(text)
        except InvalidOperation as exc: raise ValueError('候選數值格式不符。') from exc
        if not number.is_finite() or abs(number.adjusted())>100:
            raise ValueError('候選數值超出匯出範圍。')
        if field['type']=='integer':
            if number!=number.to_integral_value(): raise ValueError('候選整數格式不符。')
            result[key]=int(number)
        else: result[key]=number
    return result


def build_snapshot(template,uploads):
    try:
        definitions=strict_json(template['fields_json'])
        if not isinstance(definitions,list) or any(not isinstance(f,dict) for f in definitions):
            raise ValueError('欄位須為清單。')
        fields=validate_fields(definitions)
    except (ValueError,TypeError,KeyError) as exc: raise ValueError('母版欄位格式不符，無法匯出候選。') from exc
    result={'fields':fields,'rows':[],'page_summary':[],'issues':[],
            'summary':{'batches':0,'excluded_confirmed_batches':0,'expected_pages':0,'ai_pages':0,
                       'missing_pages':0,'failed_pages':0,'invalid_pages':0,'manual_pages':0,
                       'no_candidate_pages':0,'excluded_null_rows':0,'candidate_rows':0},
            'blocked':False,'partial':False,'review_status':'ai_unreviewed','quality_accepted':False}
    summary=result['summary']; seen_uploads=set()
    def issue(uid,page,message):
        result['issues'].append({'upload_id':uid,'page':page,'message':message})
        result['blocked']=True
    for upload in uploads:
        uid=upload['id']
        if uid in seen_uploads: raise ValueError('重複批次資料。')
        seen_uploads.add(uid)
        if upload['template_id']!=template['id']: raise ValueError('批次不屬於所選母版。')
        if upload['status']=='confirmed': summary['excluded_confirmed_batches']+=1; continue
        count=upload['page_count']
        if type(count) is not int or not 1<=count<=40: raise ValueError('批次頁數格式不符。')
        summary['batches']+=1; summary['expected_pages']+=count
        saved={}
        for page in upload['pages']:
            number=page['page_no']
            if page['upload_id']!=uid or type(number) is not int or not 1<=number<=count or number in saved:
                summary['invalid_pages']+=1
                issue(uid,number if type(number) is int else None,'保存頁碼重複、越界或來源不符。'); continue
            saved[number]=page
        for number in range(1,count+1):
            page=saved.get(number)
            info={'upload_id':uid,'filename':upload['filename'],'page':number,
                  'status':'missing','provider':None,'model':None,'candidate_rows':0,'excluded_null_rows':0,
                  'warnings':''}
            result['page_summary'].append(info)
            if page is None:
                summary['missing_pages']+=1; continue
            info.update(provider=page['provider'],model=page['model'])
            if page['status']=='failed':
                info['status']='failed'; summary['failed_pages']+=1; continue
            if page['status']!='success':
                info['status']='invalid'; summary['invalid_pages']+=1
                issue(uid,number,'保存頁面狀態不支援。'); continue
            if page['provider'] in MANUAL_PROVIDERS:
                info['status']='manual_not_ai'; summary['manual_pages']+=1; continue
            if page['provider'] not in AI_PROVIDERS:
                info['status']='invalid'; summary['invalid_pages']+=1
                issue(uid,number,'候選辨識來源不支援；不假裝成 Gemini／OpenAI。'); continue
            try:
                payload=strict_json(page['result_json'])
                if not isinstance(payload,dict) or not isinstance(payload.get('rows'),list) or len(payload['rows'])>1000:
                    raise ValueError('候選 JSON／rows 格式不符。')
                # Input claiming human approval never changes the forced export status.
                warnings=payload.get('warnings','')
                if warnings is None: warnings=''
                if not isinstance(warnings,str): raise ValueError('候選警示格式不符。')
                staged=[]; excluded=0
                for index,row in enumerate(payload['rows'],1):
                    normalized=values(row,fields)
                    if all(value is None for value in normalized.values()): excluded+=1; continue
                    staged.append({**normalized,'source_filename':upload['filename'],'source_upload_id':uid,
                        'source_pdf_sha256':upload['pdf_sha'],'source_template_code':template['code'],
                        'source_template_version':template['version'],'source_page':number,
                        'source_page_status':'success','source_candidate_row':index,
                        'source_section':None,'source_physical_row':None,
                        'source_provider':page['provider'],'source_model':page['model'],
                        'source_review_status':'ai_unreviewed','source_reviewed_by_human':False,
                        'source_warnings':warnings[:2000]})
                info.update(status='ai_unreviewed',candidate_rows=len(staged),excluded_null_rows=excluded,
                            warnings=warnings[:2000])
                summary['ai_pages']+=1; summary['excluded_null_rows']+=excluded
                if not staged: summary['no_candidate_pages']+=1
                result['rows'].extend(staged)
            except (ValueError,TypeError,KeyError,InvalidOperation):
                info['status']='invalid'; summary['invalid_pages']+=1
                issue(uid,number,'候選 JSON、欄位或數字格式不符；此頁未匯出，需先處理資料問題。')
    summary['candidate_rows']=len(result['rows'])
    result['partial']=any(summary[k] for k in ('missing_pages','failed_pages','invalid_pages','manual_pages'))
    notes=['AI 未人工審核；來源實體格位未驗證；候選數量不是已確認觀測數。']
    if result['partial']: notes.append('所選範圍不完整，包含缺頁、失敗、非 AI 頁或資料問題，請核對頁面摘要。')
    if summary['excluded_null_rows']: notes.append('已排除全 null 占位列；排除不證明原頁無觀測。')
    if summary['no_candidate_pages']: notes.append('部分頁沒有可匯出候選，不代表已確認空白或零漁獲。')
    result['notices']=notes
    for row in result['rows']:
        row['source_warnings']='；'.join([row['source_warnings']]+notes).lstrip('；')
    return result


def candidate_csv(snapshot):
    if snapshot['blocked']: raise ValueError('候選資料存在格式問題，已阻擋 CSV；請先查看頁面摘要。')
    fields=validate_fields(snapshot['fields'])
    stream=io.StringIO(newline='')
    writer=csv.DictWriter(stream,fieldnames=META+[f['key'] for f in fields],lineterminator='\n')
    writer.writeheader()
    for row in snapshot['rows']:
        if row.get('source_review_status')!='ai_unreviewed' or row.get('source_reviewed_by_human') is not False:
            raise ValueError('候選不得偽裝為已確認資料。')
        safe={}
        for key,value in row.items():
            if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')): value="'"+value
            safe[key]=value
        writer.writerow(safe)
    return stream.getvalue().encode('utf-8-sig')


def summary_json(snapshot):
    value={key:snapshot[key] for key in ('summary','page_summary','issues','blocked','partial','notices','review_status','quality_accepted')}
    return json.dumps(value,ensure_ascii=False,indent=2).encode('utf-8')
