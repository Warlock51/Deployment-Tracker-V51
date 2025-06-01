from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timedelta
import bcrypt
import jwt
from enum import Enum

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Settings
JWT_SECRET = os.environ.get('JWT_SECRET', 'your-secret-key-here')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Create the main app without a prefix
app = FastAPI(title="Deployment Tracker API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer()

# Enums
class UserRole(str, Enum):
    admin = "admin"
    developer = "developer"

class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class BugStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"

class FixStatus(str, Enum):
    pending = "pending"
    deployed = "deployed"

class IdeaStatus(str, Enum):
    new = "new"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"

class Environment(str, Enum):
    dev = "dev"
    staging = "staging"
    prod = "prod"

# Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str
    password_hash: str
    role: UserRole = UserRole.developer
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: UserRole = UserRole.developer

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: UserRole
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class Bug(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    priority: Priority = Priority.medium
    status: BugStatus = BugStatus.open
    assigned_to: Optional[str] = None
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class BugCreate(BaseModel):
    title: str
    description: str
    priority: Priority = Priority.medium
    assigned_to: Optional[str] = None

class BugUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[Priority] = None
    status: Optional[BugStatus] = None
    assigned_to: Optional[str] = None

class Fix(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    related_bug_id: Optional[str] = None
    status: FixStatus = FixStatus.pending
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class FixCreate(BaseModel):
    title: str
    description: str
    related_bug_id: Optional[str] = None

class FixUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[FixStatus] = None

class Deployment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: str
    description: str
    environment: Environment
    deployed_by: str
    deployed_at: datetime = Field(default_factory=datetime.utcnow)
    changes_included: List[str] = []

class DeploymentCreate(BaseModel):
    version: str
    description: str
    environment: Environment
    changes_included: List[str] = []

class Idea(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    priority: Priority = Priority.medium
    status: IdeaStatus = IdeaStatus.new
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class IdeaCreate(BaseModel):
    title: str
    description: str
    priority: Priority = Priority.medium

class IdeaUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[Priority] = None
    status: Optional[IdeaStatus] = None

class DashboardStats(BaseModel):
    total_bugs: int
    open_bugs: int
    resolved_bugs: int
    pending_fixes: int
    deployed_fixes: int
    recent_deployments: int
    new_ideas: int
    total_users: int

# Auth utilities
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    user = await db.users.find_one({"id": user_id})
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return User(**user)

async def get_admin_user(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# Auth routes
@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"$or": [{"username": user_data.username}, {"email": user_data.email}]})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    # Hash password
    hashed_password = hash_password(user_data.password)
    
    # Create user
    user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        role=user_data.role
    )
    
    await db.users.insert_one(user.dict())
    
    # Create token
    access_token = create_access_token(data={"sub": user.id})
    
    user_response = UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        created_at=user.created_at
    )
    
    return TokenResponse(access_token=access_token, user=user_response)

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(login_data: UserLogin):
    user = await db.users.find_one({"username": login_data.username})
    if not user or not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    access_token = create_access_token(data={"sub": user["id"]})
    
    user_response = UserResponse(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
        created_at=user["created_at"]
    )
    
    return TokenResponse(access_token=access_token, user=user_response)

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        created_at=current_user.created_at
    )

# User management routes
@api_router.get("/users", response_model=List[UserResponse])
async def get_users(current_user: User = Depends(get_current_user)):
    users = await db.users.find().to_list(1000)
    return [UserResponse(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
        created_at=user["created_at"]
    ) for user in users]

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin_user: User = Depends(get_admin_user)):
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}

# Bug routes
@api_router.post("/bugs", response_model=Bug)
async def create_bug(bug_data: BugCreate, current_user: User = Depends(get_current_user)):
    bug = Bug(**bug_data.dict(), created_by=current_user.id)
    await db.bugs.insert_one(bug.dict())
    return bug

@api_router.get("/bugs", response_model=List[Bug])
async def get_bugs(current_user: User = Depends(get_current_user)):
    bugs = await db.bugs.find().to_list(1000)
    return [Bug(**bug) for bug in bugs]

@api_router.get("/bugs/{bug_id}", response_model=Bug)
async def get_bug(bug_id: str, current_user: User = Depends(get_current_user)):
    bug = await db.bugs.find_one({"id": bug_id})
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    return Bug(**bug)

