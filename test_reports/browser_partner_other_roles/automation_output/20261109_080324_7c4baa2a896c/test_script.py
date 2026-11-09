async def run_test(page, output_dir, page_url):
    try:
        scope = {}
        exec(open('/app/tests/partner_other_roles_ui_playbook.py').read(), scope)
        await scope['run'](page)
    except Exception as e:
        print(f'FAIL partner other-role workflow: {e}')
