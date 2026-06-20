from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import List, Dict, Any
from app.database import get_session
from app.models import Sale, Product, Store, User, Role
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Note: The actual initialization of the TimesFM model is commented out
# to prevent memory issues and slow startup during development.
# In a real production scenario, you would initialize this at the app startup.
import timesfm

router = APIRouter(prefix="/api/forecast", tags=["Forecast"])

from app.auth import get_current_user

class ForecastRequest(BaseModel):
    storeIds: List[str]
    productIds: List[str]
    horizon_days: int = 7  # Predict the next 7 days

# Lazy load the model to save memory during normal API operations
tfm = None

def get_timesfm_model():
    global tfm
    if tfm is None:
        print("Initializing TimesFM model... This may take a while and download weights from HuggingFace.")
        tfm = timesfm.TimesFm(
            context_len=32,
            horizon_len=14, # Max forecasting length for this instance
            input_patch_len=32,
            output_patch_len=128,
            num_layers=20,
            model_dims=1280,
            backend='cpu' # Change to 'gpu' if you have CUDA installed
        )
        tfm.load_from_checkpoint(repo_id="google/timesfm-1.0-200m")
    return tfm

@router.post("/", response_model=Dict[str, Any])
def generate_forecast(req: ForecastRequest, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Unauthorized")

    is_all_products = "ALL" in req.productIds
    is_all_stores = "ALL" in req.storeIds

    forecast_results = []
    
    # 1. Try to load the model
    try:
        model = get_timesfm_model()
    except Exception as e:
        print(f"TimesFM Error: {e}")
        model = None

    # 2. Process based on Hybrid Logic
    if is_all_products:
        # AGGREGATE MODE: Combine all sales into 1 line
        query = select(Sale)
        if not is_all_stores:
            query = query.where(Sale.storeId.in_(req.storeIds))
            
        sales = session.exec(query.order_by(Sale.saleDate)).all()
        if not sales or len(sales) < 5:
            raise HTTPException(status_code=400, detail="Data penjualan historis belum cukup untuk membuat prediksi (Minimal butuh data 5 hari).")
            
        df = pd.DataFrame([{"date": s.saleDate.date(), "quantity": s.quantitySold} for s in sales])
        daily_sales = df.groupby("date")["quantity"].sum().reset_index()
        daily_sales["date"] = pd.to_datetime(daily_sales["date"])
        daily_sales = daily_sales.set_index("date").resample("D").sum().fillna(0).reset_index()
        
        historical_quantities = daily_sales["quantity"].tolist()
        
        if model:
            try:
                forecast_result = model.forecast(inputs=[historical_quantities])
                point_predictions = forecast_result[0][0][:req.horizon_days].tolist()
                point_predictions = [max(0, round(p)) for p in point_predictions]
            except Exception as e:
                point_predictions = [round(np.mean(historical_quantities[-7:]))] * req.horizon_days
        else:
            point_predictions = [round(np.mean(historical_quantities[-7:]))] * req.horizon_days
            
        last_date = daily_sales["date"].iloc[-1]
        future_dates = [(last_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, req.horizon_days + 1)]
        
        forecast_results.append({
            "id": "ALL_PRODUCTS",
            "name": "Total Semua Produk",
            "forecast": [
                {"date": date, "predicted_quantity": qty} 
                for date, qty in zip(future_dates, point_predictions)
            ]
        })
    else:
        # MULTI-LINE MODE: Separate lines for each selected product
        products_db = session.exec(select(Product).where(Product.id.in_(req.productIds))).all()
        product_map = {p.id: p.name for p in products_db}
        
        for pid in req.productIds:
            query = select(Sale).where(Sale.productId == pid)
            if not is_all_stores:
                query = query.where(Sale.storeId.in_(req.storeIds))
                
            sales = session.exec(query.order_by(Sale.saleDate)).all()
            if not sales or len(sales) < 5:
                continue # Skip products with insufficient data to prevent crashing the batch
                
            df = pd.DataFrame([{"date": s.saleDate.date(), "quantity": s.quantitySold} for s in sales])
            daily_sales = df.groupby("date")["quantity"].sum().reset_index()
            daily_sales["date"] = pd.to_datetime(daily_sales["date"])
            daily_sales = daily_sales.set_index("date").resample("D").sum().fillna(0).reset_index()
            
            historical_quantities = daily_sales["quantity"].tolist()
            
            if model:
                try:
                    forecast_result = model.forecast(inputs=[historical_quantities])
                    point_predictions = forecast_result[0][0][:req.horizon_days].tolist()
                    point_predictions = [max(0, round(p)) for p in point_predictions]
                except Exception as e:
                    point_predictions = [round(np.mean(historical_quantities[-7:]))] * req.horizon_days
            else:
                point_predictions = [round(np.mean(historical_quantities[-7:]))] * req.horizon_days
                
            last_date = daily_sales["date"].iloc[-1]
            future_dates = [(last_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, req.horizon_days + 1)]
            
            forecast_results.append({
                "id": pid,
                "name": product_map.get(pid, f"Produk {pid}"),
                "forecast": [
                    {"date": date, "predicted_quantity": qty} 
                    for date, qty in zip(future_dates, point_predictions)
                ]
            })
            
        if not forecast_results:
             raise HTTPException(status_code=400, detail="Data historis dari produk-produk terpilih tidak cukup (Minimal 5 hari) atau tidak ditemukan.")

    # 3. Return the structured result
    return {
        "storeIds": req.storeIds,
        "productIds": req.productIds,
        "series": forecast_results
    }
