"""Direct OCR review/download authorization and scope regression; no external services invoked."""
import uuid
from datetime import datetime, timedelta, timezone

from .test_clinical_authorization import ctx, call, appointment, grant, revoke


def synthetic_document(ctx, kind):
    did = 'TEST_doc_' + uuid.uuid4().hex[:16]
    fid = 'TEST_file_' + uuid.uuid4().hex[:16]
    collection = ctx['db'].wysh_prescriptions if kind == 'prescription' else ctx['db'].wysh_lab_reports
    document = {'document_id': did, 'file_id': fid, 'patient_id': ctx['patient']['user']['user_id'],
                'document_kind': kind, 'review_state': 'pending', 'extracted': {'notes': 'TEST_Synthetic'},
                'created_at': datetime.now(timezone.utc).isoformat()}
    collection.insert_one(document)
    ctx['db'].wysh_files.insert_one({'file_id': fid, 'owner_id': document['patient_id'], 'is_deleted': False,
                                   'storage_path': 'TEST_not_a_real_object', 'content_type': 'application/pdf'})
    return did, fid, collection


def remove_document(ctx, did, fid, collection):
    collection.delete_one({'document_id': did})
    ctx['db'].wysh_files.delete_one({'file_id': fid})
    assert collection.count_documents({'document_id': did}) == 0
    assert ctx['db'].wysh_files.count_documents({'file_id': fid}) == 0


def assert_denied(ctx, actor, did, fid):
    for method, path, kwargs in [
        ('GET', '/ocr/documents/' + did, {}),
        ('POST', '/ocr/documents/' + did + '/review', {'json': {'decision': 'approved', 'extracted': {'notes': 'TEST_Unauthorized'}}}),
        ('GET', '/ocr/files/' + fid, {}),
    ]:
        response = call(method, path, ctx[actor], **kwargs)
        assert response.status_code == 403 and response.json()['detail'] == 'Not allowed', (actor, path, response.status_code, response.text)


def test_unverified_and_nonmember_doctors_denied_ocr_read_review_download(ctx):
    # Appointment relationships and matching consent cannot bypass professional eligibility.
    for actor in ('pending_doctor', 'nonmember'):
        aid = appointment(ctx, actor, 'scheduled')
        consent = grant(ctx, ['labs', 'prescriptions'], doctor=actor)
        assert consent.status_code == 200
        try:
            for kind in ('lab_report', 'prescription'):
                did, fid, collection = synthetic_document(ctx, kind)
                try:
                    assert_denied(ctx, actor, did, fid)
                    assert collection.find_one({'document_id': did})['review_state'] == 'pending'
                    assert ctx['db'].wysh_health_records.count_documents({'source_document_id': did}) == 0
                finally:
                    remove_document(ctx, did, fid, collection)
        finally:
            ctx['db'].wysh_appointments.delete_one({'appointment_id': aid})
            revoke(ctx, consent.json()['consent_id'])


def test_ocr_uses_matching_consent_scope_and_normalized_expiry(ctx):
    # Correct scope allows real document read/review; wrong scope/revocation denies all three routes.
    for kind, scope in (('lab_report', 'labs'), ('prescription', 'prescriptions')):
        did, fid, collection = synthetic_document(ctx, kind)
        try:
            wrong = grant(ctx, ['records'])
            assert wrong.status_code == 200
            try:
                assert_denied(ctx, 'doctor', did, fid)
            finally:
                revoke(ctx, wrong.json()['consent_id'])
            expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).astimezone(timezone(timedelta(hours=-10))).isoformat()
            matching = grant(ctx, [scope], expiry=expiry)
            assert matching.status_code == 200
            cid = matching.json()['consent_id']
            try:
                normalized = datetime.fromisoformat(matching.json()['expires_at'])
                assert normalized.utcoffset() == timedelta(0)
                assert normalized == datetime.fromisoformat(expiry)
                saved = ctx['db'].wysh_chart_consents.find_one({'consent_id': cid})
                assert saved['expires_at'] == matching.json()['expires_at']
                response = call('GET', '/ocr/documents/' + did, ctx['doctor'])
                assert response.status_code == 200 and response.json()['document_id'] == did
                response = call('POST', '/ocr/documents/' + did + '/review', ctx['doctor'], json={'decision': 'rejected', 'extracted': {'notes': 'TEST_Reviewed'}})
                assert response.status_code == 200 and response.json()['review_state'] == 'rejected'
                response = call('GET', '/ocr/documents/' + did, ctx['doctor'])
                assert response.status_code == 200 and response.json()['reviewed_by'] == ctx['doctor']['user']['user_id']
                assert collection.find_one({'document_id': did})['review_state'] == 'rejected'
            finally:
                revoke(ctx, cid)
            assert_denied(ctx, 'doctor', did, fid)
        finally:
            remove_document(ctx, did, fid, collection)