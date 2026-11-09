# WYC-e Care Platform PRD

## Product boundary

WYC-e is a patient-first care presentation layer for patients, doctors, administrators and scoped care partners. The clinical system of record remains the authorised WyshCare backend. This repository provides a runnable foundation and must not duplicate production clinical data without an approved migration.

## Core workflows

- Account creation and role-aware sign-in.
- Low-friction public signup: patient accounts are approved immediately; professional and partner accounts enter `PENDING_APPROVAL` and receive no workspace token until admin approval.
- Patient dashboard, appointments, records, documents, care plan and WyshID.
- Doctor availability, consultations and claims workspace.
- ABDM M1–M3 foundations with M4/M5 explicitly gated until onboarding and certification evidence exist.
- NHCX and UHI transaction foundations with outbound calls disabled until participant, callback and cryptographic onboarding pass.
- Human review before OCR output enters any clinical record.

## Safety and release gates

Authentication, authorization, tenant/patient isolation, auditability, external callback verification and workflow tests must pass before enabling clinical writes. Synthetic data is the default local fixture. Secrets are never committed.

## Onboarding policy

Public signup collects only the minimum account information. Admins review professional/partner identity and organization details, then approve or reject from the approval queue. Approved accounts route to their role-specific workspace; all partner workspaces remain consent-gated and deny patient data by default. Admin provisioning creates an already-approved account and is recorded as an audit event.
