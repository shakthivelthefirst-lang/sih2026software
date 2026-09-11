import sqlite3
import random
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'survi.db'

def run():
    print(f"Connecting to database: {DB}")
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Add columns if they don't exist
    try:
        c.execute("ALTER TABLE parcels ADD COLUMN owner_name TEXT;")
    except sqlite3.OperationalError:
        pass # Column might already exist
    
    try:
        c.execute("ALTER TABLE parcels ADD COLUMN mobile_number TEXT;")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE parcels ADD COLUMN notification_status TEXT DEFAULT 'PENDING';")
    except sqlite3.OperationalError:
        pass

    conn.commit()

    # Fetch all parcel IDs
    c.execute("SELECT id FROM parcels ORDER BY id ASC")
    parcels = c.fetchall()
    
    if not parcels:
        print("No parcels found in database.")
        conn.close()
        return

    print(f"Total parcels found: {len(parcels)}")

    real_numbers = [
        "6379377627",
        "6379189625",
        "7397122338",
        "6369904751",
        "7904448751",
        "9171255999"
    ]

    first_names = ["Ramesh", "Suresh", "Lakshmi", "Karthik", "Priya", "Anand", "Meena", "Kumar", "Vijay", "Deepa"]
    last_names = ["Rao", "Nair", "Iyer", "Gounder", "Thevar", "Chettiar", "Naidu", "Pillai", "Reddy", "Singh"]

    def random_name():
        return f"{random.choice(first_names)} {random.choice(last_names)}"
    
    def random_number():
        # Start with 9, 8, 7, or 6 and 9 random digits
        prefix = random.choice(["9", "8", "7", "6"])
        return prefix + "".join(str(random.randint(0, 9)) for _ in range(9))

    updates = []
    
    for idx, (parcel_id,) in enumerate(parcels):
        name = random_name()
        
        if idx < len(real_numbers):
            mobile = real_numbers[idx]
            # Mark internally as REAL_DATASET_SIMULATION via remarks if possible, 
            # or we can just update the columns.
            remarks = "REAL_DATASET_SIMULATION"
        else:
            mobile = random_number()
            remarks = "SYNTHETIC_DATASET"
        
        status = "PENDING"
        
        # We append (owner_name, mobile_number, notification_status, remarks, parcel_id)
        updates.append((name, mobile, status, remarks, parcel_id))

    print("Updating parcels...")
    c.executemany("""
        UPDATE parcels 
        SET owner_name = ?, mobile_number = ?, notification_status = ?, remarks = ? 
        WHERE id = ?
    """, updates)

    conn.commit()
    conn.close()
    print("Database update complete.")

if __name__ == "__main__":
    run()
