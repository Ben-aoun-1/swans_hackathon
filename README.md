# Richards & Law — Automated Client Intake System

> From police report to signed retainer in under 3 minutes.

Built for **Richards & Law**, a personal injury law firm in New York. This system replaces a ~45-minute manual intake process with an AI-powered pipeline that extracts structured data from police report PDFs, lets a paralegal verify it, then pushes everything to Clio Manage — creating contacts, updating matters, generating retainer agreements, calendaring statute of limitations dates, and emailing the client — all in a single click.

---

## How It Works

```
                    ┌─────────────────────┐
                    │   Police Report PDF  │
                    └──────────┬──────────┘
                               ▼
              ┌────────────────────────────────┐
              │   Claude Sonnet 4.6 (Vision)    │
              │   Extracts 30+ fields per page  │
              │   with per-field confidence      │
              └────────────────┬───────────────┘
                               ▼
              ┌────────────────────────────────┐
              │   Paralegal Review UI           │
              │   Side-by-side PDF + form       │
              │   Edit, verify, approve         │
              └────────────────┬───────────────┘
                               ▼
              ┌────────────────────────────────┐
              │   19-Step Clio Pipeline          │
              │                                 │
              │   1.  Authenticate              │
              │   2.  Map custom fields         │
              │   3.  Conflict of interest check│
              │   4.  Find or create contact    │
              │   5.  Find or create matter     │
              │   6.  Duplicate report check    │
              │   7.  Update custom fields      │
              │   8.  Advance matter stages     │
              │   9.  Generate retainer (PDF)   │
              │   10. Calendar entry (+8 years) │
              │   11. AI-personalized email     │
              │   12. Send client email          │
              │   13. Upload police report       │
              │   14. Upload retainer to Clio    │
              │   15. Create task list           │
              │   16. Log intake activity        │
              │   17. Log email communication    │
              │   18. Case priority scoring      │
              │   19. Final stage advancement    │
              └────────────────────────────────┘
```

---

## Features

### AI Extraction (Claude Sonnet 4.6 Vision)
- Processes multi-page police report PDFs — no OCR pipeline needed
- Two-pass extraction: raw field reading, then plaintiff/defendant role assignment using fault analysis
- Per-field confidence tracking (high / medium / low) with source metadata
- Handles handwriting, stamps, checkboxes, and poor scan quality
- Supports NY MV-104 form layout with graceful fallback for other formats
- Extracts 30+ fields: accident details, party info, vehicles, insurance, injuries, officer info

### Human Review UI
- Side-by-side PDF viewer and editable extraction form
- Fields color-coded by confidence: green (high), orange (medium), red (low), blue (inferred)
- Expandable party cards with role badges (plaintiff/defendant/witness)
- Inline editing for every extracted field
- Occupant management (drivers, passengers, pedestrians)
- One-click "Approve & Push to Clio" or "Re-extract" to try again

### Clio Manage Integration (19-Step Pipeline)
- **Smart contact resolution** — finds existing contacts by email or name before creating duplicates
- **Smart matter resolution** — searches by contact, prefers attorney match, creates only when needed
- **Duplicate report detection** — skips re-processing if the same report number already exists on a matter
- **18 custom field updates** — accident date, location, parties, vehicles, insurance, injuries, officer info
- **Progressive stage advancement** — walks through New Lead → Report Received → Data Verified → Retainer Sent
- **Retainer generation** — via Clio document automation (with local Word-to-PDF fallback)
- **Statute of limitations calendar** — accident date + 8 years, assigned to responsible attorney
- **Police report & retainer upload** — attaches both PDFs to the matter
- **Auto-generated task list** — creates intake workflow tasks on the matter
- **Activity & communication logging** — full audit trail in Clio
- **Case priority scoring** — 1–10 scale based on injury severity, vehicle count, and other factors
- **Conflict of interest check** — warns if the defendant is an existing client

### Personalized Client Email
- AI-generated empathetic paragraph using Claude Haiku
- Retainer agreement PDF attached
- Seasonal booking link: in-office (March–August) or virtual (September–February)
- Sent via SMTP with HTML and plain text versions

### Self-Configuring Clio Setup
- One-click auto-configure: creates practice area, matter stages, and 18 custom fields
- Read-only check mode to inspect account configuration
- Step-by-step manual instructions when API permissions are restricted
- OAuth connection management with disconnect/reconnect

