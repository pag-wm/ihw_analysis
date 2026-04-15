import requests

# Testing the Annual Waste Summary Metadata
url = "https://data.texas.gov/api/views/79s2-9ack"
response = requests.get(url)

if response.status_code == 200:
    print("Successfully connected to Texas Open Data Portal!")
    print(f"Dataset Name: {response.json().get('name')}")
else:
    print(f"Connection failed: {response.status_code}")