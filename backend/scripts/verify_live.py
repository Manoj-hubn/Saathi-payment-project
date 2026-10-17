import httpx
import re

frontend_url = "https://saathi-payment-project-qulg.vercel.app"
backend_url = "https://saathi-payment-project-2.onrender.com"

print(f"Testing Frontend: {frontend_url}")
res_fe = httpx.get(frontend_url)
print(f"Frontend Status: {res_fe.status_code}")

# Find JavaScript asset
matches = re.findall(r'src="([^"]+\.js)"', res_fe.text)
print(f"Found JS files: {matches}")
if matches:
    js_url = frontend_url + "/" + matches[0].lstrip("/")
    res_js = httpx.get(js_url)
    print(f"JS file status: {res_js.status_code}")
    has_render = "saathi-payment-project-2.onrender.com" in res_js.text or "onrender.com" in res_js.text
    print(f"VITE_API_URL configured properly in bundle: {has_render}")

print("\nTesting Backend: " + backend_url)
res_health = httpx.get(f"{backend_url}/api/health")
print(f"Health Status: {res_health.status_code} -> {res_health.json()}")

res_users = httpx.get(f"{backend_url}/api/demo-users")
print(f"Demo Users Status: {res_users.status_code} -> {res_users.json()}")

res_login = httpx.post(f"{backend_url}/api/login", json={"username": "customer1", "pin": "1234"})
print(f"Customer Login: {res_login.status_code} -> {res_login.json().get('user_id')}")

token = res_login.json().get("token")
user_id = res_login.json().get("user_id")

res_acct = httpx.get(f"{backend_url}/api/account/{user_id}", headers={"Authorization": f"Bearer {token}"})
print(f"Customer Account: {res_acct.status_code} -> Balance: Rs. {res_acct.json().get('balance_rupees')}")

res_payees = httpx.get(f"{backend_url}/api/payees/{user_id}", headers={"Authorization": f"Bearer {token}"})
print(f"Customer Payees: {res_payees.status_code} -> Count: {len(res_payees.json())}")

# Test payment turn
turn_payload = {
    "user_id": user_id,
    "transcript": "Send paanch sau to Priya",
    "confidence": 0.95,
    "session_id": "test-session-123"
}
res_turn = httpx.post(f"{backend_url}/api/turn", json=turn_payload, headers={"Authorization": f"Bearer {token}"})
print(f"Voice Turn Process: {res_turn.status_code} -> {res_turn.json().get('action')}, Amount: Rs. {res_turn.json().get('amount_rupees')}")
