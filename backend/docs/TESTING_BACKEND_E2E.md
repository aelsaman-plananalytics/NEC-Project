# Testing the backend: upload contract + programme, get report

This describes how to run an end-to-end test: upload a contract (PDF), upload a programme (XER), and get a validation report (PDF).

## 1. Start the backend

From the project root:

```bash
cd backend
# Optional: activate venv first, e.g. .\venv\Scripts\Activate.ps1 (Windows) or source venv/bin/activate (Linux/Mac)
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be at `http://localhost:8000`. Ensure `.env` exists (see [RUN_INSTRUCTIONS.md](RUN_INSTRUCTIONS.md)); for a quick test, `AI_MODE=mock` and a valid `DATABASE_URL` are enough if you're not hitting auth-protected routes.

---

## 2. One-shot: contract + programme → PDF report

Use the **full review** v1 endpoint: one request with both files; response is the PDF.

- **Canonical:** `POST /api/v1/full_review`
- Legacy (deprecated): `POST /api/full_review` still works for backward compatibility.

### Using curl (Windows PowerShell)

```powershell
# Replace paths with your contract PDF and programme XER
$contractPath = "C:\path\to\your\contract.pdf"
$programmePath = "C:\path\to\your\programme.xer"
$outputPath = "C:\path\to\validation_report.pdf"

curl.exe -X POST "http://localhost:8000/api/v1/full_review" `
  -F "contract_file=@$contractPath" `
  -F "programme_file=@$programmePath" `
  -o $outputPath
```

### Using curl (Linux / Mac)

```bash
curl -X POST "http://localhost:8000/api/v1/full_review" \
  -F "contract_file=@/path/to/contract.pdf" \
  -F "programme_file=@/path/to/programme.xer" \
  -o validation_report.pdf
```

### Using the included Python script

From the `backend/` directory (with the server running):

```bash
python scripts/e2e_full_review.py path/to/contract.pdf path/to/programme.xer [output.pdf]
```

Example:

```bash
python scripts/e2e_full_review.py C:\data\nec_contract.pdf C:\data\programme.xer validation_report.pdf
```

The script uses only the Python standard library; no extra packages required.

---

## 3. Step-by-step (optional)

If you want to run analysis and validation separately, use the v1 endpoints:

1. **Analyse contract**  
   `POST /api/v1/analyze_contract` with the contract PDF.  
   The backend saves analysis JSON under `backend/app/outputs/analysis_reports/`.

2. **Validate programme**  
   `POST /api/v1/validate_programme` with:
   - `xer_file`: programme XER
   - `json_file`: (optional) contract analysis JSON from step 1; if omitted, the latest file in `analysis_reports` is used.  
   Response is validation JSON; the backend can also write it to `validation_reports`.

3. **Generate report**  
   `POST /api/v1/generate_report` (validation JSON file + `format=pdf|docx|html`) or `POST /api/v1/build_validation_report` (JSON body) for the preview structure.

For a single “upload contract + programme, get report” test, **full review** (step 2 above) is enough.

---

## 4. Quick check without real files

If you don’t have a real NEC contract and XER yet:

- Use any small PDF as the “contract” and any small `.xer` file as the “programme” to confirm the endpoint and PDF response.  
- For a correct acceptability result you need a real contract (and optionally analysis) and a matching XER; see the rest of the docs and the API contract for authoritative behaviour.

---

## 5. Health check

To confirm the backend is up and ledger/health checks pass:

```bash
curl http://localhost:8000/api/v1/health
```

You should get `{"status":"healthy","version":"v1","integrity":"ok","ledger_chain_check":"ok"}`.
