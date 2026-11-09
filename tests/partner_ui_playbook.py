"""Same-screen role login and guarded partner portal browser regression."""
import re
from pathlib import Path


async def run(page):
    origin = page.url.split('/login')[0].rstrip('/')
    credentials = Path('/app/memory/test_credentials.md').read_text()
    await page.set_viewport_size({'width': 1920, 'height': 1080})
    results = []
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    for role in ('Lab', 'Patient', 'Doctor', 'Admin'):
        try:
            await page.goto(origin + '/login')
            row = re.search(r'\|\s*' + role + r'\s*\|\s*([^|]+)\|\s*([^|]+)\|', credentials)
            assert row, 'Documented credentials missing'
            await page.get_by_test_id('login-email').fill(row[1].strip())
            await page.get_by_test_id('login-password').fill(row[2].strip())
            await page.get_by_test_id('login-submit').click(force=True)
            await page.wait_for_url('**/app/' + role.lower(), timeout=15000)
            await page.get_by_test_id('app-nav').wait_for(state='visible', timeout=15000)
            print('PASS same login screen routes ' + role + ' correctly')
            results.append(role + ' login PASS')
            if role == 'Lab':
                assert await page.get_by_test_id('partner-portal-heading').inner_text() == 'Lab operations'
                assert 'No patient information is available' in await page.get_by_test_id('partner-empty-state').inner_text()
                assert await page.get_by_test_id('partner-consent-gate').is_visible()
                assert await page.get_by_test_id('nav-operations').is_visible()
                assert await page.get_by_test_id('nav-records').count() == 0
                print('PASS lab consent-gated empty queue and partner-only navigation')
                results.append('Lab empty portal PASS')
                await page.reload()
                await page.get_by_test_id('partner-empty-state').wait_for(state='visible')
                print('PASS lab session persists after reload')
                await page.goto(origin + '/app/pharmacy')
                await page.wait_for_url('**/app/lab')
                print('PASS lab cannot open pharmacy role portal')
                await page.screenshot(path='/app/test_reports/partner-lab-desktop.jpeg', quality=40, full_page=False)
                await page.set_viewport_size({'width': 390, 'height': 844})
                assert await page.get_by_test_id('partner-empty-state').is_visible()
                assert await page.get_by_test_id('mobile-nav-select').is_visible()
                assert await page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                await page.get_by_test_id('mobile-nav-select').select_option('/app/lab')
                await page.screenshot(path='/app/test_reports/partner-lab-mobile.jpeg', quality=40, full_page=False)
                print('PASS mobile lab portal fits screen and navigation works')
                await page.set_viewport_size({'width': 1920, 'height': 1080})
            if role in ('Patient', 'Doctor', 'Admin'):
                await page.goto(origin + '/app/lab')
                await page.wait_for_url('**/app/' + role.lower(), timeout=15000)
                assert await page.get_by_test_id('partner-consent-gate').count() == 0
                print('PASS ' + role + ' lab route rejected and redirected to own dashboard')
                results.append(role + ' lab guard PASS')
            await page.get_by_test_id('nav-logout').click(force=True)
            await page.wait_for_url(origin + '/', timeout=15000)
            assert await page.evaluate("localStorage.getItem('wysh_token')") is None
            print('PASS ' + role + ' logout removes token')
        except Exception as exc:
            print('FAIL ' + role + ': ' + str(exc))
            results.append(role + ' FAIL ' + str(exc))
            await page.evaluate('localStorage.removeItem("wysh_token")')
    try:
        await page.goto(origin + '/app/lab')
        await page.wait_for_url('**/login', timeout=15000)
        print('PASS anonymous lab route redirects to login')
        results.append('Anonymous guard PASS')
    except Exception as exc:
        print('FAIL anonymous guard: ' + str(exc))
        results.append('Anonymous guard FAIL')
    error_text = await page.evaluate("""() => {
        const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
        return errorElements.map(el => el.textContent).join(", ");
    }""")
    print(f'Found error message: {error_text}' if error_text else 'No error messages found on the page')
    print('Page errors:', errors)
    print('UI results:', results)