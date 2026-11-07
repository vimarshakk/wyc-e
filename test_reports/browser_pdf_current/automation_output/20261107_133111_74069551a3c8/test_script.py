async def run_test(page, output_dir, page_url):
    try:
        scope = {}
        exec(open('/app/tests/care_pdf_ui_playbook.py').read(),scope)
        await scope['run'](page)
    except Exception as e:
        print('FAIL PDF workflow launch:',str(e))
