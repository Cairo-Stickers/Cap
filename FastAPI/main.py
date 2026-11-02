from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from datetime import datetime
import os

app = FastAPI()

# Replace with your actual MongoDB connection string
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://<username>:<password>@cluster0.../test")
client = MongoClient(MONGO_URI)

# Create a database called 'health_monitor' and a collection called 'sensor_data'
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
        
        # Here is where the AI model prediction will run later
        # is_anomaly = ai_model.predict([data.temperature, data.hr_raw, ...])
        
        return {"status": "success", "inserted_id": str(result.inserted_id)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/latest/{patient_id}")
async def get_latest_vitals(patient_id: str):
    # Endpoint for the caregiver app to pull the most recent data
    latest = collection.find_one(
        {"patient_id": patient_id}, 
        sort=[("timestamp", -1)],
        projection={"_id": 0} # Exclude the Mongo ObjectID from the response
    )
    if not latest:
        raise HTTPException(status_code=404, detail="No data found for this patient")
    return latest