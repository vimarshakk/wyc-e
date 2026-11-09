"""Audit safety regressions: public auth lifecycle, durable lockout, repository hygiene and CORS."""
import os
import re
import subprocess
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

BASE = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
ROOT = Path('/app')
HTTP = requests.Session()


def api(method, path, **kwargs):
    return HTTP.request(method, BASE + '/api' + path, timeout=30, **kwargs)


@pytest.fixture(scope='module')
def ctx():
    env = dotenv_values(ROOT / 'backend/.env')
    client = MongoClient(env['MONGO_URL'])
    state = {'db': client[env['DB_NAME']], 'ids': [], 'attempt_ids': [], 'credentials': {}}
    text = (ROOT / 'memory/test_credentials.md').read_text()
    for role in ('Patient', 'Doctor', 'Admin'):
        row = re.search(r'\|\s*' + role + r'\s*\|\s*([^|]+)\|\s*([^|]+)\|', text)
        assert row, f'Missing documented {role} credentials'
        state['credentials'][role.lower()] = {'email': row[1].strip(), 'password': row[2].strip()}
    try:
        yield state
    finally:
        for uid in state['ids']:
            state['db'].wysh_users.delete_one({'user_id': uid})
            state['db'].wysh_identities.delete_one({'user_id': uid})
            assert state['db'].wysh_users.count_documents({'user_id': uid}) == 0
        for aid in state['attempt_ids']:
            state['db'].wysh_login_attempts.delete_one({'_id': aid})
            assert state['db'].wysh_login_attempts.count_documents({'_id': aid}) == 0
        client.close()


@pytest.fixture
def disposable(ctx):
    body = {'email': f'test_safety_{uuid.uuid4().hex}@wyshcare.io', 'password': 'TEST_SafetyPass123!', 'name': 'TEST_Safety Patient', 'role': 'patient'}
    response = api('POST', '/auth/signup', json=body)
    assert response.status_code == 200, response.text
    uid = response.json()['user']['user_id']
    ctx['ids'].append(uid)
    response = api('GET', '/auth/me', headers={'Authorization': 'Bearer ' + response.json()['token']})
    assert response.status_code == 200 and response.json()['user_id'] == uid
    try:
        yield body
    finally:
        # Capture only documents belonging to this unique disposable email for exact-ID cleanup.
        docs = ctx['db'].wysh_login_attempts.find({'identifier': {'$regex': ':' + re.escape(body['email'].lower()) + '$'}})
        ctx['attempt_ids'].extend(doc['_id'] for doc in docs)


def attempt_record(ctx, email):
    docs = list(ctx['db'].wysh_login_attempts.find({'identifier': {'$regex': ':' + re.escape(email.lower()) + '$'}}))
    assert len(docs) == 1, f'Expected one durable email/IP attempt record, got {len(docs)}'
    return docs[0]


def test_health():
    response = api('GET', '/health')
    assert response.status_code == 200 and response.json() == {'status': 'healthy'}


@pytest.mark.parametrize('role', ['patient', 'doctor', 'admin'])
def test_existing_login_me_and_bcrypt(ctx, role):
    response = api('POST', '/auth/login', json=ctx['credentials'][role])
    assert response.status_code == 200, f'{role}: {response.status_code} {response.text}'
    data = response.json()
    assert data['user']['role'] == role and isinstance(data['token'], str)
    me = api('GET', '/auth/me', headers={'Authorization': 'Bearer ' + data['token']})
    assert me.status_code == 200 and me.json()['email'] == ctx['credentials'][role]['email']
    assert 'password_hash' not in me.json() and '_id' not in me.json()
    user = ctx['db'].wysh_users.find_one({'user_id': data['user']['user_id']})
    assert user['password_hash'].startswith('$2b$')


def test_lockout_exact_threshold(ctx, disposable):
    statuses = []
    for _ in range(6):
        response = api('POST', '/auth/login', json={'email': disposable['email'], 'password': 'TEST_WrongPassword!'})
        statuses.append(response.status_code)
        assert response.json()['detail']
    print('Exact-threshold statuses:', statuses)
    record = attempt_record(ctx, disposable['email'])
    print('Durable failed_count:', record['failed_count'], 'locked_until:', record.get('locked_until'))
    assert statuses == [401, 401, 401, 401, 401, 429]
    assert record['failed_count'] == 5 and record['locked_until']


def test_correct_password_denied_during_lockout(ctx, disposable):
    for _ in range(5):
        api('POST', '/auth/login', json={'email': disposable['email'], 'password': 'TEST_WrongPassword!'})
    response = api('POST', '/auth/login', json=disposable)
    assert response.status_code == 429 and response.json()['detail'] == 'Too many attempts. Try again later.'
    assert attempt_record(ctx, disposable['email'])['locked_until']


