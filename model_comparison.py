"""Bounded diagnostic only: no database writes, retries, or model substitution."""
import base64
import hashlib
import json
import threading
import time
from datetime import datetime, timezone

from word_workflow import parse_page_json, prompt_for

MODELS = {'Gemini': 'gemini-3.1-flash-lite', 'OpenAI': 'gpt-6-luna'}
PDF_SHA = '13066efec8253b71564d45963f701245fdc807ad653b3e7e563397dd44cfe8d9'
TEMPLATE_ID = '54d7616f-8dd0-4c6e-b50d-e4805de3f69d'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(pdf_bytes, template):
    if sha(pdf_bytes) != PDF_SHA or template['id'] != TEMPLATE_ID:
        raise ValueError('此輪只允許已授權的第 5 頁副本及指定樣板。')
    import io
    import pypdfium2 as pdfium
    with pdfium.PdfDocument(pdf_bytes) as pdf:
        if len(pdf) != 1:
            raise ValueError('只允許一頁副本。')
        page = pdf[0]
        try:
            bitmap = page.render(scale=2)
            try:
                output = io.BytesIO()
                bitmap.to_pil().save(output, format='JPEG', quality=90)
                image = output.getvalue()
            finally:
                bitmap.close()
        finally:
            page.close()
    # Same prompt as baseline derivative page 1; no ground-truth answer injected.
    prompt = prompt_for(template, 1)
    return image, prompt


def request_once(provider, image, prompt, key):
    import httpx
    model = MODELS[provider]
    if provider == 'OpenAI':
        url = 'https://api.openai.com/v1/responses'
        headers = {'Authorization': 'Bearer ' + key}
        payload = {'model': model, 'store': False, 'max_output_tokens': 12000,
                   'input': [{'role': 'system', 'content': prompt},
                             {'role': 'user', 'content': [{'type': 'input_image',
                              'image_url': 'data:image/jpeg;base64,' + base64.b64encode(image).decode(),
                              'detail': 'high'}]}], 'text': {'format': {'type': 'json_object'}}}
    else:
        url = 'https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent'
        headers = {'x-goog-api-key': key}
        payload = {'contents': [{'parts': [{'text': prompt}, {'inline_data': {
            'mime_type': 'image/jpeg', 'data': base64.b64encode(image).decode()}}]}],
            'generationConfig': {'responseMimeType': 'application/json', 'maxOutputTokens': 16000}}
    with httpx.Client(timeout=120, follow_redirects=False, trust_env=False,
                      transport=httpx.HTTPTransport(retries=0)) as client:
        response = client.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        return {'status': 'http_error', 'http_status': response.status_code}
    data = response.json()
    if provider == 'OpenAI':
        result = {'usage': data.get('usage'), 'response_id': data.get('id'),
                  'returned_model': data.get('model')}
        if data.get('status') != 'completed':
            return dict(result, status='incomplete')
        raw = ''.join(part.get('text', '') for item in data.get('output', [])
                      if item.get('type') == 'message' for part in item.get('content', [])
                      if part.get('type') == 'output_text')
    else:
        result = {'usage': data.get('usageMetadata'), 'response_id': data.get('responseId'),
                  'returned_model': data.get('modelVersion')}
        candidates = data.get('candidates', [])
        if not candidates or candidates[0].get('finishReason') != 'STOP':
            return dict(result, status='incomplete')
        raw = ''.join(p.get('text', '') for p in candidates[0].get('content', {}).get('parts', [])
                      if not p.get('thought'))
    return dict(result, status='received', raw=raw)


class Comparison:
    """One claim per model per application process; reruns/sessions share locks."""
    def __init__(self):
        self.lock = threading.Lock()
        self.results = {}

    def run(self, provider, image, prompt, template, key, send=request_once):
        if provider not in MODELS or not key.strip():
            raise ValueError('請提供指定服務的金鑰。')
        if template['id'] != TEMPLATE_ID:
            raise ValueError('樣板不符。')
        identity = sha(image + prompt.encode())
        with self.lock:
            if provider in self.results:
                return self.results[provider]
            record = {'provider': provider, 'model': MODELS[provider], 'status': 'started',
                      'started_at': datetime.now(timezone.utc).isoformat(),
                      'image_sha256': sha(image), 'prompt_sha256': sha(prompt.encode()),
                      'input_identity': identity, 'original_page': 5, 'derivative_page': 1,
                      'pdf_sha256': PDF_SHA, 'template_id': template['id'],
                      'template_code': template['code'], 'template_version': template['version'],
                      'review_status': 'ai_unreviewed', 'quality_accepted': False,
                      'http_attempt_limit': 1, 'durability': 'process_memory_only'}
            if self.results and any(r['input_identity'] != identity for r in self.results.values()):
                raise ValueError('兩模型輸入不一致，已阻擋。')
            self.results[provider] = record
        started = time.monotonic()
        try:
            record.update(send(provider, image, prompt, key))
            if record['status'] == 'received':
                try:
                    record['parsed'] = parse_page_json(record['raw'], json.loads(template['fields_json']))
                    record['status'] = 'success'
                except Exception:
                    record['status'] = 'parse_error'
        except Exception as exc:
            # Never persist exception strings: they may include credentials or payloads.
            record['status'] = 'request_error'
            record['error_type'] = type(exc).__name__
        finally:
            record['elapsed_seconds'] = round(time.monotonic() - started, 3)
        return record


def export(record):
    return json.dumps(record, ensure_ascii=False, indent=2, default=str).encode('utf-8')
