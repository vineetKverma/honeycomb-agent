# USES 1 quota request. Don't run repeatedly without reason.
"""Isolated validity/quota check for a Gemini API key.

Usage: python scripts/test_api_key.py AIza...

Does NOT read or write .env -- the key comes only from argv. ASCII-only output.
"""
import sys

from google import genai
from google.genai import errors


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("AIza") or len(sys.argv[1]) < 30:
        print("Usage: python scripts/test_api_key.py <AIza...key>")
        return 1

    key = sys.argv[1]
    try:
        # Hold the client in a variable: a throwaway temporary can be GC'd and
        # have its HTTP transport closed before the request completes.
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say hi in 3 words",
        )
        text = (response.text or "").encode("ascii", "replace").decode("ascii")
        print(f"[ok] API key works. Response: {text}")
        return 0
    except errors.ServerError as e:
        # Gemini-side overload (5xx) -- not a key problem.
        print(f"[FAIL] server error (Gemini overloaded, not your key): {e}")
        return 1
    except errors.ClientError as e:
        msg = str(e)
        if e.status_code == 429:
            print("[FAIL] 429 RESOURCE_EXHAUSTED - key has zero/used quota")
        elif e.status_code == 403:
            print(f"[FAIL] 403 PERMISSION_DENIED - billing or project issue: {msg}")
        else:
            print(f"[FAIL] {e.status_code}: {msg}")
        return 1
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
