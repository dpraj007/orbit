#!/usr/bin/env python3
"""Test script to check if Kafka is running and accessible."""
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.kafka import build_producer, build_consumer, send_event

def test_kafka_connection():
    """Test if Kafka is accessible."""
    print("🔍 Testing Kafka connection...")
    print("-" * 60)
    
    try:
        # Load configuration
        cfg = Config.from_env()
        
        print(f"✓ Configuration loaded")
        print(f"  Bootstrap Servers: {cfg.kafka_bootstrap}")
        print(f"  Topic: {cfg.kafka_topic}")
        print(f"  Group ID: {cfg.kafka_group}")
        print(f"  Security Protocol: {cfg.kafka_security_protocol}")
        print(f"  SASL Mechanism: {cfg.kafka_sasl_mechanism}")
        print()
        
        # Test 1: Producer
        print("📋 Test 1: Kafka Producer")
        try:
            producer = build_producer(cfg)
            print("  ✓ Producer initialized")
            
            # Send a test message
            test_message = {
                "event_type": "test_ping",
                "data": {
                    "message": "Hello from Orbit Test Script!",
                    "timestamp": time.time()
                }
            }
            
            print(f"  Sending test message to topic '{cfg.kafka_topic}'...")
            success = send_event(producer, cfg.kafka_topic, test_message)
            
            if success:
                print("  ✓ SUCCESS: Message sent successfully")
            else:
                print("  ❌ ERROR: Failed to send message")
                return False
                
        except Exception as e:
            print(f"  ❌ ERROR: Producer failed: {e}")
            return False
        finally:
            if 'producer' in locals():
                producer.flush()
        
        print()
        
        # Test 2: Consumer
        print("📋 Test 2: Kafka Consumer")
        try:
            consumer = build_consumer(cfg)
            print("  ✓ Consumer initialized")
            
            # Check connection by listing topics
            print("  Checking cluster metadata...")
            metadata = consumer.list_topics(timeout=10)
            
            if metadata.topics:
                print(f"  ✓ SUCCESS: Connected to cluster. Found {len(metadata.topics)} topics.")
                if cfg.kafka_topic in metadata.topics:
                    print(f"  ✓ Topic '{cfg.kafka_topic}' exists.")
                else:
                    print(f"  ⚠️  WARNING: Topic '{cfg.kafka_topic}' not found in metadata.")
            else:
                print("  ❌ ERROR: Could not list topics. Connection might be unstable.")
                return False
                
        except Exception as e:
            print(f"  ❌ ERROR: Consumer failed: {e}")
            return False
        finally:
            if 'consumer' in locals():
                consumer.close()
        
        return True
            
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Kafka Connection Test")
    print("=" * 60)
    print()
    
    success = test_kafka_connection()
    
    print()
    print("=" * 60)
    if success:
        print("✅ KAFKA TEST PASSED - Cluster is accessible!")
    else:
        print("❌ KAFKA TEST FAILED - Check configuration and status")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
