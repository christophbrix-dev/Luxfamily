"""One-off script: generate the Wat Elo? app icon via Gemini Nano Banana.

Saves 1024x1024 PNG to:
- /app/frontend/assets/images/icon.png            (iOS + universal)
- /app/frontend/assets/images/adaptive-icon.png   (Android adaptive)
- /app/frontend/assets/images/favicon.png         (web favicon, same asset)

Idempotent: overwrites the existing files. Runs once, not from the server.
"""
from __future__ import annotations
import asyncio
import base64
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402

BRIEF = (
    "Design a modern, playful mobile app icon for a Luxembourg discovery app called "
    "'Wat Elo?' (Luxembourgish for 'What now?'). Style: clean, minimal, flat vector, "
    "rounded square iOS-style icon with subtle gradient. Central motif: a friendly "
    "location pin combined with a subtle question mark and a small Luxembourg-red "
    "accent dot. Primary color emerald green (#059669) with off-white background. "
    "No text, no logotype, no letters. The pin should feel inviting and universal — "
    "suitable for families AND young adults. Symmetrical composition, works at 40x40 "
    "up to 1024x1024. Do not add any text characters. Output a single icon on solid "
    "background, no shadow around it, edge-to-edge composition inside a rounded "
    "square 1024x1024 canvas."
)

OUT_DIR = Path("/app/frontend/assets/images")
TARGETS = ["icon.png", "adaptive-icon.png", "favicon.png"]


async def main() -> None:
    api_key = os.environ["EMERGENT_LLM_KEY"]
    chat = (
        LlmChat(
            api_key=api_key,
            session_id="wat-elo-icon-gen",
            system_message="You are an expert mobile app icon designer.",
        )
        .with_model("gemini", "gemini-3.1-flash-image-preview")
        .with_params(modalities=["image", "text"])
    )

    text, images = await chat.send_message_multimodal_response(UserMessage(text=BRIEF))
    print(f"Model reply (truncated): {str(text)[:120]}")
    if not images:
        raise RuntimeError("Nano Banana returned no image data — cannot save icon.")

    img = images[0]
    print(f"Received image, mime={img['mime_type']}")
    data = base64.b64decode(img["data"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in TARGETS:
        (OUT_DIR / name).write_bytes(data)
        print(f"  wrote {OUT_DIR / name} ({len(data)} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
