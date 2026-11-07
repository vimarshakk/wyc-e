async def run_test(page, output_dir, page_url):
    try:
        exec(open('/app/tests/care_ui_playbook.py').read())
        await run(page)
    except Exception as e:
        print('FAIL browser workflow launch:',str(e))
