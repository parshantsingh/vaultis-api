# Vaultis API

A wallet and payments backend built with Django REST Framework. Users hold balances, transfer money to each other, and every transaction is backed by a proper ledger instead of a single balance column that can quietly drift out of sync.

## Why this project

I wanted to build something that isn't just another CRUD API. Handling money means dealing with problems most side projects skip entirely — what happens when two transfer requests hit the same wallet at the same time, what happens when a client retries a request that actually already succeeded, how do you prove after the fact that the numbers still add up. This project is me working through those problems properly instead of hand-waving them.

## Core ideas

- Balances aren't stored directly — they're derived from ledger entries. Every transaction writes a debit and a matching credit, and the database rejects anything that doesn't balance to zero.
- Transfers lock the wallet rows involved before changing anything, so two concurrent requests can't corrupt a balance.
- Mutating requests accept an `Idempotency-Key` header, so a retried request can't charge someone twice.

## Stack

Python, Django, Django REST Framework, PostgreSQL, Celery, Redis, Docker.

## Status

User accounts and wallets (one per currency) are working end to end. The ledger and transfer logic are next.

## Setup

```bash
git clone <repo-url>
cd vaultis-api
python -m venv venv
venv\Scripts\activate       # macOS/Linux: source venv/bin/activate
pip install -r requirements/base.txt
python manage.py migrate
python manage.py runserver
```

## License

MIT
