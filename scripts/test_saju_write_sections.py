"""Exercise the real report handler without network, payment, or production data."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
import unittest

class HTTPError(Exception):
    def __init__(self,status_code,detail):self.status_code=status_code;super().__init__(detail)

class SectionsTest(unittest.TestCase):
    def handler(self, *,paid=True,cached=None,preview_cap=0):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'server.py').read_text(encoding='utf-8'))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='saju_write')
        fn.decorator_list=[]
        writer=NS(ready=lambda:True,WRITE_VER=4,load=Mock(return_value=cached),
                  write_report=Mock(side_effect=lambda name,saju,sections,**kw:{'blocks':[{'title':s,'text':'generated '+s} for s in sections]}),merge=Mock())
        scope=dict(WriteBody=object,Header=lambda **kw:None,HTTPException=HTTPError,
                   _token_user=lambda auth:{'email':'fixture'},saju_writer=writer,
                   lamps_ops=NS(FREE_PRODUCTS=set(),owns=lambda *a:paid),
                   _is_free=lambda u:False,_is_owner=lambda u:False,
                   PREVIEW_SECTIONS=preview_cap,PREVIEW_DAILY_CAP=3,FREE_DAILY_CAP=3,
                   _preview_quota=Mock(),_preview_used=lambda *a:0,
                   _saju_veil_blocks=lambda blocks:[{'title':b['title'],'text':'','hooking_preview':'preview'} for b in blocks])
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'server.py','exec'),scope)
        return scope['saju_write'],writer,scope
    def body(self,n,preview=False):
        return NS(product='great',pair='fixture',sections=[f'section{i}' for i in range(n)],saju={},name='fixture',preview=preview,chars=420,force=False)
    def test_large_reports_return_every_section(self):
        for n in (23,51):
            handler,writer,_=self.handler()
            result=handler(self.body(n))
            self.assertEqual(len(result['blocks']),n)
            self.assertTrue(all(b['text'] for b in result['blocks']))
    def test_partial_cache_only_generates_missing_tail(self):
        body=self.body(51)
        cached={'ver':4,'blocks':[{'title':s,'text':'cached'} for s in body.sections[:20]]}
        handler,writer,_=self.handler(cached=cached)
        result=handler(body)
        self.assertEqual(writer.write_report.call_args.args[2],body.sections[20:])
        self.assertEqual(len(result['blocks']),51)
        self.assertEqual(result['blocks'][0]['text'],'cached')
    def test_payment_and_preview_limits_preserved(self):
        handler,writer,_=self.handler(paid=False)
        with self.assertRaises(HTTPError) as e:handler(self.body(51))
        self.assertEqual(e.exception.status_code,402)
        writer.write_report.assert_not_called()
        handler,writer,_=self.handler(paid=False,preview_cap=1)
        result=handler(self.body(51,True))
        self.assertEqual(len(result['blocks']),1)
        self.assertFalse(result['blocks'][0]['text'])
    def test_oversized_request_rejected_before_generation(self):
        handler,writer,_=self.handler()
        with self.assertRaises(HTTPError) as e:handler(self.body(65))
        self.assertEqual(e.exception.status_code,400)
        writer.write_report.assert_not_called()

if __name__=='__main__':unittest.main()
