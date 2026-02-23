# Google Calendar Booking — Phase 1 (Nylas)

A booking system that lets business owners connect their Google Calendar and allows customers to view availability and book time slots directly.

## Stack

- **Backend:** Python / FastAPI (Vercel serverless)
- **Database:** PostgreSQL (Neon)
- **Calendar API:** Nylas v3
- **Frontend:** Vanilla HTML / JS / CSS

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy env template and fill in values
cp .env.example .env

# Run locally
uvicorn api.index:app --reload
```

## Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `NYLAS_CLIENT_ID` | Nylas application client ID |
| `NYLAS_CLIENT_SECRET` | Nylas application client secret |
| `NYLAS_API_KEY` | Nylas API key for server-side calls |
| `NYLAS_API_URI` | Nylas API base URL |
| `NYLAS_CALLBACK_URI` | OAuth callback URL |
| `ENCRYPTION_KEY` | Fernet key for encrypting grant IDs at rest |
| `BUSINESS_HOURS_START` | Daily start time, e.g. `09:00` |
| `BUSINESS_HOURS_END` | Daily end time, e.g. `17:00` |
| `SLOT_DURATION_MINUTES` | Slot length in minutes, default `30` |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/auth/google?owner_id=UUID` | Redirect owner to Nylas OAuth |
| `GET` | `/auth/google/callback` | OAuth callback from Nylas |
| `GET` | `/api/availability?owner_id=UUID&date=YYYY-MM-DD` | Get available time slots |
| `POST` | `/api/book` | Book a time slot |

## Deploy to Vercel

```bash
vercel --prod
```

Set all environment variables in Vercel dashboard before deploying.
