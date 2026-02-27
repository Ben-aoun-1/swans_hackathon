# CLAUDE.md — Swans Applied AI Hackathon

## Project Overview

This is a **production-ready automation system** for Richards & Law, a personal injury law firm in New York. The system automates the intake pipeline: extracting data from police report PDFs using AI, allowing human verification, updating Clio Manage (legal CRM), auto-generating retainer agreements, calendaring statute of limitations dates, and sending personalized client emails.

**The core business problem:** Law firms lose clients because manual data entry from police reports into Clio Manage takes too long. By the time paralegals process a report, the potential client has already signed with a competitor. This system reduces that from ~45 minutes to under 3 minutes.

---

## Architecture

```
Police Report PDF
       │
       ▼
[FastAPI Backend] ──► Claude API (extract structured data from PDF)
       │
       ▼
[Next.js Frontend] ──► Human Review UI (paralegal verifies/edits extracted data)
       │
       ▼
[FastAPI Backend] ──► Clio Manage API pipeline:
       ├── 1. Update Matter custom fields with verified data
       ├── 2. Change Matter stage → triggers Clio document automation (retainer agreement)
       ├── 3. Create calendar entry (accident date + 8 years) for Responsible Attorney
       ├── 4. Retrieve generated retainer agreement PDF from Clio
       └── 5. Send personalized email to client with retainer PDF + seasonal booking link
```

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend | Python + FastAPI | 3.11+ / 0.110+ |
| Frontend | Next.js + React | 15.x / 19.x |
| Styling | Tailwind CSS + shadcn/ui | Latest |
| AI Extraction | Anthropic Claude API (claude-sonnet-4-6-20260217) | Latest |
| CRM | Clio Manage API v4 | REST + OAuth 2.0 |
| Email | SMTP (Gmail) or Resend API | — |
| PDF Handling | PyMuPDF (fitz) for reading, base64 for Claude | — |
| Document Gen | Clio's native document automation (primary) | — |
| Deployment | Local dev / ngrok for OAuth callback | — |

---

## Project Structure

```
swans-hackathon/
├── CLAUDE.md                          # This file
├── README.md                          # Project documentation
├── docker-compose.yml                 # Optional: local dev services
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app entry point
│   │   ├── config.py                  # Settings via pydantic-settings / env vars
│   │   │
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── extraction.py          # POST /api/extract — upload PDF, get extracted data
│   │   │   ├── review.py             # POST /api/approve — push verified data to Clio pipeline
│   │   │   ├── clio_auth.py          # GET /api/clio/auth, /api/clio/callback — OAuth flow
│   │   │   └── health.py             # GET /api/health
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── extraction.py          # Claude API: PDF → structured JSON
│   │   │   ├── clio_client.py         # Clio Manage API wrapper (all endpoints)
│   │   │   ├── clio_pipeline.py       # Orchestrates: update matter → stage change → calendar → email
│   │   │   ├── document_gen.py        # Handles retainer generation via Clio + fallback
│   │   │   ├── email_sender.py        # Sends personalized email with attachment
│   │   │   └── calendar.py            # Creates statute of limitations calendar entry
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── extraction.py          # Pydantic models for extracted police report data
│   │   │   ├── clio.py               # Pydantic models for Clio API requests/responses
│   │   │   └── email.py              # Email template data models
│   │   │
│   │   └── prompts/
│   │       └── extraction_prompt.py   # The Claude extraction prompt (keep separate for iteration)
│   │
│   ├── requirements.txt
│   ├── .env.example
│   └── tests/
│       ├── test_extraction.py
│       └── test_clio_client.py
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx               # Landing / upload page
│   │   │   └── review/
│   │   │       └── page.tsx           # Review & approve extracted data
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                    # shadcn/ui components
│   │   │   ├── PDFUploader.tsx        # Drag-and-drop PDF upload
│   │   │   ├── ExtractionResult.tsx   # Displays extracted fields in editable form
│   │   │   ├── PDFViewer.tsx          # Shows original PDF side-by-side
│   │   │   ├── ApprovalPanel.tsx      # Approve / edit / reject controls
│   │   │   ├── StatusTimeline.tsx     # Shows pipeline progress (extracting → reviewing → pushing to Clio → done)
│   │   │   └── EmailPreview.tsx       # Preview of the client email before sending
│   │   │
│   │   └── lib/
│   │       ├── api.ts                 # API client for FastAPI backend
│   │       └── types.ts              # TypeScript types matching backend Pydantic models
│   │
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   └── tsconfig.json
│
├── templates/
│   └── retainer_agreement.docx        # Word template with Clio merge fields
│
└── samples/
    └── (police report PDFs for testing)
```

