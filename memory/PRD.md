# WyshCare PRD — Phase 1

## Original problem statement
Build the foundational production-grade platform for WYSHCARE — India's AI-Native Healthcare Operating System. Identity (WyshID), patient/doctor/admin role-based portals, EMR records, OCR + AI prescription intelligence, appointments, audit logging. Investor-grade. Architecturally comparable to Epic / Cerner / Stripe.

## Constraints
- Environment: React (CRA) + FastAPI + MongoDB (Motor)
- AI: Claude Sonnet 4.5 via Emergent Universal LLM Key (`emergentintegrations`)
- Auth: JWT email/password + Emergent-managed Google OAuth
- Storage: Emergent object storage
- All data models designed to be migration-compatible toward Postgres+Prisma (UUID PKs, no embedded refs, ISO datetimes).

## Architecture
- Backend: modular monolith — `backend/app/{core,modules}`
  - `core/`: config, db, security (JWT/bcrypt), audit, deps (auth verifier with role guards)
  - `modules/auth`: signup, login, google/exchange, me, logout
  - `modules/identity`: WyshID issuance + lookup
  - `modules/records`: EMR CRUD + longitudinal timeline
  - `modules/ocr`: upload + Claude Sonnet 4.5 vision extraction
  - `modules/appointments`: book, mine, cancel, doctor list
  - `modules/availability`: recurring doctor hours, time-off windows, India-local slot generation
  - `modules/admin`: stats, users, audit
  - `modules/storage`: Emergent object-storage abstraction
  - `modules/ai`: LLM provider abstraction (currently Claude)
- Collections: `wysh_users`, `wysh_sessions`, `wysh_identities`, `wysh_health_records`, `wysh_prescriptions`, `wysh_appointments`, `wysh_availability`, `wysh_time_off`, `wysh_audit_logs`, `wysh_files`

## Personas
- **Patient** — claims a WyshID, scans prescriptions, books appointments, views longitudinal record.
- **Doctor** — sees scheduled queue, looks up patients by WyshID.
- **Admin** — control room with platform stats + audit log.

## Phase 1 — Implemented (2026-02-14)
- [x] Modular FastAPI architecture (DDD-inspired)
- [x] JWT email/password auth + Google OAuth (Emergent) dual verifier
- [x] WyshID issuance (`WYSH-XXXX-XXXX`) with trust scoring scaffold
- [x] RBAC: patient/doctor/admin role guards
- [x] EMR records + longitudinal timeline endpoint
- [x] OCR pipeline (upload → Emergent storage → Claude Sonnet 4.5 vision extraction → structured prescription)
- [x] Appointments (book/list/cancel)
- [x] Admin stats + audit log
- [x] Audit logging on every significant action
- [x] Landing, Login, Signup, AuthCallback (Google), Patient/Doctor/Admin dashboards, OCR upload UI, Records, Appointments, WyshID card
- [x] Premium design system: Outfit + IBM Plex Sans + Mono, bone/slate palette + coral #FF5722 accent, bento grids, glass nav
- [x] Doctor availability and slot booking UI (2026-11-07): doctor-only schedule management, time-off, India-local slots, patient slot selection, and mobile navigation
- [x] Availability safety rules (2026-11-07): past-slot exclusion, whole-slot time-off overlap handling, overlapping-window rejection, patient-only bookings, and an active doctor/slot uniqueness guard

## Latest verification (2026-11-07)
- Availability regression suite: **17/17 passed** against the public preview API.
- Frontend production build: passed.
- Browser smoke tests: doctor schedule save on desktop; mobile navigation to Availability with readable stacked controls.

## Backlog (prioritized)
- P0: Telemedicine session shell (video room, encounter notes)
- P0: Notifications (email/SMS/WhatsApp) — Twilio/Resend
- P1: Lab report OCR with normalization
- P1: Complete prescription OCR extraction pipeline hardening and review workflow
- P1: Healthcare graph layer (Neo4j-ready edges)
- P1: Consent architecture + DPDP-Act-aware data sharing flows
- P2: Billing/invoices
- P2: Imaging metadata viewer
- P2: Migration script: MongoDB → Postgres/Prisma

## Wow improvement idea
Add **medication adherence reminders** with SMS/WhatsApp triggered automatically from OCR-extracted prescriptions. Massive retention/value lever — turns every scan into an ongoing care loop and unlocks pharmacy partnerships.
