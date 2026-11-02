from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from datetime import datetime
import os

app = FastAPI()

# Updated MongoDB connection string with the URL-encoded password
MONGO_URI = "mongodb+srv://RaspberryPI:f%252%23vAmwtaQ-c.C@m0.ejnni6f.mongodb.net/health_monitor?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI)

# Database and Collection setup
db = client.health_monitor
collection = db.sensor_data

# Define the exact data structure coming from the Pico W
class SensorPayload(BaseModel):
    patient_id: str
    temperature: float
    hr_raw: int
    spo2_raw: int
    accel_mag: float
    fall_flag: int
    lat: float
    lon: float

@app.post("/api/telemetry")
async def receive_telemetry(data: SensorPayload):
    try:
        # Convert the payload to a dictionary and add a cloud timestamp
        document = data.dict()
        document["timestamp"] = datetime.utcnow()
        
        # Insert into MongoDB
        result = collection.insert_one(document)
        
        # The AI anomaly detection model logic will be inserted here later
        
        return {"status": "success", "inserted_id": str(result.inserted_id)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/latest/{patient_id}")
async def get_latest_vitals(patient_id: str):
    # Endpoint for the caregiver app to pull the most recent data
    latest = collection.find_one(
        {"patient_id": patient_id}, 
        sort=[("timestamp", -1)],
        projection={"_id": 0} # Exclude the Mongo ObjectID from the JSON response
    )
    if not latest:
        raise HTTPException(status_code=404, detail="No data found for this patient")
    return latest
