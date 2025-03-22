
import requests

CLIMATIQ_API_KEY = "9AVA99KVQ57P59J9NM9QGJ7TVW"  
CLIMATIQ_BATCH_URL = "https://api.climatiq.io/batch"
HEADERS = {"Authorization": f"Bearer {CLIMATIQ_API_KEY}"}
emissions = {"petrol_miles": 0.4}  


def calculate_footprint(data):
    vehicle_type = data.get("vehicle_type", "petrol")
    miles = float(data.get("miles", 0))
    chicken_meals = float(data.get("chicken_meals", 0))
    beef_meals = float(data.get("beef_meals", 0))
    other_meals = float(data.get("other_meals", 0))
    electricity = float(data.get("electricity", 0)) / 4
    location = data.get("location", "us").upper()
    flight_km = float(data.get("flight_km", 0)) / 52
    train_km = float(data.get("train_km", 0))

    batch_request = []
    contributions = {}

    if vehicle_type == "electric" and miles > 0:
        electric = miles/3.5
        batch_request.append({"emission_factor": {"activity_id": "electricity-supply_grid-source_supplier_mix", "data_version": "^6", "region": location}, "parameters": {"energy": electric, "energy_unit": "kWh"}})
    elif miles > 0:
        contributions["vehicle"] = miles * emissions["petrol_miles"]

    if electricity > 0:
        batch_request.append({"emission_factor": {"activity_id": "electricity-supply_grid-source_supplier_mix", "data_version": "^6", "region": location}, "parameters": {"energy": electricity, "energy_unit": "kWh"}})

    if flight_km > 0:
        haul = "long_haul_gt_3700km" if flight_km * 52 > 3700 else "short_haul_lt_3700km"
        batch_request.append({"emission_factor": {"activity_id": f"passenger_flight-route_type_international-aircraft_type_na-distance_{haul}-class_economy-rf_included", "data_version": "^6", "region": "UN"}, "parameters": {"distance": flight_km, "distance_unit": "km"}})
        emissions["flight_km"] = 0.2  

    if train_km > 0:
        batch_request.append({"emission_factor": {"activity_id": "passenger_train-route_type_na-fuel_source_electricity", "data_version": "^6", "region": "UN"}, "parameters": {"distance": train_km, "distance_unit": "km"}})
        emissions["train_km"] = 0.05  

    total = contributions.get("vehicle", 0)
    if batch_request:
        response = requests.post(CLIMATIQ_BATCH_URL, json=batch_request, headers=HEADERS)
        print("Batch Request:", batch_request)  # Debug: see what’s sent
        if response.status_code == 200:
            results = response.json()["results"]
            print("API Response:", results)  # Debug: see full response
            for i, result in enumerate(results):
                if "error" in result:
                    print(f"Error in batch item {i}: {result['message']}")
            idx = 0
            if vehicle_type == "electric" and miles > 0:
                contributions["vehicle"] = results[idx]["co2e"] if idx < len(results) and "co2e" in results[idx] else 0
                idx += 1
            if electricity > 0:
                contributions["electricity"] = results[idx]["co2e"] if idx < len(results) and "co2e" in results[idx] else 0
                idx += 1
            if flight_km > 0:
                contributions["flights"] = results[idx]["co2e"] if idx < len(results) and "co2e" in results[idx] else flight_km * emissions["flight_km"]
                idx += 1
            if train_km > 0:
                contributions["trains"] = results[idx]["co2e"] if idx < len(results) and "co2e" in results[idx] else train_km * emissions["train_km"]
            total += sum(result["co2e"] for result in results if "co2e" in result)

    emissions["chicken_meals"] = 2.0  
    emissions["beef_meals"] = 5.0     
    emissions["other_meals"] = 3.0    
    contributions["meat"] = (chicken_meals * emissions["chicken_meals"] +
                            beef_meals * emissions["beef_meals"] +
                            other_meals * emissions["other_meals"])
    total += contributions["meat"]
    return total, contributions

def predict_future(current, months=12):
    predictions = [current]
    for _ in range(months - 1):
        predictions.append(predictions[-1] * 1.05)
    return [round(p, 2) for p in predictions]

def score_reduction(current, data, contributions):
    if current <= 0:
        return 0
    scenario_data = dict(data)
   
    original_miles = float(data.get("miles", 0))
    if original_miles > 0:
        scenario_data["miles"] = str(original_miles * 0.5)
        scenario_miles, _ = calculate_footprint(scenario_data)
        score_miles = (current - scenario_miles) / current * 100
        scenario_data["miles"] = str(original_miles)
    else:
        score_miles = 0
    
    original_flights = float(data.get("flight_km", 0))
    if original_flights > 0:
        scenario_data["flight_km"] = str(original_flights * 0.5)
        scenario_flights, _ = calculate_footprint(scenario_data)
        score_flights = (current - scenario_flights) / current * 100
        scenario_data["flight_km"] = str(original_flights)
    else:
        score_flights = 0

    original_chicken = float(data.get("chicken_meals", 0))
    original_beef = float(data.get("beef_meals", 0))
    original_other = float(data.get("other_meals", 0))
    if original_chicken + original_beef + original_other > 0:
        scenario_data["chicken_meals"] = str(original_chicken * 0.5)
        scenario_data["beef_meals"] = str(original_beef * 0.5)
        scenario_data["other_meals"] = str(original_other * 0.5)
        scenario_meat, _ = calculate_footprint(scenario_data)
        score_meat = (current - scenario_meat) / current * 100
        scenario_data["chicken_meals"] = str(original_chicken)
        scenario_data["beef_meals"] = str(original_beef)
        scenario_data["other_meals"] = str(original_other)
    else:
        score_meat = 0
   
    original_electricity = float(data.get("electricity", 0))
    if original_electricity > 0:
        scenario_data["electricity"] = str(original_electricity * 0.5)
        scenario_electricity, _ = calculate_footprint(scenario_data)
        score_electricity = (current - scenario_electricity) / current * 100
        scenario_data["electricity"] = str(original_electricity)
    else:
        score_electricity = 0
    
    best_score = max(score_miles, score_flights, score_meat, score_electricity, 0)
    return min(100, int(best_score))

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