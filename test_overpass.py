import requests

query = """
[out:json][timeout:30];
area["ISO3166-1"="IN"][admin_level=2]->.india;
nwr["amenity"="hospital"](area.india);
out center 5;
"""

url = "https://overpass-api.nextzen.org/api/interpreter"

headers = {
    "User-Agent": "HEATWATCH/1.0 (OSM data ingestion for academic project)"
}

print("Testing Overpass API...")
print("URL:", url)

try:
    response = requests.post(
        url,
        data={"data": query},
        headers=headers,
        timeout=60
    )

    print("HTTP STATUS:", response.status_code)
    print("CONTENT TYPE:", response.headers.get("content-type"))
    print("RESPONSE:")
    print(response.text[:2000])

except Exception as e:
    print("ERROR:", type(e).__name__)
    print(e)