"""Opt-in actual BackendPublisher -> Spring -> PostgreSQL acceptance.

Requires a running migrated backend and SMARTPHSET_INTEGRATION_BACKEND_URL.
Leaves uniquely named synthetic scan records; never uses Roboflow or camera.
"""
import json
import os
from pathlib import Path
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from backend_publisher import BackendPublisher


@unittest.skipUnless(os.environ.get('SMARTPHSET_INTEGRATION_BACKEND_URL'),
                     'opt-in: requires running Spring/PostgreSQL')
class LiveBackendIntegrationTests(unittest.TestCase):
    def test_publisher_persistence_duplicate_queries_and_auth(self):
        base=os.environ['SMARTPHSET_INTEGRATION_BACKEND_URL'].rstrip('/')
        self.assertTrue(base.startswith(('http://','https://')))
        key=os.environ.get('SMARTPHSET_AI_INGEST_KEY','')
        fixture=json.loads((Path(__file__).parent/'fixtures/ai-detection.json').read_text())
        camera='phase7-'+uuid4().hex
        fixture.update(camera_id=camera,event_id=str(uuid4()))
        def request(method,path,payload=None,auth=None):
            headers={'Content-Type':'application/json'}
            if auth is not None:headers['X-SmartPhset-AI-Key']=auth
            req=Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,
                        headers=headers,method=method)
            try:
                with urlopen(req,timeout=5) as response:
                    return response.status,json.load(response)
            except HTTPError as exc:
                return exc.code,json.load(exc)
        status,saved=request('POST','/api/ai/detections',fixture,key)
        self.assertEqual(status,201)
        status,duplicate=request('POST','/api/ai/detections',fixture,key)
        self.assertEqual(status,200)
        differences = {field: {'initial': saved.get(field), 'duplicate': duplicate.get(field)}
                       for field in sorted(saved.keys() | duplicate.keys())
                       if saved.get(field) != duplicate.get(field)}
        self.assertEqual(saved, duplicate, 'First/duplicate field differences: ' +
                         json.dumps(differences, indent=2))
        for field,value in fixture.items():
            if field not in ('captured_at','boxes'):self.assertEqual(saved[field],value)
        self.assertEqual(sorted(saved['boxes'], key=lambda b:b['label']),
                         sorted(fixture['boxes'], key=lambda b:b['label']))
        from datetime import datetime
        self.assertEqual(datetime.fromisoformat(saved['captured_at']),datetime.fromisoformat(fixture['captured_at']))
        status,latest=request('GET','/api/ai/detections/latest?camera='+camera)
        self.assertEqual(status,200);self.assertEqual(latest['event_id'],fixture['event_id'])
        status,history=request('GET','/api/ai/detections?camera='+camera+'&limit=1')
        self.assertEqual(status,200);self.assertEqual(len(history),1)
        self.assertEqual(history[0]['id'],saved['id'])
        self.assertEqual(request('GET','/api/ai/detections?camera='+camera+'&limit=101')[0],400)
        if key:
            for supplied in (None,key+'-wrong'):
                self.assertEqual(request('POST','/api/ai/detections',fixture,supplied)[0],401)
        else:
            self.assertEqual(request('POST','/api/ai/detections',fixture)[0],200)
        complete=threading.Event(); received=[];errors=[]
        def observing_opener(req,timeout):
            try:
                response=urlopen(req,timeout=timeout)
                received.append(response.status)
                return response
            except Exception as exc:
                errors.append(type(exc).__name__)
                raise
            finally:complete.set()
        publisher=BackendPublisher(base,ingest_key=key,opener=observing_opener)
        summary={name:fixture[name] for name in ('verdict','message','severity','n_healthy','n_contaminated','max_conf','max_contaminated_conf','boxes')}
        summary.update(shape=(720,1280),ms=84,captured_at='2026-10-08T10:01:00Z')
        try:
            self.assertTrue(publisher.offer(summary,camera))
            self.assertTrue(complete.wait(6),'publisher request did not finish')
            self.assertEqual(errors,[]);self.assertEqual(received,[201])
        finally:
            publisher.close();publisher.worker.join(6)
        status,history=request('GET','/api/ai/detections?camera='+camera+'&limit=100')
        self.assertEqual(status,200);self.assertEqual(len(history),2)
        self.assertEqual(history[0]['captured_at'],'2026-10-08T10:01:00Z')
        self.assertEqual(sorted(history[0]['boxes'], key=lambda b:b['label']),
                         sorted(fixture['boxes'], key=lambda b:b['label']))
