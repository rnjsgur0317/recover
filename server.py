# -*- coding: utf-8 -*-
"""
H Company 통합 홈페이지 서버 (WSGI)
- 디스코드 OAuth2 로그인 (관리자 / 유저 분기)
- 유저: 지정 역할 보유자만 접근 → 링크 복구요청 접수(구매내역 캡쳐 필수)
- 관리자: 요청 확인 → 봇 토큰으로 유저 DM에 복구 링크 발송
- Python 표준 라이브러리만 사용. 데이터: data/recover.db, 캡쳐: data/uploads/
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
import secrets_config
SYNC_KEY = getattr(secrets_config, "SYNC_KEY", "")  # 미설정이면 동기화 API 비활성

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "recover.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
SHOP_PATH = os.path.join(DATA_DIR, "shop.json")     # 봇이 밀어올린 상품/잔액
SHOPIMG_DIR = os.path.join(DATA_DIR, "shopimg")     # 게임 소개 이미지

MAX_BODY = 16 * 1024
MAX_IMAGE_BODY = 6 * 1024 * 1024   # 캡쳐 포함 요청 최대 6MB
MAX_SYNC_BODY = 2 * 1024 * 1024    # 상품/잔액 동기화 최대 2MB
MAX_SYNC_IMAGE = 12 * 1024 * 1024  # 소개 이미지/영상 동기화 최대 12MB (base64 포함)
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
        c.executescript("""
        CREATE TABLE IF NOT EXISTS product_regs (  -- 게임 등록 신청 (봇이 products.json에 반영)
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price INTEGER NOT NULL,
            link TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '대기',    -- 대기/처리중/완료/실패
            result TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS charges (       -- 잔액 충전(문상) 신청
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT NOT NULL,
            username TEXT NOT NULL,
            amount INTEGER NOT NULL,
            code1 TEXT NOT NULL,
            code2 TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '대기',    -- 대기(봇 전달 전) / 전달됨(관리자 확인 중)
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (        -- 웹 구매 주문 / 신작 예약
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT NOT NULL,
            username TEXT NOT NULL,
            game TEXT NOT NULL,
            price INTEGER NOT NULL,                -- 주문 시점 가격 (fixed=1이면 봇이 이 금액 그대로 차감)
            status TEXT NOT NULL DEFAULT '대기',    -- 대기/처리중/완료/실패
            result TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notices (       -- 공지사항
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS upcoming (      -- 신작(출시 예정) 목록
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,                -- 출시가
            discount_price INTEGER NOT NULL,       -- 예약 구매가 (소량 할인)
            note TEXT NOT NULL DEFAULT '',
            image TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS discounts (     -- 할인 중인 게임
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game TEXT NOT NULL UNIQUE,
            sale_price INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bests (         -- BEST(인기) 게임
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game TEXT NOT NULL UNIQUE,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS gifts (         -- 사은품 (1회 구매 금액 조건)
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game TEXT NOT NULL,                    -- 사은품 게임 이름
            link TEXT NOT NULL,                    -- 지급할 링크
            value INTEGER NOT NULL DEFAULT 0,      -- 표시용 정가
            min_amount INTEGER NOT NULL,           -- 1회 구매 기준 금액
            created_at INTEGER NOT NULL
        );
        """)
        c.commit()
        for stmt in (
            "ALTER TABLE requests ADD COLUMN image TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE orders ADD COLUMN kind TEXT NOT NULL DEFAULT 'order'",   # order/reserve
            "ALTER TABLE orders ADD COLUMN fixed INTEGER NOT NULL DEFAULT 0",     # 1=웹이 정한 가격 그대로
            "ALTER TABLE orders ADD COLUMN link_sent INTEGER NOT NULL DEFAULT 0", # 예약: 출시 링크 발송됨
            "ALTER TABLE charges ADD COLUMN admin_note TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE orders ADD COLUMN gift_game TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE orders ADD COLUMN gift_link TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE gifts ADD COLUMN image TEXT NOT NULL DEFAULT ''",
        ):
            try:
                c.execute(stmt)
                c.commit()
            except sqlite3.OperationalError:
                pass  # 이미 컬럼 있음
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(SHOPIMG_DIR, exist_ok=True)
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


def remove_upload(fname):
    if fname and re.match(r"^req_\d+\.(jpg|png|webp|gif)$", fname):
        try:
            os.remove(os.path.join(UPLOAD_DIR, fname))
        except OSError:
            pass


IMG_CTYPE = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif",
             "mp4": "video/mp4", "webm": "video/webm"}
VIDEO_EXTS = ("mp4", "webm")


def decode_media(data_url, limit=8 * 1024 * 1024):
    """dataURL(이미지 또는 영상) → (bytes, 확장자). 실패 시 ValueError."""
    m = re.match(r"^data:(image/(?:png|jpeg|jpg|webp|gif)|video/(?:mp4|webm));base64,", data_url)
    if not m:
        raise ValueError("지원하지 않는 파일 형식입니다.")
    try:
        raw = base64.b64decode(data_url[m.end():])
    except Exception:
        raise ValueError("파일 형식이 올바르지 않습니다.")
    if len(raw) > limit:
        raise ValueError("파일이 너무 큽니다.")
    sub = m.group(1).split("/")[1]
    ext = "jpg" if sub in ("jpeg", "jpg") else sub
    return raw, ext


def decode_image(image_data, limit=4 * 1024 * 1024):
    """dataURL → (bytes, 확장자). 실패 시 ValueError."""
    m = re.match(r"^data:image/(png|jpeg|jpg|webp|gif);base64,", image_data)
    if not m:
        raise ValueError("이미지 형식이 올바르지 않습니다.")
    try:
        img_bytes = base64.b64decode(image_data[m.end():])
    except Exception:
        raise ValueError("이미지 형식이 올바르지 않습니다.")
    if len(img_bytes) > limit:
        raise ValueError("이미지가 너무 큽니다.")
    ext = "jpg" if m.group(1) in ("jpeg", "jpg") else m.group(1)
    return img_bytes, ext


def purge_old():
    global _last_purge
    if time.time() - _last_purge < 3600:
        return
    _last_purge = time.time()
    cutoff = now() - RETENTION_DAYS * 86400
    with db_lock:
        rows = db().execute(
            "SELECT image FROM requests WHERE created_at<? AND image!=''", (cutoff,)).fetchall()
        for r in rows:
            remove_upload(r["image"])
        db().execute("DELETE FROM requests WHERE created_at<?", (cutoff,))
        db().execute("DELETE FROM charges WHERE created_at<?", (cutoff,))
        db().execute("DELETE FROM orders WHERE created_at<?", (cutoff,))
        db().execute("DELETE FROM product_regs WHERE created_at<?", (cutoff,))
        db().commit()


# ---------------------------------------------------------------- 상점 데이터 (봇 동기화)

def load_shop():
    try:
        with open(SHOP_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"products": {}, "balances": {}, "images": {}, "updated_at": 0}


def save_shop(data):
    tmp = SHOP_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, SHOP_PATH)


def shopimg_filename(name, ext):
    return "img_" + hashlib.sha1(name.encode()).hexdigest()[:16] + "." + ext


def parse_intro_detail(content):
    """소개글 텍스트 → {official, rating, seller, comments}. 없는 항목은 생략."""
    out = {}
    m = re.search(r"공식가격\s*:\s*~~\s*([\d,]+)\s*원?\s*~~", content)
    if m:
        try:
            out["official"] = int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    m = re.search(r"수위\s*:\s*(.+)", content)
    if m:
        out["rating"] = m.group(1).strip()[:60]
    m = re.search(r"\[<\s*(https?://[^>\]]+)\s*>\]", content)
    if m:
        out["seller"] = m.group(1).strip()[:300]
    comments = []
    in_comment = False
    for line in content.splitlines():
        st = line.strip()
        if "코멘트" in st and st.startswith("#"):
            in_comment = True
            continue
        if "구매 안내" in st:
            break
        if in_comment and st.startswith("*"):
            c = st.lstrip("*").strip()
            if c:
                comments.append(c[:200])
    if comments:
        out["comments"] = comments[:10]
    return out

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


def send_dm(uid, embed):
    """봇 토큰으로 해당 유저에게 임베드 DM 전송. 반환: 오류메시지 or None(성공)"""
    status, ch = discord_call("POST", "/users/@me/channels", bot=True,
                              data={"recipient_id": str(uid)})
    if status != 200 or not isinstance(ch, dict) or "id" not in ch:
        return f"DM 채널 생성 실패 (코드 {status})"
    status, _msg = discord_call("POST", f"/channels/{ch['id']}/messages", bot=True,
                                data={"embeds": [embed]})
    if status in (200, 201):
        return None
    if status == 403:
        return "DM 전송 실패: 유저가 DM을 차단했거나 서버 멤버가 아닙니다."
    return f"DM 전송 실패 (코드 {status})"


def build_embed(title, description, fields, color):
    return {
        "title": title,
        "description": description,
        "color": color,
        "fields": [{"name": n, "value": v, "inline": False} for n, v in fields if v],
        "footer": {"text": "H Company · 링크 복구센터"},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
    }

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

    # 유저: 지정 역할 보유자만
    has_role, err = member_has_role(uid)
    if err:
        return redirect("/denied.html?r=" + urllib.parse.quote(err))
    if not has_role:
        return redirect("/denied.html?r=" + urllib.parse.quote("사이트 접근 권한이 없습니다. 디스코드 서버에서 권한을 받은 뒤 이용해주세요."))
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
    d = req.read_json(limit=MAX_IMAGE_BODY)
    if d is None:
        return json_resp({"error": "잘못된 요청 (이미지가 너무 크면 다시 시도해주세요)"}, 400)
    game = clean(d.get("game"), 80)
    note = clean(d.get("note"), 300)
    if not game:
        return json_resp({"error": "게임 이름을 입력하세요."}, 400)
    if not d.get("image"):
        return json_resp({"error": "구매내역 캡쳐를 첨부해주세요."}, 400)
    try:
        img_bytes, img_ext = decode_image(d["image"])
    except ValueError as e:
        return json_resp({"error": str(e)}, 400)
    with db_lock:
        pending = db().execute(
            "SELECT COUNT(*) FROM requests WHERE uid=? AND status='대기'", (s["uid"],)).fetchone()[0]
        if pending >= 3:
            return json_resp({"error": "대기 중인 요청이 3건 있습니다. 처리 후 다시 신청해주세요."}, 400)
        recent = db().execute(
            "SELECT MAX(created_at) FROM requests WHERE uid=?", (s["uid"],)).fetchone()[0]
        if recent and now() - recent < REQUEST_COOLDOWN:
            return json_resp({"error": "잠시 후 다시 시도해주세요."}, 400)
        cur = db().execute(
            "INSERT INTO requests(uid,username,game,note,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (s["uid"], s["name"], game, note, now(), now()))
        rid = cur.lastrowid
        fname = f"req_{rid}.{img_ext}"
        with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
            f.write(img_bytes)
        db().execute("UPDATE requests SET image=? WHERE id=?", (fname, rid))
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
        charges = db().execute(
            "SELECT id,amount,status,created_at "
            "FROM charges WHERE uid=? ORDER BY id DESC LIMIT 20", (s["uid"],)).fetchall()
        orders = db().execute(
            "SELECT id,game,price,status,result,kind,link_sent,gift_game,gift_link,"
            "created_at,updated_at "
            "FROM orders WHERE uid=? ORDER BY id DESC LIMIT 30", (s["uid"],)).fetchall()
    products = load_shop().get("products") or {}
    order_list = []
    for o in orders:
        o = dict(o)
        o["link_ok"] = (o["status"] == "완료"
                        and o["kind"] != "pass"
                        and (o["kind"] != "reserve" or o["link_sent"])
                        and now() - o["updated_at"] <= 7 * 86400
                        and bool((products.get(o["game"]) or {}).get("link")))
        o["gift_ok"] = (o["status"] == "완료" and bool(o["gift_game"]) and bool(o["gift_link"])
                        and now() - o["updated_at"] <= 7 * 86400)
        o.pop("gift_link", None)   # 링크는 전용 API로만 수령
        order_list.append(o)
    return json_resp({"requests": row_dicts(rows), "charges": row_dicts(charges),
                      "orders": order_list})


def discount_map():
    with db_lock:
        rows = db().execute("SELECT game, sale_price FROM discounts").fetchall()
    return {r["game"]: r["sale_price"] for r in rows}


def best_set():
    with db_lock:
        rows = db().execute("SELECT game FROM bests").fetchall()
    return {r["game"] for r in rows}


def media_flags(shop, name):
    files = entry_files(shop.get("images", {}).get(name))
    if not files:
        return False, None
    return True, ("video" if files[0].rsplit(".", 1)[-1] in VIDEO_EXTS else "img")


TIER_DISCOUNTS = ((120000, 10), (70000, 8), (40000, 5), (25000, 2))  # (누적액, 할인%)


def user_discount_pct(shop, uid):
    """유저의 등급 할인율(%). 봇이 push한 값 우선(Space 역할 포함), 없으면 누적액으로 계산."""
    profile = (shop.get("profiles") or {}).get(uid) or {}
    if isinstance(profile.get("discount_pct"), int):
        return max(0, min(50, profile["discount_pct"]))
    total = int(profile.get("total", 0) or 0)
    for th, pct in TIER_DISCOUNTS:
        if total >= th:
            return pct
    return 0


def apply_tier_discount(price, pct):
    return price * (100 - pct) // 100 if pct else price


def gift_list(shop):
    """유저 배너용 사은품 목록 (기준 금액 오름차순, 링크는 노출 안 함)."""
    with db_lock:
        rows = db().execute(
            "SELECT id, game, value, min_amount, image FROM gifts ORDER BY min_amount, id").fetchall()
    out = []
    for r in rows:
        # 썸네일: 사은품 자체 이미지 우선, 없으면 같은 이름의 판매 게임 이미지
        if r["image"]:
            thumb = "gift"
        else:
            has_img, _media = media_flags(shop, r["game"])
            thumb = "game" if has_img else None
        out.append({"id": r["id"], "game": r["game"], "value": r["value"],
                    "min_amount": r["min_amount"], "thumb": thumb})
    return out


def pass_info(shop, uid):
    """게임패스 화면 데이터: 패스 상품 목록 + 내 패스 상태 + 무료 수령 가능 게임."""
    passes = shop.get("passes") or {}
    gp = ((shop.get("profiles") or {}).get(uid) or {}).get("game_pass") or None
    active = bool(gp and gp.get("expires_at", 0) > now())
    defs = []
    for name, pd in passes.items():
        charge, action = int(pd.get("price", 0)), "new"
        if active:
            if gp.get("tier") == "7일" and pd.get("tier") == "30일":
                charge = int(pd.get("price", 0)) - int((passes.get("게임패스 7일") or {}).get("price", 0))
                action = "upgrade"
            else:
                action = "extend"
        defs.append({"name": name, "price": int(pd.get("price", 0)), "tier": pd.get("tier", ""),
                     "days": int(pd.get("days", 0)), "categories": pd.get("categories", []),
                     "charge": charge, "action": action})
    claimable = []
    if active and gp.get("purchased_at"):
        claimed = set(gp.get("claimed", []))
        cats = set(gp.get("categories", []))
        for name, info in (shop.get("products") or {}).items():
            if info.get("is_game_pass") or info.get("is_subscription"):
                continue
            if info.get("category") not in cats:
                continue
            reg = int(info.get("reg", 0) or 0)
            if reg <= 0 or reg < gp.get("purchased_at", 0) or reg > gp.get("expires_at", 0):
                continue
            if f"{name}|{reg}" in claimed:
                continue
            has_img, media = media_flags(shop, name)
            claimable.append({"name": name, "price": info.get("price", 0),
                              "img": has_img, "media": media,
                              "category": info.get("category", "")})
        claimable.sort(key=lambda x: x["name"])
    my = None
    if active:
        my = {"tier": gp.get("tier", ""), "purchased_at": gp.get("purchased_at", 0),
              "expires_at": gp.get("expires_at", 0), "categories": gp.get("categories", []),
              "claimed_count": len(gp.get("claimed", []))}
    return {"defs": defs, "my": my, "claimable": claimable}


def api_shopdata(req):
    """게임 목록 + 내 잔액 + 신작 목록. 봇이 약 1분마다 동기화."""
    s = req.session()
    if not s:
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    shop = load_shop()
    images = shop.get("images", {})
    details = shop.get("details", {})
    sales = discount_map()
    bests = best_set()
    cats = {}
    order = []
    for idx, (name, info) in enumerate((shop.get("products") or {}).items()):
        if info.get("is_game_pass"):
            continue  # 게임패스 상품은 전용 [게임패스] 탭에서
        cat = info.get("category") or "기타"
        if cat not in cats:
            cats[cat] = []
            order.append(cat)
        files = entry_files(images.get(name))
        media = None
        if files:
            media = "video" if files[0].rsplit(".", 1)[-1] in VIDEO_EXTS else "img"
        g = {
            "name": name,
            "price": info.get("price", 0),
            "is_subscription": bool(info.get("is_subscription")),
            "img": bool(files),
            "media": media,
        }
        official = details.get(name, {}).get("official")
        if official:
            g["official"] = official
        if name in sales:
            g["sale_price"] = sales[name]
        if name in bests:
            g["best"] = True
        g["_sort"] = (int(info.get("reg", 0) or 0), idx)
        cats[cat].append(g)
    # 최근 등록이 맨 위 (등록시각 desc, 없으면 목록 뒤쪽=최근 등록으로 간주)
    for cat in cats:
        cats[cat].sort(key=lambda x: x["_sort"], reverse=True)
        for g in cats[cat]:
            g.pop("_sort", None)
    with db_lock:
        upc = db().execute(
            "SELECT id,name,price,discount_price,note,image FROM upcoming ORDER BY id DESC").fetchall()
    balance = shop.get("balances", {}).get(s["uid"], 0)
    return json_resp({
        "balance": balance,
        "profile": shop.get("profiles", {}).get(s["uid"]),
        "updated_at": shop.get("updated_at", 0),
        "categories": [{"name": c, "games": cats[c]} for c in order],
        "upcoming": [{"id": u["id"], "name": u["name"], "price": u["price"],
                      "discount_price": u["discount_price"], "note": u["note"],
                      "img": bool(u["image"])} for u in upc],
        "pass": pass_info(shop, s["uid"]),
        "gifts": gift_list(shop),
        "discount_pct": user_discount_pct(shop, s["uid"]),
    })


def _serve_media_file(fname):
    if not fname or not re.match(r"^(img|upc|gft)_[0-9a-f]{16}\.(jpg|png|webp|gif|mp4|webm)$", fname):
        return json_resp({"error": "이미지가 없습니다."}, 404)
    fpath = os.path.join(SHOPIMG_DIR, fname)
    if not os.path.isfile(fpath):
        return json_resp({"error": "이미지가 없습니다."}, 404)
    with open(fpath, "rb") as f:
        data = f.read()
    ext = fname.rsplit(".", 1)[1]
    return Response(data, 200, [("Content-Type", IMG_CTYPE[ext]),
                                ("Cache-Control", "private, max-age=600")])


def api_shop_image(req):
    """게임 소개 이미지 (로그인 필요). ?name=게임명&i=번호"""
    if not req.session():
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    q = req.query()
    name = (q.get("name") or [""])[0]
    try:
        i = int((q.get("i") or ["0"])[0])
    except ValueError:
        i = 0
    files = entry_files(load_shop().get("images", {}).get(name))
    if not files or not (0 <= i < len(files)):
        return json_resp({"error": "이미지가 없습니다."}, 404)
    return _serve_media_file(files[i])


def api_upc_image(req):
    """신작(출시 예정) 이미지 (로그인 필요). ?id=번호"""
    if not req.session():
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    try:
        rid = int((req.query().get("id") or ["0"])[0])
    except ValueError:
        rid = 0
    with db_lock:
        row = db().execute("SELECT image FROM upcoming WHERE id=?", (rid,)).fetchone()
    return _serve_media_file(row["image"] if row else "")


def api_charge_create(req):
    """문화상품권 충전 신청 → 봇이 가져가서 관리자 DM(승인 버튼)으로 전달."""
    s = req.session()
    if not s:
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    d = req.read_json() or {}
    code1 = clean(d.get("code1"), 100)
    code2 = clean(d.get("code2"), 100)
    try:
        amount = int(str(d.get("amount", "")).replace(",", "").replace("원", "").strip())
    except ValueError:
        return json_resp({"error": "금액은 숫자만 입력해주세요."}, 400)
    if not code1:
        return json_resp({"error": "문화상품권 코드를 입력하세요."}, 400)
    if amount <= 0 or amount > 1000000:
        return json_resp({"error": "금액을 확인해주세요. (1 ~ 1,000,000원)"}, 400)
    with db_lock:
        pending = db().execute(
            "SELECT COUNT(*) FROM charges WHERE uid=? AND status='대기'", (s["uid"],)).fetchone()[0]
        if pending >= 3:
            return json_resp({"error": "전달 대기 중인 충전 신청이 3건 있습니다. 잠시 후 다시 시도해주세요."}, 400)
        recent = db().execute(
            "SELECT MAX(created_at) FROM charges WHERE uid=?", (s["uid"],)).fetchone()[0]
        if recent and now() - recent < REQUEST_COOLDOWN:
            return json_resp({"error": "잠시 후 다시 시도해주세요."}, 400)
        db().execute(
            "INSERT INTO charges(uid,username,amount,code1,code2,created_at) VALUES(?,?,?,?,?,?)",
            (s["uid"], s["name"], amount, code1, code2, now()))
        db().commit()
    return json_resp({"ok": True})

def game_order_price(shop, game, tier_pct=0):
    """(가격, fixed, 오류메시지). 게임 할인가 위에 등급 할인율까지 적용, 할인 있으면 fixed=1."""
    info = (shop.get("products") or {}).get(game)
    if not info:
        return 0, 0, "판매 중인 상품이 아닙니다."
    if info.get("is_game_pass"):
        return 0, 0, "게임패스는 [게임패스] 탭에서 구매해주세요."
    if info.get("is_subscription"):
        return 0, 0, "정기결제 상품은 구매할 수 없습니다. 관리자에게 문의해주세요."
    sale = discount_map().get(game)
    base = int(sale) if sale is not None else int(info.get("price", 0) or 0)
    final = apply_tier_discount(base, tier_pct)
    fixed = 1 if (sale is not None or final != base) else 0
    return final, fixed, None


def _order_guards(uid, games, max_inflight=10):
    """공통 가드. 오류메시지 or None. db_lock 안에서 호출."""
    inflight = db().execute(
        "SELECT COUNT(*) FROM orders WHERE uid=? AND status IN ('대기','처리중')",
        (uid,)).fetchone()[0]
    if inflight + len(games) > max_inflight:
        return "처리 중인 주문이 너무 많습니다. 잠시 후 다시 시도해주세요."
    for g in games:
        dup = db().execute(
            "SELECT COUNT(*) FROM orders WHERE uid=? AND game=? AND status IN ('대기','처리중')",
            (uid, g)).fetchone()[0]
        if dup:
            return f"'{g}' 주문이 이미 처리 중입니다."
    recent = db().execute(
        "SELECT MAX(created_at) FROM orders WHERE uid=?", (uid,)).fetchone()[0]
    if recent and now() - recent < 15:
        return "잠시 후 다시 시도해주세요."
    return None


def api_order_create(req):
    """웹 게임 구매 주문 (단건 또는 games 배열로 일괄) → 봇이 결제 처리."""
    s = req.session()
    if not s:
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    d = req.read_json() or {}
    if isinstance(d.get("games"), list):
        games = [clean(str(g), 100) for g in d["games"][:10] if clean(str(g), 100)]
        games = list(dict.fromkeys(games))  # 중복 제거
    else:
        games = [clean(d.get("game"), 100)]
    games = [g for g in games if g]
    if not games:
        return json_resp({"error": "잘못된 요청"}, 400)
    shop = load_shop()
    tier_pct = user_discount_pct(shop, s["uid"])
    priced = []
    for g in games:
        price, fixed, err = game_order_price(shop, g, tier_pct)
        if err:
            return json_resp({"error": f"'{g}': {err}"}, 400)
        priced.append((g, price, fixed))
    total = sum(p for _, p, _ in priced)
    balance = shop.get("balances", {}).get(s["uid"], 0)
    if balance < total:
        return json_resp({"error": f"잔액이 부족합니다. (내 잔액 {balance:,}원 / 총 {total:,}원) 충전 후 이용해주세요."}, 400)
    gift_game, gift_link = pick_gift(total)   # 1회 구매 총액 기준 사은품
    with db_lock:
        err = _order_guards(s["uid"], games)
        if err:
            return json_resp({"error": err}, 400)
        for i, (g, price, fixed) in enumerate(priced):
            db().execute(
                "INSERT INTO orders(uid,username,game,price,fixed,gift_game,gift_link,"
                "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (s["uid"], s["name"], g, price, fixed,
                 (gift_game or "") if i == 0 else "", (gift_link or "") if i == 0 else "",  # 사은품은 1건에만
                 now(), now()))
        db().commit()
    out = {"ok": True, "count": len(priced), "total": total}
    if gift_game:
        out["gift"] = gift_game
    return json_resp(out)


def api_reserve(req):
    """신작 예약 구매 — 예약가로 즉시 결제(봇 처리), 출시 시 링크 발송."""
    s = req.session()
    if not s:
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    d = req.read_json() or {}
    uid_ = d.get("id")
    if not isinstance(uid_, int):
        return json_resp({"error": "잘못된 요청"}, 400)
    with db_lock:
        row = db().execute("SELECT * FROM upcoming WHERE id=?", (uid_,)).fetchone()
    if not row:
        return json_resp({"error": "예약 가능한 상품이 아닙니다."}, 404)
    price = int(row["discount_price"] or row["price"])
    shop = load_shop()
    balance = shop.get("balances", {}).get(s["uid"], 0)
    if balance < price:
        return json_resp({"error": f"잔액이 부족합니다. (내 잔액 {balance:,}원 / 예약가 {price:,}원)"}, 400)
    with db_lock:
        dup = db().execute(
            "SELECT COUNT(*) FROM orders WHERE uid=? AND game=? AND kind='reserve' AND status!='실패'",
            (s["uid"], row["name"])).fetchone()[0]
        if dup:
            return json_resp({"error": "이미 예약한 게임입니다."}, 400)
        err = _order_guards(s["uid"], [row["name"]])
        if err:
            return json_resp({"error": err}, 400)
        db().execute(
            "INSERT INTO orders(uid,username,game,price,kind,fixed,created_at,updated_at) "
            "VALUES(?,?,?,?,'reserve',1,?,?)",
            (s["uid"], s["name"], row["name"], price, now(), now()))
        db().commit()
    return json_resp({"ok": True})


def api_pass_buy(req):
    """게임패스 구매/연장/업그레이드 신청 → 봇이 결제·적용."""
    s = req.session()
    if not s:
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    d = req.read_json() or {}
    name = clean(d.get("name"), 100)
    shop = load_shop()
    pinfo = pass_info(shop, s["uid"])
    target = next((p for p in pinfo["defs"] if p["name"] == name), None)
    if not target:
        return json_resp({"error": "게임패스 상품이 아닙니다."}, 400)
    charge = target["charge"]
    balance = shop.get("balances", {}).get(s["uid"], 0)
    if balance < charge:
        return json_resp({"error": f"잔액이 부족합니다. (내 잔액 {balance:,}원 / 결제 {charge:,}원)"}, 400)
    with db_lock:
        err = _order_guards(s["uid"], [name])
        if err:
            return json_resp({"error": err}, 400)
        db().execute(
            "INSERT INTO orders(uid,username,game,price,kind,fixed,created_at,updated_at) "
            "VALUES(?,?,?,?,'pass',0,?,?)",
            (s["uid"], s["name"], name, charge, now(), now()))
        db().commit()
    return json_resp({"ok": True})


def api_pass_claim(req):
    """게임패스 무료 수령 신청 → 봇이 검증 후 링크 DM."""
    s = req.session()
    if not s:
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    d = req.read_json() or {}
    game = clean(d.get("game"), 100)
    shop = load_shop()
    pinfo = pass_info(shop, s["uid"])
    if not pinfo["my"]:
        return json_resp({"error": "게임패스 권한이 없습니다. 패스를 먼저 구매해주세요."}, 400)
    if not any(c["name"] == game for c in pinfo["claimable"]):
        return json_resp({"error": "무료 수령 대상이 아니거나 이미 수령한 게임입니다."}, 400)
    with db_lock:
        err = _order_guards(s["uid"], [game])
        if err:
            return json_resp({"error": err}, 400)
        db().execute(
            "INSERT INTO orders(uid,username,game,price,kind,fixed,created_at,updated_at) "
            "VALUES(?,?,?,0,'claim',1,?,?)",
            (s["uid"], s["name"], game, now(), now()))
        db().commit()
    return json_resp({"ok": True})


def api_my_gift_link(req):
    """받은 사은품 링크 수령 (구매 완료 후 7일간, 본인만)"""
    s = req.session()
    if not s:
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    try:
        rid = int((req.query().get("id") or ["0"])[0])
    except ValueError:
        rid = 0
    with db_lock:
        row = db().execute("SELECT * FROM orders WHERE id=? AND uid=?", (rid, s["uid"])).fetchone()
    if not row or row["status"] != "완료" or not row["gift_game"] or not row["gift_link"]:
        return json_resp({"error": "사은품이 지급된 완료 주문이 아닙니다."}, 404)
    if now() - row["updated_at"] > 7 * 86400:
        return json_resp({"error": "수령 기간(7일)이 지났어요. 필요하면 [링크 복구] 탭에서 요청해주세요."}, 400)
    return json_resp({"link": row["gift_link"], "game": row["gift_game"]})


def api_notices(req):
    if not req.session():
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    with db_lock:
        rows = db().execute(
            "SELECT id,title,body,created_at,updated_at FROM notices ORDER BY id DESC LIMIT 50").fetchall()
    return json_resp({"notices": row_dicts(rows)})


def api_my_link(req):
    """구매한 게임의 다운로드 링크 (구매 완료 후 7일간, 본인만)"""
    s = req.session()
    if not s:
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    try:
        rid = int((req.query().get("id") or ["0"])[0])
    except ValueError:
        rid = 0
    with db_lock:
        row = db().execute("SELECT * FROM orders WHERE id=? AND uid=?", (rid, s["uid"])).fetchone()
    if not row or row["status"] != "완료":
        return json_resp({"error": "완료된 주문이 아닙니다."}, 404)
    if row["kind"] == "reserve" and not row["link_sent"]:
        return json_resp({"error": "아직 출시 전이에요. 출시되면 링크가 발송됩니다."}, 400)
    if now() - row["updated_at"] > 7 * 86400:
        return json_resp({"error": "다운로드 기간(7일)이 지났어요. 필요하면 [링크 복구] 탭에서 요청해주세요."}, 400)
    link = ((load_shop().get("products") or {}).get(row["game"]) or {}).get("link", "")
    if not link:
        return json_resp({"error": "링크 정보가 아직 동기화되지 않았어요. 잠시 후 다시 시도해주세요."}, 400)
    return json_resp({"link": link, "game": row["game"]})

# ---------------------------------------------------------------- API: 봇 동기화

def check_sync(req, limit=MAX_SYNC_BODY):
    """동기화 요청 인증. 성공 시 본문 dict, 실패 시 None."""
    if not SYNC_KEY:
        return None
    d = req.read_json(limit=limit)
    if not isinstance(d, dict):
        return None
    if not hmac.compare_digest(str(d.get("key", "")), SYNC_KEY):
        return None
    return d


def api_sync_pull(req):
    """봇: 미전달 충전 신청 + 웹에서 승인된 충전 건 가져가기."""
    d = check_sync(req)
    if d is None:
        return json_resp({"error": "인증 실패"}, 403)
    with db_lock:
        rows = db().execute(
            "SELECT id,uid,username,amount,code1,code2 FROM charges "
            "WHERE status='대기' ORDER BY id LIMIT 20").fetchall()
        approved = db().execute(
            "SELECT id,uid,username,amount FROM charges "
            "WHERE status='승인처리중' ORDER BY id LIMIT 20").fetchall()
    return json_resp({"charges": row_dicts(rows), "approved": row_dicts(approved)})


def api_sync_ack_approved(req):
    """봇: 웹 승인 충전 잔액 반영 완료 표시."""
    d = check_sync(req)
    if d is None:
        return json_resp({"error": "인증 실패"}, 403)
    ids = [i for i in (d.get("ids") or []) if isinstance(i, int)][:50]
    with db_lock:
        for rid in ids:
            db().execute("UPDATE charges SET status='승인' WHERE id=? AND status='승인처리중'", (rid,))
        db().commit()
    return json_resp({"ok": True})


def api_sync_ack(req):
    """봇: 관리자 DM 전달 완료 표시."""
    d = check_sync(req)
    if d is None:
        return json_resp({"error": "인증 실패"}, 403)
    ids = [i for i in (d.get("ids") or []) if isinstance(i, int)][:50]
    with db_lock:
        for rid in ids:
            db().execute("UPDATE charges SET status='전달됨' WHERE id=? AND status='대기'", (rid,))
        db().commit()
    return json_resp({"ok": True})


def api_sync_pull_regs(req):
    """봇: 게임 등록 신청 가져가기 (가져가면 처리중, 15분 초과 시 실패 처리)."""
    d = check_sync(req)
    if d is None:
        return json_resp({"error": "인증 실패"}, 403)
    with db_lock:
        db().execute(
            "UPDATE product_regs SET status='실패', result='처리 시간 초과 — 봇 상태를 확인하세요', updated_at=? "
            "WHERE status='처리중' AND updated_at<?", (now(), now() - 900))
        rows = db().execute(
            "SELECT id,name,category,price,link FROM product_regs "
            "WHERE status='대기' ORDER BY id LIMIT 10").fetchall()
        for r in rows:
            db().execute("UPDATE product_regs SET status='처리중', updated_at=? WHERE id=?",
                         (now(), r["id"]))
        db().commit()
    return json_resp({"regs": row_dicts(rows)})


def api_sync_reg_results(req):
    """봇: 게임 등록 결과 보고."""
    d = check_sync(req)
    if d is None:
        return json_resp({"error": "인증 실패"}, 403)
    with db_lock:
        for res in (d.get("results") or [])[:50]:
            if not isinstance(res, dict) or not isinstance(res.get("id"), int):
                continue
            db().execute(
                "UPDATE product_regs SET status=?, result=?, updated_at=? WHERE id=? AND status='처리중'",
                ("완료" if res.get("ok") else "실패", clean(str(res.get("msg", "")), 300),
                 now(), res["id"]))
        db().commit()
    return json_resp({"ok": True})


def api_sync_pull_orders(req):
    """봇: 대기 중인 웹 구매 주문 가져가기(가져가면 '처리중')."""
    d = check_sync(req)
    if d is None:
        return json_resp({"error": "인증 실패"}, 403)
    with db_lock:
        # 15분 넘게 결과가 안 온 '처리중' → 실패 처리 (봇 중단 등)
        db().execute(
            "UPDATE orders SET status='실패', result='처리 시간 초과 — 잔액이 차감됐다면 관리자에게 문의해주세요', updated_at=? "
            "WHERE status='처리중' AND updated_at<?", (now(), now() - 900))
        rows = db().execute(
            "SELECT id,uid,username,game,price,kind,fixed,gift_game,gift_link FROM orders "
            "WHERE status='대기' ORDER BY id LIMIT 10").fetchall()
        for r in rows:
            db().execute("UPDATE orders SET status='처리중', updated_at=? WHERE id=?", (now(), r["id"]))
        db().commit()
    return json_resp({"orders": row_dicts(rows)})


def api_sync_order_results(req):
    """봇: 주문 처리 결과 보고. {key, results: [{id, ok, msg}]}"""
    d = check_sync(req)
    if d is None:
        return json_resp({"error": "인증 실패"}, 403)
    with db_lock:
        for res in (d.get("results") or [])[:50]:
            if not isinstance(res, dict) or not isinstance(res.get("id"), int):
                continue
            db().execute(
                "UPDATE orders SET status=?, result=?, updated_at=? WHERE id=? AND status='처리중'",
                ("완료" if res.get("ok") else "실패", clean(str(res.get("msg", "")), 300), now(), res["id"]))
        db().commit()
    return json_resp({"ok": True})


def api_sync_push(req):
    """봇: 상품 목록 + 잔액 밀어올리기."""
    d = check_sync(req)
    if d is None:
        return json_resp({"error": "인증 실패"}, 403)
    updated = False
    shop = load_shop()
    if isinstance(d.get("products"), dict):
        shop["products"] = d["products"]
        updated = True
    if isinstance(d.get("balances"), dict):
        shop["balances"] = {str(k): v for k, v in d["balances"].items()}
        updated = True
    if isinstance(d.get("profiles"), dict):
        shop["profiles"] = d["profiles"]
        updated = True
    if isinstance(d.get("passes"), dict):
        shop["passes"] = d["passes"]
        updated = True
    if isinstance(d.get("intro"), dict):
        shop["intro"] = d["intro"]   # 소개채널 매핑 {channels, role} — 사이트 등록 시 소개글 게시용
        updated = True
    if not updated:
        return json_resp({"error": "잘못된 데이터"}, 400)
    shop["updated_at"] = now()
    save_shop(shop)
    return json_resp({"ok": True})


def api_sync_images(req):
    """봇: 웹이 이미 갖고 있는 이미지 목록 {게임명: 첨부ID}."""
    d = check_sync(req)
    if d is None:
        return json_resp({"error": "인증 실패"}, 403)
    shop = load_shop()
    return json_resp({"images": {n: e.get("att", "") for n, e in shop.get("images", {}).items()}})


def api_sync_details(req):
    """봇: 소개글 상세정보 push. {key, details: {게임명: 소개글 텍스트}}"""
    d = check_sync(req)
    if d is None:
        return json_resp({"error": "인증 실패"}, 403)
    details = d.get("details")
    if not isinstance(details, dict):
        return json_resp({"error": "잘못된 데이터"}, 400)
    shop = load_shop()
    store = shop.setdefault("details", {})
    for name, content in list(details.items())[:300]:
        name = clean(str(name), 100)
        if name and isinstance(content, str):
            store[name] = parse_intro_detail(content[:6000])
    save_shop(shop)
    return json_resp({"ok": True})


def api_shop_detail(req):
    """게임 상세 (로그인 필요)"""
    s = req.session()
    if not s:
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    name = clean((req.query().get("name") or [""])[0], 100)
    shop = load_shop()
    info = (shop.get("products") or {}).get(name)
    if not info:
        return json_resp({"error": "판매 중인 상품이 아닙니다."}, 404)
    files = entry_files(shop.get("images", {}).get(name))
    media_list = ["video" if f.rsplit(".", 1)[-1] in VIDEO_EXTS else "img" for f in files]
    sales = discount_map()
    out = {
        "name": name,
        "price": info.get("price", 0),
        "category": info.get("category", "기타"),
        "is_subscription": bool(info.get("is_subscription")),
        "img": bool(files),
        "media": media_list[0] if media_list else None,
        "media_list": media_list,
        "detail": shop.get("details", {}).get(name, {}),
        "balance": shop.get("balances", {}).get(s["uid"], 0),
    }
    if name in sales:
        out["sale_price"] = sales[name]
    if name in best_set():
        out["best"] = True
    return json_resp(out)


def entry_files(entry):
    """이미지 엔트리의 파일 목록 (구버전 {file} 호환)"""
    if not entry:
        return []
    files = entry.get("files")
    if isinstance(files, list) and files:
        return files
    return [entry["file"]] if entry.get("file") else []


def api_sync_image(req):
    """봇: 게임 소개 이미지/영상 업로드. {key, name, att, idx, total, image: dataURL}
    같은 게임의 미디어 여러 장을 idx=0..total-1 순서로 올린다. att는 변경 감지 키."""
    d = check_sync(req, limit=MAX_SYNC_IMAGE)
    if d is None:
        return json_resp({"error": "인증 실패"}, 403)
    name = clean(d.get("name"), 100)
    att = clean(str(d.get("att", "")), 200)
    try:
        idx = int(d.get("idx", 0))
        total = int(d.get("total", 1))
    except (TypeError, ValueError):
        return json_resp({"error": "잘못된 데이터"}, 400)
    if not name or not att or not d.get("image") or not (0 <= idx < total <= 4):
        return json_resp({"error": "잘못된 데이터"}, 400)
    try:
        img_bytes, ext = decode_media(d["image"], limit=8 * 1024 * 1024)
    except ValueError as e:
        return json_resp({"error": str(e)}, 400)
    shop = load_shop()
    images = shop.setdefault("images", {})
    entry = images.get(name) or {}
    if idx == 0:  # 새 세트 시작 — 이전 파일 정리
        for f in entry_files(entry):
            try:
                os.remove(os.path.join(SHOPIMG_DIR, f))
            except OSError:
                pass
        entry = {"files": []}
    fname = shopimg_filename(f"{name}#{idx}", ext)
    with open(os.path.join(SHOPIMG_DIR, fname), "wb") as f:
        f.write(img_bytes)
    files = entry.setdefault("files", [])
    files.append(fname)
    entry["file"] = files[0]
    if idx == total - 1:
        entry["att"] = att  # 세트 완성 시에만 확정 (중단되면 다음 동기화 때 재시도)
    images[name] = entry
    save_shop(shop)
    return json_resp({"ok": True})

# ---------------------------------------------------------------- API: 관리자

def require_admin(req):
    s = req.session()
    if not s or s.get("role") != "admin":
        return None
    return s


def api_admin_requests(req):
    with db_lock:
        rows = db().execute("SELECT * FROM requests ORDER BY id DESC LIMIT 300").fetchall()
        charges = db().execute("SELECT * FROM charges ORDER BY id DESC LIMIT 100").fetchall()
        orders = db().execute("SELECT * FROM orders ORDER BY id DESC LIMIT 100").fetchall()
        regs = db().execute("SELECT * FROM product_regs ORDER BY id DESC LIMIT 100").fetchall()
        gifts = db().execute("SELECT * FROM gifts ORDER BY min_amount, id").fetchall()
        notices = db().execute("SELECT * FROM notices ORDER BY id DESC LIMIT 50").fetchall()
        upcoming = db().execute("SELECT * FROM upcoming ORDER BY id DESC LIMIT 50").fetchall()
        discounts = db().execute("SELECT * FROM discounts ORDER BY id DESC LIMIT 100").fetchall()
        bests = db().execute("SELECT * FROM bests ORDER BY id DESC LIMIT 100").fetchall()
    shop = load_shop()
    categories = []
    for i in (shop.get("products") or {}).values():
        c = i.get("category") or "기타"
        if c not in categories:
            categories.append(c)
    return json_resp({"requests": row_dicts(rows), "charges": row_dicts(charges),
                      "orders": row_dicts(orders), "notices": row_dicts(notices),
                      "upcoming": row_dicts(upcoming), "discounts": row_dicts(discounts),
                      "bests": row_dicts(bests), "regs": row_dicts(regs),
                      "gifts": row_dicts(gifts),
                      "categories": categories,
                      "product_names": [{"name": n, "price": i.get("price", 0)}
                                        for n, i in (shop.get("products") or {}).items()
                                        if not i.get("is_subscription")],
                      "shop_updated_at": shop.get("updated_at", 0)})


def api_admin_image(req):
    """복구요청 구매내역 캡쳐 (관리자 전용)"""
    try:
        rid = int((req.query().get("id") or ["0"])[0])
    except ValueError:
        rid = 0
    with db_lock:
        row = db().execute("SELECT image FROM requests WHERE id=?", (rid,)).fetchone()
    fname = row["image"] if row else ""
    if not fname or not re.match(r"^req_\d+\.(jpg|png|webp|gif)$", fname):
        return json_resp({"error": "이미지가 없습니다."}, 404)
    fpath = os.path.join(UPLOAD_DIR, fname)
    if not os.path.isfile(fpath):
        return json_resp({"error": "이미지가 없습니다."}, 404)
    with open(fpath, "rb") as f:
        data = f.read()
    ctype = "image/jpeg" if fname.endswith(".jpg") else ("image/png" if fname.endswith(".png") else "image/webp")
    return Response(data, 200, [("Content-Type", ctype), ("Cache-Control", "private, max-age=3600")])


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
        embed = build_embed(
            "🔗 링크 복구 완료",
            f"상품 **{row['game']}** 의 다운로드 링크가 복구되었습니다.",
            [
                ("다운로드 링크", link),
                ("안내", message),
                ("유의사항", "이 링크도 일정 기간 후 만료될 수 있습니다. 필요하면 홈페이지에서 다시 요청해주세요."),
            ],
            0x2ECC71)
        reply_store, new_status = link, "완료"
    else:
        reason = message or "사유 미기재"
        embed = build_embed(
            "❌ 복구요청 거절",
            f"상품 **{row['game']}** 의 복구요청이 거절되었습니다.",
            [("사유", reason),
             ("문의", "궁금한 점은 디스코드 서버 문의 채널을 이용해주세요.")],
            0xE74C3C)
        reply_store, new_status = reason, "거절"

    err = send_dm(row["uid"], embed)
    if err:
        return json_resp({"error": err}, 400)
    with db_lock:
        db().execute("UPDATE requests SET status=?, admin_reply=?, updated_at=? WHERE id=?",
                     (new_status, reply_store, now(), rid))
        db().commit()
    return json_resp({"ok": True})


def api_admin_charge_action(req):
    """충전 신청 웹 처리. {id, action: 'approve'|'reject', reason?}
    approve → '승인처리중' (봇이 1분 내 잔액 반영+DM 후 '승인'으로 확정)
    reject → 즉시 거절 DM + '거절'"""
    d = req.read_json() or {}
    rid = d.get("id")
    action = d.get("action")
    reason = clean(d.get("reason"), 200)
    if not isinstance(rid, int) or action not in ("approve", "reject"):
        return json_resp({"error": "잘못된 요청"}, 400)
    with db_lock:
        row = db().execute("SELECT * FROM charges WHERE id=?", (rid,)).fetchone()
    if not row:
        return json_resp({"error": "없는 신청입니다."}, 404)
    if row["status"] not in ("대기", "전달됨"):
        return json_resp({"error": "이미 처리된 신청입니다."}, 400)
    if action == "approve":
        with db_lock:
            db().execute("UPDATE charges SET status='승인처리중' WHERE id=?", (rid,))
            db().commit()
        return json_resp({"ok": True, "msg": "승인 예약 완료 — 봇이 1분 내 잔액을 반영하고 DM을 보냅니다."})
    # 거절
    embed = build_embed(
        "❌ 충전 요청 거절",
        f"**{int(row['amount']):,}원** 충전 요청이 거절되었습니다.",
        [("사유", reason or "코드가 유효하지 않거나 금액이 일치하지 않습니다."),
         ("안내", "확인 후 다시 신청해주세요.")],
        0xE74C3C)
    err = send_dm(row["uid"], embed)
    if err:
        return json_resp({"error": err}, 400)
    with db_lock:
        db().execute("UPDATE charges SET status='거절', admin_note=? WHERE id=?", (reason, rid))
        db().commit()
    return json_resp({"ok": True})


def api_admin_notice(req):
    """공지 관리. {action: add|update|delete, id?, title?, body?}"""
    d = req.read_json() or {}
    action = d.get("action")
    with db_lock:
        if action == "add":
            title = clean(d.get("title"), 100)
            body = clean(d.get("body"), 2000)
            if not title:
                return json_resp({"error": "제목을 입력하세요."}, 400)
            db().execute("INSERT INTO notices(title,body,created_at,updated_at) VALUES(?,?,?,?)",
                         (title, body, now(), now()))
        elif action == "update":
            rid = d.get("id")
            if not isinstance(rid, int):
                return json_resp({"error": "잘못된 요청"}, 400)
            db().execute("UPDATE notices SET title=?, body=?, updated_at=? WHERE id=?",
                         (clean(d.get("title"), 100), clean(d.get("body"), 2000), now(), rid))
        elif action == "delete":
            rid = d.get("id")
            if not isinstance(rid, int):
                return json_resp({"error": "잘못된 요청"}, 400)
            db().execute("DELETE FROM notices WHERE id=?", (rid,))
        else:
            return json_resp({"error": "잘못된 요청"}, 400)
        db().commit()
    return json_resp({"ok": True})


def api_admin_upcoming(req):
    """신작(출시 예정) 관리. {action: add|update|delete, id?, name, price, discount_price, note, image?}"""
    d = req.read_json(limit=MAX_IMAGE_BODY) or {}
    action = d.get("action")
    img_bytes, img_ext = None, None
    if d.get("image"):
        try:
            img_bytes, img_ext = decode_media(d["image"])
        except ValueError as e:
            return json_resp({"error": str(e)}, 400)

    def parse_prices():
        try:
            price = int(str(d.get("price", "")).replace(",", "").strip())
            dc = int(str(d.get("discount_price", "")).replace(",", "").strip() or price)
        except ValueError:
            return None, None
        if price <= 0 or dc <= 0 or dc > price:
            return None, None
        return price, dc

    with db_lock:
        if action == "add":
            name = clean(d.get("name"), 100)
            price, dc = parse_prices()
            if not name or price is None:
                return json_resp({"error": "이름/가격을 확인하세요. (예약가는 출시가 이하)"}, 400)
            cur = db().execute(
                "INSERT INTO upcoming(name,price,discount_price,note,created_at) VALUES(?,?,?,?,?)",
                (name, price, dc, clean(d.get("note"), 300), now()))
            if img_bytes:
                fname = "upc_" + hashlib.sha1(f"upc{cur.lastrowid}".encode()).hexdigest()[:16] + "." + img_ext
                with open(os.path.join(SHOPIMG_DIR, fname), "wb") as f:
                    f.write(img_bytes)
                db().execute("UPDATE upcoming SET image=? WHERE id=?", (fname, cur.lastrowid))
        elif action in ("update", "delete"):
            rid = d.get("id")
            if not isinstance(rid, int):
                return json_resp({"error": "잘못된 요청"}, 400)
            row = db().execute("SELECT * FROM upcoming WHERE id=?", (rid,)).fetchone()
            if not row:
                return json_resp({"error": "없는 항목입니다."}, 404)
            if action == "delete":
                if row["image"]:
                    try:
                        os.remove(os.path.join(SHOPIMG_DIR, row["image"]))
                    except OSError:
                        pass
                db().execute("DELETE FROM upcoming WHERE id=?", (rid,))
            else:
                name = clean(d.get("name"), 100) or row["name"]
                price, dc = parse_prices()
                if price is None:
                    return json_resp({"error": "가격을 확인하세요. (예약가는 출시가 이하)"}, 400)
                db().execute("UPDATE upcoming SET name=?, price=?, discount_price=?, note=? WHERE id=?",
                             (name, price, dc, clean(d.get("note"), 300), rid))
                if img_bytes:
                    if row["image"]:
                        try:
                            os.remove(os.path.join(SHOPIMG_DIR, row["image"]))
                        except OSError:
                            pass
                    fname = "upc_" + hashlib.sha1(f"upc{rid}{now()}".encode()).hexdigest()[:16] + "." + img_ext
                    with open(os.path.join(SHOPIMG_DIR, fname), "wb") as f:
                        f.write(img_bytes)
                    db().execute("UPDATE upcoming SET image=? WHERE id=?", (fname, rid))
        else:
            return json_resp({"error": "잘못된 요청"}, 400)
        db().commit()
    return json_resp({"ok": True})


def api_admin_discount(req):
    """할인 관리. {action: 'set'|'unset', game, sale_price?}"""
    d = req.read_json() or {}
    action = d.get("action")
    game = clean(d.get("game"), 100)
    if not game:
        return json_resp({"error": "게임 이름을 입력하세요."}, 400)
    if action == "set":
        info = (load_shop().get("products") or {}).get(game)
        if not info:
            return json_resp({"error": "판매 목록에 없는 게임입니다. 이름을 정확히 입력하세요."}, 400)
        try:
            sale = int(str(d.get("sale_price", "")).replace(",", "").strip())
        except ValueError:
            return json_resp({"error": "할인가는 숫자로 입력하세요."}, 400)
        if sale <= 0 or sale >= int(info.get("price", 0) or 0):
            return json_resp({"error": "할인가는 0보다 크고 원래 판매가보다 낮아야 합니다."}, 400)
        with db_lock:
            db().execute(
                "INSERT INTO discounts(game,sale_price,created_at) VALUES(?,?,?) "
                "ON CONFLICT(game) DO UPDATE SET sale_price=excluded.sale_price",
                (game, sale, now()))
            db().commit()
    elif action == "unset":
        with db_lock:
            db().execute("DELETE FROM discounts WHERE game=?", (game,))
            db().commit()
    else:
        return json_resp({"error": "잘못된 요청"}, 400)
    return json_resp({"ok": True})


def api_admin_gift(req):
    """사은품 관리. {action: 'add'|'delete', id?, game, link, value, min_amount, image?}"""
    d = req.read_json(limit=MAX_IMAGE_BODY) or {}
    action = d.get("action")
    img_bytes, img_ext = None, None
    if d.get("image"):
        try:
            img_bytes, img_ext = decode_media(d["image"])
        except ValueError as e:
            return json_resp({"error": str(e)}, 400)
    with db_lock:
        if action == "add":
            game = clean(d.get("game"), 100)
            link = clean(d.get("link"), 500)
            try:
                min_amount = int(str(d.get("min_amount", "")).replace(",", "").strip())
                value = int(str(d.get("value", "0")).replace(",", "").strip() or 0)
            except ValueError:
                return json_resp({"error": "금액은 숫자로 입력하세요."}, 400)
            if not game or min_amount <= 0 or value < 0:
                return json_resp({"error": "사은품 게임/기준 금액을 확인하세요."}, 400)
            if not re.match(r"^https?://", link):
                return json_resp({"error": "지급 링크는 http(s):// 로 시작해야 합니다."}, 400)
            cur = db().execute(
                "INSERT INTO gifts(game,link,value,min_amount,created_at) VALUES(?,?,?,?,?)",
                (game, link, value, min_amount, now()))
            if img_bytes:
                fname = "gft_" + hashlib.sha1(f"gift{cur.lastrowid}".encode()).hexdigest()[:16] + "." + img_ext
                with open(os.path.join(SHOPIMG_DIR, fname), "wb") as f:
                    f.write(img_bytes)
                db().execute("UPDATE gifts SET image=? WHERE id=?", (fname, cur.lastrowid))
        elif action == "delete":
            rid = d.get("id")
            if not isinstance(rid, int):
                return json_resp({"error": "잘못된 요청"}, 400)
            row = db().execute("SELECT image FROM gifts WHERE id=?", (rid,)).fetchone()
            if row and row["image"]:
                try:
                    os.remove(os.path.join(SHOPIMG_DIR, row["image"]))
                except OSError:
                    pass
            db().execute("DELETE FROM gifts WHERE id=?", (rid,))
        else:
            return json_resp({"error": "잘못된 요청"}, 400)
        db().commit()
    return json_resp({"ok": True})


def api_gift_image(req):
    """사은품 이미지 (로그인 필요). ?id=번호"""
    if not req.session():
        return json_resp({"error": "로그인이 필요합니다."}, 401)
    try:
        rid = int((req.query().get("id") or ["0"])[0])
    except ValueError:
        rid = 0
    with db_lock:
        row = db().execute("SELECT image FROM gifts WHERE id=?", (rid,)).fetchone()
    return _serve_media_file(row["image"] if row else "")


def pick_gift(total):
    """1회 구매 총액으로 지급할 사은품 선택 (기준 금액이 가장 높은 것 하나)."""
    with db_lock:
        row = db().execute(
            "SELECT game, link FROM gifts WHERE min_amount<=? "
            "ORDER BY min_amount DESC, id DESC LIMIT 1", (total,)).fetchone()
    return (row["game"], row["link"]) if row else (None, None)


def api_admin_best(req):
    """BEST(인기) 게임 관리. {action: 'set'|'unset', game}"""
    d = req.read_json() or {}
    action = d.get("action")
    game = clean(d.get("game"), 100)
    if not game:
        return json_resp({"error": "게임 이름을 입력하세요."}, 400)
    if action == "set":
        if game not in (load_shop().get("products") or {}):
            return json_resp({"error": "판매 목록에 없는 게임입니다. 이름을 정확히 입력하세요."}, 400)
        with db_lock:
            db().execute("INSERT OR IGNORE INTO bests(game,created_at) VALUES(?,?)", (game, now()))
            db().commit()
    elif action == "unset":
        with db_lock:
            db().execute("DELETE FROM bests WHERE game=?", (game,))
            db().commit()
    else:
        return json_resp({"error": "잘못된 요청"}, 400)
    return json_resp({"ok": True})


def build_intro_content(name, official, server_price, rating, seller, comments, role_id):
    """디스코드 소개글 본문 — 관리자웹 build_intro_template 과 같은 형식."""
    t = "**게임 정보**\n\n"
    t += f"이름 : {name}\n"
    if official:
        t += f"공식가격 : ~~{official:,}원~~\n"
    t += f"서버가격 :__{server_price:,}원__ \n"
    if rating:
        t += f"수위 : {rating}\n"
    if seller:
        t += f"\n공식 판매처 :\n[<{seller}>]\n"
    t += "\n## 코멘트 :\n\n"
    if comments:
        for c in comments:
            t += f"* {c}\n"
    else:
        t += "*\n*\n"
    t += ("\n**구매 안내**\n\n"
          "• 구매 후 **반드시 파일 백업 바랍니다.** (재지급 X)\n"
          "• 단순 변심 환불은 불가능합니다.\n"
          "• 다운로드 문제 발생 시 문의 바랍니다.\n")
    if role_id:
        t += f"|| <@&{role_id}> ||"
    return t


def discord_post_intro(channel_id, content, media):
    """봇 토큰으로 소개글(텍스트+미디어) 게시. media: [(bytes, ext)]. 반환: 오류 or None"""
    boundary = "----HCompanyBoundary" + secrets.token_hex(8)
    payload = {"content": content[:1990], "allowed_mentions": {"parse": ["roles"]}}
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\n\r\n'.encode()
            + json.dumps(payload, ensure_ascii=False).encode() + b"\r\n")
    for i, (raw, ext) in enumerate(media):
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="files[{i}]"; '
                 f'filename="media{i}.{ext}"\r\nContent-Type: {IMG_CTYPE[ext]}\r\n\r\n'.encode()
                 + raw + b"\r\n")
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{DISCORD_API}/channels/{channel_id}/messages", data=body,
        headers={"Authorization": "Bot " + BOT_TOKEN,
                 "Content-Type": f"multipart/form-data; boundary={boundary}",
                 "User-Agent": "RecoverWeb/1.0"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            if res.status in (200, 201):
                return None
            return f"디스코드 응답 {res.status}"
    except urllib.error.HTTPError as e:
        return f"디스코드 오류 {e.code}"
    except Exception as e:
        return f"게시 실패: {e}"


def api_admin_product_reg(req):
    """게임 등록 신청 — 관리자웹 [게임출시]와 동일하게 등록 + 상세정보 + 이미지 + 소개글까지.
    상품 등록은 봇이 1분 내 products.json에 반영, 상세·이미지는 사이트에 즉시 저장,
    소개글은 소개채널에 바로 게시."""
    d = req.read_json(limit=MAX_SYNC_IMAGE) or {}
    name = clean(d.get("name"), 100)
    category = clean(d.get("category"), 30)
    link = clean(d.get("link"), 500)
    rating = clean(d.get("rating"), 40)
    seller = clean(d.get("seller"), 300)
    comments = [clean(c, 200) for c in str(d.get("comment", "")).split("\n") if clean(c, 200)][:10]
    try:
        price = int(str(d.get("price", "")).replace(",", "").strip())
    except ValueError:
        return json_resp({"error": "가격은 숫자로 입력하세요."}, 400)
    official = 0
    if str(d.get("official", "")).strip():
        try:
            official = int(str(d.get("official", "")).replace(",", "").strip())
        except ValueError:
            return json_resp({"error": "정가는 숫자로 입력하세요."}, 400)
    if not name or not category:
        return json_resp({"error": "이름과 카테고리를 입력하세요."}, 400)
    if price <= 0 or official < 0:
        return json_resp({"error": "가격을 확인하세요."}, 400)
    if not re.match(r"^https?://", link):
        return json_resp({"error": "다운로드 링크는 http(s):// 로 시작해야 합니다."}, 400)
    if seller and not re.match(r"^https?://", seller):
        return json_resp({"error": "공식 판매처 링크는 http(s):// 로 시작해야 합니다."}, 400)
    if name in (load_shop().get("products") or {}):
        return json_resp({"error": "이미 판매 중인 게임입니다. 수정은 로컬 관리자웹에서 해주세요."}, 400)
    # 미디어 디코딩 (최대 4개)
    media = []
    for du in (d.get("images") or [])[:4]:
        try:
            media.append(decode_media(du, limit=8 * 1024 * 1024))
        except ValueError as e:
            return json_resp({"error": str(e)}, 400)
    with db_lock:
        dup = db().execute(
            "SELECT COUNT(*) FROM product_regs WHERE name=? AND status IN ('대기','처리중')",
            (name,)).fetchone()[0]
        if dup:
            return json_resp({"error": "이미 등록 처리 중인 이름입니다."}, 400)
        db().execute(
            "INSERT INTO product_regs(name,category,price,link,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?)", (name, category, price, link, now(), now()))
        db().commit()
    # 상세정보 + 이미지 사이트에 즉시 저장
    shop = load_shop()
    detail = {}
    if official:
        detail["official"] = official
    if rating:
        detail["rating"] = rating
    if seller:
        detail["seller"] = seller
    if comments:
        detail["comments"] = comments
    if detail:
        shop.setdefault("details", {})[name] = detail
    if media:
        images = shop.setdefault("images", {})
        for f in entry_files(images.get(name)):
            try:
                os.remove(os.path.join(SHOPIMG_DIR, f))
            except OSError:
                pass
        files = []
        for i, (raw, ext) in enumerate(media):
            fname = shopimg_filename(f"{name}#{i}", ext)
            with open(os.path.join(SHOPIMG_DIR, fname), "wb") as f:
                f.write(raw)
            files.append(fname)
        att = "webreg-" + hashlib.sha1(b"".join(r for r, _ in media)).hexdigest()[:16]
        images[name] = {"att": att, "file": files[0], "files": files}
    if detail or media:
        save_shop(shop)
    # 디스코드 소개채널에 게시
    note = ""
    intro = shop.get("intro") or {}
    ch_id = (intro.get("channels") or {}).get(category)
    if ch_id and media:
        content = build_intro_content(name, official, price, rating, seller, comments,
                                      intro.get("role", 0))
        err = discord_post_intro(ch_id, content, media)
        note = "디스코드 소개글 게시 완료" if not err else f"소개글 게시 실패({err}) — 관리자웹에서 게시해주세요"
    elif not ch_id:
        note = f"'{category}' 소개채널 매핑이 없어 소개글은 생략했어요"
    elif not media:
        note = "이미지가 없어 소개글은 생략했어요"
    return json_resp({"ok": True, "note": note})


def api_admin_reservation_send(req):
    """예약 완료 건에 출시 링크 DM 발송. {id, message?}"""
    d = req.read_json() or {}
    rid = d.get("id")
    message = clean(d.get("message"), 300)
    if not isinstance(rid, int):
        return json_resp({"error": "잘못된 요청"}, 400)
    with db_lock:
        row = db().execute("SELECT * FROM orders WHERE id=?", (rid,)).fetchone()
    if not row or row["kind"] != "reserve" or row["status"] != "완료":
        return json_resp({"error": "결제 완료된 예약 건이 아닙니다."}, 400)
    if row["link_sent"]:
        return json_resp({"error": "이미 링크를 발송했습니다."}, 400)
    link = ((load_shop().get("products") or {}).get(row["game"]) or {}).get("link", "")
    if not link:
        return json_resp({"error": "게임이 아직 판매 목록에 없거나 링크가 동기화되지 않았어요. 게임을 먼저 등록하세요."}, 400)
    embed = build_embed(
        "🎉 예약하신 게임이 출시됐어요!",
        f"예약 구매하신 **{row['game']}** 의 다운로드 링크입니다.",
        [("다운로드 링크", link), ("안내", message),
         ("유의사항", "링크는 일정 기간 후 만료될 수 있어요. 사이트 내 정보 탭에서도 7일간 받을 수 있습니다.")],
        0x2ECC71)
    err = send_dm(row["uid"], embed)
    if err:
        return json_resp({"error": err}, 400)
    with db_lock:
        db().execute("UPDATE orders SET link_sent=1, updated_at=? WHERE id=?", (now(), rid))
        db().commit()
    return json_resp({"ok": True})


def api_admin_delete(req):
    d = req.read_json() or {}
    rid = d.get("id")
    if not isinstance(rid, int):
        return json_resp({"error": "잘못된 요청"}, 400)
    with db_lock:
        row = db().execute("SELECT image FROM requests WHERE id=?", (rid,)).fetchone()
        if row:
            remove_upload(row["image"])
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
    "/api/shopdata": api_shopdata,
    "/api/shop/image": api_shop_image,
    "/api/shop/upcimg": api_upc_image,
    "/api/shop/detail": api_shop_detail,
    "/api/notices": api_notices,
    "/api/my/link": api_my_link,
    "/api/my/gift_link": api_my_gift_link,
    "/api/shop/giftimg": api_gift_image,
}
GET_ADMIN_ROUTES = {
    "/api/admin/requests": api_admin_requests,
    "/api/admin/image": api_admin_image,
}
POST_ROUTES = {
    "/api/request": api_request_create,
    "/api/charge": api_charge_create,
    "/api/order": api_order_create,
    "/api/reserve": api_reserve,
    "/api/pass/buy": api_pass_buy,
    "/api/pass/claim": api_pass_claim,
    "/api/sync/pull": api_sync_pull,
    "/api/sync/ack_approved": api_sync_ack_approved,
    "/api/sync/pull_orders": api_sync_pull_orders,
    "/api/sync/order_results": api_sync_order_results,
    "/api/sync/pull_regs": api_sync_pull_regs,
    "/api/sync/reg_results": api_sync_reg_results,
    "/api/sync/ack": api_sync_ack,
    "/api/sync/push": api_sync_push,
    "/api/sync/images": api_sync_images,
    "/api/sync/image": api_sync_image,
    "/api/sync/details": api_sync_details,
}
POST_ADMIN_ROUTES = {
    "/api/admin/respond": api_admin_respond,
    "/api/admin/delete": api_admin_delete,
    "/api/admin/charge_action": api_admin_charge_action,
    "/api/admin/notice": api_admin_notice,
    "/api/admin/upcoming": api_admin_upcoming,
    "/api/admin/discount": api_admin_discount,
    "/api/admin/best": api_admin_best,
    "/api/admin/product_reg": api_admin_product_reg,
    "/api/admin/gift": api_admin_gift,
    "/api/admin/reservation_send": api_admin_reservation_send,
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
