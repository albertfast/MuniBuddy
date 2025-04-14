from fastapi import APIRouter, Request, HTTPException
import subprocess
import hmac
import hashlib
import os

router = APIRouter()

GITHUB_SECRET = settings.GITHUB_SECRET

@router.post("/")
async def deploy(request: Request):
    """Webhook listener to auto-deploy when main branch is updated"""
    body = await request.body()
    signature = request.headers.get('X-Hub-Signature-256')

    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    sha_name, signature_hash = signature.split('=')
    mac = hmac.new(GITHUB_SECRET.encode(), msg=body, digestmod=hashlib.sha256)

    if not hmac.compare_digest(mac.hexdigest(), signature_hash):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        # Pull the latest code
        output = subprocess.check_output(["git", "pull"], cwd="/app")  # adjust path if needed

        # Rebuild and restart the container
        subprocess.check_output(["docker-compose", "up", "--build", "-d"], cwd="/app")

        return {
            "message": "✅ Deployment successful!",
            "details": output.decode()
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"🚨 Deployment failed: {e.output.decode()}")
