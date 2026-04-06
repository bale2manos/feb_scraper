# feb_scraper

## React + FastAPI migration

### Backend

```powershell
& ".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
& ".venv\Scripts\python.exe" -m uvicorn backend.api.main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend por defecto en `http://localhost:5173` y backend en `http://localhost:8000`.
