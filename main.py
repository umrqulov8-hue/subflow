import os
import re
import uuid
import json
import time
import hmac
import hashlib
from datetime import datetime
from pathlib import Path
import deepl
from deep_translator import GoogleTranslator
from fastapi import FastAPI, UploadFile, File, Form, Header, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests as req

DEEPL_KEY = "bb3594bb-7228-42e8-892a-6c2b2b85c92e:fx"
deepl_translator = deepl.Translator(DEEPL_KEY)
DEEPL_LIMIT = 1000000

SUPABASE_URL = "https://kehjabkmrgpfjfbvwfab.supabase.co"
SUPABASE_KEY = "sb_publishable_veNIaaa-jgaKhb3jU3-HqA_u5q4dol2"

TSPAY_MERCHANT_ID = os.getenv("TSPAY_MERCHANT_ID", "696f9c0bb7854113")
TSPAY_API_KEY = os.getenv("TSPAY_API_KEY", "7e5082f37ca9f94afcbfe635f9c5147bf58a7b997c4fc499")
TSPAY_WEBHOOK_SECRET = os.getenv("TSPAY_WEBHOOK_SECRET", "d18cffe08b612c7a09bb7956b5b041b64195029548a98be4b603cc9b6faa612e")
TSPAY_API_URL = "https://api.tspay.uz/api/transactions/"
APP_URL = os.getenv("APP_URL", "http://localhost:8000")
TSPAY_WEBHOOK_URL = f"{APP_URL}/webhook/tspay"

LANG_MAP = {
    'auto': None, 'en': 'EN', 'ru': 'RU', 'uz': 'UZ', 'tr': 'TR',
    'de': 'DE', 'fr': 'FR', 'es': 'ES', 'ar': 'AR', 'zh': 'ZH', 'ko': 'KO',
}

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
STATIC_DIR = Path("static")
USERS_FILE = Path("users.json")
PAYMENTS_FILE = Path("payments.json")

app = FastAPI(title="Subtitle AI")

@app.on_event("startup")
async def startup():
    load_payments()
    load_users()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

deepl_session = req.Session()
supabase_session = req.Session()
tspay_session = req.Session()


# ─── Data Helpers (with in-memory cache) ───

_cache: dict = {"payments": None, "payments_mtime": 0.0, "users": None, "users_mtime": 0.0}

def _read_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}

def _write_json(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2))

def load_payments() -> dict:
    try:
        mtime = PAYMENTS_FILE.stat().st_mtime if PAYMENTS_FILE.exists() else 0
        if _cache["payments"] is not None and mtime == _cache["payments_mtime"]:
            return _cache["payments"]
        data = _read_json(PAYMENTS_FILE)
        _cache["payments"] = data
        _cache["payments_mtime"] = mtime
        return data
    except Exception:
        return _cache["payments"] or {}

def save_payments(payments: dict):
    _write_json(PAYMENTS_FILE, payments)
    _cache["payments"] = payments
    try:
        _cache["payments_mtime"] = PAYMENTS_FILE.stat().st_mtime
    except Exception:
        pass

def load_users() -> dict:
    try:
        mtime = USERS_FILE.stat().st_mtime if USERS_FILE.exists() else 0
        if _cache["users"] is not None and mtime == _cache["users_mtime"]:
            return _cache["users"]
        data = _read_json(USERS_FILE)
        _cache["users"] = data
        _cache["users_mtime"] = mtime
        return data
    except Exception:
        return _cache["users"] or {}

def save_users(users: dict):
    _write_json(USERS_FILE, users)
    _cache["users"] = users
    try:
        _cache["users_mtime"] = USERS_FILE.stat().st_mtime
    except Exception:
        pass


# ─── Supabase Auth Helpers ───

def verify_supabase_token(token: str) -> dict | None:
    try:
        resp = supabase_session.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={"Authorization": f"Bearer {token}", "apikey": SUPABASE_KEY}
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "id": data.get("id", ""),
                "email": data.get("email", ""),
                "name": data.get("user_metadata", {}).get("name", data.get("email", "")),
            }
    except Exception:
        pass
    return None

def get_user_from_token(authorization: str = "") -> dict | None:
    if not authorization.startswith("Bearer "):
        return None
    return verify_supabase_token(authorization[7:])


# ─── User & Subscription Helpers ───

def get_or_create_user(user_id: str, email: str, name: str = "") -> dict:
    users = load_users()
    if user_id not in users:
        users[user_id] = {
            "id": user_id, "email": email, "name": name or email,
            "plan": "free", "created_at": time.time(),
            "subscription": {"status": "none", "plan": "none", "expires_at": 0, "payment_id": None, "auto_renew": False},
            "usage": {"period_start": time.time(), "chars_used": 0},
            "payment_methods": [],
        }
        save_users(users)
    return users[user_id]

