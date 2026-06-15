import os
import database
from schema import FisheryLogSchema, CatchDetail

def run_tests():
    print("=== DFIS Database and Schema Verification Test ===")
    
    # 1. Initialize DB
    print("Initializing SQLite database...")
    database.init_db()
    if os.path.exists(database.DB_PATH):
        print(f"Success: Database file '{database.DB_PATH}' exists.")
    else:
        print("Error: Database file does not exist.")
        return
        
    # 2. Seed Mock Data
    print("\nSeeding sample data...")
    try:
        seeded = database.seed_sample_data()
        if seeded:
            print("Success: Sample data seeded into database.")
        else:
            print("Info: Seeding skipped (database already populated).")
    except Exception as e:
        print(f"Error during seeding: {e}")
        return
        
    # 3. Retrieve Species Yield Stats
    print("\nRetrieving species yield statistics...")
    df_yield = database.get_species_yield_data()
    print("Species Yield DataFrame:")
    print(df_yield)
    
    # 4. Retrieve Gear Distribution Stats
    print("\nRetrieving gear distribution statistics...")
    df_gear = database.get_gear_distribution_data()
    print("Gear Distribution DataFrame:")
    print(df_gear)
    
    # 5. Pydantic Verification
    print("\nVerifying Pydantic schema validation...")
    try:
        sample_log = {
            "vessel_name": "測試新興號",
            "log_date": "2026-06-11",
            "gear_type": "拖網",
            "gear_properties": {"mesh_size_inch": 2.5},
            "catch_records": [
                {
                    "species_raw_name": "臭肚",
                    "species_standard_name": "臭肚魚",
                    "weight_kg": 45.2,
                    "count_individual": 60,
                    "catch_properties": {"water_temperature_c": 24.5}
                }
            ]
        }
        validated = FisheryLogSchema(**sample_log)
        print("Success: FisheryLogSchema validated sample_log successfully.")
        print(f"Validated Vessel Name: {validated.vessel_name}")
        print(f"Validated Catch Records Count: {len(validated.catch_records)}")
    except Exception as e:
        print(f"Error during schema validation: {e}")
        return

    print("\n=== All Database and Schema Tests Passed! ===")

if __name__ == "__main__":
    run_tests()
