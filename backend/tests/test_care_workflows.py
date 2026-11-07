"""Public API regression: secure OCR/review, care reminders, billing and telemedicine."""
import io
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pytest
import requests
import pymupdf
from PIL import Image, ImageDraw, ImageFont
from dotenv import dotenv_values
from pymongo import MongoClient

BASE = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') + '/api'


def call(method, path, actor=None, **kwargs):
    headers = {'Authorization': 'Bearer ' + actor['token']} if actor else {}
    return requests.request(method, BASE + path, headers=headers, timeout=180, **kwargs)


def ok(response, status=200):
    assert response.status_code == status, response.text[:500]
    data = response.json()
    assert '"_id"' not in response.text
    return data


def image_data(fmt='PNG', kind='prescription'):
    img = Image.new('RGB', (1200, 700), 'white')
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=30)
    text = ('TEST_Clinic Prescription\nDoctor: Dr Test Sharma\nPatient: TEST_OCR Patient\nDate: 2026-11-07\nDiagnosis: Fever\nParacetamol 500mg twice daily for 3 days\nTake after meals' if kind == 'prescription' else 'TEST_Diagnostics Laboratory\nPatient: TEST_OCR Patient\nDate: 2026-11-07\nHemoglobin: 13.5 g/dL (Reference 12.0-16.0)\nGlucose: 95 mg/dL (Reference 70-100)')
    draw.multiline_text((40, 50), text, font=font, fill='black', spacing=20)
    output = io.BytesIO()
    img.save(output, format=fmt)
    return output.getvalue()


@pytest.fixture(scope='module')
def ctx():
    state = {'created': {}, 'docs': [], 'invoices': [], 'reminders': [], 'appointments': [], 'consultations': [], 'notes': [], 'oauth_states': [], 'sessions': []}
    # Supplied accounts are login/read-only; writes use disposable TEST_ accounts.
    credential_text = Path('/app/memory/test_credentials.md').read_text()
    for role in ['Patient', 'Doctor', 'Admin']:
        row = re.search(r'\|\s*' + role + r'\s*\|\s*([^|]+)\|\s*([^|]+)\|', credential_text)
        assert row, 'Missing documented credentials'
        response = call('POST', '/auth/login', json={'email': row[1].strip(), 'password': row[2].strip()})
        if response.status_code != 200:
            pytest.skip('Supplied authentication unavailable')
        state['supplied_' + role.lower()] = ok(response)
    try:
        for name, role in [('patient', 'patient'), ('other', 'patient'), ('doctor', 'doctor')]:
            data = ok(call('POST', '/auth/signup', json={'name': 'TEST_Care ' + name, 'email': 'test_care_' + uuid.uuid4().hex[:12] + '@wyshcare.io', 'password': 'TEST_Care123!', 'role': role, 'specialty': 'Cardiology'}))
            state[name] = data
            state['created'][name] = data['user']['user_id']
        yield state
    finally:
        # No public deletion APIs exist. Cleanup exclusively captured test IDs.
        env = dotenv_values('/app/backend/.env')
        client = MongoClient(env['MONGO_URL'])
        db = client[env['DB_NAME']]
        for doc in state['docs']:
            col = db.wysh_prescriptions if doc['document_kind'] == 'prescription' else db.wysh_lab_reports
            col.delete_one({'document_id': doc['document_id']})
            db.wysh_health_records.delete_many({'source_document_id': doc['document_id']})
            db.wysh_files.delete_one({'file_id': doc['file_id']})
        for key, col, field in [('invoices','wysh_invoices','invoice_id'), ('reminders','wysh_care_reminders','reminder_id'), ('appointments','wysh_appointments','appointment_id'), ('consultations','wysh_consultations','consultation_id'), ('notes','wysh_consultation_notes','note_id'), ('oauth_states','wysh_calendar_oauth_states','state')]:
            for ident in state[key]:
                db[col].delete_one({field: ident})
                if key == 'invoices':
                    db.wysh_invoice_lines.delete_many({'invoice_id': ident})
        for name, uid in state['created'].items():
            db.wysh_users.delete_one({'user_id': uid})
            db.wysh_identities.delete_one({'user_id': uid})
            db.wysh_reminder_preferences.delete_one({'patient_id': uid})
            db.wysh_availability.delete_many({'doctor_id': uid})
        for token in state['sessions']:
            db.wysh_sessions.delete_one({'session_token': token})
        client.close()


