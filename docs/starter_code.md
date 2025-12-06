# Python Kafka Producer Example
# Install: pip install kafka-python

from kafka import KafkaProducer
import json

# Kafka Configuration
bootstrap_servers = ''
topic_name = ''
api_key = ''
api_secret = ''

# Initialize Producer
producer = KafkaProducer(
    bootstrap_servers=bootstrap_servers.split(','),
    security_protocol='SASL_SSL',
    sasl_mechanism='PLAIN',
    sasl_plain_username=api_key,
    sasl_plain_password=api_secret,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Send a message
message = {
    'event': 'test_message',
    'data': {
        'message': 'Hello from Orbit!',
        'timestamp': '2024-01-01T00:00:00Z'
    }
}

try:
    future = producer.send(topic_name, value=message)
    record_metadata = future.get(timeout=10)
    print(f"Message sent successfully!")
    print(f"Topic: {record_metadata.topic}")
    print(f"Partition: {record_metadata.partition}")
    print(f"Offset: {record_metadata.offset}")
except Exception as e:
    print(f"Error sending message: {e}")
finally:
    producer.close()



# Python Kafka Consumer Example
# Install: pip install kafka-python

from kafka import KafkaConsumer
import json

# Kafka Configuration
bootstrap_servers = ''
topic_name = ''
api_key = ''
api_secret = ''

# Initialize Consumer
consumer = KafkaConsumer(
    topic_name,
    bootstrap_servers=bootstrap_servers.split(','),
    security_protocol='SASL_SSL',
    sasl_mechanism='PLAIN',
    sasl_plain_username=api_key,
    sasl_plain_password=api_secret,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='team-cg-b75820cf492645e28fbe38fc7857e8d5'
)

print(f"Listening to topic: {topic_name}")
print("Waiting for messages... (Press Ctrl+C to stop)")

try:
    for message in consumer:
        print(f"\nReceived message:")
        print(f"Topic: {message.topic}")
        print(f"Partition: {message.partition}")
        print(f"Offset: {message.offset}")
        print(f"Value: {message.value}")
except KeyboardInterrupt:
    print("\nStopping consumer...")
finally:
    consumer.close()
