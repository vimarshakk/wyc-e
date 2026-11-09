async def run_test(page, output_dir, page_url):
    try:
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.get_by_test_id('login-submit').wait_for(state='visible', timeout=15000)
        print('PASS login screen loads')
        print(await page.locator('body').inner_text())
        await page.screenshot(path='/app/test_reports/browser_partner_initial/automation_output/20261109_075931_a2de4eeef24d/partner-login.jpeg', type="jpeg", quality=40, full_page=False)
    except Exception as e:
        print(f'FAIL initial screen: {e}')
    error_text = await page.evaluate("""() => { const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]')); return errorElements.map(el => el.textContent).join(", "); }""")
    print(f'Found error message: {error_text}' if error_text else 'No error messages found on the page')
