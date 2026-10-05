"""Validate trusted signup completion without starting production services."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

class GateTest(unittest.TestCase):
    def test_client_cannot_claim_signup_or_count_authenticated_visits(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'server.py').read_text(encoding='utf-8'))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'funnel_event')
        fn.decorator_list = []
        send = Mock()
        scope = dict(FunnelBody=object, Request=object, _sessions={'valid': {'email':'member'}}, _funnel_from=send)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'server.py', 'exec'), scope)
        handler = scope['funnel_event']
        for step in ('signup_email', 'signup_social'):
            handler(SimpleNamespace(step=step), SimpleNamespace(headers={}))
        handler(SimpleNamespace(step='path_visit'), SimpleNamespace(headers={'authorization':'Bearer valid'}))
        send.assert_not_called()
        request = SimpleNamespace(headers={})
        handler(SimpleNamespace(step='path_product'), request)
        send.assert_called_once_with(request, 'path_product')

if __name__ == '__main__': unittest.main()
