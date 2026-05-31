import random
from fastapi import FastAPI, UploadFile, File, Form
import pandas as pd
import numpy as np

app = FastAPI(title="Smart Waste AI Engine API")

@app.get("/")
def health_check():
    return {"status": "ok", "service": "AI Engine"}

# 1. Waste Image Classification Placeholder
@app.post("/ai/classify_waste")
async def classify_waste(file: UploadFile = File(...)):
    """
    Mock AI classification endpoint.
    In production, this would use a PyTorch/TensorFlow model (e.g., ResNet) 
    to analyze the image for waste categories.
    """
    categories = ["Plastic", "Organic", "Mixed"]
    sizes = ["Small", "Medium", "Large"]
    severities = ["Low", "Medium", "Critical"]

    predicted_category = random.choice(categories)
    predicted_size = random.choice(sizes)
    predicted_severity = random.choice(severities)

    # Calculate mock health risk score
    risk_score = round(random.uniform(0, 10), 2)

    return {
        "waste_type": predicted_category,
        "garbage_size": predicted_size,
        "severity_level": predicted_severity,
        "health_risk_score": risk_score
    }

# 2. Complaint Priority Scoring Placeholder
@app.post("/ai/score_priority")
def score_priority(complaint_data: dict):
    # Dummy scoring based on inputs
    return {"complaint_id": complaint_data.get("id", 1), "priority_score": 8.5}

# 3. Intelligent Route Optimization (Greedy TSP)
@app.post("/ai/optimize_route")
def optimize_route(data: dict):
    """
    Expects data: {
      "driver_location": {"lat": 12.1, "lng": 77.1},
      "complaints": [{"id": 1, "lat": 12.2, "lng": 77.2}, ...]
    }
    Returns the optimal sequence using a nearest-neighbor approach.
    """
    driver_loc = data.get("driver_location")
    complaints = data.get("complaints", [])
    
    if not complaints:
        return {"optimized_route": []}

    def dist(p1, p2):
        return ((p1['lat'] - p2['lat'])**2 + (p1['lng'] - p2['lng'])**2)**0.5

    current_pos = driver_loc
    optimized_route = []
    unvisited = complaints[:]

    while unvisited:
        # Find nearest unvisited complaint
        nearest = min(unvisited, key=lambda c: dist(current_pos, c))
        optimized_route.append(nearest)
        current_pos = nearest
        unvisited.remove(nearest)

    return {
        "optimized_route_ids": [c['id'] for c in optimized_route],
        "full_route": optimized_route,
        "algo": "Greedy Nearest Neighbor (TSP Approximation)"
    }
# 4. Waste Growth Predictive Model
@app.get("/ai/forecast_waste")
def forecast_waste():
    """
    Returns predicted waste volumes for the next 7 days.
    Used by the Admin Dashboard chart.
    """
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    # Simulated exponential growth logic
    forecast = [65, 78, 92, 115, 140, 185, 230]
    return {
        "labels": days,
        "forecast": forecast,
        "recommendation": "High volume predicted for Fri/Sat. Increase fleet capacity by 20%."
    }

@app.get("/ai/forecast_waste/{zone_id}")
def forecast_waste_zone(zone_id: str):
    return {
        "zone": zone_id,
        "predicted_growth": "15%",
        "forecast_period": "Next 7 Days"
    }

# 5. Fraud Detection — Before/After Photo Similarity Check
@app.post("/ai/detect_fraud")
async def detect_fraud(proof_photo: UploadFile = File(...), complaint_id: int = Form(...)):
    """
    Compares a driver's 'after' photo with the original complaint to detect fraud.

    PRODUCTION UPGRADE PATH:
    Replace the heuristic below with:
      - OpenCV SSIM: skimage.metrics.structural_similarity(img1, img2)
      - If similarity > 0.85 (85%), flag as fraud.

    For now, we mock this using file-size as a naive proxy:
    If the proof photo is an unusually small file (< 5KB), it's likely a cached/copied image.
    In a real deployment, the original complaint image URL would be fetched and compared via SSIM.
    """
    proof_bytes = await proof_photo.read()
    file_size_kb = len(proof_bytes) / 1024

    # Mock heuristic: very small files are suspicious (screenshots, duplicates)
    # Real implementation would compare pixel-level similarity with stored complaint image
    similarity = round(random.uniform(0.1, 0.5), 2)  # Default: photo is different (safe)
    is_fraud = False

    if file_size_kb < 5:  # Suspiciously small — likely a duplicate or screenshot
        similarity = round(random.uniform(0.87, 0.98), 2)
        is_fraud = True

    return {
        "is_fraud": is_fraud,
        "similarity": similarity,
        "file_size_kb": round(file_size_kb, 2),
        "complaint_id": complaint_id,
        "method": "mock_heuristic_v1 (upgrade to SSIM for production)"
    }
