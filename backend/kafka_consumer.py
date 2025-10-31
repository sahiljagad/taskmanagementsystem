from kafka import KafkaConsumer
import json
import logging
from typing import Dict, Any
from notification_service import get_notification_service
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TaskEventConsumer:
    def __init__(self, bootstrap_servers=['localhost:9092']):
        self.bootstrap_servers = bootstrap_servers
        self.topic = 'task-events'
        self.consumer = None
        self.notification_service = get_notification_service()
    
    def connect(self):
        try:
            self.consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='task-event-processor',
            )
            logger.info(f"Connected to Kafka at {self.bootstrap_servers}")
            logger.info(f"Subscribed to topic: {self.topic}")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            raise
    
    def process_event(self, event: Dict[str, Any]):
        try:
            event_type = event.get('event_type')
            logger.info(f"Processing event: {event_type}")
            
            # Add to notification service
            self.notification_service.process_event(event)
            
            # Broadcast to WebSocket clients if needed
            data = event.get('data', {})
            
            if event_type == 'TASK_ASSIGNED' and 'assignee_id' in data:
                assignee_id = data['assignee_id']
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                loop.create_task(
                    self.notification_service.broadcast_to_user(
                        assignee_id,
                        {'type': 'notification', 'event': event}
                    )
                )
            
            elif event_type == 'USER_MENTIONED' and 'mentioned_user_id' in data:
                mentioned_user_id = data['mentioned_user_id']
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                loop.create_task(
                    self.notification_service.broadcast_to_user(
                        mentioned_user_id,
                        {'type': 'notification', 'event': event}
                    )
                )
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
    
    def consume_events(self):
        if not self.consumer:
            self.connect()
        
        logger.info("Starting to consume events...")
        
        try:
            for message in self.consumer: # type: ignore
                event = message.value
                self.process_event(event)
        except KeyboardInterrupt:
            logger.info("Consumer stopped by user")
        except Exception as e:
            logger.error(f"Error in consumer loop: {e}")
        finally:
            self.close()
    
    def close(self):
        if self.consumer:
            self.consumer.close()
            logger.info("Kafka consumer closed")

def main():
    consumer = TaskEventConsumer()
    
    try:
        consumer.consume_events()
    except KeyboardInterrupt:
        logger.info("Shutting down consumer")
    finally:
        consumer.close()

if __name__ == "__main__":
    main()