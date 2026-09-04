# -*- coding: utf-8 -*-
"""
게임 링크 복구센터 서버 (WSGI)
- 디스코드 OAuth2 로그인 (관리자 / 유저 분기)
- 유저: 지정 역할 보유자만 접근 → 복구요청 접수
- 관리자: 요청 확인 → 봇 토큰으로 유저 DM에 복구 링크 발송
- Python 표준 라이브러리만 사용. 데이터: data/recover.db
- 로컬 실행: python server.py [포트]   /   호스팅: server:application
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import socketserver
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from secrets_config import (
    CLIENT_ID, CLIENT_SECRET, BOT_TOKEN, ADMIN_IDS,
    GUILD_ID, USER_ROLE_ID, BASE_URL,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "recover.db")

MAX_BODY = 16 * 1024
SESSION_HOURS = 24 * 7
RETENTION_DAYS = 30          # 요청 기록 보관 기간
REQUEST_COOLDOWN = 60        # 같은 유저 연속 요청 최소 간격(초)

REDIRECT_URI = BASE_URL.rstrip("/") + "/callback"
DISCORD_API = "https://discord.com/api/v10"

# ---------------------------------------------------------------- DB

db_lock = threading.Lock()
_conn = None


def db():
    global _conn
    if _conn is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        # 주의: WAL 모드 금지 — PythonAnywhere 네트워크 디스크에서 DB 손상됨
        _conn.execute("PRAGMA journal_mode=DELETE")
    return _conn


def init_db():
    c = db()
    with db_lock:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT NOT NULL,            -- 디스코드 유저 ID
            username TEXT NOT NULL,       -- 표시 이름 (요청 당시)
            game TEXT NOT NULL,           -- 게임 이름
            note TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '대기',   -- 대기/완료/거절
            admin_reply TEXT NOT NULL DEFAULT '',  -- 보낸 링크 or 거절 사유
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        """)
        c.commit()
        if get_setting("secret") is None:
            set_setting("secret", secrets.token_hex(32))


def get_setting(key):
    row = db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(key, value):
    db().execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    db().commit()


_last_purge = 0.0


def purge_old():
    global _last_purge
    if time.time() - _last_purge < 3600:
        return
    _last_purge = time.time()
    cutoff = now() - RETENTION_DAYS * 86400
    with db_lock:
        db().execute("DELETE FROM requests WHERE created_at<?", (cutoff,))
        db().commit()

# ---------------------------------------------------------------- 유틸

def now():
    return int(time.time())


def clean(text, maxlen):
    if not isinstance(text, str):
        return ""
    return re.sub(r"[ \t]+", " ", text).strip()[:maxlen]


def row_dicts(rows):
    return [dict(r) for r in rows]


def sign(msg):
    return hmac.new(get_setting("secret").encode(), msg.encode(), hashlib.sha256).hexdigest()

# ---------------------------------------------------------------- 세션/상태 토큰

def make_session(uid, name, role):
    payload = base64.urlsafe_b64encode(json.dumps(
        {"uid": str(uid), "name": name, "role": role, "exp": now() + SESSION_HOURS * 3600},
        ensure_ascii=False).encode()).decode().rstrip("=")
    return f"{payload}.{sign(payload)}"


def parse_session(token):
    try:
        payload, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(sign(payload), sig):
            return None
        pad = payload + "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(pad).decode())
        if data.get("exp", 0) < now():
            return None
        return data
    except Exception:
        return None


def make_state(as_role):
    raw = f"{as_role}.{now()}"
    return f"{raw}.{sign(raw)}"


def parse_state(state):
    try:
        as_role, ts, sig = state.split(".", 2)
        raw = f"{as_role}.{ts}"
        if not hmac.compare_digest(sign(raw), sig):
            return None
        if int(ts) + 600 < now():   # 10분 유효
            return None
        return as_role if as_role in ("user", "admin") else None
    except Exception:
        return None

# ---------------------------------------------------------------- 디스코드 API

def discord_call(method, path, *, bot=False, bearer=None, data=None, form=False):
    """디스코드 REST 호출. 반환: (status, json|None)"""
    url = DISCORD_API + path
    headers = {"User-Agent": "RecoverWeb/1.0"}
    if bot:
        headers["Authorization"] = "Bot " + BOT_TOKEN
    elif bearer:
        headers["Authorization"] = "Bearer " + bearer
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return res.status, json.loads(res.read().decode() or "null")
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode() or "null")
        except Exception:
            detail = None
        return e.code, detail
    except Exception:
        return 0, None


