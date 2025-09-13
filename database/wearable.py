# wearable.py
import random
from datetime import datetime, timedelta
from database_manager import insert_health_metric

def insert_mock_metrics(user_id: int, hours: int = 48):
    """
    Insert 'hours' hourly datapoints into health_metrics for testing.
    """
    now = datetime.utcnow()
    for h in range(hours):
        ts = now - timedelta(hours=h)
        hr = random.randint(55, 110)
        steps = random.randint(0, 1500)
        calories = random.randint(50, 800)
        sleep_hours = round(random.uniform(0.0, 1.5), 2)  # per-hour chunk
        insert_health_metric(user_id, heart_rate=hr, steps=steps, calories=calories, sleep_hours=sleep_hours, timestamp=ts)
    print(f"Inserted {hours} mock health datapoints for user {user_id}.")
