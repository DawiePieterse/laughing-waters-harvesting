"""Apply the two preview-sandbox patches to the /tmp mirror of the Lite
backend. Run after EVERY rsync of backend/ -> /tmp/lw_lite_backend_copy:
  1. db.py: in-memory sqlite (StaticPool) so no file DB is written in /tmp
  2. main.py: FRONTEND_DIR -> /tmp/lw_lite_frontend (the frontend mirror)
"""
import re

DB = "/tmp/lw_lite_backend_copy/db.py"
MAIN = "/tmp/lw_lite_backend_copy/main.py"

src = open(DB).read()
src = src.replace(
    'DATABASE_URL = f"sqlite:///{DB_PATH}"',
    'DATABASE_URL = "sqlite:///:memory:"',
)
src = src.replace(
    'engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})',
    'from sqlalchemy.pool import StaticPool\n'
    'engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)',
)
open(DB, "w").write(src)

src = open(MAIN).read()
# Match to the END of the line - the join() call contains nested parens
# (os.path.dirname(__file__)), so a non-greedy "[^)]*)" stops too early.
src = re.sub(
    r'^FRONTEND_DIR = .*$',
    'FRONTEND_DIR = "/tmp/lw_lite_frontend"',
    src,
    flags=re.MULTILINE,
)
open(MAIN, "w").write(src)
print("patches applied")
