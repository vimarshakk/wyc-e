"""Exercise real pharmacy/insurer/partner login portals using captured disposable fixtures."""
import json
from pathlib import Path
from dotenv import dotenv_values


async def run(page):
    origin = dotenv_values('/app/frontend/.env')['REACT_APP_BACKEND_URL'].rstrip('/')
    partners = json.loads(Path('/app/tests/.partner_ui_fixtures.json').read_text())
    content = {'pharmacy': ('Pharmacy fulfilment', 'fulfilment'), 'insurer': ('Insurer workspace', 'claims'), 'partner': ('Partner workspace', 'workspace')}
    network_paths = []
    page.on('request', lambda req: network_paths.append(req.url.split('/api/', 1)[1]) if '/api/' in req.url else None)
    await page.set_viewport_size({'width': 1920, 'height': 1080})
    for body in partners:
        role = body['role']
        heading, nav = content[role]
        try:
            await page.goto(origin + '/login')
            await page.get_by_test_id('login-email').fill(body['email'])
            await page.get_by_test_id('login-password').fill(body['password'])
            await page.get_by_test_id('login-submit').click(force=True)
            await page.wait_for_url('**/app/' + role, timeout=15000)
            await page.get_by_test_id('partner-consent-gate').wait_for(state='visible')
            assert await page.get_by_test_id('partner-portal-heading').inner_text() == heading
            assert 'No patient information is available' in await page.get_by_test_id('partner-empty-state').inner_text()
            assert await page.get_by_test_id('nav-' + nav).is_visible()
            await page.get_by_test_id('nav-' + nav).click(force=True)
            assert page.url == origin + '/app/' + role
            await page.goto(origin + '/app/patient')
            await page.wait_for_url('**/app/' + role, timeout=15000)
            print('PASS ' + role + ' provisioned login, empty consent queue, nav and patient-dashboard guard')
            await page.get_by_test_id('nav-logout').click(force=True)
            await page.wait_for_url(origin + '/', timeout=15000)
        except Exception as exc:
            print('FAIL ' + role + ': ' + str(exc))
            await page.evaluate('localStorage.removeItem("wysh_token")')
    assert not any(path.startswith(('records', 'appointments', 'ocr', 'admin/', 'billing', 'nhcx')) for path in network_paths), 'Partner portal requested patient-data API: ' + str(network_paths)
    print('PASS partner portals call only auth APIs, never patient-data APIs; paths:', network_paths)
    error_text = await page.evaluate("""() => {
        const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
        return errorElements.map(el => el.textContent).join(", ");
    }""")
    print(f'Found error message: {error_text}' if error_text else 'No error messages found on the page')