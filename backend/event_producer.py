import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from kafka import KafkaProducer

logger = logging.getLogger(__name__)

class EventProducer:
    def __init__(self, bootstrap_servers=['localhost:9092']):

        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
            acks='all',
            retries=3
        )
        
        self.topic = 'task-events'
    
    def send_event(self, event_type: str, data: Dict[str, Any], user_id: int):
        event = {
            'event_type': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'data': data
        }
        
        try:
            future = self.producer.send(self.topic, event)
            if hasattr(future, 'get'):
                future.get(timeout=10)
            logger.info(f"Event sent: {event_type}")
        except Exception as e:
            logger.error(f"Failed to send event: {e}")
    
    def task_created(self, task_data: Dict[str, Any], user_id: int):
        self.send_event('TASK_CREATED', task_data, user_id)
    
    def task_updated(self, task_id: int, changes: Dict[str, Any], user_id: int):
        self.send_event('TASK_UPDATED', {
            'task_id': task_id,
            'changes': changes
        }, user_id)
    
    def task_status_changed(self, task_id: int, old_status: str, new_status: str, user_id: int):
        self.send_event('TASK_STATUS_CHANGED', {
            'task_id': task_id,
            'old_status': old_status,
            'new_status': new_status
        }, user_id)
    
    def task_assigned(self, task_id: int, assignee_id: int, assigner_id: int):
        self.send_event('TASK_ASSIGNED', {
            'task_id': task_id,
            'assignee_id': assignee_id
        }, assigner_id)
    
    def comment_added(self, task_id: int, comment_data: Dict[str, Any], user_id: int):
        self.send_event('COMMENT_ADDED', {
            'task_id': task_id,
            'comment': comment_data
        }, user_id)
    
    def user_mentioned(self, task_id: int, mentioned_user_id: int, comment_id: int, user_id: int):
        self.send_event('USER_MENTIONED', {
            'task_id': task_id,
            'mentioned_user_id': mentioned_user_id,
            'comment_id': comment_id
        }, user_id)
    
    def time_logged(self, task_id: int, hours: int, user_id: int):
        """Time logged event"""
        self.send_event('TIME_LOGGED', {
            'task_id': task_id,
            'hours': hours
        }, user_id)
    
    def close(self):
        self.producer.flush()
        self.producer.close()

# instance for injection in kafka consumer
_producer_instance: Optional[EventProducer] = None

def get_event_producer() -> EventProducer:
    global _producer_instance
    if _producer_instance is None:
        _producer_instance = EventProducer()
    return _producer_instance