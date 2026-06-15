import sqlite3
import json
import os
import pandas as pd
from typing import Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fishery_standard.db")

def get_db_connection():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if tables do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create fishery_logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fishery_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vessel_name TEXT NOT NULL,
            log_date TEXT NOT NULL,
            gear_type TEXT NOT NULL,
            gear_properties TEXT, -- JSON string
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create catch_records table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS catch_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_id INTEGER NOT NULL,
            species_raw_name TEXT NOT NULL,
            species_standard_name TEXT NOT NULL,
            weight_kg REAL,
            count_individual INTEGER,
            catch_properties TEXT, -- JSON string
            FOREIGN KEY (log_id) REFERENCES fishery_logs(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

def save_fishery_log(log_data: Dict[str, Any]) -> int:
    """
    Saves the fishery log and all its catch records in a single transaction.
    Returns the newly inserted log_id.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Insert main log metadata
        gear_props_json = json.dumps(log_data.get("gear_properties", {}), ensure_ascii=False)
        cursor.execute("""
            INSERT INTO fishery_logs (vessel_name, log_date, gear_type, gear_properties)
            VALUES (?, ?, ?, ?)
        """, (
            log_data["vessel_name"],
            log_data["log_date"],
            log_data["gear_type"],
            gear_props_json
        ))
        log_id = cursor.lastrowid
        
        # Insert species catch records
        for record in log_data.get("catch_records", []):
            catch_props_json = json.dumps(record.get("catch_properties", {}), ensure_ascii=False)
            cursor.execute("""
                INSERT INTO catch_records (log_id, species_raw_name, species_standard_name, weight_kg, count_individual, catch_properties)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                log_id,
                record["species_raw_name"],
                record["species_standard_name"],
                record.get("weight_kg"),
                record.get("count_individual"),
                catch_props_json
            ))
            
        conn.commit()
        return log_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_species_yield_data() -> pd.DataFrame:
    """
    Fetches total yield (weight_kg) aggregated by standard fish species.
    """
    conn = get_db_connection()
    query = """
        SELECT species_standard_name, SUM(weight_kg) as total_weight_kg
        FROM catch_records
        WHERE weight_kg IS NOT NULL
        GROUP BY species_standard_name
        ORDER BY total_weight_kg DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_gear_distribution_data() -> pd.DataFrame:
    """
    Fetches counts and total weight aggregated by gear/fishing method.
    """
    conn = get_db_connection()
    query = """
        SELECT l.gear_type, COUNT(DISTINCT l.id) as log_count, SUM(c.weight_kg) as total_weight_kg
        FROM fishery_logs l
        LEFT JOIN catch_records c ON l.id = c.log_id
        GROUP BY l.gear_type
        ORDER BY log_count DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def seed_sample_data() -> bool:
    """Seeds some realistic mock data into the database if empty."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if we already have records
    cursor.execute("SELECT COUNT(*) FROM fishery_logs")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return False # already seeded
        
    sample_logs = [
        {
            "vessel_name": "聖漁豐168",
            "log_date": "2026-05-10",
            "gear_type": "拖網",
            "gear_properties": {"mesh_size_inch": 2.0, "net_length_m": 120, "tow_duration_hr": 3.5},
            "catches": [
                {"species_raw_name": "白帶", "species_standard_name": "肥帶鰏", "weight_kg": 145.5, "count_individual": 80, "props": {"size_group": "大"}},
                {"species_raw_name": "鯖魚", "species_standard_name": "花腹鯖", "weight_kg": 230.0, "count_individual": 450, "props": {"quality": "優"}},
                {"species_raw_name": "秋刀", "species_standard_name": "秋刀魚", "weight_kg": 85.0, "count_individual": 200, "props": {}}
            ]
        },
        {
            "vessel_name": "小綿洋號",
            "log_date": "2026-05-12",
            "gear_type": "延繩釣",
            "gear_properties": {"total_hook_hours": 8.0, "water_depth_m": 85, "bait_type": "秋刀魚"},
            "catches": [
                {"species_raw_name": "如志", "species_standard_name": "加志", "weight_kg": 320.0, "count_individual": 40, "props": {"fork_length_mean_mm": 350}},
                {"species_raw_name": "臭肚", "species_standard_name": "臭肚魚", "weight_kg": 115.0, "count_individual": 150, "props": {}}
            ]
        },
        {
            "vessel_name": "新海龍號",
            "log_date": "2026-05-15",
            "gear_type": "一支釣",
            "gear_properties": {"water_depth_m": 45, "tide": "漲潮"},
            "catches": [
                {"species_raw_name": "石斑", "species_standard_name": "點帶石斑魚", "weight_kg": 75.0, "count_individual": 12, "props": {"live_status": "活體"}},
                {"species_raw_name": "紅魽", "species_standard_name": "杜氏鰤", "weight_kg": 180.0, "count_individual": 22, "props": {}}
            ]
        },
        {
            "vessel_name": "聖漁豐168",
            "log_date": "2026-05-18",
            "gear_type": "拖網",
            "gear_properties": {"mesh_size_inch": 2.0, "net_length_m": 120, "tow_duration_hr": 4.0},
            "catches": [
                {"species_raw_name": "白帶", "species_standard_name": "肥帶鰏", "weight_kg": 210.0, "count_individual": 120, "props": {}},
                {"species_raw_name": "臭肚", "species_standard_name": "臭肚魚", "weight_kg": 95.0, "count_individual": 110, "props": {}}
            ]
        }
    ]
    
    try:
        for log in sample_logs:
            gear_props_json = json.dumps(log["gear_properties"], ensure_ascii=False)
            cursor.execute("""
                INSERT INTO fishery_logs (vessel_name, log_date, gear_type, gear_properties)
                VALUES (?, ?, ?, ?)
            """, (log["vessel_name"], log["log_date"], log["gear_type"], gear_props_json))
            log_id = cursor.lastrowid
            
            for catch in log["catches"]:
                catch_props_json = json.dumps(catch["props"], ensure_ascii=False)
                cursor.execute("""
                    INSERT INTO catch_records (log_id, species_raw_name, species_standard_name, weight_kg, count_individual, catch_properties)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (log_id, catch["species_raw_name"], catch["species_standard_name"], catch["weight_kg"], catch["count_individual"], catch_props_json))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