---

## Environment Variables

```env
# Backend (.env)

# AI Extraction — Claude Sonnet 4.6
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6-20260217

# Clio Manage — OAuth 2.0
CLIO_CLIENT_ID=...
CLIO_CLIENT_SECRET=...
CLIO_REDIRECT_URI=http://localhost:8000/api/clio/callback
CLIO_ACCESS_TOKEN=...          # After OAuth flow
CLIO_REFRESH_TOKEN=...         # After OAuth flow
CLIO_BASE_URL=https://app.clio.com

# Email (Gmail SMTP or Resend)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...              # Gmail app password
FROM_EMAIL=...

# Booking Links
IN_OFFICE_BOOKING_URL=https://calendly.com/richards-law/in-office
VIRTUAL_BOOKING_URL=https://calendly.com/richards-law/virtual
```

---

## Clio Manage API Reference

**Base URL:** `https://app.clio.com/api/v4`
**Auth:** OAuth 2.0 Bearer token in Authorization header
**Content-Type:** application/json
**Fields:** Must explicitly request fields via `?fields=id,etag,name,...` — default only returns id + etag

### Key Endpoints We Use

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v4/matters/{id}` | PATCH | Update matter custom fields |
| `/api/v4/matters/{id}` | GET | Get matter details, documents, custom fields |
| `/api/v4/contacts` | GET | Find existing contact by email |
| `/api/v4/contacts/{id}` | PATCH | Update contact details |
| `/api/v4/calendar_entries` | POST | Create statute of limitations calendar entry |
| `/api/v4/documents` | GET | List/retrieve documents (to get generated retainer) |
| `/api/v4/documents/{id}/download` | GET | Download document content |
| `/api/v4/users/who_am_i` | GET | Get current user info (for attorney ID) |
| `/api/v4/custom_fields` | GET | List available custom fields |
| `/api/v4/custom_field_values` | PATCH | Update custom field values on a matter |

### Custom Fields to Create in Clio (Matter-level)

Create a Custom Field Set named **"Accident Details"** with these fields:

| Field Name | Clio Field Type | Description |
|-----------|----------------|-------------|
| Accident Date | Date | Date of the accident |
| Accident Location | Text Line | Where it happened |
| Accident Description | Text Area | Narrative of the incident |
| Police Report Number | Text Line | Report case number |
| Plaintiff Name | Text Line | Injured party / client full name |
| Plaintiff Address | Text Area | Client address from report |
| Plaintiff DOB | Date | Client date of birth |
| Plaintiff Phone | Text Line | Client phone |
| Defendant Name | Text Line | At-fault party name |
| Defendant Address | Text Area | Defendant address |
| Defendant Insurance | Text Line | Insurance company name |
| Defendant Policy Number | Text Line | Insurance policy number |
| Defendant Vehicle | Text Line | Year/Make/Model |
| Plaintiff Vehicle | Text Line | Year/Make/Model |
| Injuries Reported | Text Area | Injuries from the report |
| Weather Conditions | Text Line | Weather at time of accident |
| Reporting Officer | Text Line | Officer name / badge |
| Statute of Limitations Date | Date | Calculated: Accident Date + 8 years |

### Clio Document Automation

The retainer agreement MUST be generated using Clio's built-in document automation. The flow:

1. Create a Word (.docx) template with Clio merge fields like `<<Matter.Client.Name>>`, `<<Matter.CustomField.Accident Date>>`, etc.
2. Upload as a Document Template in Clio (Settings → Documents → Templates)
3. Trigger generation either:
   - **Primary:** Via Clio's Automated Workflows (matter stage change → generate document)
   - **Fallback (if not available on free plan):** Via API — POST to create document from template on a matter
4. Generated document is stored automatically in the matter's Documents

### Clio Matter Stages

Set up these stages in Clio under the "Personal Injury" practice area:

1. `New Lead` — initial state when matter is created
2. `Report Received` — police report has been uploaded
3. `Data Verified` — paralegal approved extracted data (triggers doc automation)
4. `Retainer Sent` — email with retainer has been sent to client

---

## AI Extraction Service

### Model
**Claude Sonnet 4.6** (`claude-sonnet-4-6-20260217`)
- $3 / $15 per million tokens (input / output)
- 200K context window (1M in beta)
- 64K max output tokens
- Native vision — accepts images directly, no OCR pipeline needed
- Supports adaptive thinking for complex extraction
- Best-in-class instruction following and structured output reliability

### Approach
Send the police report PDF pages as images to Claude Sonnet 4.6's vision API. Claude extracts structured data and returns JSON.

### Why images over text extraction:
- Police reports are often scanned documents with messy OCR
- Sonnet 4.6's vision handles handwriting, stamps, checkboxes, and poor scan quality
- No separate OCR pipeline needed — reduces complexity and points of failure
- Single model call per report (send all pages as images in one request)

### API Call Pattern
```python
import anthropic
import base64

