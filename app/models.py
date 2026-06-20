from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum
from sqlmodel import Field, SQLModel, Relationship
from cuid import cuid

def get_cuid() -> str:
    return cuid()

class Role(str, Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"

class User(SQLModel, table=True):
    __tablename__ = "User"
    id: str = Field(default_factory=get_cuid, primary_key=True)
    username: str = Field(unique=True, index=True)
    passwordHash: str
    name: Optional[str] = None
    role: Role = Field(default=Role.MANAGER)
    storeId: Optional[str] = Field(default=None, foreign_key="Store.id", index=True)
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    store: Optional["Store"] = Relationship(back_populates="users")


class Store(SQLModel, table=True):
    __tablename__ = "Store"
    id: str = Field(default_factory=get_cuid, primary_key=True)
    name: str
    location: Optional[str] = None
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    users: List["User"] = Relationship(back_populates="store")
    storeProducts: List["StoreProduct"] = Relationship(back_populates="store")
    sales: List["Sale"] = Relationship(back_populates="store")


class Product(SQLModel, table=True):
    __tablename__ = "Product"
    id: str = Field(default_factory=get_cuid, primary_key=True)
    name: str
    description: Optional[str] = None
    imageUrl: Optional[str] = None
    price: float
    discount: int = Field(default=0)
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    storeProducts: List["StoreProduct"] = Relationship(back_populates="product")
    sales: List["Sale"] = Relationship(back_populates="product")


class StoreProduct(SQLModel, table=True):
    __tablename__ = "StoreProduct"
    id: str = Field(default_factory=get_cuid, primary_key=True)
    storeId: str = Field(foreign_key="Store.id", index=True)
    productId: str = Field(foreign_key="Product.id", index=True)
    stockQuantity: int = Field(default=0, index=True)
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    store: "Store" = Relationship(back_populates="storeProducts")
    product: "Product" = Relationship(back_populates="storeProducts")


class Sale(SQLModel, table=True):
    __tablename__ = "Sale"
    id: str = Field(default_factory=get_cuid, primary_key=True)
    storeId: str = Field(foreign_key="Store.id", index=True)
    productId: str = Field(foreign_key="Product.id", index=True)
    quantitySold: int
    totalAmount: float
    profitAmount: float
    saleDate: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)

    store: "Store" = Relationship(back_populates="sales")
    product: "Product" = Relationship(back_populates="sales")


class AuditLog(SQLModel, table=True):
    __tablename__ = "AuditLog"
    id: str = Field(default_factory=get_cuid, primary_key=True)
    userId: Optional[str] = Field(default=None, index=True)
    username: Optional[str] = None
    action: str = Field(index=True)
    entityType: str = Field(index=True)
    entityId: Optional[str] = Field(default=None, index=True)
    entityName: Optional[str] = None
    detail: Optional[str] = None
    storeId: Optional[str] = Field(default=None, index=True)
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
