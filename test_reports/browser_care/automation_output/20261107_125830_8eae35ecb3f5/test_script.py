async def run_test(page, output_dir, page_url):
    import sys
    sys.path.insert(0, '/app/tests')
    from care_ui_playbook import run
    await run(page)
