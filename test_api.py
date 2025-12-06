import os
import json
import urllib.request
import urllib.error
import urllib.parse

def load_env(env_path='.env'):
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars

env = load_env()
BASE_URL = env.get('SERIES_BASE_URL', '').rstrip('/')
API_KEY = env.get('SERIES_API_KEY', '')
SENDER_NUMBER = env.get('SERIES_SENDER_NUMBER', '')
RECEIVER_NUMBER = env.get('RECEIVER_NUMBER', '')

print(f"Testing with:")
print(f"Base URL: {BASE_URL}")
print(f"Sender: {SENDER_NUMBER}")
print(f"Receiver: {RECEIVER_NUMBER}")
print("-" * 20)

def make_request(endpoint, method='GET', data=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {
        'Authorization': f"Bearer {API_KEY}",
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    req_data = None
    if data:
        req_data = json.dumps(data).encode('utf-8')
    
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            status = response.status
            body = response.read().decode('utf-8')
            try:
                json_body = json.loads(body)
                print(f"Success ({status}) for {endpoint}:")
                print(json.dumps(json_body, indent=2))
            except json.JSONDecodeError:
                print(f"Success ({status}) for {endpoint}:")
                print(body)
            return True
    except urllib.error.HTTPError as e:
        print(f"Error ({e.code}) for {endpoint}:")
        print(e.read().decode('utf-8'))
        return False
    except urllib.error.URLError as e:
        print(f"Connection Error for {endpoint}: {e.reason}")
        return False

# 1. Check iMessage Availability
print("\n--- Checking iMessage Availability ---")
check_payload = {
    "phone_number": RECEIVER_NUMBER
}
make_request('/api/i_message_availability/check', method='POST', data=check_payload)

# 2. Send a Message (Create Chat)
print("\n--- Sending Test Message ---")
message_payload = {
    "chat": {
        "phone_numbers": [RECEIVER_NUMBER]
    },
    "message": {
        "text": "Hello! This is a test message from the Orbit Agent."
    },
    "send_from": SENDER_NUMBER
}

def make_request_and_get_id(endpoint, method='GET', data=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {
        'Authorization': f"Bearer {API_KEY}",
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    req_data = None
    if data:
        req_data = json.dumps(data).encode('utf-8')
    
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            status = response.status
            body = response.read().decode('utf-8')
            try:
                json_body = json.loads(body)
                print(f"Success ({status}) for {endpoint}")
                # Try to extract chat_id
                chat_id = None
                if 'data' in json_body:
                    if 'id' in json_body['data']:
                         # This might be chat id or message id depending on endpoint
                         # For POST /api/chats, it returns CreateChatResponse
                         # Let's inspect the response structure
                         pass
                    if 'chat_handles' in json_body['data']:
                        # This looks like /api/chats response
                        chat_id = json_body['data'].get('id')
                
                if chat_id:
                    print(f"FOUND_CHAT_ID:{chat_id}")
                else:
                    print("Could not extract chat_id from response")
                    
                # print(json.dumps(json_body, indent=2))
                return chat_id
            except json.JSONDecodeError:
                print(f"Success ({status}) for {endpoint}:")
                print(body)
            return None
    except urllib.error.HTTPError as e:
        print(f"Error ({e.code}) for {endpoint}:")
        print(e.read().decode('utf-8'))
        return None
    except urllib.error.URLError as e:
        print(f"Connection Error for {endpoint}: {e.reason}")
        return None

chat_id = make_request_and_get_id('/api/chats', method='POST', data=message_payload)
if chat_id:
    print(f"FOUND_CHAT_ID:{chat_id}")
    
    # Test sending to existing chat
    print("\n--- Sending to Existing Chat ---")
    send_payload = {
        "message": {
            "text": "Follow up message from test script"
        }
    }
    # Note: Client.py does not include send_from in this payload. Let's see if it works.
    
    make_request_and_get_id(f'/api/chats/{chat_id}/chat_messages', method='POST', data=send_payload)


