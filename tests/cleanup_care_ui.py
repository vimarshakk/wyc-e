"""Delete only captured IDs created by this browser run; retain audit history."""
from dotenv import dotenv_values
from pymongo import MongoClient

env = dotenv_values('/app/backend/.env')
client = MongoClient(env['MONGO_URL'])
db = client[env['DB_NAME']]
docs = [('pres_bc992304663643d5','file_19dd0bb9449d4ca4','wysh_prescriptions'),('lab_3857b721077c4506','file_e81ba01be49048bb','wysh_lab_reports')]
for did,fid,col in docs:
    db[col].delete_one({'document_id':did})
    db.wysh_files.delete_one({'file_id':fid})
    db.wysh_health_records.delete_many({'source_document_id':did})
for col,field,ids in [
    ('wysh_care_reminders','reminder_id',['rem_47ad39c50b554e1b']),
    ('wysh_appointments','appointment_id',['apt_d2b508b562844481']),
    ('wysh_consultations','consultation_id',['con_7ec5199180074c4c']),
    ('wysh_consultation_notes','note_id',['note_92b3e93fef0f4fb9']),
    ('wysh_invoices','invoice_id',['inv_d704d751a2824153']),
    ('wysh_invoice_lines','invoice_id',['inv_d704d751a2824153']),
]:
    for ident in ids:
        db[col].delete_many({field:ident})
for uid in ['usr_faba422750d6442d','usr_f5f5d28b457945f1','usr_35114180f52e4b10']:
    db.wysh_users.delete_one({'user_id':uid})
    db.wysh_identities.delete_one({'user_id':uid})
    db.wysh_reminder_preferences.delete_one({'patient_id':uid})
    db.wysh_availability.delete_many({'doctor_id':uid})
assert all(db.wysh_users.count_documents({'user_id':uid}) == 0 for uid in ['usr_faba422750d6442d','usr_f5f5d28b457945f1','usr_35114180f52e4b10'])
assert all(db[col].count_documents({'document_id':did}) == 0 for did,fid,col in docs)
client.close()
print('PASS targeted browser database cleanup; synthetic storage objects retained (no delete API)')