client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var

# Convert each PDF page to a base64 image (via PyMuPDF)
# Then send all pages in a single message
response = client.messages.create(
    model="claude-sonnet-4-6-20260217",
    max_tokens=4096,
    messages=[
        {
            "role": "user",
            "content": [
                # Page images
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": page_1_base64,
                    },
                },
                # ... more pages ...
                # Extraction prompt
                {
                    "type": "text",
                    "text": EXTRACTION_PROMPT,
                },
            ],
        }
    ],
)
```

### Extraction Output Schema (Pydantic)

```python
class PartyInfo(BaseModel):
    role: Literal["plaintiff", "defendant", "witness", "other"]
    full_name: str | None
    address: str | None
    date_of_birth: str | None  # YYYY-MM-DD
    phone: str | None
    driver_license: str | None
    vehicle_year: str | None
    vehicle_make: str | None
    vehicle_model: str | None
    vehicle_color: str | None
    insurance_company: str | None
    insurance_policy_number: str | None
    injuries: str | None

class ExtractionResult(BaseModel):
    report_number: str | None
    accident_date: str | None  # YYYY-MM-DD
    accident_time: str | None
    accident_location: str | None
    accident_description: str | None
    weather_conditions: str | None
    road_conditions: str | None
    reporting_officer_name: str | None
    reporting_officer_badge: str | None
    parties: list[PartyInfo]
    number_of_vehicles: int | None
    confidence_notes: str | None  # Any uncertainties the AI flags
