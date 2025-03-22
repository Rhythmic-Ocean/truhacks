import requests

# Replace with your actual EDGAR API key
EDGAR_API_KEY = "c648209ab13171fdbf3ed042124bfea3e58ed379aa292e52011e74a4c169c4e2"

def fetch_edgar_monthly(location, year=2022):
    # Hypothetical EDGAR API endpoint (adjust if docs specify otherwise)
    url = f"https://edgar.jrc.ec.europa.eu/api/v8/emissions/CO2/monthly?country={location}&year={year}"
    headers = {"Authorization": f"Bearer {EDGAR_API_KEY}"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises error for bad status codes
        data = response.json()
        
        # Assuming response like {"emissions": {"01": 390, "02": 395, "03": 400, "04": 415, ...}}
        march = float(data["emissions"]["03"])  # Mt CO2
        april = float(data["emissions"]["04"])
        rate = april / march
        return rate
    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}")
        return 1.05  # Fallback rate
    except KeyError:
        print("Unexpected data format—check API response")
        return 1.05

def predict_future(current, location, months=12):
    rate = fetch_edgar_monthly(location.upper())
    predictions = [current]
    for _ in range(months - 1):
        predictions.append(predictions[-1] * rate)
    return [round(p, 2) for p in predictions]

# Test function
def test_edgar_predictor():
    print("EDGAR API Test - Future Footprint Predictor")
    print("Enter your current weekly CO2 footprint (kg):")
    current = float(input("> "))
    print("Enter your location (e.g., US, NP, DE):")
    location = input("> ")
    
    # Fetch rate and predict
    future = predict_future(current, location)
    
    # Print results
    print(f"\nStarting Footprint (March 2025): {future[0]} kg CO2/week")
    print("Monthly Predictions:")
    for i, value in enumerate(future, 1):
        print(f"Month {i}: {value} kg CO2/week")
    print(f"Year-End (Month 12): {future[-1]} kg CO2/week")

if __name__ == "__main__":
    test_edgar_predictor()