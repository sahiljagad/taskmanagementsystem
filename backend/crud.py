from sqlalchemy.orm import Session
from typing import List, Optional
import hashlib
from models import User, Project, Task, Comment, TimeLog, TaskStatus
from schemas import UserCreate, ProjectCreate, TaskCreate, TaskUpdate, CommentCreate, TimeLogCreate

# Helper function for password hashing
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password

# User CRUD
def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()

def create_user(db: Session, user: UserCreate) -> User:
    hashed_password = hash_password(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Project CRUD
def get_project(db: Session, project_id: int) -> Optional[Project]:
    return db.query(Project).filter(Project.id == project_id).first()

def get_projects(db: Session, owner_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[Project]:
    query = db.query(Project)
    if owner_id:
        query = query.filter(Project.owner_id == owner_id)
    return query.offset(skip).limit(limit).all()

def create_project(db: Session, project: ProjectCreate, owner_id: int) -> Project:
    db_project = Project(
        name=project.name,
        description=project.description,
        owner_id=owner_id
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

def update_project(db: Session, project_id: int, name: Optional[str] = None, description: Optional[str] = None) -> Optional[Project]:
    db_project = get_project(db, project_id)
    if not db_project:
        return None
    
    if name is not None:
        db_project.name = name
    if description is not None:
        db_project.description = description
    
    db.commit()
    db.refresh(db_project)
    return db_project

def delete_project(db: Session, project_id: int) -> bool:
    db_project = get_project(db, project_id)
    if not db_project:
        return False
    
    db.delete(db_project)
    db.commit()
    return True

# Task CRUD
def get_task(db: Session, task_id: int) -> Optional[Task]:
    return db.query(Task).filter(Task.id == task_id).first()

def get_tasks(
    db: Session, 
    project_id: Optional[int] = None, 
    assignee_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0, 
    limit: int = 100
) -> List[Task]:
    query = db.query(Task)
    
    if project_id:
        query = query.filter(Task.project_id == project_id)
    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)
    if status:
        try:
            task_status = TaskStatus[status.upper()]
            query = query.filter(Task.status == task_status)
        except KeyError:
            pass  # Invalid status, ignore filter
    
    return query.offset(skip).limit(limit).all()

def create_task(db: Session, task: TaskCreate, creator_id: int) -> Task:
    db_task = Task(
        title=task.title,
        description=task.description,
        project_id=task.project_id,
        assignee_id=task.assignee_id,
        created_by=creator_id,
        priority=task.priority,
        due_date=task.due_date
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def update_task(db: Session, task_id: int, task_update: TaskUpdate) -> Optional[Task]:
    db_task = get_task(db, task_id)
    if not db_task:
        return None
    
    if task_update.title is not None:
        db_task.title = task_update.title
    if task_update.description is not None:
        db_task.description = task_update.description
    if task_update.status is not None:
        try:
            db_task.status = TaskStatus[task_update.status.upper()]
        except KeyError:
            pass  # Invalid status, ignore
    if task_update.assignee_id is not None:
        db_task.assignee_id = task_update.assignee_id
    if task_update.priority is not None:
        db_task.priority = task_update.priority
    if task_update.due_date is not None:
        db_task.due_date = task_update.due_date
    
    db.commit()
    db.refresh(db_task)
    return db_task

def delete_task(db: Session, task_id: int) -> bool:
    db_task = get_task(db, task_id)
    if not db_task:
        return False
    
    db.delete(db_task)
    db.commit()
    return True

# Comment CRUD
def get_comment(db: Session, comment_id: int) -> Optional[Comment]:
    return db.query(Comment).filter(Comment.id == comment_id).first()

def get_comments(db: Session, task_id: int, skip: int = 0, limit: int = 100) -> List[Comment]:
    return db.query(Comment).filter(Comment.task_id == task_id).order_by(Comment.created_at.desc()).offset(skip).limit(limit).all()

def create_comment(db: Session, comment: CommentCreate, author_id: int) -> Comment:
    db_comment = Comment(
        content=comment.content,
        task_id=comment.task_id,
        author_id=author_id
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment

# TimeLog CRUD
def get_time_logs(db: Session, task_id: Optional[int] = None, user_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[TimeLog]:
    query = db.query(TimeLog)
    
    if task_id:
        query = query.filter(TimeLog.task_id == task_id)
    if user_id:
        query = query.filter(TimeLog.user_id == user_id)
    
    return query.order_by(TimeLog.logged_at.desc()).offset(skip).limit(limit).all()

def create_time_log(db: Session, time_log: TimeLogCreate, user_id: int) -> TimeLog:
    db_time_log = TimeLog(
        task_id=time_log.task_id,
        user_id=user_id,
        hours=time_log.hours,
        description=time_log.description
    )
    db.add(db_time_log)
    db.commit()
    db.refresh(db_time_log)
    return db_time_log