```

### Extraction Prompt Guidelines
- Be explicit about the JSON schema expected
- Instruct Claude to handle OCR artifacts (misread characters, broken lines)
- Ask for confidence notes on uncertain fields
- Handle multi-page reports (send all pages as images)
- Identify plaintiff vs defendant based on report context (who was injured, who was at fault)
- The prompt is in `backend/app/prompts/extraction_prompt.py` — keep it separate for easy iteration

---

## Email Logic

### Personalized Client Email Requirements
- **Warm tone** referencing the specific accident (date, brief description, location)
- **Retainer agreement PDF** attached
- **Seasonal booking link:**
  - March (3) through August (8) → in-office scheduling link
  - September (9) through February (2) → virtual scheduling link
- Sent TO: the contact's email from the Clio Matter (for final delivery: `talent.legal-engineer.hackathon.automation-email@swans.co`)

### Email Template Variables
- `client_first_name`
- `accident_date` (formatted nicely, e.g., "March 15, 2024")
- `accident_description` (brief, 1 sentence)
- `accident_location`
- `booking_link` (seasonal)
- `retainer_pdf` (attachment)

---

## Frontend Behavior

### Page 1: Upload (`/`)
- Drag-and-drop PDF upload zone
- "Extract Data" button
- Loading state with progress indicator while Claude processes
- Error handling for non-PDF files, oversized files

### Page 2: Review (`/review`)
- **Left panel:** PDF viewer (embedded PDF or page images)
- **Right panel:** Editable form with all extracted fields
- Fields with low confidence highlighted in yellow/orange
- Parties displayed as expandable cards (plaintiff, defendant, witnesses)
- **Bottom bar:**
  - "Approve & Push to Clio" button (primary action)
  - "Re-extract" button (try again with different prompt)
  - Status timeline showing: Upload → Extraction → Review → Clio Update → Document Gen → Email Sent

### Page 3: Status / Confirmation
- Real-time progress as the Clio pipeline runs
- WebSocket or polling for status updates
- Final confirmation with:
  - ✅ Matter updated
  - ✅ Retainer agreement generated
  - ✅ Calendar entry created
  - ✅ Email sent
  - Links to view in Clio

---

## Code Conventions

### Python (Backend)
- Use **async/await** throughout — FastAPI is async-first
- **Pydantic v2** for all data models
- **httpx** (async) for external API calls (Clio, Claude)
- Type hints on everything
- Docstrings on all service functions
- Loguru or structlog for logging
- Error handling: raise HTTPException with clear messages, catch external API errors gracefully
- Keep business logic in `services/`, keep routing thin in `routers/`

### TypeScript (Frontend)
- **App Router** (Next.js 15)
- **Server Components** by default, Client Components only where needed (forms, interactivity)
- **shadcn/ui** for components (install via `npx shadcn@latest init`)
- **Tailwind CSS** for styling
- **fetch** or **axios** for API calls to backend
- Keep API types in sync with backend Pydantic models (define in `lib/types.ts`)
- Use React Hook Form + Zod for form validation on the review page

### General
- No hardcoded values — everything in env vars or config
- Meaningful error messages that help debugging
- Each service function should be independently testable
- Comments explaining "why" not "what"

---

## Critical Implementation Notes

1. **Clio OAuth Flow:** You need to register a developer app in Clio's developer portal to get client_id/secret. The OAuth callback URL must be accessible (use ngrok for local dev). After initial auth, store the access_token and refresh_token. Implement auto-refresh when the token expires.

2. **Clio Custom Fields via API:** When updating custom fields on a matter, you need the custom field's ID (not name). First GET `/api/v4/custom_fields` to map field names to IDs, then PATCH the matter with custom_field_values array.

3. **Document Generation Trigger:** After updating custom fields and changing the matter stage to "Data Verified", Clio's Automated Workflow should auto-generate the retainer. Add a polling loop to check for the new document in the matter's documents list.

4. **PDF Download from Clio:** After the retainer is generated, GET the document, then download it to attach to the email. The Clio API returns a download URL.

5. **Calendar Entry:** POST to `/api/v4/calendar_entries` with:
   - `name`: "Statute of Limitations - [Client Name]"
   - `start_at`: accident_date + 8 years (as ISO datetime)
   - `end_at`: same date + 1 hour
   - `all_day`: true
   - `attendees`: [{ id: responsible_attorney_id, type: "User" }]
   - `matter`: { id: matter_id }
   - `description`: "Statute of Limitations expires for [matter description]"

6. **The automation email for final delivery** must be sent TO `talent.legal-engineer.hackathon.automation-email@swans.co`. This is the contact's email in Clio.

7. **Test with GUILLERMO_REYES_v_LIONEL_FRANCOIS** police report for the final demo, but the system must handle any of the provided reports.

---

## Development Workflow

### Key Python Dependencies
```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
anthropic>=0.45.0          # Claude Sonnet 4.6 SDK
httpx>=0.27.0              # Async HTTP client for Clio API
pydantic>=2.6.0
pydantic-settings>=2.2.0
python-multipart>=0.0.9    # File upload support
PyMuPDF>=1.24.0            # PDF → page images (import fitz)
python-dotenv>=1.0.0
aiosmtplib>=3.0.0          # Async SMTP for email
jinja2>=3.1.3              # Email templates
python-jose>=3.3.0         # JWT handling for OAuth
```

### Key Node Dependencies (Frontend)
```
next@15
react@19
tailwindcss
@shadcn/ui
react-hook-form
zod
@hookform/resolvers
axios
react-pdf (or @react-pdf-viewer/core)
lucide-react
```

1. Start backend: `cd backend && uvicorn app.main:app --reload --port 8000`
2. Start frontend: `cd frontend && npm run dev` (port 3000)
3. Frontend proxies API calls to `http://localhost:8000`
4. For Clio OAuth: run `ngrok http 8000` and update CLIO_REDIRECT_URI

---

## Testing Checklist

- [ ] PDF upload and extraction returns valid JSON for all sample reports
- [ ] Review UI displays extracted data correctly and allows editing
- [ ] Clio OAuth flow works (auth → callback → token storage)
- [ ] Matter custom fields update via API
- [ ] Matter stage change triggers document generation in Clio
- [ ] Calendar entry created with correct date (accident + 8 years)
- [ ] Generated retainer PDF retrieved from Clio
- [ ] Personalized email sent with correct content, attachment, and seasonal link
- [ ] Works end-to-end with GUILLERMO_REYES_v_LIONEL_FRANCOIS report
- [ ] Works with at least 2 other sample police reports
