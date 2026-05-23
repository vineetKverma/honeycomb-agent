"""Launch the Honeycomb Streamlit app.

Equivalent to: streamlit run app/streamlit_app.py

No extra environment variables are needed -- the app reads GEMINI_API_KEY (and
the Mongo settings) from .env via config.py, the same as the rest of the project.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app" / "streamlit_app.py"


def main() -> int:
    return subprocess.call(
        [sys.executable, "-m", "streamlit", "run", str(APP)], cwd=str(ROOT)
    )


if __name__ == "__main__":
    raise SystemExit(main())
