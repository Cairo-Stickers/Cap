from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from datetime import datetime
import os
import joblib
import numpy as np

app = FastAPI()

# --- Database Setup ---
MONGO_URI = "mongodb+srv://RaspberryPI:f%252%23vAmwtaQ-c.C@m0.ejnni6f.mongodb.net/health_monitor?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI)
db = client.health_monitor
collection = db.sensor_data

# --- AI Model Loading (Fixed for Vercel Serverless Pathing) ---
# This forces Vercel to look in the exact same directory as this main.py script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'anomaly_watchdog.pkl')

try:
    watchdog_model = joblib.load(MODEL_PATH)
    print("AI Watchdog loaded successfully.")
except Exception as e:
    print(f"Error loading AI model: {e}")
    watchdog_model = None

# --- Data Schema ---
class SensorPayload(BaseModel):
    patient_id: str
    temperature: float
    hr_raw: int      
    spo2_raw: int    
    accel_mag: float
    fall_flag: int
    lat: float
    lon: float

# --- AI Evaluation Logic ---
def evaluate_patient_risk(data: SensorPayload):
    risk_score = 0
    anomalies = []

    # 1. Hardcoded Emergency Rules
    if data.fall_flag == 1:
        risk_score += 10
        anomalies.append("FALL DETECTED")

    if data.temperature > 39.0:
        risk_score += 5
        anomalies.append(f"High Temp ({data.temperature}C)")
    elif data.temperature < 35.0 and data.temperature > 10.0:
        risk_score += 5
        anomalies.append(f"Low Temp ({data.temperature}C)")

    # 2. AI Sensor Fusion Watchdog (Isolation Forest)
    if watchdog_model is not None and data.hr_raw > 10000 and data.spo2_raw > 10000:
        # Features must match the training order: ['temperature', 'accel_mag', 'hr_raw', 'spo2_raw']
        ai_input = np.array([[data.temperature, data.accel_mag, data.hr_raw, data.spo2_raw]])
        ai_prediction = watchdog_model.predict(ai_input)
        
        if ai_prediction[0] == -1: 
            risk_score += 5
            anomalies.append("AI WATCHDOG: Multi-Variable Vital Anomaly")

    return risk_score, anomalies

# --- API Endpoints ---
@app.post("/api/telemetry")
async def receive_telemetry(data: SensorPayload):
    try:
        document = data.dict()
        document["timestamp"] = datetime.utcnow()
        
        # Calculate Risk using the AI
        risk_score, detected_anomalies = evaluate_patient_risk(data)
        document["risk_score"] = risk_score
        document["anomalies"] = detected_anomalies
        
        # Save to DB
        result = collection.insert_one(document)
        document["alert_triggered"] = risk_score >= 8
        document["_id"] = str(result.inserted_id) 
        
        return {"status": "success", "data": document}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/latest/{patient_id}")
async def get_latest_vitals(patient_id: str):
    latest = collection.find_one(
        {"patient_id": patient_id}, 
        sort=[("timestamp", -1)],
        projection={"_id": 0} 
    )
    if not latest:
        raise HTTPException(status_code=404, detail="No data found for this patient")
    return latest

@app.get("/")
async def root():
    return {"status": "online", "message": "IoT Health Monitor API is running."}
