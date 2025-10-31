from fastapi import FastAPI, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import re

from database import get_db
from models import TaskStatus
from analytics import AnalyticsService
from event_producer import get_event_producer
from notification_service import get_notification_service
import schemas as schemas
import crud as crud

app = FastAPI(
    title="Task Management API",
    description="A collaborative task management system",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Very insecure, I just dont want to deal with CORS now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple authentication: just pass user_id in header for now
# use proper JWT authentication later
def get_current_user_id(user_id: int = 1) -> int:
    return user_id

# Helper function to extract mentions
def extract_mentions(content: str) -> List[str]:
    return re.findall(r'@(\w+)', content)

# Root endpoint/ root health check
@app.get("/")
def read_root():
    return {
        "message": "Task Management API",
        
    }

# Basic health check, can be improved greatly
@app.get("/health")
def health_check():
    return {"status": "healthy"}

# USER ENDPOINTS

@app.post("/users/", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if username already exists
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check if email already exists
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    return crud.create_user(db=db, user=user)

@app.get("/users/", response_model=List[schemas.UserResponse])
def list_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = crud.get_users(db, skip=skip, limit=limit)
    return users

@app.get("/users/{user_id}", response_model=schemas.UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@app.get("/users/username/{username}", response_model=schemas.UserResponse)
def get_user_by_username(username: str, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=username)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

# PROJECT ENDPOINTS 

@app.post("/projects/", response_model=schemas.ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project: schemas.ProjectCreate, 
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """Create a new project"""
    return crud.create_project(db=db, project=project, owner_id=current_user_id)

@app.get("/projects/", response_model=List[schemas.ProjectResponse])
def list_projects(
    owner_id: Optional[int] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """Get list of projects"""
    projects = crud.get_projects(db, owner_id=owner_id, skip=skip, limit=limit)
    return projects

@app.get("/projects/{project_id}", response_model=schemas.ProjectDetailResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get a specific project with details"""
    db_project = crud.get_project(db, project_id=project_id)
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return db_project

@app.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int, 
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """Delete a project"""
    db_project = crud.get_project(db, project_id=project_id)
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if user is the owner
    if db_project.owner_id != current_user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this project")
    
    crud.delete_project(db, project_id=project_id)
    return None

# ==================== TASK ENDPOINTS ====================

@app.post("/tasks/", response_model=schemas.TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    task: schemas.TaskCreate, 
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    # Verify project exists
    db_project = crud.get_project(db, project_id=task.project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Verify assignee exists if provided
    if task.assignee_id:
        db_assignee = crud.get_user(db, user_id=task.assignee_id)
        if not db_assignee:
            raise HTTPException(status_code=404, detail="Assignee not found")
    
    db_task = crud.create_task(db=db, task=task, creator_id=current_user_id)
    
    # Send events
    producer = get_event_producer()
    event_data = {
        'task_id': db_task.id,
        'title': db_task.title,
        'project_id': db_task.project_id,
        'assignee_id': db_task.assignee_id
    }
    producer.task_created(event_data, current_user_id)
    
    # Process event for notifications
    notif_service = get_notification_service()
    notif_service.process_event({
        'event_type': 'TASK_CREATED',
        'timestamp': datetime.utcnow().isoformat(),
        'user_id': current_user_id,
        'data': event_data
    })
    
    # Notify assignee if assigned
    if task.assignee_id:
        producer.task_assigned(db_task.id, task.assignee_id, current_user_id)
        notif_service.process_event({
            'event_type': 'TASK_ASSIGNED',
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': current_user_id,
            'data': {'task_id': db_task.id, 'assignee_id': task.assignee_id}
        })
    
    return db_task

@app.get("/tasks/", response_model=List[schemas.TaskResponse])
def list_tasks(
    project_id: Optional[int] = None,
    assignee_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0, # Simple pagination
    limit: int = 100,
    db: Session = Depends(get_db)
):
    tasks = crud.get_tasks(
        db, 
        project_id=project_id, 
        assignee_id=assignee_id,
        status=status,
        skip=skip, 
        limit=limit
    )
    return tasks

@app.get("/tasks/{task_id}", response_model=schemas.TaskDetailResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    db_task = crud.get_task(db, task_id=task_id)
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return db_task

@app.put("/tasks/{task_id}", response_model=schemas.TaskResponse)
def update_task(
    task_id: int, 
    task_update: schemas.TaskUpdate, 
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    db_task = crud.get_task(db, task_id=task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Store old values for change tracking
    old_status = db_task.status.value if db_task.status else None
    old_assignee = db_task.assignee_id
    
    # Update task
    db_task = crud.update_task(db, task_id=task_id, task_update=task_update)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Send events
    producer = get_event_producer()
    notif_service = get_notification_service()
    
    # Task updated event
    changes = {}
    if task_update.title: changes['title'] = task_update.title
    if task_update.description: changes['description'] = task_update.description
    if task_update.status: changes['status'] = task_update.status
    if task_update.assignee_id: changes['assignee_id'] = task_update.assignee_id
    
    producer.task_updated(task_id, changes, current_user_id)
    notif_service.process_event({
        'event_type': 'TASK_UPDATED',
        'timestamp': datetime.utcnow().isoformat(),
        'user_id': current_user_id,
        'data': {'task_id': task_id, 'changes': changes}
    })
    
    # Status changed event
    if task_update.status and old_status != task_update.status:
        producer.task_status_changed(task_id, old_status, task_update.status, current_user_id)
        notif_service.process_event({
            'event_type': 'TASK_STATUS_CHANGED',
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': current_user_id,
            'data': {'task_id': task_id, 'old_status': old_status, 'new_status': task_update.status}
        })
    
    # Assignment changed event
    if task_update.assignee_id and old_assignee != task_update.assignee_id:
        producer.task_assigned(task_id, task_update.assignee_id, current_user_id)
        notif_service.process_event({
            'event_type': 'TASK_ASSIGNED',
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': current_user_id,
            'data': {'task_id': task_id, 'assignee_id': task_update.assignee_id}
        })
    
    return db_task

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int, 
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    db_task = crud.get_task(db, task_id=task_id)
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Supposed to add authorization check here for security!
    
    crud.delete_task(db, task_id=task_id)
    return None

#  COMMENT ENDPOINTS 

@app.post("/comments/", response_model=schemas.CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(
    comment: schemas.CommentCreate, 
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    # Verify task exists
    db_task = crud.get_task(db, task_id=comment.task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db_comment = crud.create_comment(db=db, comment=comment, author_id=current_user_id)
    
    # Send events
    producer = get_event_producer()
    notif_service = get_notification_service()
    
    comment_data = {
        'comment_id': db_comment.id,
        'content': db_comment.content,
        'author_id': current_user_id,
        'task_id': comment.task_id
    }
    
    producer.comment_added(comment.task_id, comment_data, current_user_id)
    notif_service.process_event({
        'event_type': 'COMMENT_ADDED',
        'timestamp': datetime.utcnow().isoformat(),
        'user_id': current_user_id,
        'data': comment_data
    })
    
    # Check for mentions
    mentions = extract_mentions(comment.content)
    for username in mentions:
        mentioned_user = crud.get_user_by_username(db, username=username)
        if mentioned_user:
            producer.user_mentioned(comment.task_id, mentioned_user.id, db_comment.id, current_user_id)
            notif_service.process_event({
                'event_type': 'USER_MENTIONED',
                'timestamp': datetime.utcnow().isoformat(),
                'user_id': current_user_id,
                'data': {
                    'task_id': comment.task_id,
                    'mentioned_user_id': mentioned_user.id,
                    'comment_id': db_comment.id
                }
            })
    
    return db_comment

@app.get("/tasks/{task_id}/comments", response_model=List[schemas.CommentResponse])
def list_task_comments(
    task_id: int, 
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    # Verify task exists
    db_task = crud.get_task(db, task_id=task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return crud.get_comments(db, task_id=task_id, skip=skip, limit=limit)

# TIME LOG ENDPOINTS 

@app.post("/time-logs/", response_model=schemas.TimeLogResponse, status_code=status.HTTP_201_CREATED)
def create_time_log(
    time_log: schemas.TimeLogCreate, 
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    # Verify task exists
    db_task = crud.get_task(db, task_id=time_log.task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return crud.create_time_log(db=db, time_log=time_log, user_id=current_user_id)

@app.get("/time-logs/", response_model=List[schemas.TimeLogResponse])
def list_time_logs(
    task_id: Optional[int] = None,
    user_id: Optional[int] = None,
    skip: int = 0, #simple pagination
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    return crud.get_time_logs(db, task_id=task_id, user_id=user_id, skip=skip, limit=limit)

@app.get("/tasks/{task_id}/time-logs", response_model=List[schemas.TimeLogResponse])
def list_task_time_logs(
    task_id: int, 
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    # Verify task exists
    db_task = crud.get_task(db, task_id=task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return crud.get_time_logs(db, task_id=task_id, skip=skip, limit=limit)

# ANALYTICS ENDPOINTS

@app.get("/analytics/completion-rate")
def get_completion_rate(
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    start_date: Optional[datetime] = Query(None, description="Start date for filtering"),
    end_date: Optional[datetime] = Query(None, description="End date for filtering"),
    db: Session = Depends(get_db)
):
    analytics = AnalyticsService(db)
    return analytics.get_task_completion_rate(project_id, start_date, end_date)

@app.get("/analytics/status-distribution")
def get_status_distribution(
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    db: Session = Depends(get_db)
):
    analytics = AnalyticsService(db)
    return analytics.get_task_status_distribution(project_id)

@app.get("/analytics/team-productivity")
def get_team_productivity(
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """Get team productivity metrics"""
    analytics = AnalyticsService(db)
    return analytics.get_team_productivity(project_id, days)

@app.get("/analytics/overdue-tasks")
def get_overdue_tasks(
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    db: Session = Depends(get_db)
):
    """Get list of overdue tasks"""
    analytics = AnalyticsService(db)
    return analytics.get_overdue_tasks(project_id)

@app.get("/analytics/velocity")
def get_task_velocity(
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    weeks: int = Query(4, description="Number of weeks to analyze"),
    db: Session = Depends(get_db)
):
    """Get task completion velocity over time"""
    analytics = AnalyticsService(db)
    return analytics.get_task_velocity(project_id, weeks)

@app.get("/analytics/avg-completion-time")
def get_avg_completion_time(
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    db: Session = Depends(get_db)
):
    """Get average task completion time"""
    analytics = AnalyticsService(db)
    return analytics.get_average_completion_time(project_id)

@app.get("/analytics/time-tracking")
def get_time_tracking_summary(
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """Get time tracking summary"""
    analytics = AnalyticsService(db)
    return analytics.get_time_tracking_summary(project_id, user_id, days)

@app.get("/analytics/project-dashboard/{project_id}")
def get_project_dashboard(project_id: int, db: Session = Depends(get_db)):
    """Get comprehensive project dashboard with all metrics"""
    # Verify project exists
    db_project = crud.get_project(db, project_id=project_id)
    if not db_project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    analytics = AnalyticsService(db)
    return analytics.get_project_dashboard(project_id)

@app.get("/analytics/user-statistics/{user_id}")
def get_user_statistics(
    user_id: int,
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """Get statistics for a specific user"""
    # Verify user exists
    db_user = crud.get_user(db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    analytics = AnalyticsService(db)
    return analytics.get_user_statistics(user_id, days)

# REAL-TIME ENDPOINTS

@app.get("/activity-feed")
def get_activity_feed(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    limit: int = Query(20, description="Number of activities to return")
):
    """Get activity feed"""
    notif_service = get_notification_service()
    return notif_service.get_activity_feed(user_id, limit)

@app.get("/notifications")
def get_notifications(
    limit: int = Query(20, description="Number of notifications to return"),
    current_user_id: int = Depends(get_current_user_id)
):
    notif_service = get_notification_service()
    return {
        'notifications': notif_service.get_notifications(current_user_id, limit),
        'unread_count': notif_service.get_unread_count(current_user_id)
    }

@app.post("/notifications/mark-read")
def mark_notifications_read(
    notification_id: Optional[str] = Query(None, description="Specific notification ID to mark as read"),
    current_user_id: int = Depends(get_current_user_id)
):
    notif_service = get_notification_service()
    
    if notification_id:
        notif_service.mark_notification_read(current_user_id, notification_id)
        return {"message": "Notification marked as read"}
    else:
        notif_service.mark_notifications_read(current_user_id)
        return {"message": "All notifications marked as read"}

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await websocket.accept()
    
    notif_service = get_notification_service()
    notif_service.register_websocket(user_id, websocket)
    
    try:
        # Send welcome message
        await websocket.send_json({
            'type': 'connection',
            'message': f'Connected as user {user_id}',
            'timestamp': datetime.utcnow().isoformat()
        })
        
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            
            if data == "ping":
                await websocket.send_text("pong")
            elif data == "get_notifications":
                notifications = notif_service.get_notifications(user_id)
                await websocket.send_json({
                    'type': 'notifications',
                    'data': notifications
                })
            elif data == "get_activity":
                activities = notif_service.get_activity_feed(user_id)
                await websocket.send_json({
                    'type': 'activity',
                    'data': activities
                })
    
    except WebSocketDisconnect:
        notif_service.unregister_websocket(user_id, websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)