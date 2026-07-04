import requests
import os
from dotenv import load_dotenv
from pathlib import Path

dotenv_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

API_BASE_URL = os.getenv("API_BASE_URL")

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
}

def get_all_events():
    """Fetches all events from the API."""
    response = requests.get(API_BASE_URL, headers=HEADERS)
    response.raise_for_status()  # Raise an exception for bad status codes
    return response.json()

def get_events_by_date(date):
    """Fetches events for a specific date from the API."""
    params = {"start_date": date}
    response = requests.get(API_BASE_URL, params=params, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def get_event_by_id(event_id):
    """Fetches a single event by its ID from the API."""
    params = {"id": event_id}
    response = requests.get(API_BASE_URL, params=params, headers=HEADERS)
    response.raise_for_status()
    return response.json()
