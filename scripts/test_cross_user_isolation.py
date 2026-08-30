import jwt, time, httpx
from harness.config import get_settings

s = get_settings()
BASE = "http://localhost:8000"

def token(user_id: str)-> str:
    return jwt.encode(
        {"sub": user_id, "role": "user", "jti": f"test-{user_id}-{time.time()}",
        "exp": int(time.time())+ 3600},
        s.jwt_secret, algorithm = s.jwt_algorithm
    )

def h(user_id):
    return {"Authorization": f"Bearer{token(user_id)}"}

r = httpx.post(f"BASE/ask", header = h("user-A"), json = {"question": "what is 6 times 7?"}, timeout = 60)
assert r.status_code == 200, r.text
print("User-A created a thread")

print("PASS scaffold: extend with a cross-read once a thread-read route exists")