def test_supplied_login_roles(ctx):
    for role in ['patient', 'doctor', 'admin']:
        actor = ctx['supplied_' + role]
        assert actor['user']['role'] == role
        assert ok(call('GET', '/auth/me', actor))['user_id'] == actor['user']['user_id']


@pytest.mark.parametrize('fmt,mime,kind', [('PNG','image/png','prescription'), ('JPEG','image/jpeg','prescription'), ('WEBP','image/webp','prescription'), ('PDF','application/pdf','lab_report')])
def test_upload_actual_extraction_pending(ctx, fmt, mime, kind):
    if fmt == 'PDF':
        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_text((40, 50), 'TEST_Diagnostics Lab\nPatient: TEST_OCR Patient\nHemoglobin: 13.5 g/dL (Reference 12.0-16.0)\nGlucose: 95 mg/dL (Reference 70-100)', fontsize=16)
        content = pdf.tobytes()
    else:
        content = image_data(fmt, kind)
    data = ok(call('POST', '/ocr/documents/' + kind, ctx['patient'], files={'file': ('TEST_report.' + fmt.lower(), content, mime)}))
    ctx['docs'].append(data)
    assert data['review_state'] == 'pending'
    assert data['extraction_status'] == 'complete'
    assert data['extracted']['overall_confidence'] > 0
    extracted = data['extracted']
    assert any('paracetamol' in med['name'].lower() for med in extracted['medications']) if kind == 'prescription' else any('hemoglobin' in obs['name'].lower() for obs in extracted['observations'])
    assert ok(call('GET', '/ocr/documents/' + data['document_id'], ctx['patient']))['review_state'] == 'pending'
    assert not any(r.get('source_document_id') == data['document_id'] for r in ok(call('GET','/records',ctx['patient'])))
    download = call('GET','/ocr/files/' + data['file_id'],ctx['patient'])
    assert download.status_code == 200 and download.content == content


def test_document_owner_authorization(ctx):
    doc = ctx['docs'][0]
    for path in ['/ocr/documents/' + doc['document_id'], '/ocr/files/' + doc['file_id']]:
        assert ok(call('GET',path,ctx['other']),403)['detail'] == 'Not allowed'
    assert ok(call('POST','/ocr/documents/' + doc['document_id'] + '/review',ctx['other'],json={'decision':'approved','extracted':{}}),403)['detail'] == 'Not allowed'


def test_unsupported_empty_oversize_rejected(ctx):
    for filename, content, mime in [('TEST.txt',b'invalid','text/plain'),('TEST.png',b'','image/png'),('TEST.png',b'a'*(20*1024*1024+1),'image/png')]:
        result = ok(call('POST','/ocr/documents/prescription',ctx['patient'], files={'file':(filename,content,mime)}),400)
        assert result['detail']


def test_review_approved_exactly_once(ctx):
    for doc in [ctx['docs'][0],ctx['docs'][-1]]:
        body = {'decision':'approved','extracted':{**doc['extracted'],'notes':'TEST_Reviewed correction'}}
        first = ok(call('POST','/ocr/documents/' + doc['document_id'] + '/review',ctx['patient'],json=body))
        second = ok(call('POST','/ocr/documents/' + doc['document_id'] + '/review',ctx['patient'],json=body))
        assert first['review_state'] == 'approved' and first['emr_record_id'] == second['emr_record_id']
        fetched = ok(call('GET','/ocr/documents/' + doc['document_id'],ctx['patient']))
        assert fetched['reviewed_extraction']['notes'] == 'TEST_Reviewed correction'
        committed = [r for r in ok(call('GET','/records',ctx['patient'])) if r.get('source_document_id') == doc['document_id']]
        assert len(committed) == 1 and committed[0]['data']['notes'] == 'TEST_Reviewed correction'


def test_rejection_does_not_commit(ctx):
    doc = ctx['docs'][1]
    assert ok(call('POST','/ocr/documents/' + doc['document_id'] + '/review',ctx['patient'],json={'decision':'rejected','extracted':doc['extracted']}))['review_state'] == 'rejected'
    assert ok(call('GET','/ocr/documents/' + doc['document_id'],ctx['patient']))['review_state'] == 'rejected'
    assert not any(r.get('source_document_id') == doc['document_id'] for r in ok(call('GET','/records',ctx['patient'])))


