# Vaultis API

![CI](https://github.com/parshantsingh/vaultis-api/actions/workflows/ci.yml/badge.svg)

A wallet and payments backend built with Django REST Framework. Users hold balances, transfer money to each other, and every transaction is backed by a proper ledger instead of a single balance column that can quietly drift out of sync.

## Why this project

I wanted to build something that isn't just another CRUD API. Handling money means dealing with problems most side projects skip entirely — what happens when two transfer requests hit the same wallet at the same time, what happens when a client retries a request that actually already succeeded, how do you prove after the fact that the numbers still add up. This project is me working through those problems properly instead of hand-waving them.

## Core ideas

- Every transfer writes a matching debit and credit as a single database transaction. Before anything commits, the entries are checked to sum to zero — if they don't, nothing is written.
- Transfers lock the wallet rows involved before changing anything, so two concurrent requests can't corrupt a balance.
- The transfer endpoint accepts an `Idempotency-Key` header — a retried request with the same key and the same payload replays the original response instead of moving money again. Reusing the same key for a different request is rejected rather than silently allowed.

## Stack

Python, Django, Django REST Framework, PostgreSQL, Celery, Redis, Docker.

## Status

User accounts, wallets, and transfers (row-locked, concurrency-safe, idempotent) are working end to end. Deposits and withdrawals via Stripe are next.

## Running tests

```bash
docker compose exec web pytest
```

19 tests, including two that fire real concurrent requests at the transfer and idempotency endpoints to prove the row-locking and race-safety actually hold under load, not just in a single-request happy path. Coverage is gated at 90%. Every push to `main` and every pull request runs this same suite via GitHub Actions (see the badge above).

## Code quality

```bash
pip install -r requirements/dev.txt
pre-commit install       # runs ruff, black, and mypy automatically on every commit
pre-commit run --all-files
```

Ruff lints and sorts imports, Black formats, mypy type-checks against django-stubs. All three also run in CI on every push.

## Setup

```bash
git clone <repo-url>
cd vaultis-api
cp .env.example .env          # then edit values if needed
docker compose up --build
docker compose exec web python manage.py migrate
```

API available at `http://localhost:8000/`, docs at `/api/docs/`.

## License

MIT
