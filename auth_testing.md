# WyshCare Auth Testing

- WyshCare uses `wysh_sessions` collection (not `user_sessions`).
- `users` collection is `wysh_users`; user IDs are `usr_<hex16>`, WyshIDs are `WYSH-XXXX-XXXX`.
- All queries use `{"_id": 0}` projection.
- Two auth modes:
  1. JWT Bearer (signup/login) — `Authorization: Bearer <jwt>`.
  2. Emergent Google session — cookie `session_token` OR Bearer with session_token.

## Quick verification
```bash
# signup
curl -s -X POST $BACKEND/api/auth/signup -H 'Content-Type: application/json' \
  -d '{"email":"x@y.io","password":"TestPass123!","name":"X Y","role":"patient"}' | jq

# me
curl -s $BACKEND/api/auth/me -H "Authorization: Bearer <token>" | jq
```
