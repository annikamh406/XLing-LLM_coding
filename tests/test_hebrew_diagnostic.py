"""Test protocol diagnostics with fragmented UTF-8 and mocked HTTP responses."""
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
import copy
import unicodedata
from unittest.mock import patch
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'scripts'))
import diagnose_qwen_hebrew as diagnostic
import run_bloom_coding as runner

class Response:
    status=200
    def __init__(self,chunks):self.chunks=iter(chunks)
    def read1(self,n):return next(self.chunks,b'')
    def __enter__(self):return self
    def __exit__(self,*args):pass

def answer(ids):
    return {'schema_version':'bloom_v5','predictions':[dict(record_id=i,bloom_label='Denial',certain='Yes',comments='',
       flags={k:'No' for k in runner.REQUIRED_FLAGS}) for i in ids]}

class DiagnosticTests(unittest.TestCase):
    def test_normalization_preserves_accents_and_source(self):
        record={'record_id':'a','target_utterance':'xaruzi\u0304m ʔo\u0304k\u0323el',
                'context_before':[{'utterance':'ʔo\u0304k\u0323el'}],'sampling_label':'Denial'}
        original=copy.deepcopy(record)
        targeted=diagnostic.normalize_records([record],'compose-o-macron')[0]
        nfc=diagnostic.normalize_records([record],'nfc')[0]
        self.assertEqual(targeted['target_utterance'],'xaruzi\u0304m ʔōk\u0323el')
        self.assertEqual(nfc['target_utterance'],'xaruzīm ʔōḳel')
        for transformed in [targeted,nfc]:
            self.assertEqual(unicodedata.normalize('NFD',transformed['target_utterance']),
                             unicodedata.normalize('NFD',record['target_utterance']))
            self.assertNotIn('sampling_label',transformed)
        self.assertEqual(record,original)
        before=diagnostic.request_payload([record],'system o\u0304',0,False)
        after=diagnostic.request_payload([record],'system o\u0304',0,False,'nfc')
        self.assertEqual(before['messages'][0],after['messages'][0])
        self.assertEqual(before['options'],after['options'])
        self.assertEqual(before['format'],after['format'])

    def test_stream_fragmented_unicode_and_complete_response(self):
        events=[{'message':{'thinking':'שלום'},'done':False},
                {'message':{'content':json.dumps(answer(['a']))},'done':False},
                {'done':True,'done_reason':'stop','eval_count':500}]
        data=('\n'.join(json.dumps(e,ensure_ascii=False) for e in events)+'\n').encode()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);start=time.monotonic()
            parsed=diagnostic.collect(Response([data[i:i+1] for i in range(len(data))]),path,True,start,start+10)
            self.assertEqual(parsed,events)
            self.assertEqual((path/'response-body.bin').read_bytes(),data)
            result=diagnostic.summarize(parsed,['a'],True)
            self.assertEqual(result['outcome'],'valid_complete_response')
            self.assertEqual(result['thinking_characters'],4)
            self.assertEqual(result['generation_tokens'],500)

    def test_buffered_abort_and_schema_failures(self):
        incomplete={'message':{'thinking':'partial','content':''},'done':False}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);start=time.monotonic();data=json.dumps(incomplete).encode()
            parsed=diagnostic.collect(Response([data[:10],data[10:]]),path,False,start,start+10)
            self.assertEqual(diagnostic.summarize(parsed,['a'],False)['outcome'],'incomplete_response')
        duplicate={'message':{'content':json.dumps(answer(['a','a']))},'done':True}
        self.assertEqual(diagnostic.summarize([duplicate],['a','b'],False)['outcome'],'invalid_final_answer')
        self.assertEqual(diagnostic.summarize([{'error':'parser failed'}],['a'],True)['outcome'],'server_error')
        # A plausible answer without final completion is still incomplete.
        duplicate['done']=False
        self.assertEqual(diagnostic.summarize([duplicate],['a','b'],False)['outcome'],'incomplete_response')

    def test_request_is_label_free_and_transport_is_only_difference(self):
        records=[{'record_id':'a','language':'Hebrew','transcript_id':'x','target_negator':'no',
            'target_utterance':'no','context_before':[],'context_after':[],
            'sampling_label':'Denial','coder_1':{'bloom_label':'Denial'},'bloom_1':'Denial'}]
        buffered=diagnostic.request_payload(records,'frozen',0,False)
        streaming=diagnostic.request_payload(records,'frozen',0,True)
        self.assertEqual({k:v for k,v in buffered.items() if k!='stream'},
                         {k:v for k,v in streaming.items() if k!='stream'})
        for field in ['sampling_label','coder_1','bloom_1']:
            self.assertNotIn(field,buffered['messages'][1]['content'])
        with tempfile.TemporaryDirectory() as directory:
            response=Response([json.dumps({'done':False,'message':{'content':'','thinking':'partial'}}).encode()])
            with patch.object(diagnostic.urllib.request,'urlopen',return_value=response):
                result=diagnostic.run_request('http://local.test/api/chat',buffered,Path(directory),10)
            self.assertEqual(result['outcome'],'incomplete_response')
            self.assertTrue((Path(directory)/'request.json').exists())
            self.assertFalse(list(Path(directory).glob('*predictions*')))

    def test_invalid_utf8_is_preserved_for_diagnosis(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);start=time.monotonic()
            with self.assertRaises(UnicodeDecodeError):
                diagnostic.collect(Response([b'{"x":"\xff"}']),path,False,start,start+10)
            self.assertEqual((path/'response-body.bin').read_bytes(),b'{"x":"\xff"}')

if __name__=='__main__':unittest.main()
