from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from datetime import datetime
import os

app = FastAPI()

# --- Database Setup ---
MONGO_URI = "mongodb+srv://RaspberryPI:f%252%23vAmwtaQ-c.C@m0.ejnni6f.mongodb.net/health_monitor?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI)
db = client.health_monitor
collection = db.sensor_data

# --- 1. Updated Schema for Edge Computing DSP ---
class SensorPayload(BaseModel):
    patient_id: str
    temperature: float
    bpm: int         # Updated from hr_raw
    spo2: float      # Updated from spo2_raw
    accel_mag: float
    fall_flag: int
    lat: float
    lon: float

def evaluate_patient_risk(data: SensorPayload):
    """
    Expert System AI: Now evaluates actual human metrics.
    """
    risk_score = 0
    anomalies = []

    if data.fall_flag == 1:
        risk_score += 10
        anomalies.append("FALL DETECTED")

    if data.temperature > 39.0:
        risk_score += 5
        anomalies.append(f"High Temp ({data.temperature}C)")
    elif data.temperature < 35.0 and data.temperature > 10.0:
        risk_score += 5
        anomalies.append(f"Low Temp ({data.temperature}C)")

    # --- 2. Updated rules for SpO2% and BPM ---
    if data.spo2 > 0 and data.spo2 < 90.0: 
        risk_score += 4
        anomalies.append(f"Low Oxygen ({data.spo2}%)")
        
    if data.bpm > 130:
        risk_score += 3
        anomalies.append(f"High Heart Rate ({data.bpm} BPM)")
    elif data.bpm > 0 and data.bpm < 40:
        risk_score += 3
        anomalies.append(f"Low Heart Rate ({data.bpm} BPM)")

    return risk_score, anomalies

@app.post("/api/telemetry")
async def receive_telemetry(data: SensorPayload):
    try:
        document = data.dict()
        document["timestamp"] = datetime.utcnow()
        
        # Calculate Risk
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
