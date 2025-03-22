from flask import Flask, render_template, request
import requests

app = Flask(__name__)

CLIMATIQ_API_KEY = "YOUR_API_KEY_HERE"
CLIMATIQ_BATCH_URL = "https://api.climatiq.io/batch"
HEADERS = {"Authorization": f"Bearer {CLIMATIQ_API_KEY}"}
emissions = {"petrol_miles": 0.4, "meat_meals": 2.5}

def calculate_footprint(data):
    vehicle_type = data.get("vehicle_type", "petrol")
    miles = float(data.get("miles", 0))
    meat_meals = float(data.get("meat_meals", 0))
    electricity = float(data.get("electricity", 0)) / 4
    location = data.get("location", "us").upper()
    flight_km = float(data.get("flight_km", 0)) / 52
    train_km = float(data.get("train_km", 0))

    batch_request = []
    contributions = {}

    if vehicle_type == "electric" and miles > 0:
        batch_request.append({"emission_factor": {"activity_id": "passenger_vehicle-vehicle_type_car-fuel_source_electric", "region": location}, "parameters": {"distance": miles, "distance_unit": "mi"}})
    elif miles > 0:
        contributions["vehicle"] = miles * emissions["petrol_miles"]

    if electricity > 0:
        batch_request.append({"emission_factor": {"activity_id": "electricity-supply_grid-source_residual_mix", "region": location}, "parameters": {"energy": electricity, "energy_unit": "kWh"}})

    if flight_km > 0:
        haul = "long_haul_gt_3700km" if flight_km * 52 > 3700 else "short_haul_lt_3700km"
        batch_request.append({"emission_factor": {"activity_id": f"passenger_flight-route_type_international-aircraft_type_na-distance_{haul}-class_economy-rf_included", "region": location}, "parameters": {"distance": flight_km, "distance_unit": "km"}})

    if train_km > 0:
        batch_request.append({"emission_factor": {"activity_id": "passenger_train-route_type_na-fuel_source_electricity", "region": location}, "parameters": {"distance": train_km, "distance_unit": "km"}})

    total = contributions.get("vehicle", 0)
    if batch_request:
        response = requests.post(CLIMATIQ_BATCH_URL, json=batch_request, headers=HEADERS)
        if response.status_code == 200:
            results = response.json()
            idx = 0
            if vehicle_type == "electric" and miles > 0:
                contributions["vehicle"] = results[idx]["co2e"]
                idx += 1
            if electricity > 0:
                contributions["electricity"] = results[idx]["co2e"]
                idx += 1
            if flight_km > 0:
                contributions["flights"] = results[idx]["co2e"]
                idx += 1
            if train_km > 0:
                contributions["trains"] = results[idx]["co2e"]
            total += sum(result["co2e"] for result in results)

    contributions["meat"] = meat_meals * emissions["meat_meals"]
    total += contributions["meat"]
    return total, contributions

def predict_future(current, months=12):
    predictions = [current]
    for _ in range(months - 1):
        predictions.append(predictions[-1] * 1.05)
    return [round(p, 2) for p in predictions]

def score_reduction(current, scenario):
    reduction = current - scenario
    return min(100, max(0, int(reduction / current * 100))) if current > 0 else 0

def find_best_tip(contributions, location, vehicle_type):
    max_emitter = max(contributions.items(), key=lambda x: x[1], default=("none", 0))
    emitter, value = max_emitter
    tips = {
        "vehicle": "Cut car miles—try biking or an electric car!" if vehicle_type == "petrol" else "Your electric car’s great—reduce miles!",
        "electricity": "Switch to renewables—your grid’s dirty!" if location == "US" else "Lower your kWh—every bit helps!",
        "flights": "Reduce flights—opt for trains or virtual meetings!",
        "trains": "Your trains are low-impact—keep it up or cut other travel!",
        "meat": "Go meatless a few days—huge impact!"
    }
    return tips.get(emitter, "Small changes add up—start anywhere!")

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/calculate", methods=["POST"])
def calculate():
    current_footprint, contributions = calculate_footprint(request.form)
    future_footprint = predict_future(current_footprint)
    scenario_data = dict(request.form)
    scenario_data["miles"] = str(float(request.form.get("miles", 0)) * 0.5)
    scenario_footprint, _ = calculate_footprint(scenario_data)
    scenario_future = predict_future(scenario_footprint)
    score = score_reduction(current_footprint, scenario_footprint)
    tip = find_best_tip(contributions, request.form.get("location", "us").upper(), request.form.get("vehicle_type", "petrol"))
    return render_template("index.html", 
                          current=current_footprint, 
                          future=future_footprint, 
                          scenario=scenario_future, 
                          score=score, 
                          tip=tip,
                          calculated=True, 
                          original_score=score) 

@app.route("/whatif", methods=["POST"])
def whatif():
    original_current = float(request.form.get("original_current", 0))
    original_score = int(request.form.get("original_score", 0))
 
    whatif_footprint, contributions = calculate_footprint(request.form)
    whatif_future = predict_future(whatif_footprint)
    scenario_data = dict(request.form)
    scenario_data["miles"] = str(float(request.form.get("miles", 0)) * 0.5)
    whatif_scenario, _ = calculate_footprint(scenario_data)
    whatif_score = score_reduction(whatif_footprint, whatif_scenario)
    tip = find_best_tip(contributions, request.form.get("location", "us").upper(), request.form.get("vehicle_type", "petrol"))
    
    return render_template("index.html",
                          current=original_current,  # Original results
                          future=predict_future(original_current),
                          scenario=predict_future(float(request.form.get("original_scenario", original_current))),
                          score=original_score,
                          tip=tip,
                          calculated=True,
                          original_score=original_score,
                          whatif_current=whatif_footprint,  # New "What If" results
                          whatif_future=whatif_future,
                          whatif_score=whatif_score)

if __name__ == "__main__":
    app.run(debug=True)