def check_subscription_expiry(user: dict, user_id: str):
    sub = user.get("subscription", {})
    if sub.get("status") == "active" and sub.get("expires_at"):
        now = time.time()
        if now > sub["expires_at"]:
            if sub.get("auto_renew"):
                payment_id = "pay_" + uuid.uuid4().hex[:12]
                payments = load_payments()
                payments[payment_id] = {
                    "payment_id": payment_id, "user_id": user_id,
                    "email": user.get("email", ""), "amount": 5.49,
                    "currency": "USD", "card_last4": "0000", "card_masked": "•••• 0000",
                    "plan": sub.get("plan", "pro"), "status": "completed",
                    "created_at": now, "next_billing": now + 30 * 24 * 3600, "auto_charged": True,
                }
                save_payments(payments)
                user["subscription"]["expires_at"] = now + 30 * 24 * 3600
                user["subscription"]["payment_id"] = payment_id
                user["usage"] = {"period_start": now, "chars_used": 0}
            else:
                user["subscription"]["status"] = "expired"
                user["plan"] = "free"
            users = load_users()
            users[user_id] = user
            save_users(users)

def get_user_usage(user: dict) -> dict:
    usage = user.get("usage", {})
    period_start = usage.get("period_start", 0)
    now = time.time()
    month_seconds = 30 * 24 * 3600
    if now - period_start > month_seconds:
        user["usage"] = {"period_start": now, "chars_used": 0}
        usage = user["usage"]
    limit = DEEPL_LIMIT if user.get("plan") == "pro" else 0
    return {
        "used": usage.get("chars_used", 0), "limit": limit,
        "remaining": max(0, limit - usage.get("chars_used", 0)),
        "exhausted": usage.get("chars_used", 0) >= limit,
    }

def add_user_usage(user: dict, user_id: str, chars: int):
    usage = user.get("usage", {})
    now = time.time()
    month_seconds = 30 * 24 * 3600
    if now - usage.get("period_start", 0) > month_seconds:
        user["usage"] = {"period_start": now, "chars_used": chars}
    else:
        user["usage"]["chars_used"] = usage.get("chars_used", 0) + chars
    users = load_users()
    users[user_id] = user
    save_users(users)


# ─── Models ───

class CreatePaymentRequest(BaseModel):
    plan: str = "pro"


# ─── TSPay Webhook ───

@app.post("/webhook/tspay")
async def tspay_webhook(request: Request):
    try:
        body = await request.json()
        headers = dict(request.headers)

        sig = headers.get("x-signature", "")
        ts = headers.get("x-timestamp", "")
        params = body.get("params", {})
        method = body.get("method", "")

        print(f"[TSPAY] method={method} params={params} sig={sig} ts={ts}")

        if not params or not method:
            return JSONResponse({"allow": False, "reason": "Invalid request structure"}, status_code=400)

        order_id = str(params.get("order_id", "")).strip()
        amount_str = str(params.get("amount", "")).strip()
        if amount_str and "." not in amount_str:
            amount_str += ".0"

        timestamp = str(ts).strip()
        data_to_sign = f"{order_id}:{amount_str}:{timestamp}"
        expected = "sha256=" + hmac.new(
            TSPAY_WEBHOOK_SECRET.encode(), data_to_sign.encode(), hashlib.sha256
        ).hexdigest()

        print(f"[TSPAY] data_to_sign={data_to_sign}")
        print(f"[TSPAY] expected={expected}")
        print(f"[TSPAY] got={sig}")

        if not hmac.compare_digest(sig, expected):
            return JSONResponse({"allow": False, "reason": "Invalid signature"}, status_code=401)

        payments = load_payments()

        if method == "checkPerform":
            order = payments.get(order_id)
            if not order:
                return JSONResponse({"allow": False, "reason": "Buyurtma topilmadi"})
            if float(order.get("amount", 0)) != float(amount_str):
                return JSONResponse({"allow": False, "reason": "Summa mos emas"})
            return JSONResponse({"allow": True, "additional": {"dbId": order.get("id", order_id)}})

        if method == "createTransaction":
            order = payments.get(order_id)
            if not order:
                return JSONResponse({"success": False, "error": "Order not found"})
            if order.get("cheque_id"):
                if float(order.get("amount", 0)) != float(amount_str):
                    return JSONResponse({"error": {"code": -31001, "message": "Summa xato"}}, status_code=400)
                return JSONResponse({"success": True, "transaction_id": order["cheque_id"]})
            if float(order.get("amount", 0)) != float(amount_str):
                return JSONResponse({"error": {"code": -31001, "message": "Summa xato"}}, status_code=400)
            payments[order_id]["cheque_id"] = params.get("cheque_id")
            save_payments(payments)
            return JSONResponse({"success": True})

        if method == "performTransaction":
            order = payments.get(order_id)
            if not order:
                return JSONResponse({"success": False, "reason": "Payment not found"})
            if order.get("status") == "success":
                return JSONResponse({"success": True})

            payments[order_id]["status"] = "success"
            save_payments(payments)

            user_id = order.get("user_id", "")
            if user_id:
                users = load_users()
                user = users.get(user_id)
                if user:
                    now = time.time()
                    sub = user.get("subscription", {})
                    expires_at = now + 30 * 24 * 3600
                    if sub.get("status") == "active" and sub.get("expires_at") and sub["expires_at"] > now:
                        expires_at = sub["expires_at"] + 30 * 24 * 3600

                    user["subscription"] = {
                        "status": "active", "plan": order.get("plan", "pro"),
                        "started_at": now, "expires_at": expires_at,
                        "payment_id": order_id, "auto_renew": True,
                    }
                    user["plan"] = order.get("plan", "pro")
                    user["usage"] = {"period_start": now, "chars_used": 0}
                    users[user_id] = user
                    save_users(users)

            return JSONResponse({"success": True})

        return JSONResponse({"allow": False, "reason": "Noma'lum metod"}, status_code=400)

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── Payment Endpoints ───

