from fastapi import APIRouter, Request, HTTPException
import subprocess
import hmac, hashlib
from app.config import settings
from datetime import datetime

router = APIRouter()

@router.post("/")  # this matches /api/v1/deploy when prefix is set in main.py
async def deploy(request: Request):
    body = await request.body()
    print(f"[🚀 DEPLOY] Webhook triggered at {datetime.now()}")
    signature = request.headers.get('X-Hub-Signature-256')

    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    try:
        sha_name, signature_hash = signature.split('=')
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed signature")

    if sha_name != "sha256":
        raise HTTPException(status_code=400, detail="Unsupported signature method")

    mac = hmac.new(settings.GITHUB_SECRET.encode(), msg=body, digestmod=hashlib.sha256)
    if not hmac.compare_digest(mac.hexdigest(), signature_hash):
        raise HTTPException(status_code=403, detail="Invalid signature")
    print("✅ Signature (local):", mac.hexdigest())
    print("✅ Signature (from GitHub):", signature_hash)

    print("✅ Computed HMAC:", mac.hexdigest())
    print("✅ GitHub HMAC:", signature_hash)
    print("✅ Equal?", hmac.compare_digest(mac.hexdigest(), signature_hash))

    try:
        output = subprocess.check_output(["git", "pull"], cwd="/app")
        subprocess.check_output(["docker-compose", "up", "--build", "-d"], cwd="/app")
        return {
            "message": "✅ Deployment successful",
            "details": output.decode()
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"🚨 Deployment failed: {e.output.decode()}")
