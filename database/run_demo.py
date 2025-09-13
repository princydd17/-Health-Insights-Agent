# run_demo.py
from dotenv import load_dotenv
load_dotenv()

from database_manager import init_db, get_all_users, create_user
from wearable import insert_mock_metrics
from qr_manager import generate_emergency_qr, generate_health_metric_qrs

def main():
    print("Initializing DB...")
    init_db()
    users = get_all_users()
    if not users:
        print("No users found. Creating sample user...")
        uid = create_user("Alice Example", age=30, blood_type="O+", allergies="None", emergency_contact="Jane Doe +15550100")
    else:
        uid = users[0]["id"]
        print("Using existing user id", uid)

    print("Inserting mock wearable metrics...")
    insert_mock_metrics(uid, hours=48)

    print("Generating emergency QR...")
    generate_emergency_qr(uid)

    print("Generating health metric QR codes (latest 10)...")
    generate_health_metric_qrs(uid, limit=10)

    print("Demo complete. Check the 'qr_profiles/' folder for generated QR images.")

if __name__ == "__main__":
    main()
