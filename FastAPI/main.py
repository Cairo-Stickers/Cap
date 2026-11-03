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

# --- Raw Data Schema ---
class SensorPayload(BaseModel):
    patient_id: str
    temperature: float
    hr_raw: int      # Receiving raw Red LED light data
    spo2_raw: int    # Receiving raw IR LED light data
    accel_mag: float
    fall_flag: int
    lat: float
    lon: float

def evaluate_patient_risk(data: SensorPayload):
    risk_score = 0
    anomalies = []

    # 1. Fall Detection
    if data.fall_flag == 1:
        risk_score += 10
        anomalies.append("FALL DETECTED")

    # 2. Temperature Anomalies
    if data.temperature > 39.0:
        risk_score += 5
        anomalies.append(f"High Temp ({data.temperature}C)")
    elif data.temperature < 35.0 and data.temperature > 10.0:
        risk_score += 5
        anomalies.append(f"Low Temp ({data.temperature}C)")

    # 3. Optical Sensor Check (Ensures finger is on the sensor)
    if data.hr_raw < 100 or data.spo2_raw < 100:
        risk_score += 1
        anomalies.append("Optical Sensor Disconnected")

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