def test_success_clears_failed_state(ctx, disposable):
    for _ in range(2):
        response = api('POST', '/auth/login', json={'email': disposable['email'], 'password': 'TEST_WrongPassword!'})
        assert response.status_code == 401 and response.json()['detail'] == 'Invalid credentials'
    before = attempt_record(ctx, disposable['email'])
    assert before['failed_count'] == 2
    success = api('POST', '/auth/login', json=disposable)
    assert success.status_code == 200 and success.json()['user']['email'] == disposable['email']
    after = attempt_record(ctx, disposable['email'])
    assert after['failed_count'] == 0 and after['locked_until'] is None and after['cleared_at']
    response = api('POST', '/auth/login', json={'email': disposable['email'], 'password': 'TEST_WrongPassword!'})
    assert response.status_code == 401 and attempt_record(ctx, disposable['email'])['failed_count'] == 1


def test_password_login_httponly_cookie(disposable):
    response = api('POST', '/auth/login', json=disposable)
    assert response.status_code == 200 and response.json()['user']['role'] == 'patient'
    cookies = response.raw.headers.getlist('Set-Cookie')
    auth = [c for c in cookies if c.startswith(('session_token=', 'access_token=', 'jwt='))]
    assert auth and all('httponly' in c.lower() for c in auth), 'Password login returns JWT only; no auth httpOnly cookie'


def test_logout_revokes_authenticated_access(disposable):
    login = api('POST', '/auth/login', json=disposable)
    assert login.status_code == 200
    headers = {'Authorization': 'Bearer ' + login.json()['token']}
    logout = api('POST', '/auth/logout', headers=headers)
    assert logout.status_code == 200 and logout.json() == {'ok': True}
    me = api('GET', '/auth/me', headers=headers)
    assert me.status_code == 401, f'JWT replay after logout remains HTTP {me.status_code}'
    assert me.json()['detail'] == 'Not authenticated'


def test_unauthenticated_me_denied():
    response = api('GET', '/auth/me')
    assert response.status_code == 401 and response.json()['detail'] == 'Not authenticated'


def test_mixed_case_signup_can_login(ctx, disposable):
    body = dict(disposable, email=disposable['email'].replace('test_', 'TEST_', 1))
    # The case-distinct test account and its identity are captured for exact-ID cleanup.
    response = api('POST', '/auth/signup', json=body)
    assert response.status_code == 200, response.text
    ctx['ids'].append(response.json()['user']['user_id'])
    login = api('POST', '/auth/login', json=body)
    assert login.status_code == 200 and login.json()['user']['user_id'] == response.json()['user']['user_id'], 'Mixed-case signup login does not authenticate its own account'


def test_ignore_rules_cover_sensitive_artifacts():
    paths = ['.env', 'backend/.env', 'frontend/.env', 'backend/.env.production', 'test_reports/iteration_7.json', 'backend/example.log']
    result = subprocess.run(['git', 'check-ignore', '--no-index', *paths], cwd=ROOT, text=True, capture_output=True)
    assert set(result.stdout.splitlines()) == set(paths)


def test_no_sensitive_artifacts_tracked():
    result = subprocess.run(['git', 'ls-files', '--', '.env', '**/.env', '.env.*', '**/.env.*', '*.log', '**/*.log', 'test_reports/**', 'memory/test_credentials.md'], cwd=ROOT, text=True, capture_output=True, check=True)
    tracked = result.stdout.splitlines()
    print('Tracked sensitive/report artifacts:', len(tracked))
    assert tracked == [], f'{len(tracked)} report artifacts remain tracked despite ignore rules'


def test_cors_config_has_no_code_fallback():
    source = (ROOT / 'backend/app/core/config.py').read_text()
    assert 'CORS_ORIGINS: str = os.environ["CORS_ORIGINS"]' in source
    env = dotenv_values(ROOT / 'backend/.env')
    origins = env['CORS_ORIGINS'].split(',')
    print('Configured application CORS origins:', origins)
    assert origins and '*' not in origins and BASE in origins


def test_public_cors_observation():
    allowed = api('OPTIONS', '/auth/login', headers={'Origin': BASE, 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type'})
    print('Public allowed preflight:', allowed.status_code, dict(allowed.headers))
    assert allowed.status_code == 200 and allowed.headers.get('Access-Control-Allow-Credentials') == 'true'
    rejected = api('OPTIONS', '/auth/login', headers={'Origin': 'https://untrusted.invalid', 'Access-Control-Request-Method': 'POST'})
    print('Public untrusted preflight:', rejected.status_code, dict(rejected.headers), rejected.text)
    get = api('GET', '/health', headers={'Origin': BASE})
    print('Public health CORS:', get.headers.get('Access-Control-Allow-Origin'), get.headers.get('Access-Control-Allow-Credentials'))
    assert get.status_code == 200 and get.json() == {'status': 'healthy'}