@app.post("/api/create-payment")
async def create_payment(req_body: CreatePaymentRequest, authorization: str = Header("")):
    supa_user = get_user_from_token(authorization)
    if not supa_user:
        return JSONResponse({"error": "Sign in required"}, status_code=401)

    user_id = supa_user["id"]
    email = supa_user["email"]
    order_id = int(time.time() * 1000)

    payments = load_payments()
    str_order_id = str(order_id)
    payments[str_order_id] = {
        "id": str_order_id, "order_id": order_id,
        "user_id": user_id, "email": email,
        "amount": 70000, "amount_usd": 5.49,
        "currency": "UZS",
        "plan_name": req_body.plan, "status": "pending",
        "cheque_id": None, "created_at": time.time(),
    }
    save_payments(payments)

    try:
        resp = tspay_session.post(
            TSPAY_API_URL,
            json={
                "merchant_id": TSPAY_MERCHANT_ID,
                "amount": 70000,
                "order_id": order_id,
                "redirect_url": APP_URL,
                "webhook_url": TSPAY_WEBHOOK_URL,
            },
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {TSPAY_API_KEY}",
            }
        )

        if resp.status_code == 200:
            data = resp.json()
            cheque_id = data.get("cheque_id", "")
            payment_url = data.get("payment_url", "")
            if cheque_id:
                payments[str_order_id]["cheque_id"] = cheque_id
                save_payments(payments)
            if payment_url:
                return {"ok": True, "payment_url": payment_url, "order_id": str_order_id, "cheque_id": cheque_id}
            return JSONResponse({"error": "No payment URL in response", "details": data}, status_code=400)
        else:
            return JSONResponse({"error": f"TSPay API error: {resp.text}"}, status_code=resp.status_code)

    except Exception as e:
        return JSONResponse({"error": f"TSPay error: {str(e)}"}, status_code=500)


@app.get("/api/payment-status/{order_id}")
async def payment_status(order_id: str, authorization: str = Header("")):
    supa_user = get_user_from_token(authorization)
    if not supa_user:
        return JSONResponse({"error": "Sign in required"}, status_code=401)

    payments = load_payments()
    order = payments.get(order_id)
    if not order:
        return JSONResponse({"error": "Order not found"}, status_code=404)

    return {
        "order_id": order_id,
        "status": order.get("status", "pending"),
        "cheque_id": order.get("cheque_id"),
    }


# ─── Subscription Endpoints ───

@app.get("/api/subscription")
async def get_subscription(authorization: str = Header("")):
    supa_user = get_user_from_token(authorization)
    if not supa_user:
        return JSONResponse({"error": "Sign in required"}, status_code=401)

    user_id = supa_user["id"]
    users = load_users()
    user = users.get(user_id, {"subscription": {"status": "none"}, "usage": {"period_start": 0, "chars_used": 0}, "payment_methods": []})
    check_subscription_expiry(user, user_id)

    sub = user.get("subscription", {"status": "none"})
    usage = get_user_usage(user)
    methods = user.get("payment_methods", [])

    last_payment = None
    payments = load_payments()
    for p in payments.values():
        if p.get("user_id") == user_id and p["status"] == "success":
            if not last_payment or p["created_at"] > last_payment["created_at"]:
                last_payment = p

    return {"subscription": sub, "usage": usage, "payment_methods": methods, "last_payment": last_payment}


