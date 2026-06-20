from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models import AuditLog
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/api/audits", tags=["Audits"])

@router.delete("/clear")
def clear_logs(daysToKeep: int, session: Session = Depends(get_session)):
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
