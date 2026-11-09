"""Partner provisioning, role authentication and consent-bound authorization via public APIs."""
import os
import re
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

BASE = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') + '/api'
ROLES = ('lab', 'pharmacy', 'insurer', 'partner')


def request(method, path, **kwargs):
    return requests.request(method, BASE + path, timeout=30, **kwargs)


@pytest.fixture(scope='module')
def ctx():
    text = Path('/app/memory/test_credentials.md').read_text()
    state = {'created_ids': [], 'created_records': [], 'partners': {}}
    env = dotenv_values('/app/backend/.env')
    client = MongoClient(env['MONGO_URL'])
    state['db'] = client[env['DB_NAME']]
    try:
        for role in ('Patient', 'Doctor', 'Admin', 'Lab'):
            row = re.search(r'\|\s*' + role + r'\s*\|\s*([^|]+)\|\s*([^|]+)\|', text)
            assert row, f'Missing documented {role} credential'
            payload = {'email': row[1].strip(), 'password': row[2].strip()}
            response = request('POST', '/auth/login', json=payload)
            if response.status_code != 200:
                pytest.skip(f'Documented {role} login failed: HTTP {response.status_code}')
            state[role.lower()] = {'headers': {'Authorization': 'Bearer ' + response.json()['token']}, 'user': response.json()['user'], 'credentials': payload}
        yield state
    finally:
        db = state['db']
        for rid in state['created_records']:
            db.wysh_health_records.delete_one({'record_id': rid})
            assert db.wysh_health_records.count_documents({'record_id': rid}) == 0
        for uid in state['created_ids']:
            db.wysh_users.delete_one({'user_id': uid})
            db.wysh_identities.delete_one({'user_id': uid})
            assert db.wysh_users.count_documents({'user_id': uid}) == 0
        client.close()


def payload(partner_role, **updates):
    body = {'email': f'TEST_partner_{uuid.uuid4().hex[:12]}@wyshcare.io', 'password': 'TEST_PartnerPass123!', 'name': 'TEST_Partner QA', 'role': partner_role, 'organization_name': 'TEST_Consent QA'}
    body.update(updates)
    return body


def provision(ctx, body):
    response = request('POST', '/auth/partners', headers=ctx['admin']['headers'], json=body)
    if response.status_code == 201:
        ctx['created_ids'].append(response.json()['user_id'])
    return response


def test_health():
    response = request('GET', '/health')
    assert response.status_code == 200 and response.json() == {'status': 'healthy'}


def test_public_signup_rejects_privileged_roles(ctx):
    for role in (*ROLES, 'doctor', 'admin'):
        body = payload(role)
        response = request('POST', '/auth/signup', json=body)
        if response.status_code == 200:
            ctx['created_ids'].append(response.json()['user']['user_id'])
        assert response.status_code == 403 and response.json()['detail'] == 'Only patient self-registration is available', role
        assert ctx['db'].wysh_users.count_documents({'email': body['email']}) == 0


def test_existing_role_login_and_me(ctx):
    for role in ('patient', 'doctor', 'admin', 'lab'):
        assert ctx[role]['user']['role'] == role
        response = request('GET', '/auth/me', headers=ctx[role]['headers'])
        assert response.status_code == 200
        assert response.json()['user_id'] == ctx[role]['user']['user_id']
        assert response.json()['email'] == ctx[role]['credentials']['email']
        assert 'password_hash' not in response.json() and '_id' not in response.json()


def test_provision_requires_admin(ctx):
    for role, expected in ((None, 401), ('patient', 403), ('doctor', 403), ('lab', 403)):
        body = payload('lab')
        response = request('POST', '/auth/partners', json=body, headers=ctx[role]['headers'] if role else {})
        if response.status_code == 201:
            ctx['created_ids'].append(response.json()['user_id'])
        assert response.status_code == expected and response.json()['detail']
        assert ctx['db'].wysh_users.count_documents({'email': body['email']}) == 0


def test_admin_provisions_all_partner_roles_and_persistence(ctx):
    for role in ROLES:
        body = payload(role)
        response = provision(ctx, body)
        assert response.status_code == 201, f'{role}: HTTP {response.status_code}'
        data = response.json()
        for field in ('email', 'name', 'role', 'organization_name'):
            assert data[field] == body[field]
        assert data['partner_status'] == 'active'
        assert isinstance(data['user_id'], str) and data['wysh_id'].startswith('WYSH-')
        assert 'password_hash' not in data and '_id' not in data
        login = request('POST', '/auth/login', json={'email': body['email'], 'password': body['password']})
        assert login.status_code == 200 and login.json()['user']['role'] == role
        headers = {'Authorization': 'Bearer ' + login.json()['token']}
        persisted = request('GET', '/auth/me', headers=headers)
        assert persisted.status_code == 200 and persisted.json()['organization_name'] == body['organization_name']
        identity = request('GET', '/wyshid/me', headers=headers)
        assert identity.status_code == 200 and identity.json()['wysh_id'] == data['wysh_id']
        ctx['partners'][role] = {'body': body, 'headers': headers, 'user': data}


