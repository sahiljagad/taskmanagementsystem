from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict


class NotificationService:    
    def __init__(self):
        # Store activities (list of events)
        self.global_activity: List[Dict[str, Any]] = []
        self.user_activities: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        
        # Store notifications per user
        self.notifications: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        self.unread_counts: Dict[int, int] = defaultdict(int)
        
        # WebSocket connections
        self.websocket_connections: Dict[int, List[Any]] = defaultdict(list)
        
        # Max items to keep in memory
        self.max_activities = 100
        self.max_notifications = 50
    
    def add_activity(self, event: Dict[str, Any]):
        # Add to global feed
        self.global_activity.insert(0, event)
        if len(self.global_activity) > self.max_activities:
            self.global_activity = self.global_activity[:self.max_activities]
        
        # Add to user-specific feeds if user
        user_id = event.get('user_id')
        if user_id:
            self.user_activities[user_id].insert(0, event)
            if len(self.user_activities[user_id]) > self.max_activities:
                self.user_activities[user_id] = self.user_activities[user_id][:self.max_activities]
        
        # Add to assignee feed assignee
        if event.get('data', {}).get('assignee_id'):
            assignee_id = event['data']['assignee_id']
            self.user_activities[assignee_id].insert(0, event)
            if len(self.user_activities[assignee_id]) > self.max_activities:
                self.user_activities[assignee_id] = self.user_activities[assignee_id][:self.max_activities]
    
    def create_notification(self, user_id: int, event: Dict[str, Any]):
        notification = {
            'id': f"{event['timestamp']}:{event['event_type']}:{user_id}",
            'type': event['event_type'],
            'message': self._generate_notification_message(event),
            'timestamp': event['timestamp'],
            'read': False,
            'data': event['data']
        }
        
        self.notifications[user_id].insert(0, notification)
        if len(self.notifications[user_id]) > self.max_notifications:
            self.notifications[user_id] = self.notifications[user_id][:self.max_notifications]
        
        # Increment unread counter
        self.unread_counts[user_id] += 1
    
    def _generate_notification_message(self, event: Dict[str, Any]) -> str:
        event_type = event['event_type']
        data = event.get('data', {})
        
        messages = {
            'TASK_CREATED': f"New task created: {data.get('title', 'Untitled')}",
            'TASK_ASSIGNED': "You have been assigned to a task",
            'TASK_STATUS_CHANGED': f"Task status changed to {data.get('new_status', 'unknown')}",
            'COMMENT_ADDED': "New comment on a task you're following",
            'USER_MENTIONED': "You were mentioned in a comment",
            'TIME_LOGGED': f"{data.get('hours', 0)} hours logged on a task"
        }
        
        return messages.get(event_type, f"Task update: {event_type}")
    
    def get_activity_feed(self, user_id: Optional[int] = None, limit: int = 20) -> List[Dict[str, Any]]:
        if user_id:
            activities = self.user_activities.get(user_id, [])
        else:
            activities = self.global_activity
        
        return activities[:limit]
    
    def get_notifications(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        return self.notifications.get(user_id, [])[:limit]
    
    def get_unread_count(self, user_id: int) -> int:
        return self.unread_counts.get(user_id, 0)
    
    def mark_notifications_read(self, user_id: int):
        for notification in self.notifications.get(user_id, []):
            notification['read'] = True
        self.unread_counts[user_id] = 0
    
    def mark_notification_read(self, user_id: int, notification_id: str):
        for notification in self.notifications.get(user_id, []):
            if notification['id'] == notification_id and not notification['read']:
                notification['read'] = True
                self.unread_counts[user_id] = max(0, self.unread_counts[user_id] - 1)
                break
    
    def register_websocket(self, user_id: int, websocket):
        self.websocket_connections[user_id].append(websocket)
    
    def unregister_websocket(self, user_id: int, websocket):
        if user_id in self.websocket_connections:
            if websocket in self.websocket_connections[user_id]:
                self.websocket_connections[user_id].remove(websocket)
            if not self.websocket_connections[user_id]:
                del self.websocket_connections[user_id]
    
    async def broadcast_to_user(self, user_id: int, message: Dict[str, Any]):
        if user_id not in self.websocket_connections:
            return
        
        dead_connections = []
        for ws in self.websocket_connections[user_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)
        
        # Clean up dead connections
        for ws in dead_connections:
            self.unregister_websocket(user_id, ws)
    
    def process_event(self, event: Dict[str, Any]):
        event_type = event['event_type']
        data = event.get('data', {})
        
        # Add to activity feed
        self.add_activity(event)
        
        # Create notifications based on event type
        if event_type == 'TASK_ASSIGNED' and 'assignee_id' in data:
            self.create_notification(data['assignee_id'], event)
        
        elif event_type == 'USER_MENTIONED' and 'mentioned_user_id' in data:
            self.create_notification(data['mentioned_user_id'], event)
        
        elif event_type in ['TASK_STATUS_CHANGED', 'COMMENT_ADDED']:
            # notify task assignee/creator here
            pass

# Singleton instance
_notification_service: Optional[NotificationService] = None

def get_notification_service() -> NotificationService:
    #inject service into kafka consumers
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service