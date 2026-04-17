# 🚀 How to Run Invoice AI System

## Step 1 — Add Your Groq API Key (Required for AI features)

1. Get a free key at: https://console.groq.com
2. Open `backend/.env`
3. Replace `your_groq_api_key_here` with your actual key:
   ```
   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
   ```

> **Without Groq key**: Login, upload, and dashboard still work.
> OCR extraction will use regex fallback instead of AI.

---

## Step 2 — Install Backend Dependencies

```powershell
cd backend
pip install -r requirements.txt
```

---

## Step 3 — Start the Backend

```powershell
cd backend
python -m uvicorn main:app --reload --port 8000
```

You should see:
```
✅ Invoice AI System started.
INFO: Uvicorn running on http://0.0.0.0:8000
```

Backend API docs: http://localhost:8000/api/docs

---

## Step 4 — Start the Frontend

Open a **new terminal**:

```powershell
cd frontend
npm install
npm start
```

App opens at: http://localhost:3000

---

## Step 5 — Login

Use demo credentials shown on the login page:
- **Username**: admin
- **Password**: admin123

---

## Database

By default uses **SQLite** (no setup needed) — file saved as `backend/invoice_ai.db`.

To use **PostgreSQL** instead, update `DATABASE_URL` in `backend/.env`:
```
DATABASE_URL=postgresql://user:password@localhost:5432/invoice_db
```

---

## What Works Without API Keys

| Feature | Without Keys | With Groq Key |
|---------|-------------|---------------|
| Login / Auth | ✅ | ✅ |
| Upload invoice | ✅ | ✅ |
| OCR text extraction | ✅ (regex) | ✅ (AI) |
| Dashboard analytics | ✅ | ✅ |
| Invoice list | ✅ | ✅ |
| AI Chat (RAG) | ⚠️ DB stats only | ✅ Full AI |
| Agent Actions | ✅ | ✅ |
