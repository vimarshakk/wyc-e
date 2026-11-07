"""Public API authorization and synthetic local ABDM callback regression; no external ABDM calls."""
import os
import re
import uuid
from pathlib import Path
from datetime import datetime, timezone
import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

BASE = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') + '/api'


@pytest.fixture(scope='module')
def ctx():
    state = {'responses': []}
    text = Path('/app/memory/test_credentials.md').read_text()
    for role in ['Patient', 'Doctor', 'Admin']:
        row = re.search(r'\|\s*' + role + r'\s*\|\s*([^|]+)\|\s*([^|]+)\|', text)
        assert row
        r = requests.post(BASE+'/auth/login', json={'email':row[1].strip(),'password':row[2].strip()},timeout=30)
        if r.status_code != 200:
            pytest.skip('Documented auth unavailable')
        state[role.lower()] = {'Authorization':'Bearer '+r.json()['token']}
    # Read opaque credentials only for request construction/leak assertions; never print values.
    env = dotenv_values('/app/backend/.env')
    client = MongoClient(env['MONGO_URL'])
    state['db'] = db = client[env['DB_NAME']]
    secret = os.environ.get('ABDM_CALLBACK_SHARED_SECRET') or env.get('ABDM_CALLBACK_SHARED_SECRET')
    state['callback_headers'] = {'X-Callback-Secret':secret} if secret else None
    state['secrets'] = [os.environ.get(k) or env.get(k) for k in ('GOOGLE_CLIENT_SECRET','ABDM_CLIENT_SECRET','ABDM_CALLBACK_SHARED_SECRET') if os.environ.get(k) or env.get(k)]
    state['correlation'] = str(uuid.uuid4())
    state['pid'] = 'TEST_callback_'+uuid.uuid4().hex
    state['tid'] = 'TEST_transaction_'+uuid.uuid4().hex
    db.wysh_abdm_transactions.insert_one({'transaction_id':state['tid'],'request_id':state['correlation'],'patient_id':state['pid'],'kind':'hip_link_token','status':'submitted','created_at':datetime.now(timezone.utc).isoformat()})
    try:
        yield state
    finally:
        db.wysh_abdm_transactions.delete_one({'transaction_id':state['tid']})
        db.wysh_abdm_callback_events.delete_one({'correlation_id':state['correlation'],'event_type':'link_token'})
        db.wysh_abdm_patient_links.delete_one({'patient_id':state['pid']})
        client.close()


def call(ctx, method, path, headers=None, **kw):
    r = requests.request(method,BASE+path,headers=headers,timeout=30,**kw)
    ctx['responses'].append(r.text)
    return r


def test_admin_endpoints_protected(ctx):
    for path in ['/calendar/status','/calendar/connect','/abdm/status']:
        for role, expected in [(None,401),('patient',403),('doctor',403)]:
            r = call(ctx,'GET',path,ctx.get(role))
            assert r.status_code == expected and r.json()['detail']


def test_admin_status_truthful(ctx):
    r = call(ctx,'GET','/abdm/status',ctx['admin'])
    assert r.status_code == 200
    assert r.json()['sandbox_configured'] is True
    assert r.json()['hie_cm'] == 'M2 link-token ready'
    r = call(ctx,'GET','/calendar/status',ctx['admin'])
    assert r.status_code == 200 and r.json()['connected'] is False


def test_callback_missing_and_wrong_secret(ctx):
    for headers in [None,{'X-Callback-Secret':'TEST_wrong'}]:
        r = call(ctx,'POST','/abdm/v3/hip/token/on-generate-token',headers,json={'requestId':ctx['correlation'],'linkToken':'TEST_never_accepted'})
        assert r.status_code == 401 and r.json()['detail'] == 'Unauthorized callback'
    assert ctx['db'].wysh_abdm_transactions.find_one({'transaction_id':ctx['tid']})['status'] == 'submitted'


def test_callback_correlation_validation(ctx):
    if not ctx['callback_headers']:
        pytest.skip('Opaque callback credential unavailable to test process')
    for payload, expected in [({},400),({'requestId':str(uuid.uuid4())},404)]:
        r = call(ctx,'POST','/abdm/v3/hip/token/on-generate-token',ctx['callback_headers'],json=payload)
        assert r.status_code == expected and r.json()['detail']


def test_callback_duplicate_is_idempotent(ctx):
    if not ctx['callback_headers']:
        pytest.skip('Opaque callback credential unavailable to test process')
    for token in ['TEST_synthetic_link_token','TEST_duplicate_must_not_replace']:
        r = call(ctx,'POST','/abdm/v3/hip/token/on-generate-token',ctx['callback_headers'],json={'requestId':ctx['correlation'],'linkToken':token})
        assert r.status_code == 202 and r.json() == {'status':'accepted'}
        link = ctx['db'].wysh_abdm_patient_links.find_one({'patient_id':ctx['pid']})
        assert link['status'] == 'token_ready' and 'TEST_' not in link['encrypted_link_token']
        if token == 'TEST_synthetic_link_token':
            first = link['encrypted_link_token']
        else:
            assert link['encrypted_link_token'] == first
    assert ctx['db'].wysh_abdm_callback_events.count_documents({'correlation_id':ctx['correlation']}) == 1
    assert ctx['db'].wysh_abdm_transactions.find_one({'transaction_id':ctx['tid']})['status'] == 'token_ready'


def test_callback_invalid_body_returns_4xx(ctx):
    if not ctx['callback_headers']:
        pytest.skip('Opaque callback credential unavailable to test process')
    r = call(ctx,'POST','/abdm/v3/hip/token/on-generate-token',ctx['callback_headers'],json=[])
    assert r.status_code in (400,422), 'Malformed callback returned HTTP '+str(r.status_code)


def test_responses_and_logs_no_configured_secrets(ctx):
    if not ctx['secrets']:
        pytest.skip('No opaque credentials available for exact-value leak comparison')
    content = '\n'.join(ctx['responses'])
    paths = list(Path('/var/log/supervisor').glob('backend*.log'))
    assert paths, 'No backend logs available for verification'
    content += '\n'.join(p.read_text(errors='replace') for p in paths)
    for index, secret in enumerate(ctx['secrets']):
        assert secret not in content, 'Configured secret leak detected (opaque index '+str(index)+')'


def test_public_signup_cannot_grant_admin(ctx):
    response = call(ctx,'POST','/auth/signup',json={'name':'TEST_Security Admin','email':'test_privilege_'+uuid.uuid4().hex[:12]+'@wyshcare.io','password':'TEST_Security123!','role':'admin'})
    if response.status_code == 200:
        data = response.json()
        uid = data['user']['user_id']
        try:
            privileged = call(ctx,'GET','/abdm/status',{'Authorization':'Bearer '+data['token']})
            print('Unauthenticated admin signup granted protected ABDM status: HTTP',privileged.status_code)
        finally:
            ctx['db'].wysh_users.delete_one({'user_id':uid})
            ctx['db'].wysh_identities.delete_one({'user_id':uid})
    assert response.status_code in (403,422), 'Public signup accepted administrator role: HTTP '+str(response.status_code)