"""Reusable Playwright patient flow corresponding to the browser-tested booking sequence.

Call run(page) from an async Playwright harness. Only books/cancels its own appointment.
The caller must delete the returned test-owned appointment ID after the run.
"""
from datetime import datetime, timedelta, timezone
from dotenv import dotenv_values


async def run(page):
    base = dotenv_values('/app/frontend/.env')['REACT_APP_BACKEND_URL'].rstrip('/')
    await page.set_viewport_size({'width': 1920, 'height': 1080})
    apt = None
    try:
        await page.goto(base + '/login')
        await page.get_by_test_id('login-email').fill('patient@wyshcare.io')
        await page.get_by_test_id('login-password').fill('TestPass123!')
        await page.get_by_test_id('login-submit').click()
        await page.wait_for_url('**/app/patient')
        print('PASS patient login')
        await page.goto(base + '/app/availability')
        await page.wait_for_url('**/app/patient')
        print('PASS doctor-only route protection')
        await page.get_by_test_id('nav-appointments').click()
        await page.wait_for_function("Array.from(document.querySelector('[data-testid=\"appt-doctor-select\"]').options).some(o=>o.text.includes('Dr. Anaya Shah'))")
        did = await page.get_by_test_id('appt-doctor-select').evaluate("el=>Array.from(el.options).find(o=>o.text.includes('Dr. Anaya Shah')).value")
        nextmon = (datetime.now(timezone.utc).date() + timedelta(days=(7 - datetime.now(timezone.utc).weekday()) % 7 or 7)).isoformat()
        await page.get_by_test_id('appt-doctor-select').select_option(did)
        await page.get_by_test_id('appt-date').fill(nextmon)
        await page.get_by_test_id('slot-grid').wait_for(state='visible')
        await page.get_by_test_id('slot-grid').locator('[data-testid^="slot-"]').first.click()
        await page.get_by_test_id('appt-mode-in_person').click()
        reason = 'TEST_UI booking ' + datetime.now(timezone.utc).isoformat()
        await page.get_by_test_id('appt-reason').fill(reason)
        async with page.expect_response(lambda r: r.url.endswith('/api/appointments') and r.request.method == 'POST') as info:
            await page.get_by_test_id('appt-book-btn').click()
        response = await info.value
        assert response.status == 200
        apt = await response.json()
        print('TEST_CREATED_APPOINTMENT_ID=' + apt['appointment_id'])
        await page.get_by_test_id('appt-cancel-' + apt['appointment_id']).wait_for(state='visible')
        assert reason in await page.get_by_test_id('appt-list').inner_text()
        print('PASS scheduled list persistence')
        token = await page.evaluate("localStorage.getItem('wysh_token')")
        response = await page.request.get(base + '/api/availability/' + did + '/slots?date=' + nextmon,
                                          headers={'Authorization': 'Bearer ' + token})
        assert response.status == 200
        assert apt['scheduled_at'] not in (await response.json())['slots']
        print('PASS booked slot exclusion')
        await page.get_by_test_id('appt-cancel-' + apt['appointment_id']).click()
        await page.get_by_test_id('appt-cancel-' + apt['appointment_id']).wait_for(state='detached')
        print('PASS own appointment cancellation')
    except Exception as error:
        print('FAIL patient flow:', str(error))
        raise
    finally:
        if apt:
            token = await page.evaluate("localStorage.getItem('wysh_token')")
            response = await page.request.post(base + '/api/appointments/' + apt['appointment_id'] + '/cancel',
                                               headers={'Authorization': 'Bearer ' + token})
            print('Cleanup cancellation:', response.status)
        error_text = await page.evaluate("""() => {
          const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
          return errorElements.map(el => el.textContent).join(', ');
        }""")
        print(f'Found error message: {error_text}' if error_text else 'No error messages found on the page')
    return apt['appointment_id']