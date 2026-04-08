import requests, json

resp = requests.get("https://gamma-api.polymarket.com/markets", params={
    "closed": "false", "limit": 10, "order": "volume24hr", "ascending": "false"
})
markets = resp.json()

for m in markets[:10]:
    question = m.get("question", "")[:70]
    condition_id = m.get("conditionId")
    
    # Get order book via CLOB
    resp2 = requests.get("https://clob.polymarket.com/markets", params={"conditionID": condition_id})
    data = resp2.json()
    
    if data:
        token_id = data[0].get("token_id", "")
        print(f"Market: {question}")
        print(f"  ConditionID: {condition_id}")
        print(f"  TokenID: {token_id[:50]}...")
        print(f"  neg_risk: {data[0].get('neg_risk')}")
        print()