### Multi-User Support
- Per-session Clio token storage — multiple users can connect their own accounts
- Session-based cookie authentication (httponly, 24h expiration)
- Automatic token refresh on expiration

---

## Tech Stack

### Backend

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI |
| Language | Python 3.11+ |
| AI Extraction | Claude Sonnet 4.6 (Anthropic SDK) |
| AI Email | Claude Haiku |
| CRM | Clio Manage API v4 (OAuth 2.0) |
| HTTP Client | httpx (async) |
| PDF Processing | PyMuPDF (fitz) |
| Data Validation | Pydantic v2 |
| Email | aiosmtplib (async SMTP) |
| Document Gen | python-docx + LibreOffice |
| Logging | loguru |

### Frontend

| Component | Technology |
|-----------|-----------|
| Framework | Next.js 14 (App Router) |
| UI Library | React 18 |
| Styling | Tailwind CSS |
| Components | shadcn/ui (Radix UI) |
| Forms | React Hook Form + Zod |
| HTTP Client | Axios |
| Icons | Lucide React |
| Language | TypeScript 5 |

---

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI entry point, CORS, routers
│   │   ├── config.py                   # Environment settings (pydantic-settings)
│   │   ├── routers/
│   │   │   ├── extraction.py           # POST /api/extract
│   │   │   ├── review.py              # POST /api/approve
│   │   │   ├── clio_auth.py           # OAuth flow (/api/clio/auth, /callback)
│   │   │   ├── clio_setup.py          # Auto-configure (/api/clio/setup/*)
│   │   │   └── health.py             # GET /api/health
│   │   ├── services/
│   │   │   ├── extraction.py           # PDF → Claude Vision → structured JSON
│   │   │   ├── clio_client.py          # Clio API v4 wrapper (all endpoints)
│   │   │   ├── clio_pipeline.py        # 19-step pipeline orchestration
│   │   │   ├── clio_setup.py           # Auto-configure Clio account
│   │   │   ├── document_gen.py         # Retainer PDF (Clio + local fallback)
│   │   │   ├── email_sender.py         # SMTP email with seasonal booking
│   │   │   ├── calendar.py             # Statute of limitations entry
│   │   │   └── token_store.py          # Per-session token management
│   │   ├── models/
│   │   │   ├── extraction.py           # ExtractionResult, PartyInfo, FieldExtraction
│   │   │   ├── clio.py                # PipelineResult, PipelineStep
│   │   │   └── email.py              # EmailData
│   │   └── prompts/
│   │       └── extraction_prompt.py    # Claude extraction prompt (iterable)
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx                # Upload page (drag-and-drop)
│   │   │   ├── review/page.tsx         # Review & verify extracted data
│   │   │   ├── status/page.tsx         # Real-time pipeline progress
│   │   │   ├── settings/page.tsx       # Clio auth & auto-setup
│   │   │   └── layout.tsx
│   │   ├── components/ui/              # shadcn/ui components
│   │   └── lib/
│   │       ├── api.ts                  # Axios API client
│   │       ├── types.ts               # TypeScript types
│   │       └── ExtractionContext.tsx   # Global state management
│   ├── package.json
│   └── next.config.ts
│
├── templates/
│   └── retainer_agreement.docx         # Word template with Clio merge fields
│
├── samples/                            # Police report PDFs for testing
│
└── CLAUDE.md                           # AI-assisted development instructions
```

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- A [Clio Manage](https://www.clio.com/) account (US region)
- An [Anthropic API key](https://console.anthropic.com/)
- Gmail account with [app-specific password](https://support.google.com/accounts/answer/185833) (for email)

### 1. Clone & configure

```bash
git clone https://github.com/Ben-aoun-1/swans_hackathon.git
cd swans_hackathon
```

### 2. Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials (see Environment Variables below)
```

### 3. Frontend setup

```bash
cd frontend
npm install
```

### 4. Register a Clio Developer App

