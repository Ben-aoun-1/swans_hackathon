# Swans Legal AI Hackathon — Richards & Law Intake Automation

Automates the personal injury intake pipeline: extract data from police report PDFs using Claude AI, verify via a review UI, push to Clio Manage, generate retainer agreements, and send personalized client emails.

## Quick Start

### Backend

```bash
cd backend
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY
pip install -r requirements.txt
chmod +x run.sh
./run.sh
```

Server runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
npm run dev
```

Frontend runs at `http://localhost:3000`.

## Architecture

```
Police Report PDF → Claude AI Extraction → Human Review UI → Clio Manage Pipeline
                                                              ├── Update Matter
                                                              ├── Generate Retainer
                                                              ├── Create Calendar Entry
                                                              └── Send Client Email
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/extract` | Upload PDF, get extracted data |
| POST | `/api/approve` | Push verified data to Clio |
| GET | `/api/clio/auth` | Start Clio OAuth flow |
| GET | `/api/clio/callback` | Clio OAuth callback |
| GET | `/api/health` | Health check |
