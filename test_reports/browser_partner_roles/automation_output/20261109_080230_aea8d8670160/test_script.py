async def run_test(page, output_dir, page_url):
    scope = {}
    exec(open('/app/tests/partner_ui_playbook.py').read(), scope)
    await scope['run'](page)