@app.post("/api/cancel")
async def cancel_subscription(authorization: str = Header("")):
    supa_user = get_user_from_token(authorization)
    if not supa_user:
        return JSONResponse({"error": "Sign in required"}, status_code=401)
    user_id = supa_user["id"]
    users = load_users()
    sub = users[user_id].get("subscription", {})
    sub["auto_renew"] = False
    users[user_id]["subscription"] = sub
    save_users(users)
    expires = datetime.fromtimestamp(sub.get("expires_at", 0)).strftime("%b %d, %Y")
    return {"ok": True, "message": f"Auto-renew cancelled. Access until {expires}"}


@app.post("/api/reactivate")
async def reactivate_subscription(authorization: str = Header("")):
    supa_user = get_user_from_token(authorization)
    if not supa_user:
        return JSONResponse({"error": "Sign in required"}, status_code=401)
    user_id = supa_user["id"]
    users = load_users()
    sub = users[user_id].get("subscription", {})
    sub["auto_renew"] = True
    users[user_id]["subscription"] = sub
    save_users(users)
    return {"ok": True, "message": "Auto-renew enabled"}


# ─── Usage Endpoint ───

@app.get("/usage")
async def usage(authorization: str = Header("")):
    supa_user = get_user_from_token(authorization) if authorization else None
    if supa_user:
        users = load_users()
        user = users.get(supa_user["id"], {})
        if user:
            return get_user_usage(user)
    try:
        resp = deepl_session.get(
            "https://api-free.deepl.com/v2/usage",
            headers={"Authorization": f"DeepL-Auth-Key {DEEPL_KEY}"}
        )
        data = resp.json()
        used = data["character_count"]
        limit = data["character_limit"]
        return {"used": used, "limit": limit, "remaining": limit - used, "exhausted": limit - used <= 0}
    except Exception:
        return {"used": 0, "limit": DEEPL_LIMIT, "remaining": DEEPL_LIMIT, "exhausted": False}


# ─── Translation Helpers ───

def translate_deepl_batch(texts: list[str], target: str, user: dict = None, user_id: str = "") -> list[str]:
    if not texts:
        return []
    deepl_target = LANG_MAP.get(target, target.upper())
    if not deepl_target:
        return texts
    try:
        joined = "\n".join(texts)
        result = deepl_translator.translate_text(joined, target_lang=deepl_target)
        if user and user_id:
            add_user_usage(user, user_id, len(joined))
        translated = str(result).split("\n")
        while len(translated) < len(texts):
            translated.append(texts[len(translated)])
        return translated[:len(texts)]
    except Exception:
        return texts

def translate_google_batch(texts: list[str], source: str, target: str) -> list[str]:
    if not texts:
        return []
    try:
        joined = "\n".join(texts)
        result = GoogleTranslator(source=source if source != "auto" else "auto", target=target).translate(joined)
        translated = result.split("\n")
        while len(translated) < len(texts):
            translated.append(texts[len(translated)])
        return translated[:len(texts)]
    except Exception:
        return [GoogleTranslator(source=source if source != "auto" else "auto", target=target).translate(t) for t in texts]

def translate_texts(texts: list[str], source: str, target: str, engine: str, user: dict = None, user_id: str = "") -> list[str]:
    if engine == "pro" and user:
        usage = get_user_usage(user)
        remaining = usage["remaining"]
        total_len = sum(len(t) for t in texts) + len(texts) - 1
        if remaining > total_len:
            return translate_deepl_batch(texts, target, user, user_id)
    return translate_google_batch(texts, source, target)


# ─── File Parsing ───

def parse_srt(content: str):
    blocks = re.split(r"\n\n+", content.strip())
    parsed = []
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 2:
            time_line = None
            text_lines = []
            for i, line in enumerate(lines):
                if "-->" in line:
                    time_line = line
                    text_lines = lines[i + 1:]
                    break
            if time_line:
                parsed.append({"index": lines[0] if lines[0].strip().isdigit() else "", "time": time_line, "text": "\n".join(text_lines)})
    return parsed

def parse_ass(content: str):
    lines = content.split("\n")
    header = []
    dialogues = []
    for line in lines:
        if line.startswith("Dialogue:"):
            parts = line.split(",", 9)
            if len(parts) == 10:
                dialogues.append({"parts": parts, "text": parts[9].strip()})
            else:
                header.append(line)
        else:
            header.append(line)
    return header, dialogues

