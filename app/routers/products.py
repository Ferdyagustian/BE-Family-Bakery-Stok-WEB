from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models import Store, Product, StoreProduct, Sale, AuditLog, User, Role
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

router = APIRouter(prefix="/api/products", tags=["Products"])

from app.auth import get_current_user

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    imageUrl: Optional[str] = None
    price: float

class ProductUpdate(BaseModel):
    name: str
    description: Optional[str] = None
    imageUrl: Optional[str] = None
    price: float
    discount: int = 0

class SaleRecord(BaseModel):
    storeId: str
    quantity: int

class AddStoreProductReq(BaseModel):
    storeId: str
    productId: str
    stockQuantity: int

class RestockItem(BaseModel):
    productId: str
    qty: int
    name: Optional[str] = None

class BulkRestockReq(BaseModel):
    storeId: str
    restocks: List[RestockItem]

class SaleItem(BaseModel):
    productId: str
    quantity: int

class BulkSaleReq(BaseModel):
    storeId: str
    items: List[SaleItem]

class PriceItem(BaseModel):
    id: str
    price: float

class BulkPriceReq(BaseModel):
    items: List[PriceItem]

class AdjustAllReq(BaseModel):
    type: str  # 'increase' or 'decrease'
    amountType: str  # 'nominal' or 'percent'
    value: float

@router.get("/", response_model=List[Product])
def get_products(session: Session = Depends(get_session)):
    return session.exec(select(Product)).all()

