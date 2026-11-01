from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    assert client.get('/health').json()['clinical_use_authorized'] is False

def test_reject_real_patient():
    response = client.post('/v1/snapshots', json={'tenant_id':'tenant-1','patient_id':'patient-1','synthetic':True})
    assert response.status_code == 403

def test_reject_unmarked_data():
    response = client.post('/v1/snapshots', json={'tenant_id':'synthetic-tenant','patient_id':'synthetic-patient'})
    assert response.status_code == 403

def test_snapshot_requires_review():
    payload = {'tenant_id':'synthetic-tenant','patient_id':'synthetic-patient','synthetic':True,
      'facts':[{'statement':'Synthetic example only','evidence':[{'source_id':'synthetic-observation-1','source_type':'observation','recorded_at':'2026-01-01T00:00:00Z'}]}]}
    response = client.post('/v1/snapshots', json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body['state'] == 'DRAFT'
    assert body['human_review_required'] is True
    assert body['clinical_use_authorized'] is False
    assert body['facts'][0]['evidence'][0]['source_id'] == 'synthetic-observation-1'

def test_prod_disabled(monkeypatch):
    monkeypatch.setenv('WMI_ENV','production')
    response = client.post('/v1/snapshots', json={'tenant_id':'synthetic-tenant','patient_id':'synthetic-patient','synthetic':True})
    assert response.status_code == 503
