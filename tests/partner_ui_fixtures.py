"""Create and clean only captured disposable UI partners; never modify documented accounts."""
import json
import re
import sys
import uuid
from pathlib import Path
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

fixture = Path('/app/tests/.partner_ui_fixtures.json')
if sys.argv[1] == 'setup':
    origin = dotenv_values('/app/frontend/.env')['REACT_APP_BACKEND_URL'].rstrip('/')
    row = re.search(r'\|\s*Admin\s*\|\s*([^|]+)\|\s*([^|]+)\|', Path('/app/memory/test_credentials.md').read_text())
    login = requests.post(origin + '/api/auth/login', json={'email': row[1].strip(), 'password': row[2].strip()}, timeout=30)
    assert login.status_code == 200
    headers = {'Authorization': 'Bearer ' + login.json()['token']}
    partners = []
    fixture.write_text('[]')
    for role in ('pharmacy', 'insurer', 'partner'):
        body = {'email': 'TEST_ui_partner_' + uuid.uuid4().hex[:12] + '@wyshcare.io', 'password': 'TEST_UIPartnerPass123!', 'name': 'TEST_UI Partner', 'role': role, 'organization_name': 'TEST_UI Consent Organization'}
        response = requests.post(origin + '/api/auth/partners', json=body, headers=headers, timeout=30)
        assert response.status_code == 201
        partners.append({**body, 'user_id': response.json()['user_id']})
        fixture.write_text(json.dumps(partners))
    print('Prepared three disposable admin-provisioned partners')
elif sys.argv[1] == 'cleanup':
    env = dotenv_values('/app/backend/.env')
    client = MongoClient(env['MONGO_URL'])
    db = client[env['DB_NAME']]
    partners = json.loads(fixture.read_text())
    for partner in partners:
        uid = partner['user_id']
        db.wysh_users.delete_one({'user_id': uid})
        db.wysh_identities.delete_one({'user_id': uid})
        assert db.wysh_users.count_documents({'user_id': uid}) == 0
    fixture.unlink()
    client.close()
    print('Verified cleanup of captured UI partner IDs:', len(partners))