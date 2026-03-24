import json
import os

import requests
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    api_url = os.getenv("RECONCILIATION_API_URL", "http://financial.exactflow.ngrok.dev/api/Transaction")
    api_key = os.getenv("x_api_key")

    headers = {"x-api-key": api_key} if api_key else {}
    response = requests.get(api_url, params={"page": 1, "size": 10}, headers=headers, timeout=30)

    print("Status:", response.status_code)
    print("Content-Type:", response.headers.get("Content-Type"))

    try:
        data = response.json()
    except json.JSONDecodeError:
        print("Non-JSON response (first 500 chars):")
        print(response.text[:500])
        return

    if isinstance(data, dict):
        print("Top-level keys:", list(data.keys()))
    elif isinstance(data, list):
        print("List length:", len(data))
        if data:
            print("First item keys:", list(data[0].keys()))
    else:
        print("Unexpected JSON type:", type(data).__name__)


if __name__ == "__main__":
    main()