1. Go to [Clio Developer Portal](https://app.clio.com/nc/#/settings/developer_applications)
2. Create a new application
3. Set redirect URI to `http://localhost:8000/api/clio/callback`
4. Copy the Client ID and Client Secret to your `.env`

### 5. Run

```bash
# Terminal 1 — Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

- Frontend: http://localhost:3000
- Backend API docs: http://localhost:8000/docs

### 6. Connect to Clio

1. Open http://localhost:3000/settings
2. Click "Connect to Clio" and authorize
3. Click "Check Setup" to verify your account configuration
4. Click "Auto-Configure Clio" to create required fields and stages
5. If stages can't be created via API, follow the on-screen manual instructions

---

## Environment Variables

Create `backend/.env`:

```env
# Required — AI Extraction
ANTHROPIC_API_KEY=sk-ant-...

# Required — Clio OAuth
CLIO_CLIENT_ID=your_client_id
CLIO_CLIENT_SECRET=your_client_secret
CLIO_REDIRECT_URI=http://localhost:8000/api/clio/callback

# Required — Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password
FROM_EMAIL=intake@your-firm.com

# Optional — Clio (auto-populated after OAuth)
CLIO_BASE_URL=https://app.clio.com

# Optional — Booking Links
IN_OFFICE_BOOKING_URL=https://calendly.com/swans-santiago-p/summer-spring
VIRTUAL_BOOKING_URL=https://calendly.com/swans-santiago-p/winter-autumn
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/extract` | Upload PDF, extract data via Claude |
| `POST` | `/api/approve` | Push verified data through 19-step Clio pipeline |
| `GET` | `/api/clio/auth` | Get Clio OAuth authorization URL |
| `GET` | `/api/clio/callback` | OAuth callback (exchanges code for tokens) |
| `GET` | `/api/clio/status` | Check Clio connection status |
| `POST` | `/api/clio/disconnect` | Clear session tokens |
| `GET` | `/api/clio/setup/check` | Read-only Clio account inspection |
| `POST` | `/api/clio/setup/run` | Auto-configure Clio (create fields, stages) |

---

## Extraction Fields

The AI extracts the following from each police report:

**Accident Details:** report number, date, time, location, description, weather conditions, road conditions, number of vehicles

**Per Party (plaintiff, defendant, witnesses):** full name, address, date of birth, phone, driver license, vehicle (year/make/model/color), insurance company, policy number, injuries, citations issued, occupants

**Officer Info:** reporting officer name, badge number

**Metadata:** form type (MV-104), amendment status, total pages, field counts, confidence summary

Each field includes:
- `value` — the extracted data
- `confidence` — high, medium, or low
- `source` — explicit (read from form), inferred (interpreted from context), or not_found
- `notes` — explanation of uncertainty if applicable

---

## Clio Custom Fields

The system creates/uses 18 custom fields on matters under an "Accident Details" field set:

| Field | Type |
|-------|------|
| Accident Date | Date |
| Accident Location | Text Line |
| Accident Description | Text Area |
| Police Report Number | Text Line |
| Plaintiff Name | Text Line |
| Plaintiff Address | Text Area |
| Plaintiff DOB | Date |
| Plaintiff Phone | Text Line |
| Plaintiff Vehicle | Text Line |
| Defendant Name | Text Line |
| Defendant Address | Text Area |
| Defendant Insurance | Text Line |
| Defendant Policy Number | Text Line |
| Defendant Vehicle | Text Line |
| Injuries Reported | Text Area |
| Weather Conditions | Text Line |
| Reporting Officer | Text Line |
| Statute of Limitations Date | Date |

---

## Limitations

**Clio API**
- Currently supports US-region Clio accounts only
- Some Clio plans restrict stage and custom field creation via API — the UI provides manual setup instructions as a fallback
- Document templates must be uploaded manually in Clio (Settings → Documents → Templates)
- Document generation via Clio is asynchronous and requires polling

**PDF Processing**
- Optimized for NY MV-104 police report forms; other formats work but with lower confidence
- Severely degraded scans or illegible handwriting may produce low-confidence extractions
- Maximum file size: 50MB

**Session Management**
- Token storage is in-memory — server restarts clear all sessions
- No distributed session management (single-server deployment)

**Email**
- Gmail SMTP has per-minute rate limits
- Requires an app-specific password (not regular Gmail password)

**Document Generation**
- Local PDF fallback (Word → PDF) requires LibreOffice installed on the server
- Clio's document automation is the preferred path

---

## Sample Reports

The `samples/` directory includes NY MV-104 police reports for testing:

- `GUILLERMO_REYES_v_LIONEL_FRANCOIS` — primary demo report
- `DARSHAME_NOEL_v_FRANCIS_E_FREESE`
- `FAUSTO_CASTILLO_v_CHIMIE_DORJEE`
- `JOHN_GRILLO_v_JOHN_GRILLO`
- `MARDOCHEE_VINCENT_v_MARDOCHEE_VINCENT`

---

## License

Private — built for the Swans Applied AI Hackathon.
