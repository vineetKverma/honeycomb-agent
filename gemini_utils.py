import time
import random
import sys
from google.genai import errors


def call_with_retry(fn, *args, max_retries=5, base_delay=2.0, **kwargs):
    """
    Wrap a google-genai SDK call with retry logic for transient errors.

    Retries on:
      - ServerError (any 5xx: 500, 502, 503, 504)
      - ClientError if it represents 429 RESOURCE_EXHAUSTED

    Does NOT retry on:
      - Auth errors, invalid arguments, schema errors, etc.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except errors.ServerError as e:
            last_exc = e
            if attempt == max_retries:
                raise
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            print(
                f"  [retry] ServerError on attempt {attempt + 1}/{max_retries + 1}, "
                f"sleeping {delay:.1f}s...",
                file=sys.stderr,
            )
            time.sleep(delay)
        except errors.ClientError as e:
            err_str = str(e).lower()
            is_rate_limit = "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str
            if not is_rate_limit or attempt == max_retries:
                raise
            last_exc = e
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            print(
                f"  [retry] Rate limit on attempt {attempt + 1}/{max_retries + 1}, "
                f"sleeping {delay:.1f}s...",
                file=sys.stderr,
            )
            time.sleep(delay)
    raise last_exc  # safety net, shouldn't reach here
