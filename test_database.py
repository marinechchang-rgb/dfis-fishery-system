import os
import database
from schema import FisheryLogBatchSchema, FisheryLogSchema, CatchDetail

def run_tests():
    print("=== DFIS Database Categorization & Batch Verification Test ===")
    
    # 1. Initialize DB
    print("Initializing SQLite database...")
    database.init_db()
    if os.path.exists(database.DB_PATH):
        print(f"Success: Database file '{database.DB_PATH}' exists.")
    else:
        print("Error: Database file does not exist.")
        return
        
    # 2. Get and Print Default Categories
    print("\nRetrieving default database categories...")
    cats = database.get_database_categories()
    print("Categories found:", cats)
    if len(cats) >= 4:
        print("Success: Default 4 categories initialized correctly.")
    else:
        print(f"Error: Expected at least 4 default categories, found {len(cats)}.")
        return
        
    # 3. Add Custom Category
    new_cat = "圍網類漁業報表資料庫"
    print(f"\nAdding custom database category '{new_cat}'...")
    database.add_database_category(new_cat)
    cats_updated = database.get_database_categories()
    print("Updated categories list:", cats_updated)
    if new_cat in cats_updated:
        print("Success: Custom category added dynamically.")
    else:
        print("Error: Custom category was not found in database.")
        return

    # 4. Seed Mock Data
    print("\nSeeding sample logs data...")
    try:
        seeded = database.seed_sample_data()
        if seeded:
            print("Success: Sample data seeded into database.")
        else:
            print("Info: Seeding skipped (database already populated).")
    except Exception as e:
        print(f"Error during seeding: {e}")
        return
        
    # 5. Insert Log with Custom Category
    print(f"\nInserting a new test log tagged with custom category '{new_cat}'...")
    try:
        test_payload = {
            "database_type": new_cat,
            "vessel_name": "測試自主號",
            "log_date": "2026-06-15",
            "gear_type": "圍網",
            "gear_properties": {"mesh_size_inch": 3.0},
            "catch_records": [
                {
                    "species_raw_name": "石姥",
                    "species_standard_name": "波紋唇魚",
                    "weight_kg": 150.0,
                    "count_individual": 20,
                    "catch_properties": {"handwritten_correction": True}
                }
            ]
        }
        log_id = database.save_fishery_log(test_payload)
        print(f"Success: Saved test log. ID = {log_id}")
    except Exception as e:
        print(f"Error saving log: {e}")
        return

    # 6. Query Statistics Filtered by Category
    print(f"\nQuerying stats filtered by category '{new_cat}'...")
    df_yield_filtered = database.get_species_yield_data(database_type=new_cat)
    print("Filtered Yield Stats:")
    print(df_yield_filtered)
    
    # Check if correct fish was retrieved in the filter
    if not df_yield_filtered.empty and "波紋唇魚" in df_yield_filtered["species_standard_name"].values:
        print(f"Success: Statistics filtered correctly for database '{new_cat}'.")
    else:
        print("Error: Could not retrieve the filtered statistics properly.")
        return

    # 7. Batch Schema Validation
    print("\nVerifying FisheryLogBatchSchema Pydantic validation...")
    try:
        sample_batch = {
            "logs": [
                {
                    "database_type": "拖網類漁業報表資料庫",
                    "vessel_name": "小綿洋",
                    "log_date": "2026-06-11",
                    "gear_type": "拖網",
                    "gear_properties": {},
                    "catch_records": [
                        {
                            "species_raw_name": "石姥",
                            "species_standard_name": "波紋唇魚",
                            "weight_kg": 12.0,
                            "count_individual": 30,
                            "catch_properties": {}
                        }
                    ]
                },
                {
                    "database_type": "釣具類漁業報表資料庫",
                    "vessel_name": "小綿洋",
                    "log_date": "2026-06-12",
                    "gear_type": "一支釣",
                    "gear_properties": {},
                    "catch_records": [
                        {
                            "species_raw_name": "黃石斑",
                            "species_standard_name": "青石斑魚",
                            "weight_kg": 15.0,
                            "count_individual": 20,
                            "catch_properties": {}
                        }
                    ]
                }
            ]
        }
        validated = FisheryLogBatchSchema(**sample_batch)
        print("Success: FisheryLogBatchSchema validated batch log structure successfully.")
        print(f"Validated Logs Batch Count: {len(validated.logs)}")
    except Exception as e:
        print(f"Error validating batch schema: {e}")
        return

    print("\n=== All Database Categorization & Batch Tests Passed! ===")

if __name__ == "__main__":
    run_tests()
