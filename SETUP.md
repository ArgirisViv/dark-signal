# Setup Instructions

Αυτές είναι οι οδηγίες για να τρέξεις το project σε νέο περιβάλλον ανάπτυξης ή για να το παραδώσεις με καθαρή διαδικασία εγκατάστασης.

## Προαπαιτούμενα

1. **Python 3.12+** - [Download Python](https://www.python.org/downloads/)
2. **Node.js 20+** - [Download Node.js](https://nodejs.org/)
3. **npm** (έρχεται με Node.js)
4. **Docker Desktop** για την προτεινόμενη εκτέλεση με PostgreSQL

## Βήματα Setup

### 0. Ασφαλής δημιουργία του `.env`

Από το root folder του project:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Τρέξε την εντολή δημιουργίας τρεις φορές και βάλε διαφορετική τιμή στα
`POSTGRES_PASSWORD`, `SECRET_KEY` και `BOOTSTRAP_TOKEN` του `.env`. Το
`OPENAI_API_KEY` είναι προαιρετικό και πρέπει να συμπληρωθεί μόνο με νέο,
προσωπικό API key. Το πραγματικό `.env` δεν ανεβαίνει ποτέ στο GitHub.

### 1. Εγκατάσταση Backend Dependencies

Ανοίγεις terminal στο root folder του project και τρέχεις:

```bash
# Δημιουργία virtual environment
python -m venv .venv

# Ενεργοποίηση virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Εγκατάσταση Python packages
pip install -r backend/requirements.txt
```

### 2. Εγκατάσταση Frontend Dependencies

Στο ίδιο terminal (ή νέο):

```bash
cd frontend
npm install
cd ..
```

### 3. Εκκίνηση της Εφαρμογής

Μετά το setup, μπορείς να χρησιμοποιήσεις τα `.bat` αρχεία:

- **`start-all.bat`** - Τρέχει και τα δύο (backend + frontend)
- **`start-backend.bat`** - Τρέχει μόνο το backend
- **`start-frontend.bat`** - Τρέχει μόνο το frontend

Ή χειροκίνητα:

**Backend:**
```bash
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm run dev
```

**Προτεινόμενη εκτέλεση με Docker και PostgreSQL:**

```powershell
docker compose up --build
```

Το Docker Compose σταματά με σαφές μήνυμα αν λείπει κάποιο από τα υποχρεωτικά
secrets. Για είσοδο σε καθαρή εγκατάσταση χρησιμοποίησε την τιμή
`BOOTSTRAP_TOKEN` μόνο στη φόρμα “Create first admin”.

## URLs

- Backend API: http://localhost:8000
- Frontend: http://localhost:5173
- API Documentation: http://localhost:8000/docs

## Deployment Notes

- Build the frontend with `npm run build` and deploy the `frontend/dist` folder to a static host such as Netlify, Vercel, or any other static file host.
- Set `VITE_API_BASE_URL` in the deployment environment to the public URL of the backend.
- Deploy the backend separately on a Python-capable host such as Railway, Render, Fly.io, or DigitalOcean.
- For a quick production health check, call `http://your-backend-url/health`.

## Σημειώσεις

- Το virtual environment (`.venv`) και τα `node_modules` **ΔΕΝ** πρέπει να ανέβουν στο flash drive (είναι πολύ μεγάλα).
- Κάνε setup σε κάθε νέο PC που θέλεις να τρέξεις το project.
- Αν αλλάξεις PC, απλά τρέξε ξανά τα βήματα 1-2.

## Troubleshooting

**Error: Virtual environment not found**
→ Τρέξε `python -m venv .venv` και μετά `pip install -r backend/requirements.txt`

**Error: node_modules not found**
→ Τρέξε `cd frontend && npm install`

**Error: npm not found**
→ Εγκατέστησε Node.js από https://nodejs.org/

**Port already in use**
→ Κλείσε άλλες εφαρμογές που χρησιμοποιούν port 8000 ή 5173
