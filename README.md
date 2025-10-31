# Task Management System


## Features

### Core Functionality
- **Project & Task Management** - Create projects and organize tasks
- **Task Assignment** - Assign tasks to team members
- **Status Tracking** - Todo, In Progress, Done workflow
- **Comments** - Discuss tasks with team members
- **@Mentions** - Mention users with @username syntax
- **Time Tracking** - Log hours spent on tasks

### Real-Time Collaboration
- **Live Updates** - See changes instantly without refreshing
- **Smart Notifications** - Get notified when assigned or mentioned
- **Activity Feed** - Track all team activity in real-time
- **WebSocket Connection** - Persistent connection for instant updates

### Analytics & Reporting
- **Task Completion** - Track project progress
- **Team Productivity** - Monitor individual performance
- **Time Tracking** - Aggregate hours logged per task/user (in DB not in frontend)


### Technology Stack


## Prerequisites

- **Python 3.11+** 
- **Docker Desktop**

## Quick Start

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd task-management-system
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Kafka with Docker

```bash
docker-compose -f config/docker-compose-kafka.yml up -d
```

Wait ~10 seconds for Kafka to initialize.

### 4. Seed the Database

```bash
cd backend
python database.py # if taskmanamanagemnt.db does not exist
python seed_data.py
cd ..
```

This creates the database and adds test users:
- han@example.com
- chewy@example.com
- luke@example.com

### 5. Start the Backend API

**Terminal 1:**
```bash
cd backend
python main.py
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### 6. Start the Kafka Consumer

**Terminal 2:**
```bash
cd backend
python kafka_consumer.py
```

You should see:
```
INFO - Connected to Kafka at ['localhost:9092']
INFO - Starting to consume events...
```

### 7. Open the Frontend

**Terminal 3 or Browser:**
```bash
open frontend/index.html
# Or double-click frontend/index.html
```

The frontend will open in your browser. Look for the green "WebSocket: Connected" indicator. Switch users at the top to see specialized notifications. Open the app in multiple tabs to see data flow between users!
