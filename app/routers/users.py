from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.auth import get_current_user
from app.models import User, Role
from pydantic import BaseModel
import bcrypt

router = APIRouter(prefix="/api/users", tags=["Users"])

class UserCreate(BaseModel):
    username: str
    password: str
    name: str
    storeId: str

@router.post("/")
def create_manager(user_data: UserCreate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if current_user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
        
    existing = session.exec(select(User).where(User.username == user_data.username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username sudah digunakan")
    
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(user_data.password.encode('utf-8'), salt).decode('utf-8')
    
    new_user = User(
        username=user_data.username,
        passwordHash=hashed,
        name=user_data.name,
        role=Role.MANAGER,
        storeId=user_data.storeId
    )
    session.add(new_user)
    session.commit()
    return {"success": True}

@router.delete("/{user_id}")
def delete_manager(user_id: str, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if current_user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
        
    user = session.get(User, user_id)
    if user:
        session.delete(user)
        session.commit()
    return {"success": True}
