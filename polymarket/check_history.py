#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv

load_dotenv()


def main():
    client_key = os.environ.get("POLYMARKET_PRIVATE_KEY")
    funder = os.environ.get("FUNDER_ADDRESS")

    # Try authenticated endpoints
    headers = {
        "Content-Type": "application/json",
    }

    # Try data/trades with credentials
    print("=== HISTORY ===\n")

    urls = [
        "https://clob.polymarket.com/trades",
        "https://clob.polymarket.com/data/trades?limit=50",
        "https://clob.polymarket.com/v1/trades",
    ]

    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            print(f"{url}")
            print(f"  Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"  Data: {str(data)[:200]}")
                break
        except Exception as e:
            print(f"{url}: {e}")
        print()


if __name__ == "__main__":
    main()
