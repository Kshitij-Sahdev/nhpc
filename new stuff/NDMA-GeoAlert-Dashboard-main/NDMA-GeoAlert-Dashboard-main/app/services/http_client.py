import requests

session = requests.Session()
session.headers.update({"User-Agent": "NDMA-Alert-Aggregator/1.0"})
