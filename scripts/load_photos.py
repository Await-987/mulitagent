import asyncio
import json
from pathlib import Path

from PIL import Image
from camel.agents import ChatAgent
from camel.messages import BaseMessage
from loguru import logger

from agents.backend_model import backend_model_image

BASE_DIR = Path(__file__).resolve().parent.parent
PHOTOS_DIR = BASE_DIR / "mock_data" / "photos"
DATA_FILE = PHOTOS_DIR / "photos_data.json"

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif"}

VISION_SYSTEM_MSG = BaseMessage.make_assistant_message(
    role_name="Senior Computer Vision Analyst",
    content=(
        "You are an image analysis expert. "
        "Provide a detailed description of the image, "
        "including any visible objects, scenes, and text if present."
    ),
)


def load_existing_data() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to load photos_data.json. Starting fresh.")
        return []


def save_data(data: list[dict]) -> None:
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def scan_local_images() -> set[str]:
    return {
        str(p.resolve())
        for p in PHOTOS_DIR.iterdir()
        if p.suffix.lower() in VALID_EXTENSIONS
    }


async def _analyze_one(img_path: str, idx: int, total: int) -> dict | None:
    try:
        loop = asyncio.get_event_loop()
        image = await loop.run_in_executor(None, Image.open, img_path)

        user_msg = BaseMessage.make_user_message(
            role_name="User",
            content=f"This image is about {Path(img_path).stem}. Please use Chinese to describe the contents of this image.",
            image_list=[image],
        )
        agent = ChatAgent(system_message=VISION_SYSTEM_MSG, model=backend_model_image())
        response = await agent.astep(user_msg)
        del agent

        print(f"[{idx}/{total}] Completed: {Path(img_path).name}")
        return {
            "title": img_path,
            "content": {
                "data": response.msgs[0].content,
                "metadata": Path(img_path).stem,
            },
        }
    except Exception as e:
        print(f"[{idx}/{total}] Failed:    {Path(img_path).name} — {e}")
        return None


async def async_main():
    existing_data = load_existing_data()

    recorded_paths = {
        str(Path(entry["title"]).resolve())
        for entry in existing_data
        if isinstance(entry, dict) and "title" in entry
    }

    local_images = scan_local_images()
    missing = local_images - recorded_paths
    stale   = recorded_paths - local_images

    if not missing and not stale:
        logger.info("Photos app is up to date. Nothing to do.")
        return

    if stale:
        logger.info(f"Removing {len(stale)} stale record(s) (file no longer exists):")
        for p in sorted(stale):
            print(f"  - {p}")
        existing_data = [
            e for e in existing_data
            if str(Path(e["title"]).resolve()) not in stale
        ]

    if missing:
        sorted_missing = sorted(missing)
        total = len(sorted_missing)
        logger.info(f"Found {total} new image(s) to analyze (all running concurrently):")
        for p in sorted_missing:
            print(f"  + {p}")

        tasks = [
            _analyze_one(img_path, idx, total)
            for idx, img_path in enumerate(sorted_missing, start=1)
        ]
        results = await asyncio.gather(*tasks)

        new_entries = [r for r in results if r is not None]
        existing_data.extend(new_entries)
        logger.info(f"Successfully analyzed {len(new_entries)}/{total} image(s).")

    save_data(existing_data)
    logger.info(f"photos_data.json updated ({len(existing_data)} records total).")


if __name__ == "__main__":
    asyncio.run(async_main())