@router.post("/", response_model=Product)
def create_master_product(prod_data: ProductCreate, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    if prod_data.price <= 0:
        raise HTTPException(status_code=400, detail="Data tidak valid")
        
    existing = session.exec(select(Product).where(Product.name == prod_data.name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Produk dengan nama ini sudah ada di Master Katalog")
        
    product = Product(
        name=prod_data.name,
        description=prod_data.description,
        imageUrl=prod_data.imageUrl,
        price=prod_data.price
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    
    stores = session.exec(select(Store)).all()
    for s in stores:
        sp = StoreProduct(storeId=s.id, productId=product.id, stockQuantity=0)
        session.add(sp)
        
    audit = AuditLog(
        userId=user.id,
        username=user.username,
        action="CREATE_PRODUCT",
        entityType="Product",
        entityId=product.id,
        entityName=product.name,
        detail=f"price: {product.price}"
    )
    session.add(audit)
    session.commit()
    
    return product

@router.post("/store-product")
def add_store_product(req: AddStoreProductReq, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    product = session.get(Product, req.productId)
    if not product:
        raise HTTPException(status_code=404, detail="Produk Master tidak ditemukan")
        
    sp = session.exec(select(StoreProduct).where(StoreProduct.storeId == req.storeId, StoreProduct.productId == req.productId)).first()
    if sp:
        sp.stockQuantity += req.stockQuantity
        session.add(sp)
    else:
        sp = StoreProduct(storeId=req.storeId, productId=req.productId, stockQuantity=req.stockQuantity)
        session.add(sp)
        
    audit = AuditLog(
        userId=user.id,
        username=user.username,
        action="RESTOCK_PRODUCT",
        entityType="StoreProduct",
        entityId=req.productId,
        entityName=product.name,
        storeId=req.storeId,
        detail=f"added: {req.stockQuantity}"
    )
    session.add(audit)
    session.commit()
    return {"success": True}

@router.put("/{product_id}", response_model=Product)
def update_product(product_id: str, prod_data: ProductUpdate, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
        
    product.name = prod_data.name
    product.description = prod_data.description
    product.imageUrl = prod_data.imageUrl
    product.price = prod_data.price
    product.discount = prod_data.discount
    
    session.add(product)
    
    audit = AuditLog(
        userId=user.id,
        username=user.username,
        action="UPDATE_PRODUCT",
        entityType="Product",
        entityId=product.id,
        entityName=product.name
    )
    session.add(audit)
    session.commit()
    session.refresh(product)
    
    return product

@router.delete("/{product_id}")
def delete_product(product_id: str, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
        
    prod_name = product.name
    session.delete(product)
    
    audit = AuditLog(
        userId=user.id,
        username=user.username,
        action="DELETE_MASTER_PRODUCT",
        entityType="Product",
        entityId=product_id,
        entityName=prod_name
    )
    session.add(audit)
    session.commit()
    
    return {"success": True}

@router.delete("/store-product/{store_id}/{product_id}")
def delete_store_product(store_id: str, product_id: str, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    sp = session.exec(select(StoreProduct).where(StoreProduct.storeId == store_id, StoreProduct.productId == product_id)).first()
    if not sp:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan di cabang ini")
        
    product = session.get(Product, product_id)
    prod_name = product.name if product else "Unknown"
    
    session.delete(sp)
    
    audit = AuditLog(
        userId=user.id,
        username=user.username,
        action="DELETE_STORE_PRODUCT",
        entityType="StoreProduct",
        entityId=product_id,
        entityName=prod_name,
        storeId=store_id,
        detail="Product removed from branch"
    )
    session.add(audit)
    session.commit()
    
    return {"success": True}

@router.post("/{product_id}/record-sale")
def record_sale(product_id: str, sale_data: SaleRecord, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
        
    store_product = session.exec(select(StoreProduct).where(
        StoreProduct.productId == product_id, 
        StoreProduct.storeId == sale_data.storeId
    )).first()
    
    if not store_product or store_product.stockQuantity < sale_data.quantity:
        raise HTTPException(status_code=400, detail="Stok tidak cukup atau sudah habis terjual")
        
    store_product.stockQuantity -= sale_data.quantity
    
    discount_pct = product.discount or 0
    effective_price = product.price * (1 - discount_pct / 100)
    total_amount = effective_price * sale_data.quantity
    
    sale = Sale(
        storeId=sale_data.storeId,
        productId=product_id,
        quantitySold=sale_data.quantity,
        totalAmount=total_amount,
        profitAmount=total_amount
    )
    
    session.add(store_product)
    session.add(sale)
    
    audit = AuditLog(
        userId=user.id,
        username=user.username,
        action="RECORD_SALE",
        entityType="Sale",
        entityId=product_id,
        entityName=product.name,
        storeId=sale_data.storeId
    )
    session.add(audit)
    session.commit()
    return {"success": True}

@router.post("/bulk-restock")
def bulk_restock(req: BulkRestockReq, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    count = 0
    for r in req.restocks:
        sp = session.exec(select(StoreProduct).where(StoreProduct.storeId == req.storeId, StoreProduct.productId == r.productId)).first()
        if sp:
            sp.stockQuantity += r.qty
            session.add(sp)
            count += 1
            
    audit = AuditLog(
        userId=user.id,
        username=user.username,
        action="RESTOCK_PRODUCT",
        entityType="StoreProduct",
        storeId=req.storeId,
        detail=f"Bulk restocked {count} items"
    )
    session.add(audit)
    session.commit()
    return {"success": True, "count": count}

@router.post("/bulk-sales")
def record_bulk_sales(req: BulkSaleReq, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    for item in req.items:
        product = session.get(Product, item.productId)
        if not product:
            raise HTTPException(status_code=404, detail=f"Produk {item.productId} tidak ditemukan")
            
        sp = session.exec(select(StoreProduct).where(StoreProduct.storeId == req.storeId, StoreProduct.productId == item.productId)).first()
        if not sp or sp.stockQuantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Stok tidak cukup untuk produk {product.name}")
            
        sp.stockQuantity -= item.quantity
        discount_pct = product.discount or 0
        effective_price = product.price * (1 - discount_pct / 100)
        total_amount = effective_price * item.quantity
        
        sale = Sale(
            storeId=req.storeId,
            productId=item.productId,
            quantitySold=item.quantity,
            totalAmount=total_amount,
            profitAmount=total_amount
        )
        session.add(sp)
        session.add(sale)
        
    audit = AuditLog(
        userId=user.id,
        username=user.username,
        action="RECORD_SALE",
        entityType="Sale",
        storeId=req.storeId,
        detail=f"Bulk sale {len(req.items)} items"
    )
    session.add(audit)
    session.commit()
    return {"success": True}

@router.post("/bulk-prices")
def update_bulk_prices(req: BulkPriceReq, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    for item in req.items:
        product = session.get(Product, item.id)
        if product:
            product.price = item.price
            session.add(product)
            
    audit = AuditLog(
        userId=user.id,
        username=user.username,
        action="UPDATE_BULK_PRICES",
        entityType="Product",
        detail=f"count: {len(req.items)}"
    )
    session.add(audit)
    session.commit()
    return {"success": True}

@router.post("/adjust-all-prices")
def adjust_all_prices(req: AdjustAllReq, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    products = session.exec(select(Product)).all()
    for product in products:
        new_price = product.price
        if req.amountType == 'nominal':
            new_price = product.price + req.value if req.type == 'increase' else max(0, product.price - req.value)
        elif req.amountType == 'percent':
            change = product.price * (req.value / 100)
            new_price = product.price + change if req.type == 'increase' else max(0, product.price - change)
            
        product.price = round(new_price)
        session.add(product)
        
    audit = AuditLog(
        userId=user.id,
        username=user.username,
        action="ADJUST_ALL_PRICES",
        entityType="Product",
        detail=f"{req.type} {req.amountType} {req.value}"
    )
    session.add(audit)
    session.commit()
    return {"success": True}