def oauth_exchange(code):
    return discord_call("POST", "/oauth2/token", data={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": REDIRECT_URI,
    }, form=True)


def fetch_me(access_token):
    return discord_call("GET", "/users/@me", bearer=access_token)


def member_has_role(uid):
    """길드 멤버의 역할에 USER_ROLE_ID 가 있는지. (있음/없음/오류메시지)"""
    status, data = discord_call("GET", f"/guilds/{GUILD_ID}/members/{uid}", bot=True)
    if status == 200 and isinstance(data, dict):
        return str(USER_ROLE_ID) in [str(r) for r in (data.get("roles") or [])], None
    if status == 404:
        return False, None  # 서버 미가입
    return False, f"디스코드 조회 실패 (코드 {status})"


def send_dm(uid, content):
    """봇 토큰으로 해당 유저에게 DM 전송. 반환: 오류메시지 or None(성공)"""
    status, ch = discord_call("POST", "/users/@me/channels", bot=True,
                              data={"recipient_id": str(uid)})
    if status != 200 or not isinstance(ch, dict) or "id" not in ch:
        return f"DM 채널 생성 실패 (코드 {status})"
    status, _msg = discord_call("POST", f"/channels/{ch['id']}/messages", bot=True,
                                data={"content": content})
    if status in (200, 201):
        return None
    if status == 403:
        return "DM 전송 실패: 유저가 DM을 차단했거나 서버 멤버가 아닙니다."
    return f"DM 전송 실패 (코드 {status})"

# ---------------------------------------------------------------- WSGI 기반

STATUS_TEXT = {200: "200 OK", 302: "302 Found", 400: "400 Bad Request",
               401: "401 Unauthorized", 403: "403 Forbidden",
               404: "404 Not Found", 500: "500 Internal Server Error"}

MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8", ".png": "image/png",
        ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".ico": "image/x-icon"}


