"""Probe the local WSGI port with the configured public Host; print no secrets."""
import os
import sys
import urllib.request


def main():
    host = os.environ.get('JOBCOMPASS_ALLOWED_HOSTS', '').split(',')[0].strip()
    if not host:
        return 1
    request = urllib.request.Request('http://127.0.0.1:8765/api/health', headers={'Host': host})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return 0 if response.status == 200 else 1
    except Exception:
        return 1


if __name__ == '__main__':
    sys.exit(main())
