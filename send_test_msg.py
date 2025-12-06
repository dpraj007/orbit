#!/usr/bin/env python3
"""Send a test message to the Orbit agent."""
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.kafka import build_producer, send_event
import os

def load_env_manual(env_path='.env'):
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

def send_agent_message():
    """Send a message that matches the agent's expected schema."""
    print("🚀 Sending test message to Orbit Agent...")
    
    cfg = Config.from_env()
    env = load_env_manual()
    receiver_number = env.get('RECEIVER_NUMBER', '+19298776648')
    # Use the chat_id found from test_api.py
    chat_id = 1701723
    
    producer = build_producer(cfg)
    
    # Message matching src/kafka/schemas.py structure
    message = {
        "event_type": "message",
        "data": {
            "text": "Hello Orbit! Are you working?",
            "from_phone": receiver_number,
            "chat_id": chat_id,
            "chat_handles": [
                {"phone_number": receiver_number, "display_name": "Test User"},
                {"phone_number": cfg.series_sender_number, "display_name": "Orbit"}
            ]
        },
        "timestamp": str(time.time())
    }
    
    print(f"Topic: {cfg.kafka_topic}")
    print(f"Payload: {message}")
    
    success = send_event(producer, cfg.kafka_topic, message)
    producer.flush()
    
    if success:
        print("✅ Message sent!")
    else:
        print("❌ Failed to send message")

if __name__ == "__main__":
    send_agent_message()