def test_duplicate_partner_email(ctx):
    response = provision(ctx, ctx['partners']['lab']['body'])
    assert response.status_code == 409 and response.json()['detail'] == 'Email already registered'


def test_provision_validation(ctx):
    for updates in ({'role': 'admin'}, {'role': 'patient'}, {'password': 'short'}, {'email': 'invalid'}, {'organization_name': ''}):
        response = provision(ctx, payload('lab', **updates))
        assert response.status_code == 422 and isinstance(response.json()['detail'], list)


def test_partner_roles_cannot_provision(ctx):
    for role in ROLES:
        response = request('POST', '/auth/partners', headers=ctx['partners'][role]['headers'], json=payload('partner'))
        if response.status_code == 201:
            ctx['created_ids'].append(response.json()['user_id'])
        assert response.status_code == 403 and response.json()['detail'] == 'Insufficient permissions'


def test_partner_roles_denied_patient_and_admin_data(ctx):
    patient = ctx['patient']['user']
    paths = ('/records?patient_id=' + patient['user_id'], '/wyshid/' + patient['wysh_id'], '/admin/users', '/admin/stats', '/admin/audit', '/billing/patients', '/nhcx/episodes/mine', '/abdm/my-status')
    for role in ROLES:
        for path in paths:
            response = request('GET', path, headers=ctx['partners'][role]['headers'])
            assert response.status_code == 403 and response.json()['detail'], f'{role} {path}: HTTP {response.status_code}'


def test_partner_self_scoped_queues_empty(ctx):
    for role in ROLES:
        for path in ('/records', '/records/timeline', '/ocr/documents', '/appointments/mine', '/consultations/mine', '/billing/invoices/mine'):
            response = request('GET', path, headers=ctx['partners'][role]['headers'])
            assert response.status_code == 200 and response.json() == [], f'{role} {path}'


def test_partner_cannot_book_without_patient_role(ctx):
    response = request('POST', '/appointments', headers=ctx['lab']['headers'], json={'doctor_id': ctx['doctor']['user']['user_id'], 'scheduled_at': '2099-01-01T09:00:00+05:30'})
    assert response.status_code == 403 and response.json()['detail'] == 'Insufficient permissions'


def test_existing_dashboard_api_access(ctx):
    for role, path in (('patient', '/records/timeline'), ('doctor', '/appointments/mine'), ('admin', '/admin/stats')):
        response = request('GET', path, headers=ctx[role]['headers'])
        assert response.status_code == 200
        if role == 'admin':
            assert isinstance(response.json()['patients'], int)
        else:
            assert isinstance(response.json(), list)


def test_bcrypt_hash_format(ctx):
    for role in ('patient', 'doctor', 'admin', 'lab'):
        user = ctx['db'].wysh_users.find_one({'user_id': ctx[role]['user']['user_id']})
        assert user['password_hash'].startswith('$2b$')


def test_login_sets_httponly_cookie(ctx):
    response = request('POST', '/auth/login', json=ctx['lab']['credentials'])
    assert response.status_code == 200 and response.json()['user']['role'] == 'lab'
    cookies = response.raw.headers.getlist('Set-Cookie')
    auth_cookies = [cookie for cookie in cookies if cookie.startswith(('session_token=', 'access_token=', 'jwt='))]
    assert auth_cookies and all('httponly' in cookie.lower() for cookie in auth_cookies), 'Password login does not set an auth httpOnly cookie (JWT is stored in localStorage); infrastructure cookies do not count'


def test_lockout_after_five_failed_attempts(ctx):
    body = payload('partner')
    created = provision(ctx, body)
    assert created.status_code == 201
    for attempt in range(5):
        response = request('POST', '/auth/login', json={'email': body['email'], 'password': 'TEST_WrongPassword!'})
        assert response.status_code in (401, 403, 423, 429) and response.json()['detail']
    response = request('POST', '/auth/login', json={'email': body['email'], 'password': body['password']})
    assert response.status_code in (403, 423, 429), 'Correct login remains HTTP ' + str(response.status_code) + ' after five failed attempts'
    assert response.json()['detail']


def test_cors_explicit_origin_and_credentials():
    origin = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
    response = request('OPTIONS', '/auth/login', headers={'Origin': origin, 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type'})
    assert response.status_code == 200
    assert response.headers.get('Access-Control-Allow-Origin') == origin
    assert response.headers.get('Access-Control-Allow-Credentials') == 'true'