# 🤖 Invoice AI System

> AI-Powered Invoice Processing & Document Intelligence System with RAG and Agent Automation

---

## 🧱 Architecture Overview

```
Upload → OCR → Preprocessing → LLM Extraction → Validation → Storage
                                                                  ↓
                                                Embedding (Pinecone) → RAG Chatbot
                                                                  ↓
                                                       Agent Automation
```

---

## 🗂️ Project Structure

```
invoice-ai-system/
├── backend/
│   ├── main.py                  # FastAPI app & all routes
│   ├── config.py                # Settings (pydantic-settings)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example             # ← Copy to .env and fill values
│   ├── database/
│   │   └── db.py                # SQLAlchemy models & session
│   ├── models/
│   │   └── schemas.py           # Pydantic request/response schemas
│   ├── modules/
│   │   ├── ocr.py               # Tesseract OCR engine (PDF + image)
│   │   ├── extraction.py        # GPT-4o LLM extraction
│   │   ├── validation.py        # Compliance & duplicate detection
│   │   ├── embeddings.py        # Pinecone vector store
│   │   ├── rag.py               # RAG query engine
│   │   └── agents.py            # Automation agent
│   └── utils/
│       └── auth.py              # JWT auth & RBAC
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Main app with sidebar routing
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx    # Analytics & charts
│   │   │   ├── UploadPage.jsx   # Drag-and-drop upload
│   │   │   ├── InvoicesPage.jsx # Invoice list + detail panel
│   │   │   ├── ChatPage.jsx     # RAG chatbot interface
│   │   │   ├── ActionsPage.jsx  # Agent action management
│   │   │   └── LoginPage.jsx    # JWT login
│   │   └── services/
│   │       └── api.js           # Axios API client
│   ├── Dockerfile
│   └── package.json
│
└── docker-compose.yml           # Full stack orchestration
```

---

## ⚡ Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL
- Tesseract OCR (`brew install tesseract` / `apt install tesseract-ocr`)

### 1. Clone & Setup Backend

```bash
cd backend
cp .env.example .env
# Edit .env with your OpenAI and Pinecone API keys

pip install -r requirements.txt
python main.py
```

Backend runs at: http://localhost:8000
API Docs: http://localhost:8000/api/docs

### 2. Setup Frontend

```bash
cd frontend
npm install
npm start
```

Frontend runs at: http://localhost:3000

### 3. Login

| Username | Password | Role  |
|----------|----------|-------|
| admin    | admin123 | admin |

---

## 🐳 Docker Compose (Recommended)

```bash
# Fill in your .env first
cp backend/.env.example backend/.env

# Start all services
docker-compose up --build
```

Services:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- PostgreSQL: localhost:5432

---

## 🔑 Required API Keys

| Key | Where to Get | Required |
|-----|-------------|----------|
| `OPENAI_API_KEY` | https://platform.openai.com | Yes |
| `PINECONE_API_KEY` | https://app.pinecone.io | Optional |

> Without Pinecone, the system uses keyword-based search as fallback.
> Without OpenAI, regex-based extraction is used as fallback.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload invoice (PDF/image) |
| GET | `/api/invoice/{id}` | Get invoice details |
| GET | `/api/invoices` | List all invoices (paginated) |
| DELETE | `/api/invoice/{id}` | Delete invoice |
| GET | `/api/validate/{id}` | Re-run validation |
| POST | `/api/query` | RAG chatbot query |
| GET | `/api/agent-actions` | List agent actions |
| POST | `/api/agent-action/{id}/resolve` | Resolve action |
| GET | `/api/analytics` | Dashboard analytics |
| POST | `/api/auth/login` | Get JWT token |
| GET | `/api/health` | System health check |

---

## 🧠 Core Modules

### OCR Engine (`modules/ocr.py`)
- PDF: PyMuPDF renders pages → Tesseract OCR
- Images: Preprocessing (sharpen, contrast, resize) → Tesseract
- Auto-detects digital vs scanned PDFs

### Extraction Engine (`modules/extraction.py`)
- Sends OCR text to GPT-4o with structured prompt
- Extracts: invoice_number, vendor, GSTIN, dates, amounts, line_items
- Regex fallback when no OpenAI key

### Validation Engine (`modules/validation.py`)
- Required fields check
- Indian GSTIN format validation (regex)
- Amount consistency (subtotal + tax = total)
- Duplicate detection (invoice_number + vendor match)

### RAG Engine (`modules/rag.py`)
- Vector search via Pinecone for relevant invoices
- Augments context with full DB record details
- GPT-4o generates natural language answers

### Agent (`modules/agents.py`)
- **Duplicate alert** → logs + email
- **Missing GSTIN** → compliance flag
- **High value (>₹1L)** → approval request + email
- **Validation failure** → review flag

---

## 🔐 Security

- JWT tokens (HS256) with configurable expiry
- Role-based access: `admin`, `finance`, `viewer`
- Passwords hashed with bcrypt
- CORS configured per environment

---

## 📊 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, SQLAlchemy |
| AI/LLM | OpenAI GPT-4o |
| OCR | Tesseract, PyMuPDF |
| Vector DB | Pinecone |
| Relational DB | PostgreSQL |
| Frontend | React 18, Tailwind CSS, Recharts |
| Auth | JWT (python-jose) |
| Deployment | Docker, docker-compose |

---

## 🚀 Extending the System

### Add Email Alerts
Set SMTP credentials in `.env`:
```
SMTP_USER=your@email.com
SMTP_PASSWORD=app_password
ALERT_EMAIL=finance@company.com
```

### Enable Auth on Routes
In `main.py`, uncomment the `user: User = Depends(get_current_user)` lines.

### Add New Agent Rules
In `modules/agents.py`, add a new rule block in the `run()` method:
```python
if your_condition(invoice):
    self._trigger(invoice.id, "your_action_type", "Your message", db)
```

---

## 🎯 Evaluation Metrics

- **OCR Accuracy**: Measured via Tesseract confidence score
- **Extraction Accuracy**: Compare extracted vs ground truth JSON
- **Processing Time**: Logged per invoice (`processing_time_ms`)
- **RAG Relevance**: Track source match scores from Pinecone

---

## 📦 Future Scope

- ERP integration (SAP, Zoho Books)
- Fine-tuned LLM on Indian invoice dataset
- Voice query interface
- Mobile app (React Native)
- Graph analytics for vendor relationships
- Multi-language OCR (Hindi, Tamil, etc.)