@api_router.put("/bugs/{bug_id}", response_model=Bug)
async def update_bug(bug_id: str, bug_update: BugUpdate, current_user: User = Depends(get_current_user)):
    bug = await db.bugs.find_one({"id": bug_id})
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    # Check permissions
    if current_user.role != UserRole.admin and bug["created_by"] != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    update_data = {k: v for k, v in bug_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    await db.bugs.update_one({"id": bug_id}, {"$set": update_data})
    updated_bug = await db.bugs.find_one({"id": bug_id})
    return Bug(**updated_bug)

@api_router.delete("/bugs/{bug_id}")
async def delete_bug(bug_id: str, current_user: User = Depends(get_current_user)):
    bug = await db.bugs.find_one({"id": bug_id})
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    
    # Check permissions
    if current_user.role != UserRole.admin and bug["created_by"] != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    await db.bugs.delete_one({"id": bug_id})
    return {"message": "Bug deleted successfully"}

# Fix routes
@api_router.post("/fixes", response_model=Fix)
async def create_fix(fix_data: FixCreate, current_user: User = Depends(get_current_user)):
    fix = Fix(**fix_data.dict(), created_by=current_user.id)
    await db.fixes.insert_one(fix.dict())
    return fix

@api_router.get("/fixes", response_model=List[Fix])
async def get_fixes(current_user: User = Depends(get_current_user)):
    fixes = await db.fixes.find().to_list(1000)
    return [Fix(**fix) for fix in fixes]

@api_router.put("/fixes/{fix_id}", response_model=Fix)
async def update_fix(fix_id: str, fix_update: FixUpdate, current_user: User = Depends(get_current_user)):
    fix = await db.fixes.find_one({"id": fix_id})
    if not fix:
        raise HTTPException(status_code=404, detail="Fix not found")
    
    # Check permissions
    if current_user.role != UserRole.admin and fix["created_by"] != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    update_data = {k: v for k, v in fix_update.dict().items() if v is not None}
    await db.fixes.update_one({"id": fix_id}, {"$set": update_data})
    updated_fix = await db.fixes.find_one({"id": fix_id})
    return Fix(**updated_fix)

# Deployment routes
@api_router.post("/deployments", response_model=Deployment)
async def create_deployment(deployment_data: DeploymentCreate, current_user: User = Depends(get_current_user)):
    deployment = Deployment(**deployment_data.dict(), deployed_by=current_user.id)
    await db.deployments.insert_one(deployment.dict())
    return deployment

@api_router.get("/deployments", response_model=List[Deployment])
async def get_deployments(current_user: User = Depends(get_current_user)):
    deployments = await db.deployments.find().to_list(1000)
    return [Deployment(**deployment) for deployment in deployments]

# Idea routes
@api_router.post("/ideas", response_model=Idea)
async def create_idea(idea_data: IdeaCreate, current_user: User = Depends(get_current_user)):
    idea = Idea(**idea_data.dict(), created_by=current_user.id)
    await db.ideas.insert_one(idea.dict())
    return idea

@api_router.get("/ideas", response_model=List[Idea])
async def get_ideas(current_user: User = Depends(get_current_user)):
    ideas = await db.ideas.find().to_list(1000)
    return [Idea(**idea) for idea in ideas]

@api_router.put("/ideas/{idea_id}", response_model=Idea)
async def update_idea(idea_id: str, idea_update: IdeaUpdate, current_user: User = Depends(get_current_user)):
    idea = await db.ideas.find_one({"id": idea_id})
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    
    # Check permissions
    if current_user.role != UserRole.admin and idea["created_by"] != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    update_data = {k: v for k, v in idea_update.dict().items() if v is not None}
    await db.ideas.update_one({"id": idea_id}, {"$set": update_data})
    updated_idea = await db.ideas.find_one({"id": idea_id})
    return Idea(**updated_idea)

# Dashboard route
@api_router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(current_user: User = Depends(get_current_user)):
    # Get counts
    total_bugs = await db.bugs.count_documents({})
    open_bugs = await db.bugs.count_documents({"status": BugStatus.open})
    resolved_bugs = await db.bugs.count_documents({"status": BugStatus.resolved})
    pending_fixes = await db.fixes.count_documents({"status": FixStatus.pending})
    deployed_fixes = await db.fixes.count_documents({"status": FixStatus.deployed})
    recent_deployments = await db.deployments.count_documents({
        "deployed_at": {"$gte": datetime.utcnow() - timedelta(days=7)}
    })
    new_ideas = await db.ideas.count_documents({"status": IdeaStatus.new})
    total_users = await db.users.count_documents({})
    
    return DashboardStats(
        total_bugs=total_bugs,
        open_bugs=open_bugs,
        resolved_bugs=resolved_bugs,
        pending_fixes=pending_fixes,
        deployed_fixes=deployed_fixes,
        recent_deployments=recent_deployments,
        new_ideas=new_ideas,
        total_users=total_users
    )

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
