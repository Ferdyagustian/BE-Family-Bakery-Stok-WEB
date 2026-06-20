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

def get_current_user() -> User:
    return User(id="dummy_admin", username="admin", passwordHash="xxx", role=Role.ADMIN)

class ForecastRequest(BaseModel):
    storeId: str
    productId: str
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

    # 1. Fetch historical sales data from the database
    sales = session.exec(
        select(Sale)
        .where(Sale.storeId == req.storeId)
        .where(Sale.productId == req.productId)
        .order_by(Sale.saleDate)
    ).all()
    
    if not sales or len(sales) < 5:
        # TimesFM needs a decent amount of context (historical data) to predict accurately
        raise HTTPException(status_code=400, detail="Data penjualan historis belum cukup untuk membuat prediksi (Minimal butuh data 5-32 hari ke belakang).")
        
    # 2. Process data into a daily time series
    # Convert to Pandas DataFrame for easy grouping
    df = pd.DataFrame([{"date": s.saleDate.date(), "quantity": s.quantitySold} for s in sales])
    
    # Group by date and sum the quantities
    daily_sales = df.groupby("date")["quantity"].sum().reset_index()
    
    # Ensure there are no gaps in the dates
    daily_sales["date"] = pd.to_datetime(daily_sales["date"])
    daily_sales = daily_sales.set_index("date").resample("D").sum().fillna(0).reset_index()
    
    historical_quantities = daily_sales["quantity"].tolist()
    
    # 3. Load the model and make the forecast
    try:
        model = get_timesfm_model()
        
        # We pass the historical data as a list of lists (batching format)
        # TimesFM returns a tuple, usually (point_forecasts, experimental_quantiles)
        forecast_result = model.forecast(inputs=[historical_quantities])
        
        # forecast_result[0] contains the point forecasts.
        # It's shaped [batch_size, horizon_len]. We take the first batch [0] and slice up to horizon_days.
        point_predictions = forecast_result[0][0][:req.horizon_days].tolist()
        
        # Cap predictions at 0 (can't have negative sales)
        point_predictions = [max(0, round(p)) for p in point_predictions]
        
    except Exception as e:
        print(f"TimesFM Error: {e}")
        # Fallback dummy data if model fails to load or memory is insufficient
        point_predictions = [round(np.mean(historical_quantities[-7:]))] * req.horizon_days
        return {"warning": "Model failed to load. Using simple moving average fallback.", "predictions": point_predictions}

    # Generate the dates for the predictions
    last_date = daily_sales["date"].iloc[-1]
    future_dates = [(last_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, req.horizon_days + 1)]

    # 4. Return the structured result
    return {
        "storeId": req.storeId,
        "productId": req.productId,
        "historical_data_length": len(historical_quantities),
        "forecast": [
            {"date": date, "predicted_quantity": qty} 
            for date, qty in zip(future_dates, point_predictions)
        ]
    }
