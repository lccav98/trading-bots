import requests

# Search for the specific markets - they may be archived/closed
search_queries = [
    "Will Bitcoin dip to $50,000 in April",
    "Will the price of Bitcoin be above $60,000 on April 7",
]

for q in search_queries:
    print(f"\n=== Searching: {q} ===")
    
    # Try different search approaches
    for try_num in range(3):
        params = {"question_contains": q[:20], "limit": 20}
        if try_num == 1:
            params = {"question_contains": "bitcoin 50000 april", "limit": 20}
        elif try_num == 2:
            params = {"question_contains": "bitcoin 60000 april", "limit": 20}
            
        resp = requests.get(
            "https://clob.polymarket.com/markets",
            params=params,
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            markets = data.get("data", [])
            
            for m in markets:
                q_text = m.get("question", "")
                # Check if it contains bitcoin and either 50 or 60
                if "bitcoin" in q_text.lower() and ("50" in q_text or "60" in q_text):
                    print(f"\nFound: {q_text[:80]}")
                    print(f"  Condition ID: {m.get('conditionId')}")
                    print(f"  Active: {m.get('active')}")
                    print(f"  Closed: {m.get('closed')}")
                    print(f"  Volume: {m.get('volume')}")
                    
                    # If we found it, get more details
                    cond_id = m.get("conditionId")
                    if cond_id:
                        # Try to get order book for this market
                        try:
                            book_resp = requests.get(
                                f"https://clob.polymarket.com/orderbook?conditionId={cond_id}",
                                timeout=10
                            )
                            print(f"  Orderbook status: {book_resp.status_code}")
                        except:
                            pass
                    break