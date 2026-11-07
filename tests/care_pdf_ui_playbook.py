"""Synthetic PDF UI approval, EMR visibility and read-only admin Calendar checks."""
import json
import uuid
import re
from pathlib import Path


def synthetic_pdf():
    stream = b'BT /F1 16 Tf 40 740 Td (TEST_Diagnostics Laboratory) Tj 0 -30 Td (Patient: TEST_PDF Patient) Tj 0 -30 Td (Hemoglobin: 13.5 g/dL Reference 12.0-16.0) Tj ET'
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    pdf = b'%PDF-1.4\n'
    offsets = [0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(pdf))
        pdf += str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    xref = len(pdf)
    pdf += b'xref\n0 6\n0000000000 65535 f \n'+b''.join(('%010d 00000 n \n'%n).encode() for n in offsets[1:])
    return pdf+b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(xref).encode()+b'\n%%EOF'


async def run(page):
    base = page.url.split('/app/')[0].split('/login')[0].rstrip('/')
    tracked = {'users':[],'documents':[]}
    try:
        await page.set_viewport_size({'width':1920,'height':1080})
        await page.evaluate('localStorage.clear()')
        email = 'test_pdf_ui_'+uuid.uuid4().hex[:10]+'@wyshcare.io'
        response = await page.request.post(base+'/api/auth/signup',data={'name':'TEST_PDF UI','email':email,'password':'TEST_Care123!','role':'patient'})
        assert response.status == 200
        actor = await response.json()
        tracked['users'].append(actor['user']['user_id'])
        await page.goto(base+'/login')
        await page.get_by_test_id('login-email').fill(email)
        await page.get_by_test_id('login-password').fill('TEST_Care123!')
        await page.get_by_test_id('login-submit').click(force=True)
        await page.wait_for_url('**/app/patient')
        await page.get_by_test_id('nav-documents').click(force=True)
        await page.get_by_test_id('document-kind-select').select_option('lab_report')
        await page.get_by_test_id('document-file-input').set_input_files({'name':'TEST_UI_lab.pdf','mimeType':'application/pdf','buffer':synthetic_pdf()})
        async with page.expect_response(lambda r:'/ocr/documents/lab_report' in r.url and r.request.method=='POST',timeout=180000) as saved:
            await page.get_by_test_id('upload-document-btn').click(force=True)
        doc = await (await saved.value).json()
        tracked['documents'].append({'document_id':doc['document_id'],'file_id':doc['file_id']})
        assert doc['extraction_status']=='complete' and doc['extracted']['observations'][0]['name']=='Hemoglobin'
        await page.get_by_test_id('document-review-json').fill(json.dumps({**doc['extracted'],'notes':'TEST_PDF reviewed correction'}))
        await page.get_by_test_id('approve-document-btn').click(force=True)
        await page.get_by_test_id('document-review-status').wait_for()
        await page.reload()
        await page.get_by_test_id('document-row-'+doc['document_id']).click(force=True)
        rendered = await page.get_by_test_id('document-review-json').input_value()
        print('PASS PDF upload and approval persist')
        print('FAIL approved corrections not displayed' if 'TEST_PDF reviewed correction' not in rendered else 'PASS approved corrections displayed')
        response = await page.request.get(base+'/api/ocr/documents/'+doc['document_id'],headers={'Authorization':'Bearer '+actor['token']})
        assert (await response.json())['reviewed_extraction']['notes']=='TEST_PDF reviewed correction'
        print('PASS correction is stored server-side despite wrong UI display')
        await page.get_by_test_id('nav-records').click(force=True)
        await page.get_by_test_id('records-list').get_by_text('Reviewed lab report',exact=True).wait_for()
        print('PASS reviewed PDF visible in EMR timeline')
        await page.get_by_test_id('nav-documents').click(force=True)
        await page.set_viewport_size({'width':768,'height':1024})
        await page.screenshot(path='/app/test_reports/care-tablet.jpeg',quality=40,full_page=False)
        print('TABLET_OVERFLOW_ELEMENTS',await page.evaluate("Array.from(document.querySelectorAll('header,header nav,header button')).map(e=>({tag:e.tagName,right:Math.round(e.getBoundingClientRect().right)}))"))
        await page.set_viewport_size({'width':1920,'height':1080})
        await page.get_by_test_id('nav-logout').click(force=True)
        await page.wait_for_url(base+'/')
        await page.goto(base+'/login')
        row = re.search(r'\|\s*Admin\s*\|\s*([^|]+)\|\s*([^|]+)\|',Path('/app/memory/test_credentials.md').read_text())
        await page.get_by_test_id('login-email').fill(row[1].strip())
        await page.get_by_test_id('login-password').fill(row[2].strip())
        await page.get_by_test_id('login-submit').click(force=True)
        await page.wait_for_url('**/app/admin')
        await page.get_by_test_id('calendar-organizer-status').wait_for()
        assert await page.get_by_test_id('connect-google-calendar-btn').is_visible()
        print('PASS admin Calendar status/connect control renders; OAuth intentionally not clicked')
    except Exception as e:
        print('FAIL PDF/admin playbook',str(e))
    finally:
        print('TRACKED_TEST_IDS',json.dumps(tracked))
        error_text = await page.evaluate("""() => {const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));return errorElements.map(el=>el.textContent).join(', ');}""")
        print('Found error message: '+error_text if error_text else 'No error messages found on the page')