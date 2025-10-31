from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_
from datetime import datetime, timedelta
from typing import Dict, List, Any
from models import Task, User, Project, TimeLog, TaskStatus

class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_task_completion_rate(self, project_id: int = None, start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        query = self.db.query(
            func.count(Task.id).label('total'),
            func.sum(case((Task.status == TaskStatus.DONE, 1), else_=0)).label('completed')
        )
        
        if project_id:
            query = query.filter(Task.project_id == project_id)
        
        if start_date:
            query = query.filter(Task.created_at >= start_date)
        
        if end_date:
            query = query.filter(Task.created_at <= end_date)
        
        result = query.first()
        total = result.total or 0
        completed = result.completed or 0
        
        completion_rate = (completed / total * 100) if total > 0 else 0
        
        return {
            'total_tasks': total,
            'completed_tasks': completed,
            'in_progress': total - completed,
            'completion_rate': round(completion_rate, 2)
        }
    
    def get_task_status_distribution(self, project_id: int = None) -> List[Dict[str, Any]]:
        query = self.db.query(
            Task.status,
            func.count(Task.id).label('count')
        ).group_by(Task.status)
        
        if project_id:
            query = query.filter(Task.project_id == project_id)
        
        results = query.all()
        
        return [
            {
                'status': result.status.value,
                'count': result.count
            }
            for result in results
        ]
    
    def get_team_productivity(self, project_id: int = None, days: int = 30) -> List[Dict[str, Any]]:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get all users and their task counts
        query = self.db.query(
            User.id,
            User.username,
            User.full_name,
            func.count(Task.id).label('total_tasks'),
            func.sum(case((Task.status == TaskStatus.DONE, 1), else_=0)).label('completed_tasks')
        ).outerjoin(Task, Task.assignee_id == User.id)
        
        if project_id:
            query = query.filter(or_(Task.project_id == project_id, Task.project_id.is_(None)))
        
        query = query.filter(or_(Task.created_at >= start_date, Task.created_at.is_(None)))
        query = query.group_by(User.id, User.username, User.full_name)
        
        results = query.all()
        
        # Get time logs separately
        team_data = []
        for result in results:
            time_query = self.db.query(
                func.coalesce(func.sum(TimeLog.hours), 0).label('total_hours')
            ).filter(TimeLog.user_id == result.id).filter(TimeLog.logged_at >= start_date)
            
            if project_id:
                time_query = time_query.join(Task).filter(Task.project_id == project_id)
            
            time_result = time_query.first()
            total_hours = float(time_result.total_hours) if time_result else 0
            
            team_data.append({
                'user_id': result.id,
                'username': result.username,
                'full_name': result.full_name,
                'total_tasks': result.total_tasks or 0,
                'completed_tasks': result.completed_tasks or 0,
                'completion_rate': round((result.completed_tasks / result.total_tasks * 100) if result.total_tasks else 0, 2),
                'total_hours': total_hours
            })
        
        return team_data
    
    def get_overdue_tasks(self, project_id: int = None) -> List[Dict[str, Any]]:
        now = datetime.utcnow()
        
        query = self.db.query(Task)\
            .filter(Task.due_date < now)\
            .filter(Task.status != TaskStatus.DONE)
        
        if project_id:
            query = query.filter(Task.project_id == project_id)
        
        tasks = query.all()
        
        return [
            {
                'id': task.id,
                'title': task.title,
                'project_id': task.project_id,
                'assignee_id': task.assignee_id,
                'due_date': task.due_date.isoformat(),
                'days_overdue': (now - task.due_date).days,
                'status': task.status.value,
                'priority': task.priority
            }
            for task in tasks
        ]
    
    def get_task_velocity(self, project_id: int = None, weeks: int = 4) -> List[Dict[str, Any]]:
        start_date = datetime.utcnow() - timedelta(weeks=weeks)
        
        # For SQLite, use strftime instead of date_trunc
        query = self.db.query(
            func.strftime('%Y-%W', Task.updated_at).label('week'),
            func.count(Task.id).label('completed')
        ).filter(Task.status == TaskStatus.DONE)\
         .filter(Task.updated_at >= start_date)\
         .group_by(func.strftime('%Y-%W', Task.updated_at))\
         .order_by(func.strftime('%Y-%W', Task.updated_at))
        
        if project_id:
            query = query.filter(Task.project_id == project_id)
        
        results = query.all()
        
        return [
            {
                'week': result.week,
                'completed_tasks': result.completed
            }
            for result in results
        ]
    
    def get_average_completion_time(self, project_id: int = None) -> Dict[str, Any]:
        #Calculate seconds, convert to hours
        query = self.db.query(
            func.avg(
                (func.julianday(Task.updated_at) - func.julianday(Task.created_at)) * 24
            ).label('avg_hours')
        ).filter(Task.status == TaskStatus.DONE)
        
        if project_id:
            query = query.filter(Task.project_id == project_id)
        
        result = query.first()
        avg_hours = result.avg_hours or 0
        
        return {
            'average_hours': round(float(avg_hours), 2),
            'average_days': round(float(avg_hours) / 24, 2)
        }
    
    def get_time_tracking_summary(self, project_id: int = None, user_id: int = None, days: int = 30) -> Dict[str, Any]:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = self.db.query(
            func.sum(TimeLog.hours).label('total_hours'),
            func.count(func.distinct(TimeLog.task_id)).label('tasks_worked_on')
        ).filter(TimeLog.logged_at >= start_date)
        
        if project_id:
            query = query.join(Task).filter(Task.project_id == project_id)
        
        if user_id:
            query = query.filter(TimeLog.user_id == user_id)
        
        result = query.first()
        
        return {
            'total_hours': float(result.total_hours or 0),
            'tasks_worked_on': result.tasks_worked_on or 0,
            'period_days': days
        }
    
    def get_project_dashboard(self, project_id: int) -> Dict[str, Any]:
        return {
            'completion_metrics': self.get_task_completion_rate(project_id),
            'status_distribution': self.get_task_status_distribution(project_id),
            'team_productivity': self.get_team_productivity(project_id),
            'overdue_tasks': self.get_overdue_tasks(project_id),
            'velocity': self.get_task_velocity(project_id),
            'avg_completion_time': self.get_average_completion_time(project_id),
            'time_tracking': self.get_time_tracking_summary(project_id)
        }
    
    def get_user_statistics(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Task counts
        total_tasks = self.db.query(func.count(Task.id))\
            .filter(Task.assignee_id == user_id)\
            .filter(Task.created_at >= start_date)\
            .scalar()
        
        completed_tasks = self.db.query(func.count(Task.id))\
            .filter(Task.assignee_id == user_id)\
            .filter(Task.status == TaskStatus.DONE)\
            .filter(Task.created_at >= start_date)\
            .scalar()
        
        # Time tracking
        time_summary = self.get_time_tracking_summary(user_id=user_id, days=days)
        
        return {
            'user_id': user_id,
            'period_days': days,
            'total_tasks_assigned': total_tasks or 0,
            'tasks_completed': completed_tasks or 0,
            'completion_rate': round((completed_tasks / total_tasks * 100) if total_tasks else 0, 2),
            'total_hours_logged': time_summary['total_hours'],
            'tasks_worked_on': time_summary['tasks_worked_on']
        }