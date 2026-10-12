import requests

urls = [
    "http://127.0.0.1:5000/",
    "http://127.0.0.1:5000/styles.css",
    "http://127.0.0.1:5000/app.js",
    "http://127.0.0.1:5000/frontend/styles.css",
    "http://127.0.0.1:5000/frontend/app.js",
    "http://127.0.0.1:5000/frontend/api.js",
    "http://127.0.0.1:5000/frontend/ui.js",
    "http://127.0.0.1:5000/api/health",
    "http://127.0.0.1:5000/api/phrases",
    "http://127.0.0.1:5000/api/practice/scenarios",
    "http://127.0.0.1:5000/api/phrasebook",
    "http://127.0.0.1:5000/api/progress",
    "http://127.0.0.1:5000/api/revision"
]

all_ok = True
for u in urls:
    try:
        r = requests.get(u, timeout=3)
        print(f"[{r.status_code}] {u} ({r.headers.get('content-type', 'unknown')})")
        if r.status_code != 200:
            all_ok = False
    except Exception as e:
        print(f"[FAIL] {u}: {e}")
        all_ok = False

if all_ok:
    print("\nSUCCESS: All endpoints and static assets returned 200 OK!")
else:
    print("\nFAILURE: Some endpoints failed.")

