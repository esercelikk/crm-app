from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Kaynak Kodları"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from crm_app.veritabani import DatabaseManager


def main() -> int:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        api_key = getpass.getpass("OpenRouter API key: ").strip()

    if not api_key:
        print("API key bos olamaz.")
        return 1

    model = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip() or "openrouter/free"

    db = DatabaseManager()
    try:
        db.set_setting("ai_api_key", api_key)
        db.set_setting("ai_model", model)
    finally:
        db.close()

    print("AI ayarlari kaydedildi.")
    print(f"Model: {model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
