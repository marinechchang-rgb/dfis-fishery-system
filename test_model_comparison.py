import json
import unittest
from unittest.mock import patch
import httpx
from model_comparison import Comparison, MODELS, TEMPLATE_ID, prepare, request_once, export

TEMPLATE = {'id': TEMPLATE_ID, 'code': 'FORM_ca51e7dd', 'version': 1,
            'fields_json': json.dumps([{'key': 'count', 'label': '尾數', 'type': 'integer', 'scope': 'detail'}]),
            'snapshot_json': '{}'}


class ComparisonTests(unittest.TestCase):
    def test_repeat_does_not_send(self):
        state = Comparison()
        calls = []
        def send(*args):
            calls.append(args)
            return {'status': 'received', 'raw': '{"matched":true,"empty":false,"rows":[{"count":0}],"warnings":""}', 'usage': {'tokens': 5}}
        first = state.run('Gemini', b'image', 'prompt', TEMPLATE, 'PRIVATE-KEY', send)
        self.assertEqual(first['status'], 'success')
        self.assertIs(first, state.run('Gemini', b'image', 'prompt', TEMPLATE, 'PRIVATE-KEY', send))
        self.assertEqual(len(calls), 1)
        self.assertNotIn(b'PRIVATE-KEY', export(first))
        self.assertEqual(first['parsed']['rows'][0]['count'], 0)

    def test_failure_consumes_claim_and_sanitizes(self):
        state = Comparison()
        def fail(*args): raise RuntimeError('secret token payload')
        record = state.run('OpenAI', b'image', 'prompt', TEMPLATE, 'key', fail)
        self.assertEqual(record['status'], 'request_error')
        self.assertNotIn(b'secret token', export(record))
        state.run('OpenAI', b'image', 'prompt', TEMPLATE, 'key', lambda *a: self.fail('retried'))

    def test_changed_input_blocked_for_second_model(self):
        state = Comparison()
        state.run('Gemini', b'a', 'prompt', TEMPLATE, 'key', lambda *a: {'status': 'http_error'})
        with self.assertRaises(ValueError):
            state.run('OpenAI', b'b', 'prompt', TEMPLATE, 'key', lambda *a: self.fail('sent'))
        self.assertNotIn('OpenAI', state.results)

    def test_invalid_key_provider_template_and_pdf_blocked(self):
        for provider, key, template in [('other', 'key', TEMPLATE), ('Gemini', '', TEMPLATE),
                                         ('Gemini', 'key', dict(TEMPLATE, id='other'))]:
            with self.assertRaises(ValueError): Comparison().run(provider, b'i', 'p', template, key)
        with self.assertRaises(ValueError): prepare(b'invalid', TEMPLATE)

    def test_parse_failure_is_retained(self):
        result = Comparison().run('Gemini', b'i', 'p', TEMPLATE, 'key',
            lambda *a: {'status': 'received', 'raw': '{truncated'})
        self.assertEqual(result['status'], 'parse_error')
        self.assertEqual(result['raw'], '{truncated')

    def transport(self, provider, status, payload):
        calls = []
        real = httpx.Client
        def handler(request):
            calls.append(request)
            return httpx.Response(status, json=payload, headers={'Location': 'https://example.invalid'})
        def factory(**kwargs):
            self.assertFalse(kwargs['follow_redirects'])
            self.assertFalse(kwargs['trust_env'])
            kwargs['transport'].close()
            kwargs['transport'] = httpx.MockTransport(handler)
            return real(**kwargs)
        with patch('httpx.Client', side_effect=factory):
            result = request_once(provider, b'image', 'same-prompt', 'private-key')
        self.assertEqual(len(calls), 1)
        body = json.loads(calls[0].content)
        self.assertEqual(body.get('model', MODELS[provider]), MODELS[provider])
        self.assertNotIn('2025', calls[0].content.decode())
        return result

    def test_openai_http_failure_once(self):
        self.assertEqual(self.transport('OpenAI', 503, {'error': 'private'})['http_status'], 503)

    def test_gemini_http_failure_once(self):
        self.assertEqual(self.transport('Gemini', 429, {'error': 'private'})['http_status'], 429)

    def test_no_redirect_following(self):
        self.assertEqual(self.transport('OpenAI', 302, {})['status'], 'http_error')

    def test_openai_response(self):
        result = self.transport('OpenAI', 200, {'id': 'id', 'model': MODELS['OpenAI'], 'status': 'completed',
            'usage': {'input_tokens': 2}, 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': '{}'}]}]})
        self.assertEqual(result['raw'], '{}')
        self.assertEqual(result['usage']['input_tokens'], 2)

    def test_gemini_response(self):
        result = self.transport('Gemini', 200, {'candidates': [{'finishReason': 'STOP',
            'content': {'parts': [{'text': 'hidden', 'thought': True}, {'text': '{}'}]}}]})
        self.assertEqual(result['raw'], '{}')

    def test_incomplete_not_parsed(self):
        self.assertEqual(self.transport('OpenAI', 200, {'status': 'incomplete'})['status'], 'incomplete')
        self.assertEqual(self.transport('Gemini', 200, {'candidates': []})['status'], 'incomplete')


if __name__ == '__main__': unittest.main()
