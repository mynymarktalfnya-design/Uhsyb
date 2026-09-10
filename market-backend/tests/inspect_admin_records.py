import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
from database import db, C

rows = list(db[C.users].find({}, {"_id": 0, "username": 1, "email": 1, "role": 1, "is_active": 1, "deleted_at": 1, "failed_login_attempts": 1, "locked_until": 1}))
for row in rows:
    print(row)
