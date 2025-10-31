from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# User Schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

# Project Schemas
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectResponse(ProjectBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Task Schemas
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: int = 1
    due_date: Optional[datetime] = None

class TaskCreate(TaskBase):
    project_id: int
    assignee_id: Optional[int] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None  # "todo", "in_progress", "done"
    assignee_id: Optional[int] = None
    priority: Optional[int] = None
    due_date: Optional[datetime] = None

class TaskResponse(TaskBase):
    id: int
    status: str
    project_id: int
    assignee_id: Optional[int]
    created_by: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Comment Schemas
class CommentBase(BaseModel):
    content: str

class CommentCreate(CommentBase):
    task_id: int

class CommentResponse(CommentBase):
    id: int
    task_id: int
    author_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# TimeLog Schemas
class TimeLogBase(BaseModel):
    hours: int
    description: Optional[str] = None

class TimeLogCreate(TimeLogBase):
    task_id: int

class TimeLogResponse(TimeLogBase):
    id: int
    task_id: int
    user_id: int
    logged_at: datetime
    
    class Config:
        from_attributes = True

# Response with nested data
class TaskDetailResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: str
    project_id: int
    assignee_id: Optional[int]
    created_by: int
    created_at: datetime
    updated_at: datetime
    priority: int
    due_date: Optional[datetime] = None
    assignee: Optional[UserResponse] = None
    creator: UserResponse
    project: ProjectResponse
    
    class Config:
        from_attributes = True

class ProjectDetailResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    owner_id: int
    created_at: datetime
    updated_at: datetime
    owner: UserResponse
    tasks: List[TaskResponse] = []
    
    class Config:
        from_attributes = True