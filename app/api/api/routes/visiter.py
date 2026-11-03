import os
import httpx

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["visitor"])


@router.post("/visitor")
async def visitor_alert():

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise HTTPException(
            status_code=500,
            detail="Telegram credentials are not configured"
        )

    message = (
        "Nigga Someone opened the website!"
    )

    telegram_url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                telegram_url,
                json={
                    "chat_id": chat_id,
                    "text": message
                }
            )

        response.raise_for_status()

    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="Failed to send Telegram notification"
        )

    return {"success": True}