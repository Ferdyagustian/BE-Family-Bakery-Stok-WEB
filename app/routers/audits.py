from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.auth import get_current_user
from app.models import AuditLog, User, Role
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/api/audits", tags=["Audits"])

@router.delete("/clear")
def clear_logs(daysToKeep: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    if current_user.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
        
    cutoff = datetime.now(timezone.utc) - timedelta(days=daysToKeep)
    
    if daysToKeep > 0:
        logs = session.exec(select(AuditLog).where(AuditLog.createdAt < cutoff)).all()
    else:
        logs = session.exec(select(AuditLog)).all()
        
    count = len(logs)
    for log in logs:
        session.delete(log)
        
    session.commit()
    return {"success": True, "count": count}
