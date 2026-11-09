"""Professional verification/membership and patient chart consent via real public APIs."""
import os
import re
import time
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

BASE = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') + '/api'


def call(method, path, actor=None, **kwargs):
    return requests.request(method, BASE + path, headers=actor['headers'] if actor else {}, timeout=30, **kwargs)


@pytest.fixture(scope='module')
def ctx():
    env = dotenv_values('/app/backend/.env')
    client = MongoClient(env['MONGO_URL'])
    db = client[env['DB_NAME']]
    state = {'db': db, 'uids': [], 'consents': [], 'records': [], 'orgs': [], 'appts': [], 'docs': []}
    try:
        text = Path('/app/memory/test_credentials.md').read_text()
        for role in ('Patient', 'Doctor', 'Admin'):
            row = re.search(r'\|\s*' + role + r'\s*\|\s*([^|]+)\|\s*([^|]+)\|', text)
            assert row, 'Missing documented credential for ' + role
            r = call('POST', '/auth/login', json={'email': row[1].strip(), 'password': row[2].strip()})
            if r.status_code != 200:
                pytest.skip('Documented login unavailable: ' + role)
            state['documented_' + role.lower()] = {'headers': {'Authorization': 'Bearer ' + r.json()['token']}, 'user': r.json()['user']}
        for key, role in [('patient', 'patient'), ('other_patient', 'patient'), ('pending_doctor', 'doctor'), ('nonmember', 'doctor'), ('doctor', 'doctor'), ('lab', 'lab'), ('pharmacy', 'pharmacy'), ('insurer', 'insurer'), ('partner', 'partner')]:
            body = {'name': 'TEST_Clinical ' + key, 'email': 'TEST_clinical_' + uuid.uuid4().hex[:16] + '@wyshcare.io', 'password': 'TEST_ClinicalPass123!', 'role': role, 'organization_name': 'TEST_Clinical QA', 'registration_number': 'TEST_' + uuid.uuid4().hex[:12]}
            r = call('POST', '/auth/signup', json=body)
            assert r.status_code == 200, 'Isolated signup failed: ' + key
            data = r.json()
            state['uids'].append(data['user']['user_id'])
            state[key] = {'headers': {'Authorization': 'Bearer ' + data['token']}, 'user': data['user']}
        for key in ('nonmember', 'doctor'):
            uid = state[key]['user']['user_id']
            r = call('POST', '/auth/partners/' + uid + '/verification', state['documented_admin'], json={'decision': 'APPROVED'})
            assert r.status_code == 200 and r.json()['verification_status'] == 'APPROVED'
            persisted = call('GET', '/auth/me', state[key])
            assert persisted.json()['verification_status'] == 'APPROVED'
        r = call('POST', '/organizations', state['documented_admin'], json={'name': 'TEST_Clinical QA ' + uuid.uuid4().hex[:8], 'kind': 'clinic'})
        assert r.status_code == 200
        state['org'] = r.json()['organization_id']
        state['orgs'].append(state['org'])
        uid = state['doctor']['user']['user_id']
        r = call('POST', '/organizations/' + state['org'] + '/members/' + uid, state['documented_admin'])
        assert r.status_code == 200 and r.json() == {'ok': True}
        assert db.wysh_organization_memberships.find_one({'organization_id': state['org'], 'user_id': uid})['status'] == 'ACTIVE'
        yield state
    finally:
        for cid in state['consents']:
            db.wysh_chart_consents.delete_one({'consent_id': cid})
            assert db.wysh_chart_consents.count_documents({'consent_id': cid}) == 0
        for rid in state['records']:
            db.wysh_health_records.delete_one({'record_id': rid})
            assert db.wysh_health_records.count_documents({'record_id': rid}) == 0
        for aid in state['appts']:
            db.wysh_appointments.delete_one({'appointment_id': aid})
        for did in state['docs']:
            db.wysh_lab_reports.delete_one({'document_id': did})
        for oid in state['orgs']:
            db.wysh_organizations.delete_one({'organization_id': oid})
        for uid in state['uids']:
            db.wysh_organization_memberships.delete_many({'user_id': uid})
            db.wysh_users.delete_one({'user_id': uid})
            db.wysh_identities.delete_one({'user_id': uid})
            assert db.wysh_users.count_documents({'user_id': uid}) == 0
        client.close()


