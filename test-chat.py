#!/usr/bin/env python3
"""Test script for chat endpoints."""
import httpx

BASE_URL = "http://localhost:8000"


def test_visitor_chat():
    """Test visitor chat (no auth)."""
    print("\n=== Testing Visitor Chat (no auth) ===")
    url = f"{BASE_URL}/api/v1/chat/visitor"
    payload = {
        "message": "Bonjour, quel est le droit du travail malgache ?",
        "language": "fr"
    }
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            print(f"✅ Success! Status code: {response.status_code}")
            print("Response:")
            print(data)
            if data["success"]:
                print("🤖 Assistant's answer:")
                print(data["data"]["answer"])
            return data
    except Exception as e:
        print(f"❌ Error: {type(e).__name__} - {e}")
        import traceback
        print(traceback.format_exc())
        return None


def test_auth_chat():
    """Test authenticated chat flow."""
    print("\n=== Testing Authenticated Chat ===")
    
    # First, register and login
    print("\n1. Registering user...")
    register_url = f"{BASE_URL}/api/v1/auth/register"
    register_payload = {
        "email": "test-chat2@example.mg",
        "password": "TestChat123!",
        "full_name": "Test Chat User"
    }
    
    with httpx.Client(timeout=30.0) as client:
        try:
            client.post(register_url, json=register_payload)
        except Exception:
            pass
        
        print("\n2. Logging in...")
        login_url = f"{BASE_URL}/api/v1/auth/login"
        login_payload = {
            "email": "test-chat2@example.mg",
            "password": "TestChat123!"
        }
        login_response = client.post(login_url, json=login_payload)
        login_response.raise_for_status()
        login_data = login_response.json()
        access_token = login_data["data"]["access_token"]
        print(f"✅ Got access token")
        
        # Create conversation
        print("\n3. Creating conversation...")
        conv_url = f"{BASE_URL}/api/v1/chat/conversations"
        conv_payload = {"title": "Test Droit du Travail"}
        conv_response = client.post(
            conv_url,
            headers={"Authorization": f"Bearer {access_token}"},
            json=conv_payload
        )
        conv_response.raise_for_status()
        conv_data = conv_response.json()
        conv_id = conv_data["data"]["id"]
        print(f"✅ Created conversation: ID {conv_id}")
        
        # Send message
        print("\n4. Sending message...")
        msg_url = f"{BASE_URL}/api/v1/chat/conversations/{conv_id}/messages"
        msg_payload = {
            "message": "Quelles sont les heures de travail légales ?"
        }
        msg_response = client.post(
            msg_url,
            headers={"Authorization": f"Bearer {access_token}"},
            json=msg_payload
        )
        msg_response.raise_for_status()
        msg_data = msg_response.json()
        print(f"✅ Message sent!")
        print("🤖 Assistant's answer:")
        print(msg_data["data"]["assistant_message"]["content"])
        
        # Get conversation
        print("\n5. Getting conversation details...")
        get_conv_url = f"{BASE_URL}/api/v1/chat/conversations/{conv_id}"
        get_conv_response = client.get(
            get_conv_url,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        get_conv_response.raise_for_status()
        get_conv_data = get_conv_response.json()
        print(f"✅ Got conversation, {len(get_conv_data['data']['messages'])} messages")
        
        # List conversations
        print("\n6. Listing all conversations...")
        list_conv_url = f"{BASE_URL}/api/v1/chat/conversations"
        list_conv_response = client.get(
            list_conv_url,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        list_conv_response.raise_for_status()
        list_conv_data = list_conv_response.json()
        print(f"✅ Got {len(list_conv_data['data']['items'])} conversations")


if __name__ == "__main__":
    test_visitor_chat()
    test_auth_chat()
    print("\n🎉 All chat tests completed!")