def reassemble_ass(header: list, dialogues: list) -> str:
    result = list(header)
    for d in dialogues:
        d["parts"][9] = d["text"]
        result.append(",".join(d["parts"]))
    return "\n".join(result)


# ─── Static & Upload ───

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/static/{path:path}")
async def serve_static(path: str):
    file_path = STATIC_DIR / path
    if file_path.exists() and file_path.is_file():
        media_type = "text/css" if path.endswith(".css") else "application/javascript" if path.endswith(".js") else "text/plain"
        return FileResponse(file_path, media_type=media_type)
    return HTMLResponse(status_code=404)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_id = uuid.uuid4().hex[:8]
    ext = Path(file.filename or "subtitle.srt").suffix
    save_name = f"{file_id}{ext}"
    save_path = UPLOAD_DIR / save_name
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)
    return {"file_id": file_id, "filename": file.filename, "saved_as": save_name}


@app.get("/translate_progress")
async def translate_progress(
    file_id: str = "", source: str = "auto", target: str = "uz",
    engine: str = "free", token: str = "",
):
    user = None
    user_id = ""
    if token:
        supa_user = verify_supabase_token(token)
        if supa_user:
            user_id = supa_user["id"]
            users = load_users()
            user = users.get(user_id)
            if not user:
                user = get_or_create_user(user_id, supa_user["email"], supa_user["name"])
            else:
                check_subscription_expiry(user, user_id)
                if engine == "pro" and user.get("plan") != "pro":
                    engine = "free"

    upload_files = list(UPLOAD_DIR.glob(f"{file_id}.*"))
    if not upload_files:
        async def err():
            yield f"data: {json.dumps({'type': 'error', 'message': 'File not found'})}\n\n"
        return StreamingResponse(err(), media_type="text/event-stream")

    file_path = upload_files[0]
    is_ass = file_path.suffix == ".ass"
    content = file_path.read_text(encoding="utf-8", errors="replace")
    BATCH_SIZE = 25

    async def generate():
        if is_ass:
            header, dialogues = parse_ass(content)
            total = len(dialogues)
            start_time = time.time()
            for batch_start in range(0, total, BATCH_SIZE):
                batch = dialogues[batch_start:batch_start + BATCH_SIZE]
                texts = [d["text"] for d in batch]
                translated = translate_texts(texts, source, target, engine, user, user_id)
                for j, t in enumerate(translated):
                    batch[j]["text"] = t
                current = min(batch_start + BATCH_SIZE, total)
                elapsed = time.time() - start_time
                speed = current / elapsed if elapsed > 0 else 1
                remaining = (total - current) / speed if speed > 0 else 0
                yield f"data: {json.dumps({'type': 'progress', 'current': current, 'total': total, 'percent': round(current / total * 100), 'eta': round(remaining)})}\n\n"
            translated = reassemble_ass(header, dialogues)
        else:
            parsed = parse_srt(content)
            total = len(parsed)
            start_time = time.time()
            for batch_start in range(0, total, BATCH_SIZE):
                batch = parsed[batch_start:batch_start + BATCH_SIZE]
                texts = [p["text"] for p in batch]
                translated = translate_texts(texts, source, target, engine, user, user_id)
                for j, t in enumerate(translated):
                    batch[j]["text"] = t
                current = min(batch_start + BATCH_SIZE, total)
                elapsed = time.time() - start_time
                speed = current / elapsed if elapsed > 0 else 1
                remaining = (total - current) / speed if speed > 0 else 0
                yield f"data: {json.dumps({'type': 'progress', 'current': current, 'total': total, 'percent': round(current / total * 100), 'eta': round(remaining)})}\n\n"
            result_lines = []
            for i, p in enumerate(parsed):
                result_lines.append(str(i + 1))
                result_lines.append(p["time"])
                result_lines.append(p["text"])
                result_lines.append("")
            translated = "\n".join(result_lines)

        out_name = f"{file_id}_translated{file_path.suffix}"
        out_path = OUTPUT_DIR / out_name
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(translated)
        yield f"data: {json.dumps({'type': 'complete', 'file_id': file_id, 'filename': out_name, 'download': f'/download/{out_name}'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if file_path.exists():
        return FileResponse(file_path, filename=f"translated_{filename.replace('_translated', '')}", media_type="text/plain")
    return HTMLResponse(status_code=404)


@app.get("/health")
async def health():
    return {"ok": True, "time": time.time()}


@app.get("/ping")
async def ping():
    return "pong"
