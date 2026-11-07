async def run_test(page, output_dir, page_url):
    try:
        scope = {}
        exec(open('/app/tests/care_admin_ui_playbook.py').read(),scope)
        await scope['run'](page)
    except Exception as e:
        print('FAIL admin workflow launch:',str(e))
