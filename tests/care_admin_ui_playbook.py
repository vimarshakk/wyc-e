"""Isolated documented-admin login; never invoke external organizer OAuth."""
import re
from pathlib import Path

async def run(page):
    base = page.url.split('/app/')[0].rstrip('/')
    try:
        await page.set_viewport_size({'width':1920,'height':1080})
        await page.evaluate('localStorage.clear()')
        await page.goto(base+'/login')
        row = re.search(r'\|\s*Admin\s*\|\s*([^|]+)\|\s*([^|]+)\|',Path('/app/memory/test_credentials.md').read_text())
        await page.get_by_test_id('login-email').fill(row[1].strip())
        await page.get_by_test_id('login-password').fill(row[2].strip())
        await page.get_by_test_id('login-submit').click(force=True)
        await page.wait_for_url('**/app/admin')
        await page.get_by_test_id('calendar-organizer-status').wait_for()
        assert await page.get_by_test_id('connect-google-calendar-btn').is_visible()
        print('PASS isolated admin Calendar status/connect control renders; no external OAuth invoked')
        await page.screenshot(path='/app/test_reports/care-admin.jpeg',quality=40,full_page=False)
    except Exception as e:
        print('FAIL isolated admin UI:',str(e))
    error_text = await page.evaluate("""() => {const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));return errorElements.map(el=>el.textContent).join(', ');}""")
    print('Found error message: '+error_text if error_text else 'No error messages found on the page')