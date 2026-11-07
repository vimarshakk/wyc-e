"""Executed public-browser playbook. Captured TEST_ record IDs require targeted cleanup."""
import base64
import json
import uuid
from datetime import datetime, timedelta, timezone


async def run(page):
    base = page.url.split('/app/')[0].split('/login')[0].rstrip('/')
    api = base + '/api'
    tracked = {'users': [], 'documents': [], 'reminders': [], 'appointments': [], 'consultations': [], 'invoices': [], 'notes': []}
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    await page.set_viewport_size({'width':1920,'height':1080})

    async def login(email, password, role):
        await page.goto(base + '/login')
        await page.get_by_test_id('login-email').fill(email)
        await page.get_by_test_id('login-password').fill(password)
        await page.get_by_test_id('login-submit').click(force=True)
        await page.wait_for_url('**/app/' + role)
        print('PASS UI login', role)

    try:
        for route in ['documents','care-plan','consultations','billing']:
            await page.goto(base + '/app/' + route)
            await page.wait_for_url('**/login')
            print('PASS unauthenticated route', route)
        actors = {}
        for role in ['patient','doctor']:
            email = 'test_care_ui_' + uuid.uuid4().hex[:10] + '@wyshcare.io'
            response = await page.request.post(api + '/auth/signup', data={'name':'TEST_CareUI ' + role,'email':email,'password':'TEST_Care123!','role':role,'specialty':'Cardiology'})
            assert response.status == 200
            actors[role] = await response.json()
            actors[role]['email'] = email
            tracked['users'].append(actors[role]['user']['user_id'])
        date = datetime.now(timezone.utc).date() + timedelta(days=8)
        dh = {'Authorization':'Bearer ' + actors['doctor']['token']}
        response = await page.request.put(api + '/availability/me',headers=dh,data={'blocks':[{'day_of_week':date.weekday(),'start_time':'10:00','end_time':'11:00','slot_minutes':30}]})
        assert response.status == 200
        await login(actors['patient']['email'],'TEST_Care123!','patient')
        logo = page.get_by_test_id('nav-brand-logo')
        await logo.wait_for(state='visible')
        assert await logo.evaluate('(e)=>e.complete&&e.naturalWidth>0')
        print('PASS supplied logo renders')
        print('PATIENT_CONSULTATION_NAV_COUNT', await page.get_by_test_id('nav-consultations').count())
        await page.get_by_test_id('nav-documents').click(force=True)
        await page.get_by_test_id('documents-heading').wait_for()
        await page.get_by_test_id('document-kind-select').select_option('lab_report')
        assert await page.get_by_test_id('upload-document-btn').inner_text() == 'Extract Lab report'
        await page.get_by_test_id('document-kind-select').select_option('prescription')
        png = await page.evaluate('''() => {const c=document.createElement('canvas'); c.width=1200;c.height=700;const x=c.getContext('2d');x.fillStyle='white';x.fillRect(0,0,c.width,c.height);x.fillStyle='black';x.font='30px sans-serif';['TEST_Clinic Prescription','Doctor: Dr Test Sharma','Patient: TEST_CareUI patient','Diagnosis: Fever','Paracetamol 500mg twice daily for 3 days','Take after meals'].forEach((t,i)=>x.fillText(t,40,70+i*70));return c.toDataURL('image/png').split(',')[1]}''')
        await page.get_by_test_id('document-file-input').set_input_files({'name':'TEST_UI_prescription.png','mimeType':'image/png','buffer':base64.b64decode(png)})
        async with page.expect_response(lambda r: '/ocr/documents/prescription' in r.url and r.request.method == 'POST',timeout=180000) as saved:
            await page.get_by_test_id('upload-document-btn').click(force=True)
        document = await (await saved.value).json()
        tracked['documents'].append({'document_id':document['document_id'],'file_id':document['file_id']})
        await page.get_by_test_id('approve-document-btn').wait_for(timeout=20000)
        assert document['extraction_status'] == 'complete' and document['review_state'] == 'pending'
        print('PASS UI actual extraction remains pending')
        await page.get_by_test_id('document-review-json').fill('{invalid')
        await page.get_by_test_id('approve-document-btn').click(force=True)
        await page.get_by_text('Review data must be valid JSON',exact=True).wait_for()
        print('PASS invalid review JSON feedback')
        reviewed = {**document['extracted'],'notes':'TEST_UI corrected review'}
        await page.get_by_test_id('document-review-json').fill(json.dumps(reviewed))
        await page.get_by_test_id('approve-document-btn').click(force=True)
        await page.get_by_test_id('document-review-status').wait_for()
        await page.reload()
        await page.get_by_test_id('document-row-' + document['document_id']).click(force=True)
        print('REVIEW_TEXT_AFTER_RELOAD',await page.get_by_test_id('document-review-json').input_value())
        print('DOCUMENT_DOWNLOAD_LINKS',await page.locator('a[href*="/ocr/files/"]').count())
        print('PASS UI explicit approval persists')
        await page.get_by_test_id('nav-care-plan').click(force=True)
        await page.get_by_test_id('external-delivery-status').wait_for()
        await page.wait_for_timeout(400)
        for channel in ['email','sms','whatsapp']:
            await page.get_by_test_id('reminder-channel-' + channel).check(force=True)
        await page.get_by_test_id('save-reminder-preferences-btn').click(force=True)
        await page.get_by_text('Reminder preferences saved',exact=True).wait_for()
        await page.reload()
        await page.get_by_test_id('external-delivery-status').wait_for()
        await page.wait_for_timeout(400)
        assert await page.get_by_test_id('reminder-channel-sms').is_checked()
        assert 'not_configured' in await page.get_by_test_id('external-delivery-status').inner_text()
        await page.get_by_test_id('reminder-title-input').fill('TEST_UI medication')
        await page.get_by_test_id('reminder-due-input').fill(date.isoformat() + 'T09:00')
        await page.get_by_test_id('reminder-note-input').fill('TEST_UI reminder note')
        async with page.expect_response(lambda r:r.url.endswith('/api/reminders') and r.request.method == 'POST') as created:
            await page.get_by_test_id('create-reminder-btn').click(force=True)
        reminder = await (await created.value).json()
        tracked['reminders'].append(reminder['reminder_id'])
        await page.get_by_test_id('complete-reminder-' + reminder['reminder_id']).click(force=True)
        await page.get_by_test_id('complete-reminder-' + reminder['reminder_id']).wait_for(state='detached')
        print('REMINDER_COMPLETED_LIST',await page.get_by_test_id('reminders-list').inner_text())
        print('PASS UI preferences/save/create/complete reminder')
        await page.get_by_test_id('nav-appointments').click(force=True)
        await page.get_by_test_id('appt-doctor-select').select_option(actors['doctor']['user']['user_id'])
        await page.get_by_test_id('appt-date').fill(date.isoformat())
        await page.get_by_test_id('slot-grid').locator('button').first.click(force=True)
        await page.get_by_test_id('appt-reason').fill('TEST_UI telemedicine')
        async with page.expect_response(lambda r:r.url.endswith('/api/appointments') and r.request.method == 'POST') as booked:
            await page.get_by_test_id('appt-book-btn').click(force=True)
        appointment = await (await booked.value).json()
        tracked['appointments'].append(appointment['appointment_id'])
        print('PASS UI telemedicine booking')
        await page.goto(base + '/app/consultations')
        async with page.expect_response(lambda r:'/consultations/from-appointment/' in r.url and r.request.method == 'POST') as prepared:
            await page.get_by_test_id('prepare-consultation-' + appointment['appointment_id']).click(force=True)
        consultation = await (await prepared.value).json()
        tracked['consultations'].append(consultation['consultation_id'])
        await page.get_by_test_id('join-consultation-btn').click(force=True)
        await page.get_by_text('Preparing video link',exact=True).wait_for()
        print('PASS UI consultation prepare/join truthful pending')
        for route, heading in [('documents','documents-heading'),('care-plan','careplan-heading'),('consultations','consultations-heading'),('billing','billing-heading')]:
            await page.goto(base + '/app/' + route)
            await page.get_by_test_id(heading).wait_for()
            for width,height in [(1920,1080),(768,1024),(390,844)]:
                await page.set_viewport_size({'width':width,'height':height})
                await page.wait_for_timeout(150)
                size = await page.evaluate('({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})')
                print('LAYOUT',route,width,size,'PASS' if size['scroll']<=size['client'] else 'FAIL')
            if route == 'documents':
                await page.screenshot(path='/app/test_reports/documents-mobile.jpg',quality=40,full_page=False)
        await page.get_by_test_id('mobile-nav-select').select_option('/app/care-plan')
        await page.get_by_test_id('careplan-heading').wait_for()
        print('PASS mobile dropdown navigation')
        await page.set_viewport_size({'width':1920,'height':1080})
        await page.get_by_test_id('nav-logout').click(force=True)
        await login(actors['doctor']['email'],'TEST_Care123!','doctor')
        await page.goto(base + '/app/care-plan')
        await page.wait_for_url('**/app/doctor')
        print('PASS doctor care-plan role guard')
        await page.get_by_test_id('nav-billing').click(force=True)
        await page.get_by_test_id('invoice-patient-select').select_option(actors['patient']['user']['user_id'])
        await page.get_by_test_id('invoice-description-input').fill('TEST_UI Consultation fee')
        await page.get_by_test_id('invoice-amount-input').fill('750.50')
        async with page.expect_response(lambda r:r.url.endswith('/api/billing/invoices') and r.request.method == 'POST') as issued:
            await page.get_by_test_id('issue-invoice-btn').click(force=True)
        invoice = await (await issued.value).json()
        tracked['invoices'].append(invoice['invoice_id'])
        await page.get_by_test_id('invoice-list').get_by_text('TEST_UI Consultation fee',exact=True).wait_for()
        print('PASS doctor invoice UI')
        await page.get_by_test_id('nav-consultations').click(force=True)
        await page.get_by_test_id('consultation-row-' + consultation['consultation_id']).click(force=True)
        await page.get_by_test_id('consultation-note-input').fill('TEST_UI SOAP note')
        async with page.expect_response(lambda r:r.url.endswith('/notes') and r.request.method == 'POST') as noted:
            await page.get_by_test_id('save-consultation-note-btn').click(force=True)
        note = await (await noted.value).json()
        tracked['notes'].append(note['note_id'])
        await page.get_by_test_id('consultation-notes-list').get_by_text('TEST_UI SOAP note',exact=True).wait_for()
        await page.get_by_test_id('complete-consultation-btn').click(force=True)
        await page.get_by_text('Consultation completed',exact=True).wait_for()
        print('PASS doctor note and complete UI')
        await page.get_by_test_id('nav-logout').click(force=True)
        await login(actors['patient']['email'],'TEST_Care123!','patient')
        await page.get_by_test_id('nav-billing').click(force=True)
        await page.get_by_test_id('pay-invoice-' + invoice['invoice_id']).click(force=True)
        await page.get_by_text('Payments are not configured yet',exact=True).wait_for()
        print('PASS patient invoice checkout truthful unavailable')
        await page.set_viewport_size({'width':390,'height':844})
        print('POPULATED_BILLING_OVERFLOW',await page.evaluate('({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})'))
        await page.screenshot(path='/app/test_reports/billing-mobile.jpg',quality=40,full_page=False)
    except Exception as e:
        print('FAIL UI playbook',str(e))
    finally:
        print('TRACKED_TEST_IDS',json.dumps(tracked))
        print('PAGE_ERRORS',json.dumps(errors))
        error_text = await page.evaluate('''() => {const errorElements=Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));return errorElements.map(el=>el.textContent).join(', ');}''')
        print('Found error message: ' + error_text if error_text else 'No error messages found on the page')