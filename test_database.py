import os
import database
from fishery_schema import FisheryLogBatchSchema, FisheryLogSchema, CatchDetail

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

    # 8. Test Ports, Vessels, Species CRUD
    print("\nTesting Ports, Vessels, and Species CRUD...")
    try:
        # Ports CRUD
        database.add_port("測試港口", "測試縣市")
        df_ports = database.get_ports()
        assert "測試港口" in df_ports["name"].values, "Add port failed"
        port_id = df_ports[df_ports["name"] == "測試港口"]["id"].values[0]
        database.delete_port(port_id)
        df_ports = database.get_ports()
        assert "測試港口" not in df_ports["name"].values, "Delete port failed"
        print("- Ports CRUD: PASSED")

        # Vessels CRUD
        database.add_vessel("測試船隻", "CT9-9999")
        df_vessels = database.get_vessels()
        assert "測試船隻" in df_vessels["name"].values, "Add vessel failed"
        vessel_id = df_vessels[df_vessels["name"] == "測試船隻"]["id"].values[0]
        database.delete_vessel(vessel_id)
        df_vessels = database.get_vessels()
        assert "測試船隻" not in df_vessels["name"].values, "Delete vessel failed"
        print("- Vessels CRUD: PASSED")

        # Species CRUD
        database.add_species("測試魚種", "T001", "Test", "test")
        df_species = database.get_species()
        assert "測試魚種" in df_species["chinese_name"].values, "Add species failed"
        species_id = df_species[df_species["chinese_name"] == "測試魚種"]["id"].values[0]
        database.delete_species(species_id)
        df_species = database.get_species()
        assert "測試魚種" not in df_species["chinese_name"].values, "Delete species failed"
        print("- Species CRUD: PASSED")
    except Exception as e:
        print(f"Error testing parameters CRUD: {e}")
        return

    # 9. Test Biological Parameters CRUD
    print("\nTesting Biological Parameters (Reproduction) CRUD...")
    try:
        # Save single record
        bio_rec = {
            "collection_date": "2026-06-16",
            "collection_id": "Tg-TestCRUD",
            "port": "南方澳",
            "vessel_name": "小綿洋",
            "form_code": "1017",
            "species_name": "大棘大眼鯛",
            "sex": "雄性",
            "maturity": "成熟",
            "total_length_mm": 210.5,
            "weight_g": 180.2,
            "gsi": 2.55,
            "remarks": "測試備註"
        }
        rec_id = database.save_biological_parameter(bio_rec)
        df_bio = database.get_biological_parameters(species="大棘大眼鯛")
        assert "Tg-TestCRUD" in df_bio["collection_id"].values, "Save biological parameter failed"
        
        # Update record
        bio_rec["id"] = rec_id
        bio_rec["remarks"] = "已更新備註"
        database.save_biological_parameter(bio_rec)
        df_bio = database.get_biological_parameters(species="大棘大眼鯛")
        updated_remarks = df_bio[df_bio["id"] == rec_id]["remarks"].values[0]
        assert updated_remarks == "已更新備註", "Update biological parameter failed"
        
        # Delete record
        database.delete_biological_parameter(rec_id)
        df_bio = database.get_biological_parameters(species="大棘大眼鯛")
        assert "Tg-TestCRUD" not in df_bio["collection_id"].values, "Delete biological parameter failed"
        print("- Single Biological Parameter CRUD: PASSED")

        # Save batch records
        bio_batch = [
            {
                "collection_date": "2026-06-16",
                "collection_id": "Tg-BatchTest1",
                "port": "南方澳",
                "vessel_name": "小綿洋",
                "form_code": "1017",
                "species_name": "大棘大眼鯛",
                "sex": "雌性",
                "maturity": "成熟",
                "total_length_mm": 220.0,
                "weight_g": 190.0,
                "gsi": 3.10,
                "remarks": ""
            },
            {
                "collection_date": "2026-06-16",
                "collection_id": "Tg-BatchTest2",
                "port": "南方澳",
                "vessel_name": "小綿洋",
                "form_code": "1017",
                "species_name": "大棘大眼鯛",
                "sex": "雄性",
                "maturity": "稍有精液",
                "total_length_mm": 200.0,
                "weight_g": 150.0,
                "gsi": 1.20,
                "remarks": ""
            }
        ]
        database.save_biological_parameters_batch(bio_batch)
        df_bio = database.get_biological_parameters(species="大棘大眼鯛")
        assert "Tg-BatchTest1" in df_bio["collection_id"].values, "Batch save failed for record 1"
        assert "Tg-BatchTest2" in df_bio["collection_id"].values, "Batch save failed for record 2"
        
        # Cleanup batch
        id1 = df_bio[df_bio["collection_id"] == "Tg-BatchTest1"]["id"].values[0]
        id2 = df_bio[df_bio["collection_id"] == "Tg-BatchTest2"]["id"].values[0]
        database.delete_biological_parameter(id1)
        database.delete_biological_parameter(id2)
        print("- Batch Biological Parameter CRUD: PASSED")
    except Exception as e:
        print(f"Error testing biological parameters CRUD: {e}")
        return

    print("\n=== All Database Categorization, Parameters CRUD & Batch Tests Passed! ===")

if __name__ == "__main__":
    run_tests()

