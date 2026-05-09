# Baytseha Backend

FastAPI backend for بيت الصحة - Baytseha wellness store.

## Stack

- Python 3.12
- FastAPI
- SQLAlchemy 2.x async + asyncpg
- Alembic migrations
- PostgreSQL
- MaxMind minFraud Insights
- Meta/TikTok/Snapchat CAPI
- Google Sheets webhook

## Local Setup

1. Copy env example and fill values:
   ```bash
   cp .env.example .env.local
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run migrations and start server:
   ```bash
   RUN_MIGRATIONS_ON_START=true uvicorn app.main:app --reload --port 8000
   ```

## Docker (local dev)

From the project root:
```bash
docker compose up --build
```

## EasyPanel Deployment

- Service name: `baytseha-api`
- Domain: `api.Baytseha.shop`
- Port: `8000`
- Set all env vars from `.env.example` in EasyPanel service config.
- Use existing EasyPanel PostgreSQL database.
- If your database password contains `@`, URL-encode it as `%40` in DATABASE_URL.

## API Endpoints

- `GET /api/v1/health` - Health check
- `POST /api/v1/orders/validate` - Validate order before upsell
- `POST /api/v1/orders` - Create order (fraud check, CAPI, Sheets)
- `GET /api/v1/currency/rates` - Exchange rates for display

## Environment

Required for production:
- `DATABASE_URL` - PostgreSQL async URL
- `MAXMIND_ACCOUNT_ID` + `MAXMIND_LICENSE_KEY` - Fraud prevention
- `GOOGLE_SHEETS_WEBHOOK_URL` + `GOOGLE_SHEETS_WEBHOOK_SECRET` - Order sync
- `META_CAPI_ACCESS_TOKEN` - Meta Conversions API
- `TIKTOK_ACCESS_TOKEN` - TikTok Events API
- `SNAP_ACCESS_TOKEN` - Snapchat CAPI

## Tests

```bash
pytest tests/ -v
```