class Request:
    def __init__(self, environ):
        self.environ = environ
        self.method = environ.get("REQUEST_METHOD", "GET")
        self.path = environ.get("PATH_INFO", "/")

    def query(self):
        return urllib.parse.parse_qs(self.environ.get("QUERY_STRING", ""))

    def read_json(self, limit=MAX_BODY):
        try:
            length = int(self.environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            return None
        if length <= 0 or length > limit:
            return None
        try:
            return json.loads(self.environ["wsgi.input"].read(length).decode())
        except Exception:
            return None

    def session(self):
        cookie = self.environ.get("HTTP_COOKIE") or ""
        for part in cookie.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "session":
                return parse_session(v)
        return None


class Response:
    def __init__(self, body, status=200, headers=None):
        self.body = body if isinstance(body, bytes) else body.encode()
        self.status = status
        self.headers = headers or []


def json_resp(obj, status=200, set_cookie=None):
    headers = [("Content-Type", "application/json; charset=utf-8"),
               ("Cache-Control", "no-store")]
    if set_cookie:
        headers.append(("Set-Cookie", set_cookie))
    return Response(json.dumps(obj, ensure_ascii=False), status, headers)


def redirect(url, set_cookie=None):
    headers = [("Location", url)]
    if set_cookie:
        headers.append(("Set-Cookie", set_cookie))
    return Response(b"", 302, headers)


def session_cookie(token):
    return f"session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_HOURS*3600}"


def serve_file(name):
    fpath = os.path.join(PUBLIC_DIR, name)
    if not os.path.isfile(fpath):
        return Response("Not Found", 404, [("Content-Type", "text/plain")])
    with open(fpath, "rb") as f:
        data = f.read()
    ext = os.path.splitext(fpath)[1].lower()
    return Response(data, 200, [("Content-Type", MIME.get(ext, "application/octet-stream")),
                                ("Cache-Control", "no-cache")])


def serve_static(path):
    if path == "/":
        return serve_file("index.html")
    fname = os.path.normpath(path.lstrip("/"))
    if fname.startswith("..") or os.path.isabs(fname) or ":" in fname:
        return Response("Not Found", 404, [("Content-Type", "text/plain")])
    if fname in ("user.html", "admin.html"):   # 세션 라우트로만 접근
        return Response("Not Found", 404, [("Content-Type", "text/plain")])
    return serve_file(fname)

# ---------------------------------------------------------------- 라우트: 인증

def route_login(req):
    as_role = (req.query().get("as") or ["user"])[0]
    if as_role not in ("user", "admin"):
        as_role = "user"
    params = urllib.parse.urlencode({
        "client_id": CLIENT_ID, "response_type": "code",
        "redirect_uri": REDIRECT_URI, "scope": "identify",
        "state": make_state(as_role), "prompt": "none",
    })
    return redirect("https://discord.com/oauth2/authorize?" + params)


def route_callback(req):
    q = req.query()
    code = (q.get("code") or [""])[0]
    as_role = parse_state((q.get("state") or [""])[0])
    if not code or not as_role:
        return redirect("/denied.html?r=" + urllib.parse.quote("로그인 정보가 올바르지 않습니다. 다시 시도해주세요."))
    status, tok = oauth_exchange(code)
    if status != 200 or not isinstance(tok, dict) or "access_token" not in tok:
        return redirect("/denied.html?r=" + urllib.parse.quote("디스코드 로그인에 실패했습니다. 다시 시도해주세요."))
    status, me = fetch_me(tok["access_token"])
    if status != 200 or not isinstance(me, dict) or "id" not in me:
        return redirect("/denied.html?r=" + urllib.parse.quote("계정 정보를 가져오지 못했습니다."))
    uid = str(me["id"])
    name = me.get("global_name") or me.get("username") or uid

    if as_role == "admin":
        if int(uid) not in ADMIN_IDS:
            return redirect("/denied.html?r=" + urllib.parse.quote("이 계정은 관리자가 아닙니다."))
        return redirect("/admin", set_cookie=session_cookie(make_session(uid, name, "admin")))

    # 유저: 역할 확인
    has_role, err = member_has_role(uid)
    if err:
        return redirect("/denied.html?r=" + urllib.parse.quote(err))
    if not has_role:
        return redirect("/denied.html?r=" + urllib.parse.quote("사이트 접근 권한이 없습니다. 구매 이력이 있는 계정으로 로그인해주세요."))
    return redirect("/user", set_cookie=session_cookie(make_session(uid, name, "user")))


def route_logout(req):
    return redirect("/", set_cookie="session=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax")

# ---------------------------------------------------------------- 라우트: 페이지

def route_user_page(req):
    s = req.session()
    if not s:
        return redirect("/")
    return serve_file("user.html")


def route_admin_page(req):
    s = req.session()
    if not s or s.get("role") != "admin":
        return redirect("/")
    return serve_file("admin.html")

# ---------------------------------------------------------------- API: 공통/유저

def api_me(req):
    s = req.session()
    if not s:
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    return json_resp({"uid": s["uid"], "name": s["name"], "role": s["role"]})


def api_request_create(req):
    s = req.session()
    if not s:
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    d = req.read_json() or {}
    game = clean(d.get("game"), 80)
    note = clean(d.get("note"), 300)
    if not game:
        return json_resp({"error": "게임 이름을 입력하세요."}, 400)
    with db_lock:
        pending = db().execute(
            "SELECT COUNT(*) FROM requests WHERE uid=? AND status='대기'", (s["uid"],)).fetchone()[0]
        if pending >= 3:
            return json_resp({"error": "대기 중인 요청이 3건 있습니다. 처리 후 다시 신청해주세요."}, 400)
        recent = db().execute(
            "SELECT MAX(created_at) FROM requests WHERE uid=?", (s["uid"],)).fetchone()[0]
        if recent and now() - recent < REQUEST_COOLDOWN:
            return json_resp({"error": "잠시 후 다시 시도해주세요."}, 400)
        db().execute(
            "INSERT INTO requests(uid,username,game,note,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (s["uid"], s["name"], game, note, now(), now()))
        db().commit()
    return json_resp({"ok": True})


def api_my_requests(req):
    s = req.session()
    if not s:
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    with db_lock:
        rows = db().execute(
            "SELECT id,game,note,status,admin_reply,created_at,updated_at "
            "FROM requests WHERE uid=? ORDER BY id DESC LIMIT 20", (s["uid"],)).fetchall()
    return json_resp({"requests": row_dicts(rows)})

# ---------------------------------------------------------------- API: 관리자

def require_admin(req):
    s = req.session()
    if not s or s.get("role") != "admin":
        return None
    return s


def api_admin_requests(req):
    with db_lock:
        rows = db().execute("SELECT * FROM requests ORDER BY id DESC LIMIT 300").fetchall()
    return json_resp({"requests": row_dicts(rows)})


def api_admin_respond(req):
    d = req.read_json() or {}
    rid = d.get("id")
    action = d.get("action")
    link = clean(d.get("link"), 500)
    message = clean(d.get("message"), 500)
    if not isinstance(rid, int) or action not in ("approve", "reject"):
        return json_resp({"error": "잘못된 요청"}, 400)
    with db_lock:
        row = db().execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
    if not row:
        return json_resp({"error": "없는 요청입니다."}, 404)
    if row["status"] != "대기":
        return json_resp({"error": "이미 처리된 요청입니다."}, 400)

    if action == "approve":
        if not link:
            return json_resp({"error": "복구 링크를 입력하세요."}, 400)
        content = (f"🔗 **[{row['game']}] 링크 복구 안내**\n"
                   f"요청하신 다운로드 링크가 복구되었습니다.\n\n{link}")
        if message:
            content += f"\n\n💬 {message}"
        content += "\n\n(이 링크도 일정 기간 후 만료될 수 있어요. 필요하면 복구센터에서 다시 요청해주세요.)"
        reply_store, new_status = link, "완료"
    else:
        reason = message or "사유 미기재"
        content = (f"❌ **[{row['game']}] 복구요청 안내**\n"
                   f"요청이 거절되었습니다.\n사유: {reason}")
        reply_store, new_status = reason, "거절"

    err = send_dm(row["uid"], content)
    if err:
        return json_resp({"error": err}, 400)
    with db_lock:
        db().execute("UPDATE requests SET status=?, admin_reply=?, updated_at=? WHERE id=?",
                     (new_status, reply_store, now(), rid))
        db().commit()
    return json_resp({"ok": True})


def api_admin_delete(req):
    d = req.read_json() or {}
    rid = d.get("id")
    if not isinstance(rid, int):
        return json_resp({"error": "잘못된 요청"}, 400)
    with db_lock:
        db().execute("DELETE FROM requests WHERE id=?", (rid,))
        db().commit()
    return json_resp({"ok": True})

# ---------------------------------------------------------------- 라우팅

GET_ROUTES = {
    "/login": route_login,
    "/callback": route_callback,
    "/logout": route_logout,
    "/user": route_user_page,
    "/admin": route_admin_page,
    "/api/me": api_me,
    "/api/my": api_my_requests,
}
GET_ADMIN_ROUTES = {
    "/api/admin/requests": api_admin_requests,
}
POST_ROUTES = {
    "/api/request": api_request_create,
}
POST_ADMIN_ROUTES = {
    "/api/admin/respond": api_admin_respond,
    "/api/admin/delete": api_admin_delete,
}

_init_done = False
_init_lock = threading.Lock()


def handle(req):
    global _init_done
    if not _init_done:
        with _init_lock:
            if not _init_done:
                init_db()
                _init_done = True
    if req.path.startswith("/api/"):
        purge_old()
    if req.method in ("GET", "HEAD"):
        if req.path in GET_ROUTES:
            return GET_ROUTES[req.path](req)
        if req.path in GET_ADMIN_ROUTES:
            if not require_admin(req):
                return json_resp({"error": "관리자 로그인이 필요합니다."}, 401)
            return GET_ADMIN_ROUTES[req.path](req)
        if req.path.startswith("/api/"):
            return json_resp({"error": "없는 API"}, 404)
        return serve_static(req.path)
    if req.method == "POST":
        if req.path in POST_ROUTES:
            return POST_ROUTES[req.path](req)
        if req.path in POST_ADMIN_ROUTES:
            if not require_admin(req):
                return json_resp({"error": "관리자 로그인이 필요합니다."}, 401)
            return POST_ADMIN_ROUTES[req.path](req)
        return json_resp({"error": "없는 API"}, 404)
    return json_resp({"error": "지원하지 않는 메서드"}, 404)


def application(environ, start_response):
    req = Request(environ)
    try:
        res = handle(req)
    except Exception as e:
        res = json_resp({"error": "서버 오류: " + str(e)}, 500)
    headers = list(res.headers)
    headers.append(("Content-Length", str(len(res.body))))
    start_response(STATUS_TEXT.get(res.status, f"{res.status} Error"), headers)
    if req.method == "HEAD":
        return [b""]
    return [res.body]

# ---------------------------------------------------------------- 로컬 실행

def main():
    from wsgiref.simple_server import make_server, WSGIServer, WSGIRequestHandler

    class ThreadingWSGIServer(socketserver.ThreadingMixIn, WSGIServer):
        daemon_threads = True
        allow_reuse_address = True

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, fmt, *args):
            pass

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    init_db()
    with make_server("0.0.0.0", port, application,
                     server_class=ThreadingWSGIServer, handler_class=QuietHandler) as httpd:
        print(f"[복구센터] 서버 시작: http://localhost:{port}")
        print("[복구센터] 종료: Ctrl+C")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
