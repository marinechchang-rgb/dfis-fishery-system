"""One image per request, strict JSON validation, no silent truncation repair."""
import base64
from word_workflow import parse_page_json, prompt_for


def extract_page(image_bytes,template,page_no,provider,model,key):
    if provider not in {'OpenAI','Gemini'}:
        raise ValueError('此辨識服務尚未接入，未執行任何 API 請求。')
    if not key: raise ValueError('請輸入所選服務的 API 金鑰。')
    prompt=prompt_for(template,page_no)
    if provider=='OpenAI':
        from openai import OpenAI
        with OpenAI(api_key=key,timeout=120,max_retries=2) as client:
            response=client.responses.create(model=model,store=False,
                input=[{'role':'system','content':prompt},
                       {'role':'user','content':[{'type':'input_image','image_url':'data:image/jpeg;base64,'+base64.b64encode(image_bytes).decode(),'detail':'high'}]}],
                text={'format':{'type':'json_object'}},max_output_tokens=12000)
            if getattr(response,'status','completed')!='completed':
                raise ValueError('模型輸出未完成，請重試此頁。')
            raw=response.output_text
    else:
        from google import genai
        from google.genai import types
        client=genai.Client(api_key=key,http_options={'timeout':120000})
        try:
            response=client.models.generate_content(model=model,
                contents=[prompt,types.Part.from_bytes(data=image_bytes,mime_type='image/jpeg')],
                config=types.GenerateContentConfig(response_mime_type='application/json',max_output_tokens=16000))
            raw=response.text
        finally: client.close()
    import json
    return parse_page_json(raw,json.loads(template['fields_json']))
