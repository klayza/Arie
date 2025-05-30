import requests
import json

query = "yo mama"
url = "http://localhost:5000/generate_code?input=" + query.replace(" ", "%20")
response = requests.get(url)

data = response.json()
print(data["code"])