def grant(ctx, scopes=None, expiry=None, doctor='doctor'):
    r = call('POST', '/consents', ctx['patient'], json={'grantee_id': ctx[doctor]['user']['user_id'], 'scopes': scopes if scopes is not None else ['records'], 'expires_at': expiry or (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()})
    if r.status_code == 200:
        ctx['consents'].append(r.json()['consent_id'])
    return r


def chart(ctx, doctor='doctor'):
    return call('GET', '/records', ctx[doctor], params={'patient_id': ctx['patient']['user']['user_id']})


def revoke(ctx, cid):
    r = call('POST', '/consents/' + cid + '/revoke', ctx['patient'])
    assert r.status_code == 200 and r.json() == {'ok': True}


def appointment(ctx, doctor, status):
    aid = 'TEST_apt_' + uuid.uuid4().hex[:16]
    ctx['appts'].append(aid)
    ctx['db'].wysh_appointments.insert_one({'appointment_id': aid, 'doctor_id': ctx[doctor]['user']['user_id'], 'patient_id': ctx['patient']['user']['user_id'], 'status': status, 'scheduled_at': (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(), 'created_at': datetime.now(timezone.utc).isoformat()})
    return aid


def test_health():
    r = call('GET', '/health')
    assert r.status_code == 200 and r.json() == {'status': 'healthy'}


def test_unverified_professional_roles_denied(ctx):
    for key in ('pending_doctor', 'lab', 'pharmacy', 'insurer', 'partner'):
        r = chart(ctx, key)
        assert r.status_code == 403 and r.json()['detail'] == 'Not allowed', key
    r = call('GET', '/availability/me', ctx['pending_doctor'])
    assert r.status_code == 403 and r.json()['detail'] == 'Account verification is pending'


def test_approved_doctor_without_membership_denied(ctx):
    r = call('GET', '/availability/me', ctx['nonmember'])
    assert r.status_code == 403 and r.json()['detail'] == 'Active organization membership is required'


def test_inactive_membership_denied(ctx):
    uid = ctx['nonmember']['user']['user_id']
    ctx['db'].wysh_organization_memberships.insert_one({'organization_id': ctx['org'], 'user_id': uid, 'status': 'INACTIVE'})
    r = call('GET', '/availability/me', ctx['nonmember'])
    assert r.status_code == 403 and r.json()['detail'] == 'Active organization membership is required'


def test_verified_member_and_documented_doctor_availability(ctx):
    for key in ('doctor', 'documented_doctor'):
        r = call('GET', '/availability/me', ctx[key])
        assert r.status_code == 200 and r.json()['doctor_id'] == ctx[key]['user']['user_id']
        assert isinstance(r.json()['blocks'], list)


def test_no_relationship_denies_records_read_and_write(ctx):
    r = chart(ctx)
    assert r.status_code == 403 and r.json()['detail'] == 'Not allowed'
    r = call('POST', '/records', ctx['doctor'], json={'patient_id': ctx['patient']['user']['user_id'], 'title': 'TEST_Unauthorized', 'record_type': 'note'})
    if r.status_code == 200:
        ctx['records'].append(r.json()['record_id'])
    assert r.status_code == 403 and r.json()['detail'] == 'Not allowed'


def test_patient_own_records_and_other_patient_denied(ctx):
    r = call('POST', '/records', ctx['patient'], json={'title': 'TEST_Patient Own', 'record_type': 'note'})
    assert r.status_code == 200
    rec = r.json(); ctx['records'].append(rec['record_id'])
    assert rec['patient_id'] == ctx['patient']['user']['user_id'] and rec['title'] == 'TEST_Patient Own'
    r = call('GET', '/records', ctx['patient'])
    assert r.status_code == 200 and any(v['record_id'] == rec['record_id'] and v['title'] == 'TEST_Patient Own' for v in r.json())
    r = chart(ctx, 'other_patient')
    assert r.status_code == 403 and r.json()['detail'] == 'Not allowed'


def test_consent_grant_persistence_doctor_read_write_and_revoke(ctx):
    r = grant(ctx)
    assert r.status_code == 200
    consent = r.json(); cid = consent['consent_id']
    try:
        assert consent['patient_id'] == ctx['patient']['user']['user_id'] and consent['scopes'] == ['records'] and consent['status'] == 'active'
        mine = call('GET', '/consents/mine', ctx['patient'])
        assert mine.status_code == 200 and any(v['consent_id'] == cid and v['scopes'] == ['records'] for v in mine.json())
        assert ctx['db'].wysh_appointments.count_documents({'doctor_id': ctx['doctor']['user']['user_id'], 'patient_id': ctx['patient']['user']['user_id']}) == 0
        r = chart(ctx)
        assert r.status_code == 200 and isinstance(r.json(), list)
        r = call('POST', '/records', ctx['doctor'], json={'patient_id': ctx['patient']['user']['user_id'], 'title': 'TEST_Consent Doctor Note', 'record_type': 'note'})
        assert r.status_code == 200
        rec = r.json(); ctx['records'].append(rec['record_id'])
        assert rec['author_id'] == ctx['doctor']['user']['user_id']
        r = chart(ctx)
        assert any(v['record_id'] == rec['record_id'] and v['title'] == 'TEST_Consent Doctor Note' for v in r.json())
        r = call('POST', '/consents/' + cid + '/revoke', ctx['other_patient'])
        assert r.status_code == 404 and r.json()['detail'] == 'Active consent not found'
    finally:
        revoke(ctx, cid)
    mine = call('GET', '/consents/mine', ctx['patient'])
    assert any(v['consent_id'] == cid and v['status'] == 'revoked' for v in mine.json())
    assert chart(ctx).status_code == 403


def test_invalid_scope_empty_scope_and_past_expiry_rejected(ctx):
    for scopes, expiry, expected in [(['all'], None, 400), ([], None, 422), (['records'], (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), 400), (['records'], 'invalid', 400)]:
        r = grant(ctx, scopes, expiry)
        assert r.status_code == expected and r.json()['detail']


def test_wrong_scope_does_not_grant_records(ctx):
    r = grant(ctx, ['labs']); assert r.status_code == 200
    try:
        assert chart(ctx).status_code == 403
    finally:
        revoke(ctx, r.json()['consent_id'])


def test_consent_cannot_bypass_verification_or_membership(ctx):
    for key in ('pending_doctor', 'nonmember'):
        r = grant(ctx, doctor=key); assert r.status_code == 200
        try:
            denied = chart(ctx, key)
            assert denied.status_code == 403 and denied.json()['detail'] == 'Not allowed'
        finally:
            revoke(ctx, r.json()['consent_id'])


def test_expired_utc_consent_denied(ctx):
    r = grant(ctx, expiry=(datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()); assert r.status_code == 200
    try:
        time.sleep(3)
        r2 = chart(ctx)
        assert r2.status_code == 403 and r2.json()['detail'] == 'Not allowed'
    finally:
        revoke(ctx, r.json()['consent_id'])


def test_expired_offset_consent_denied(ctx):
    expiry = (datetime.now(timezone.utc) + timedelta(seconds=2)).astimezone(timezone(timedelta(hours=10))).isoformat()
    r = grant(ctx, expiry=expiry); assert r.status_code == 200
    try:
        time.sleep(3)
        r2 = chart(ctx)
        assert r2.status_code == 403, 'Expired +10:00 consent still authorizes chart: HTTP ' + str(r2.status_code)
    finally:
        revoke(ctx, r.json()['consent_id'])


def test_unexpired_negative_offset_consent_authorizes(ctx):
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).astimezone(timezone(timedelta(hours=-10))).isoformat()
    r = grant(ctx, expiry=expiry); assert r.status_code == 200
    try:
        r2 = chart(ctx)
        assert r2.status_code == 200 and isinstance(r2.json(), list), 'Unexpired -10:00 consent denied: HTTP ' + str(r2.status_code)
    finally:
        revoke(ctx, r.json()['consent_id'])


def test_naive_expiry_rejected_without_server_error(ctx):
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(tzinfo=None).isoformat()
    r = grant(ctx, expiry=expiry)
    assert r.status_code in (400, 422) and r.json()['detail'], 'Timezone-free expiry returns HTTP ' + str(r.status_code)


def test_scheduled_completed_relationship_and_cancelled_denial(ctx):
    for status in ('scheduled', 'completed', 'cancelled'):
        aid = appointment(ctx, 'doctor', status)
        try:
            r = chart(ctx)
            assert r.status_code == (403 if status == 'cancelled' else 200), status
            assert r.json()['detail'] if status == 'cancelled' else isinstance(r.json(), list)
        finally:
            ctx['db'].wysh_appointments.delete_one({'appointment_id': aid})


def test_unverified_appointment_doctor_denied_ocr_chart(ctx):
    aid = appointment(ctx, 'pending_doctor', 'scheduled')
    did = 'TEST_lab_' + uuid.uuid4().hex[:16]; ctx['docs'].append(did)
    ctx['db'].wysh_lab_reports.insert_one({'document_id': did, 'patient_id': ctx['patient']['user']['user_id'], 'document_kind': 'lab_report', 'review_state': 'pending', 'extracted': {'notes': 'TEST_Synthetic clinical content'}, 'created_at': datetime.now(timezone.utc).isoformat()})
    try:
        r = call('GET', '/ocr/documents/' + did, ctx['pending_doctor'])
        assert r.status_code == 403, 'Unverified doctor reads OCR chart: HTTP ' + str(r.status_code)
    finally:
        ctx['db'].wysh_appointments.delete_one({'appointment_id': aid})


def test_nonmember_appointment_doctor_denied_clinical_queue(ctx):
    aid = appointment(ctx, 'nonmember', 'scheduled')
    try:
        r = call('GET', '/appointments/mine', ctx['nonmember'])
        assert r.status_code == 403, 'Nonmember doctor reads appointment and patient data: HTTP ' + str(r.status_code)
    finally:
        ctx['db'].wysh_appointments.delete_one({'appointment_id': aid})