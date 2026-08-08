"""Preview-sandbox launcher for the LITE app: serves the /tmp mirror with an
in-memory DB and auto-seeds demo data once the API is up.
Master copy lives at .claude/preview_launcher.py in the Lite repo -
copy to /tmp/lw_lite_launcher.py after a /tmp purge (see .claude/rebuild_preview.sh)."""
import sys, os
sys.path = [p for p in sys.path if p]
port = int(os.environ.get('PORT', '8823'))

# Auto-seed demo data once the API is up. The preview DB is in-memory, so
# every server start is a blank slate - seed it so screens aren't empty.
import threading, subprocess, urllib.request, time

def seed_when_ready():
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        time.sleep(1)
        try:
            urllib.request.urlopen(f"{base}/api/blocks", timeout=2)
            break
        except Exception:
            continue
    else:
        print("[auto-seed] server never became ready, skipping", flush=True)
        return
    print("[auto-seed] seeding demo data...", flush=True)
    r = subprocess.run(
        [sys.executable, "/tmp/lw_lite_backend_copy/seed_demo.py", base],
        capture_output=True, text=True,
    )
    print(r.stdout, flush=True)
    if r.returncode != 0:
        print(f"[auto-seed] failed:\n{r.stderr}", flush=True)

threading.Thread(target=seed_when_ready, daemon=True).start()

import uvicorn
uvicorn.run('main:app', host='127.0.0.1', port=port, loop='asyncio', http='h11',
            app_dir='/tmp/lw_lite_backend_copy')
