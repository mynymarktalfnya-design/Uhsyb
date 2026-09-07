"""Pydantic schemas for POS sales."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from models import SaleStatus


class SaleItemIn(BaseModel):
    product_id: str
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    discount: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    sale_unit: str = Field(default="piece", pattern="^(piece|carton)$")
    pieces_per_carton: Optional[int] = Field(default=None, ge=1, le=10000)


class SaleCreate(BaseModel):
    customer_id: Optional[str] = None
    shift_id: Optional[str] = None
    items: List[SaleItemIn] = Field(..., min_length=1)
    payment_method: str = "cash"
    notes: Optional[str] = None
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)


class SaleItemOut(BaseModel):
    id: str
    product_id: str
    product_name: Optional[str] = None
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    sale_unit: str = "piece"
    pieces_per_carton: Optional[int] = None

    class Config:
        from_attributes = True


class SaleOut(BaseModel):
    id: str
    invoice_no: str
    cashier_id: str
    customer_id: Optional[str] = None
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total: Decimal
    paid_amount: Decimal
    change_amount: Decimal
    payment_method: str
    status: SaleStatus
    items: List[SaleItemOut] = []
    created_at: datetime

    class Config:
        from_attributes = True


class ShiftOpen(BaseModel):
    opening_cash: Decimal = Decimal("0")
    notes: Optional[str] = None


class ShiftClose(BaseModel):
    closing_cash: Decimal
    notes: Optional[str] = None


class ShiftOut(BaseModel):
    id: str
    cashier_id: str
    opened_at: datetime
    closed_at: Optional[datetime]
    opening_cash: Decimal
    closing_cash: Optional[Decimal]
    expected_cash: Optional[Decimal]
    variance: Optional[Decimal]
    status: str
    notes: Optional[str]

    class Config:
        from_attributes = True
