# WYC-e

WYC-e is a mobile-friendly care platform scaffold with a FastAPI/Mongo backend and React frontend.

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

MongoDB is optional for the initial local health/auth workflow. Configure `backend/.env` before enabling external integrations.

## Frontend

```bash
cd frontend
yarn install
yarn start
```

The frontend reads `REACT_APP_API_URL`; default is `http://localhost:8000/api/v1`.

## Safety boundary

ABDM, UHI and NHCX routes are foundations only. External traffic and clinical writes remain gated until authentication, authorization, patient isolation, callback verification, tenant controls and workflow tests pass. Never commit real `.env` values.
