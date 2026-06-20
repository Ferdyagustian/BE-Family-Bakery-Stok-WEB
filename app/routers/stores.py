from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models import Store, Product, StoreProduct, AuditLog, User, Role
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/stores", tags=["Stores"])

# --- Placeholder for Auth ---
# In a real scenario, this would extract the JWT token from the header
def get_current_user() -> User:
    # Dummy admin user for now so development can continue
    return User(id="dummy_admin", username="admin", passwordHash="xxx", role=Role.ADMIN)

class StoreCreate(BaseModel):
    name: str
    location: Optional[str] = None

class StoreUpdate(BaseModel):
    name: str
    location: Optional[str] = None

@router.get("/", response_model=List[Store])
def get_stores(session: Session = Depends(get_session)):
    stores = session.exec(select(Store)).all()
    return stores

@router.post("/", response_model=Store)
def create_store(store_data: StoreCreate, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Create Store
    new_store = Store(name=store_data.name, location=store_data.location)
    session.add(new_store)
    session.commit()
    session.refresh(new_store)
    
    # Auto-populate all master products into the new store with 0 stock
    products = session.exec(select(Product)).all()
    for p in products:
        sp = StoreProduct(storeId=new_store.id, productId=p.id, stockQuantity=0)
        session.add(sp)
    
    # Audit Log
    audit = AuditLog(
        userId=user.id,
        username=user.username,
        action="CREATE_STORE",
        entityType="Store",
        entityId=new_store.id,
        entityName=new_store.name,
        detail=f"Location: {store_data.location}"
    )
    session.add(audit)
    session.commit()
    
    return new_store

@router.put("/{store_id}", response_model=Store)
def update_store(store_id: str, store_data: StoreUpdate, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    store = session.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
        
    store.name = store_data.name
    store.location = store_data.location
    session.add(store)
    
    audit = AuditLog(
        userId=user.id,
        username=user.username,
        action="UPDATE_STORE",
        entityType="Store",
        entityId=store.id,
        entityName=store.name
    )
    session.add(audit)
    session.commit()
    session.refresh(store)
    
    return store

@router.delete("/{store_id}")
def delete_store(store_id: str, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    store = session.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
        
    store_name = store.name
    session.delete(store)
    
    audit = AuditLog(
        userId=user.id,
        username=user.username,
        action="DELETE_STORE",
        entityType="Store",
        entityId=store_id,
        entityName=store_name
    )
    session.add(audit)
    session.commit()
    
    return {"success": True}
