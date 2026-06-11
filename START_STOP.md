# Start/Stop (Local)

## Start everything (Website + Chatbot API)

### Terminal 1: Start the website (the browser will load this)
```powershell
cd "C:\Users\oswal\OneDrive\Desktop\Oz Personals\Oswald Portfolio\oz-portfolio-main\Oswald"
python -m http.server 8001 --directory website
```

### Terminal 2: Start the chatbot API (required for the chat widget)
```powershell
cd "C:\Users\oswal\OneDrive\Desktop\Oz Personals\Oswald Portfolio\oz-portfolio-main\Oswald\chatbot"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> Note: On Windows, `uvicorn --reload` can sometimes restart repeatedly if file watching detects unrelated package changes. Use the command above for a stable local API server.

## Open the browser
After Terminal 1 is running, open:
`http://localhost:8001/`

Optional one-liner to open it:
```powershell
Start-Process "http://localhost:8001/"
```

## Stop (what to do in the terminals)

### Stop the website server
- Go to **Terminal 1** and press `Ctrl+C`.

### Stop the chatbot API
- Go to **Terminal 2** and press `Ctrl+C`.

## Stop by port (fallback if Ctrl+C is not available)

### Stop whatever is using port `8001` (website)
```powershell
$p = (Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess)
if ($p) { Stop-Process -Id $p -Force }
```

### Stop whatever is using port `8000` (chatbot API)
```powershell
$p = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess)
if ($p) { Stop-Process -Id $p -Force }
```