def test_reminder_preferences_persistence(ctx):
    defaults = ok(call('GET','/reminders/preferences',ctx['patient']))
    assert defaults['in_app'] is True
    prefs = {'in_app':True,'email':True,'sms':True,'whatsapp':True}
    saved = ok(call('PUT','/reminders/preferences',ctx['patient'],json=prefs))
    fetched = ok(call('GET','/reminders/preferences',ctx['patient']))
    assert all(fetched[k] == v for k,v in prefs.items())
    assert saved['external_delivery'] == fetched['external_delivery'] == 'not_configured'
    assert ok(call('GET','/reminders/preferences',ctx['doctor']),403)['detail']


def test_reminder_create_complete(ctx):
    due = (datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    data = ok(call('POST','/reminders',ctx['patient'],json={'title':'TEST_Medication','due_at':due,'category':'medication'}))
    ctx['reminders'].append(data['reminder_id'])
    item = next(r for r in ok(call('GET','/reminders/mine',ctx['patient'])) if r['reminder_id'] == data['reminder_id'])
    assert item['title'] == 'TEST_Medication' and item['status'] == 'active'
    assert ok(call('POST','/reminders/' + data['reminder_id'] + '/complete',ctx['other']),404)['detail']
    assert ok(call('POST','/reminders/' + data['reminder_id'] + '/complete',ctx['patient']))['ok'] is True
    assert next(r for r in ok(call('GET','/reminders/mine',ctx['patient'])) if r['reminder_id'] == data['reminder_id'])['status'] == 'completed'
    assert ok(call('POST','/reminders',ctx['patient'],json={'title':'TEST_Invalid','due_at':'invalid'}),400)['detail']


def test_telemedicine_book_prepare_join_authorization(ctx):
    now = datetime.now(timezone.utc)
    date = now.date()+timedelta(days=7)
    blocks = [{'day_of_week':date.weekday(),'start_time':'10:00','end_time':'11:00','slot_minutes':30}]
    assert ok(call('PUT','/availability/me',ctx['doctor'],json={'blocks':blocks}))
    slots = ok(call('GET','/availability/' + ctx['created']['doctor'] + '/slots',ctx['patient'],params={'date':date.isoformat()}))['slots']
    apt = ok(call('POST','/appointments',ctx['patient'],json={'doctor_id':ctx['created']['doctor'],'scheduled_at':slots[0],'mode':'telemedicine','reason':'TEST_Care consultation'}))
    ctx['appointments'].append(apt['appointment_id'])
    assert apt['video_link_status'] == 'organizer_not_connected' and not apt.get('meeting_url')
    assert any(a['appointment_id'] == apt['appointment_id'] for a in ok(call('GET','/appointments/mine',ctx['patient'])))
    assert ok(call('POST','/consultations/from-appointment/' + apt['appointment_id'],ctx['other']),403)['detail']
    consultation = ok(call('POST','/consultations/from-appointment/' + apt['appointment_id'],ctx['patient']))
    cid = consultation['consultation_id']
    ctx['consultations'].append(cid)
    assert ok(call('POST','/consultations/from-appointment/' + apt['appointment_id'],ctx['patient']))['consultation_id'] == cid
    assert ok(call('GET','/consultations/' + cid,ctx['patient']))['patient_id'] == ctx['created']['patient']
    assert ok(call('GET','/consultations/' + cid,ctx['other']),403)['detail']
    assert ok(call('POST','/consultations/' + cid + '/join',ctx['other']),403)['detail']
    assert ok(call('POST','/consultations/' + cid + '/join',ctx['patient']),409)['detail'] == 'Preparing video link'
    note = ok(call('POST','/consultations/' + cid + '/notes',ctx['doctor'],json={'content':'TEST_SOAP assessment'}))
    ctx['notes'].append(note['note_id'])
    assert ok(call('GET','/consultations/' + cid,ctx['patient']))['notes'][0]['content'] == 'TEST_SOAP assessment'
    assert ok(call('POST','/consultations/' + cid + '/complete',ctx['doctor']))['ok'] is True
    assert ok(call('GET','/consultations/' + cid,ctx['patient']))['status'] == 'completed'


def test_invoice_issue_view_checkout_not_configured(ctx):
    patients = ok(call('GET','/billing/patients',ctx['doctor']))
    assert any(p['user_id'] == ctx['created']['patient'] for p in patients)
    inv = ok(call('POST','/billing/invoices',ctx['doctor'],json={'patient_id':ctx['created']['patient'],'lines':[{'description':'TEST_Consultation fee','amount_paise':125050}]}))
    ctx['invoices'].append(inv['invoice_id'])
    fetched = next(i for i in ok(call('GET','/billing/invoices/mine',ctx['patient'])) if i['invoice_id'] == inv['invoice_id'])
    assert fetched['currency'] == 'INR' and fetched['total_paise'] == 125050 and fetched['status'] == 'issued'
    assert fetched['lines'][0]['description'] == 'TEST_Consultation fee'
    assert not any(i['invoice_id'] == inv['invoice_id'] for i in ok(call('GET','/billing/invoices/mine',ctx['other'])))
    assert ok(call('POST','/billing/invoices/' + inv['invoice_id'] + '/checkout',ctx['patient']),503)['detail'] == 'Payments are not configured yet'
    assert ok(call('POST','/billing/invoices/' + inv['invoice_id'] + '/checkout',ctx['other']),404)['detail'] == 'Invoice not found'


def test_calendar_status_oauth_start(ctx):
    status = ok(call('GET','/calendar/status',ctx['supplied_admin']))
    assert status['connected'] is False and status['organizer_email'] is None
    assert ok(call('GET','/calendar/status',ctx['patient']),403)['detail']
    data = ok(call('GET','/calendar/connect',ctx['supplied_admin']))
    assert set(data) == {'authorization_url'}
    parsed = urlparse(data['authorization_url'])
    query = parse_qs(parsed.query)
    ctx['oauth_states'].extend(query['state'])
    assert parsed.hostname == 'accounts.google.com'
    assert 'client_secret' not in query and 'access_token' not in query
    assert query['redirect_uri'][0] == BASE + '/calendar/callback', 'OAuth callback must use public HTTPS origin: ' + query['redirect_uri'][0]


def test_timeline_merged(ctx):
    events = ok(call('GET','/records/timeline',ctx['patient']))
    kinds = {e['kind'] for e in events}
    assert {'prescription','lab_report','appointment','consultation'} <= kinds
    for doc in [ctx['docs'][0],ctx['docs'][-1]]:
        current = ok(call('GET','/ocr/documents/' + doc['document_id'],ctx['patient']))
        assert sum(e['id'] == current['emr_record_id'] for e in events) == 1


def test_multipage_pdf_extracts_all_observations(ctx):
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((40,50),'TEST_Multipage Laboratory\nPatient: TEST_OCR Patient\nHemoglobin: 13.5 g/dL (Reference 12.0-16.0)',fontsize=16)
    page = pdf.new_page()
    page.insert_text((40,50),'TEST_Multipage Laboratory - page 2\nPatient: TEST_OCR Patient\nGlucose: 95 mg/dL (Reference 70-100)',fontsize=16)
    doc = ok(call('POST','/ocr/documents/lab_report',ctx['patient'],files={'file':('TEST_multipage.pdf',pdf.tobytes(),'application/pdf')}))
    ctx['docs'].append(doc)
    assert doc['extraction_status'] == 'complete'
    observations = doc['extracted']['observations']
    assert any('glucose' in obs['name'].lower() for obs in observations), 'Second-page glucose observation missing: ' + str(observations)


def test_expired_session_cannot_download(ctx):
    # Test-only expired Google-style session fixture; no real OAuth is performed.
    token = 'TEST_expired_' + uuid.uuid4().hex
    env = dotenv_values('/app/backend/.env')
    client = MongoClient(env['MONGO_URL'])
    client[env['DB_NAME']].wysh_sessions.insert_one({'session_token':token,'user_id':ctx['created']['patient'],'expires_at':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()})
    client.close()
    ctx['sessions'].append(token)
    actor = {'token':token}
    assert ok(call('GET','/auth/me',actor),401)['detail'] == 'Not authenticated'
    response = call('GET','/ocr/files/' + ctx['docs'][0]['file_id'],actor)
    assert response.status_code == 401, 'Expired session downloaded private document: HTTP ' + str(response.status_code)
