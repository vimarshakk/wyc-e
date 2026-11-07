"""Remove only captured test-owned UI records; no prefix-based or unfiltered cleanup."""
from dotenv import dotenv_values
from pymongo import MongoClient

env = dotenv_values('/app/backend/.env')
client = MongoClient(env['MONGO_URL'])
db = client[env['DB_NAME']]
uid = 'usr_6b02aa07fd6c4d13'
aid = 'apt_95d10f2dadd14a84'
tid = 'toff_9231a5427b4f41'
assert db.wysh_users.find_one({'user_id': uid})['name'] == 'TEST_UI Availability Doctor'
assert db.wysh_appointments.find_one({'appointment_id': aid})['reason'].startswith('TEST_UI booking ')
print('Removed test appointment:', db.wysh_appointments.delete_one({'appointment_id': aid}).deleted_count)
print('Removed own timeoff if present:', db.wysh_time_off.delete_one({'time_off_id': tid, 'doctor_id': uid}).deleted_count)
print('Removed own schedule:', db.wysh_availability.delete_many({'doctor_id': uid}).deleted_count)
print('Removed own identity:', db.wysh_identities.delete_one({'user_id': uid}).deleted_count)
print('Removed own doctor:', db.wysh_users.delete_one({'user_id': uid}).deleted_count)
assert not db.wysh_appointments.find_one({'appointment_id': aid})
assert not db.wysh_users.find_one({'user_id': uid})
client.close()