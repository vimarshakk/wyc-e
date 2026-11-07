"""Public API regression tests for doctor schedules, slot exclusion and appointment booking."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

BASE = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') + '/api'
NEXT_MON = (datetime.now(timezone.utc).date() + timedelta(days=(7 - datetime.now(timezone.utc).weekday()) % 7 or 7)).isoformat()
BLOCK = dict(day_of_week=0, start_time='09:00', end_time='10:00', slot_minutes=30)


@pytest.fixture(scope='module')
def ctx():
    state = {'users': [], 'appointments': [], 'timeoffs': []}
    for role in ['doctor', 'patient']:
        response = requests.post(BASE + '/auth/signup', json={
            'name': 'TEST_Availability ' + role,
            'email': 'test_availability_' + uuid.uuid4().hex[:12] + '@wyshcare.io',
            'password': 'TestPass123!', 'role': role, 'specialty': 'Cardiology',
        }, timeout=30)
        assert response.status_code == 200, response.text
        data = response.json()
        state[role] = data
        state['users'].append(data['user']['user_id'])
    state['dh'] = {'Authorization': 'Bearer ' + state['doctor']['token']}
    state['ph'] = {'Authorization': 'Bearer ' + state['patient']['token']}
    state['did'] = state['doctor']['user']['user_id']
    setup = requests.put(BASE + '/availability/me', headers=state['dh'], json={'blocks': [BLOCK]}, timeout=30)
    assert setup.status_code == 200, setup.text
    yield state
    # No deletion API exists: remove exclusively this fixture's captured record IDs.
    env = dotenv_values('/app/backend/.env')
    client = MongoClient(env['MONGO_URL'])
    db = client[env['DB_NAME']]
    for aid in state['appointments']:
        db.wysh_appointments.delete_one({'appointment_id': aid})
    for tid in state['timeoffs']:
        db.wysh_time_off.delete_one({'time_off_id': tid})
    for uid in state['users']:
        db.wysh_availability.delete_many({'doctor_id': uid})
        db.wysh_users.delete_one({'user_id': uid})
        db.wysh_identities.delete_one({'user_id': uid})
    client.close()


def get_slots(ctx, date=NEXT_MON):
    r = requests.get(BASE + f'/availability/{ctx["did"]}/slots', headers=ctx['ph'], params={'date': date}, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()['doctor_id'] == ctx['did']
    return r.json()['slots']


def create_timeoff(ctx, start, end):
    r = requests.post(BASE + '/availability/time-off', headers=ctx['dh'], json={
        'start_at': start, 'end_at': end, 'reason': 'TEST_Availability time off',
    }, timeout=30)
    assert r.status_code == 200, r.text
    tid = r.json()['time_off_id']
    ctx['timeoffs'].append(tid)
    return tid


def delete_timeoff(ctx, tid):
    r = requests.delete(BASE + '/availability/time-off/' + tid, headers=ctx['dh'], timeout=30)
    assert r.status_code == 200 and r.json()['ok'] is True


def test_supplied_credentials():
    text = Path('/app/memory/test_credentials.md').read_text()
    for role in ['doctor', 'patient']:
        email = role + '@wyshcare.io'
        assert email in text and 'TestPass123!' in text
        r = requests.post(BASE + '/auth/login', json={'email': email, 'password': 'TestPass123!'}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()['user']['role'] == role
        assert r.json()['user']['email'] == email
        assert isinstance(r.json()['token'], str)


def test_schedule_persistence(ctx):
    r = requests.get(BASE + '/availability/me', headers=ctx['dh'], timeout=30)
    assert r.status_code == 200, r.text
    b = r.json()['blocks'][0]
    assert all(b[k] == v for k, v in BLOCK.items())


def test_schedule_requires_doctor(ctx):
    for method in ['get', 'put']:
        r = requests.request(method, BASE + '/availability/me', headers=ctx['ph'], json={'blocks': [BLOCK]}, timeout=30)
        assert r.status_code == 403 and r.json()['detail']


def test_unauthenticated_slots(ctx):
    r = requests.get(BASE + f'/availability/{ctx["did"]}/slots', params={'date': NEXT_MON}, timeout=30)
    assert r.status_code == 401 and r.json()['detail']


def test_monday_slot_grid(ctx):
    assert get_slots(ctx) == [NEXT_MON + 'T09:00:00+05:30', NEXT_MON + 'T09:30:00+05:30']


def test_invalid_schedule_preserves_schedule(ctx):
    r = requests.put(BASE + '/availability/me', headers=ctx['dh'], json={'blocks': [{**BLOCK, 'end_time': '08:00'}]}, timeout=30)
    assert r.status_code == 400 and 'end_time' in r.json()['detail']
    assert len(get_slots(ctx)) == 2


def test_invalid_slot_date(ctx):
    r = requests.get(BASE + f'/availability/{ctx["did"]}/slots', headers=ctx['ph'], params={'date': 'bad-date'}, timeout=30)
    assert r.status_code == 400 and 'Invalid date' in r.json()['detail']


def test_timeoff_full_slot_and_delete(ctx):
    first_slot = get_slots(ctx)[0]
    first_end = (datetime.fromisoformat(first_slot) + timedelta(minutes=30)).isoformat()
    tid = create_timeoff(ctx, first_slot, first_end)
    try:
        r = requests.get(BASE + '/availability/time-off/me', headers=ctx['dh'], timeout=30)
        assert r.status_code == 200
        assert any(t['time_off_id'] == tid and t['reason'] == 'TEST_Availability time off' for t in r.json())
        assert get_slots(ctx) == [NEXT_MON + 'T09:30:00+05:30']
    finally:
        delete_timeoff(ctx, tid)
    assert len(get_slots(ctx)) == 2
    r = requests.delete(BASE + '/availability/time-off/' + tid, headers=ctx['dh'], timeout=30)
    assert r.status_code == 404 and r.json()['detail']


def test_booking_persistence_exclusion_cancel(ctx):
    slot = get_slots(ctx)[0]
    r = requests.post(BASE + '/appointments', headers=ctx['ph'], json={'doctor_id': ctx['did'], 'scheduled_at': slot, 'mode': 'in_person', 'reason': 'TEST_Availability booking'}, timeout=30)
    assert r.status_code == 200, r.text
    aid = r.json()['appointment_id']
    ctx['appointments'].append(aid)
    try:
        mine = requests.get(BASE + '/appointments/mine', headers=ctx['ph'], timeout=30)
        assert mine.status_code == 200
        saved = next(a for a in mine.json() if a['appointment_id'] == aid)
        assert saved['scheduled_at'] == slot and saved['status'] == 'scheduled' and saved['mode'] == 'in_person'
        assert slot not in get_slots(ctx)
        dup = requests.post(BASE + '/appointments', headers=ctx['ph'], json={'doctor_id': ctx['did'], 'scheduled_at': slot}, timeout=30)
        assert dup.status_code == 409 and dup.json()['detail'] == 'Slot is not available'
    finally:
        cancel = requests.post(BASE + '/appointments/' + aid + '/cancel', headers=ctx['ph'], timeout=30)
        assert cancel.status_code == 200 and cancel.json()['ok'] is True
    mine = requests.get(BASE + '/appointments/mine', headers=ctx['ph'], timeout=30).json()
    assert next(a for a in mine if a['appointment_id'] == aid)['status'] == 'cancelled'
    assert slot in get_slots(ctx)


def test_doctor_list(ctx):
    r = requests.get(BASE + '/appointments/doctors', headers=ctx['ph'], timeout=30)
    assert r.status_code == 200
    assert any(d['user_id'] == ctx['did'] for d in r.json())
    assert all('_id' not in d and 'password_hash' not in d for d in r.json())


def test_timeoff_invalid_iso_returns_validation_error(ctx):
    r = requests.post(BASE + '/availability/time-off', headers=ctx['dh'], json={'start_at': 'not-a-date', 'end_at': 'not-a-date', 'reason': 'TEST_Invalid'}, timeout=30)
    assert r.status_code in [400, 422], r.text
    assert r.json()['detail']


def test_partial_timeoff_overlap_blocks_slot(ctx):
    first_slot = datetime.fromisoformat(get_slots(ctx)[0])
    tid = create_timeoff(
        ctx,
        (first_slot + timedelta(minutes=15)).isoformat(),
        (first_slot + timedelta(minutes=45)).isoformat(),
    )
    try:
        assert get_slots(ctx) == [], 'Both 30-minute slots overlap time off'
    finally:
        delete_timeoff(ctx, tid)


def test_overlapping_schedule_no_duplicate_slots(ctx):
    r = requests.put(BASE + '/availability/me', headers=ctx['dh'], json={'blocks': [BLOCK, BLOCK]}, timeout=30)
    assert r.status_code == 400
    try:
        grid = get_slots(ctx)
        assert len(grid) == len(set(grid)), grid
    finally:
        requests.put(BASE + '/availability/me', headers=ctx['dh'], json={'blocks': [BLOCK]}, timeout=30)


def test_past_slots_unavailable(ctx):
    past = (datetime.fromisoformat(NEXT_MON).date() - timedelta(days=14)).isoformat()
    assert get_slots(ctx, past) == [], 'Past dates must not offer bookable appointments'


def test_india_weekly_hours_timezone(ctx):
    grid = get_slots(ctx)
    india = timezone(timedelta(hours=5, minutes=30))
    assert datetime.fromisoformat(grid[0]).astimezone(india).strftime('%H:%M') == '09:00', 'India doctor 09:00 weekly hours currently become 14:30 IST'


def test_doctor_cannot_book_as_patient(ctx):
    r = requests.post(BASE + '/appointments', headers=ctx['dh'], json={'doctor_id': ctx['did'], 'scheduled_at': get_slots(ctx)[0], 'reason': 'TEST_Doctor booking'}, timeout=30)
    if r.status_code == 200:
        ctx['appointments'].append(r.json()['appointment_id'])
    assert r.status_code == 403, r.text


def test_concurrent_booking_is_atomic(ctx):
    slot = get_slots(ctx)[0]
    def send(_):
        return requests.post(BASE + '/appointments', headers=ctx['ph'], json={
            'doctor_id': ctx['did'], 'scheduled_at': slot, 'reason': 'TEST_Concurrent booking',
        }, timeout=30)
    # Concurrent requests must not both reserve the same doctor slot.
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(send, range(6)))
    successes = [r for r in responses if r.status_code == 200]
    for r in successes:
        ctx['appointments'].append(r.json()['appointment_id'])
    assert len(successes) == 1, f'{len(successes)} bookings succeeded: {[r.status_code for r in responses]}'
    assert all(r.status_code in [200, 409] for r in responses)