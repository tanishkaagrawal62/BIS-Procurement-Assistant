# BIS Assist — React + Vite

This existing frontend uses React and Vite with Oxlint. Backend setup, supported workflows and current service limits are documented below.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and Oxlint's TypeScript related rules in your project.

## BIS Assist backend and run instructions

This project keeps the existing React/Vite frontend and adds a FastAPI backend. Open two terminals in the project folder.

On Windows, you can start the app with one command instead: right-click `Start BIS Assist.ps1`, choose **Run with PowerShell**, and open `http://localhost:5173`. The launcher starts whichever local service is stopped and checks that both services respond. Startup logs are written to the Windows Temp folder.

Terminal 1 (Windows):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://localhost:5173`, create an account, then submit a tender. Vite forwards `/api` to the backend. SQLite is created at `backend/data/bis_assist.sqlite3` and excluded from Git.

Run checks with `npm run build`, `npm run lint`, and `python -m pytest backend/tests -q`.

### Implemented

- PBKDF2 password hashing, bearer sessions and account-scoped analysis history.
- Manual requirement submission and text-based PDF extraction with a 20 MB size limit.
- Deterministic field extraction with supporting snippets, BM25 keyword ranking, and optional local SBERT.
- Up to three evidence-supported recommendations from records loaded in the local catalogue.
- Generated PDF reports with source/provenance, evidence, ranking indicators and a disclaimer.
- Live keyword search against the public BIS Know Your Standards service. Search results are cached locally as metadata and ranked against the submitted tender text.

### BIS data and verification limits

The live connector uses BIS's public `searchKnowStandards` service for keyword search and caches the returned standard number, title, publication/validity dates and withdrawal indicator. It does not download standard PDFs or clause text. The recommendation score compares tender text with those returned metadata fields, so it is a discovery aid rather than a full clause-by-clause compliance check. Reconfirm the current record on the official [Know Your Standards search](https://www.services.bis.gov.in/php/BIS_2.0/bisconnect/knowyourstandards/indian_standards/isdetails). BIS publishes an official portal guide for navigating published-standard listings: [Standards Portal guide](https://standards.bis.gov.in/website/how-to-use).

The latest local cache can be exported as a readable JSON snapshot with `python backend/export_standards.py`; it writes `backend/data/bis_standards_cache.json`. This is the set of genuine records fetched by searches run in this app, not a complete BIS catalogue export.

Set `BIS_LIVE_SEARCH_ENABLED=false` to disable calls to BIS. The live connector searches up to five high-signal terms per analysis. BIS's full catalogue Excel export is permission-controlled; the app does not bypass that permission or copy copyrighted specification documents. To import a separately authorized full catalogue, use the reviewed-record importer below.

Only import records from a reviewed, permitted BIS source. Follow `backend/data/standards_catalogue.example.json` and include the source and retrieval date in each `provenance` field. Import with:

```powershell
python backend/import_standards.py path\to\reviewed-bis-catalogue.json
```

The importer accepts HTTPS BIS hosts and `cached` or `unverified` states; it cannot mark records live-verified. A match score does not determine legal applicability or a certification requirement.

### PDF, OCR, SBERT and deployment

Text-based PDFs use PyMuPDF and are processed in memory; extracted text and analysis metadata are stored in the database. Scanned PDFs need OCR, which is not configured; enter their requirements manually. BM25 works locally. SBERT is disabled unless `BIS_SBERT_MODEL_PATH` points to a pre-downloaded model; configure local `sentence-transformers` and `scikit-learn` packages to enable it. No model download or paid AI service is used automatically.

Set `BIS_DATABASE_URL` and `BIS_CORS_ORIGINS` for deployment (see `.env.example`). Use persistent PostgreSQL, HTTPS and backups in production, and set `VITE_API_BASE` to the deployed API URL when building the frontend. No hosting provider is configured in the project. OCR, password reset, rate limiting, database migrations and live BIS verification remain unconfigured.
