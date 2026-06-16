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
    
    # 1. Create database_categories table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS database_categories (
            name TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Seed default categories if empty
    cursor.execute("SELECT COUNT(*) FROM database_categories")
    if cursor.fetchone()[0] == 0:
        default_categories = [
            ("生物學參數資料庫",),
            ("拖網類漁業報表資料庫",),
            ("刺網類漁業報表資料庫",),
            ("釣具類漁業報表資料庫",),
            ("休閒船釣漁業資料庫",)
        ]
        cursor.executemany("INSERT INTO database_categories (name) VALUES (?)", default_categories)
    else:
        cursor.execute("INSERT OR IGNORE INTO database_categories (name) VALUES ('休閒船釣漁業資料庫')")
    
    # 2. Create fishery_logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fishery_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            database_type TEXT DEFAULT '拖網類漁業報表資料庫',
            vessel_name TEXT NOT NULL,
            log_date TEXT NOT NULL,
            gear_type TEXT NOT NULL,
            gear_properties TEXT, -- JSON string
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (database_type) REFERENCES database_categories(name)
        )
    """)
    
    # Check if database_type column exists (migration helper)
    cursor.execute("PRAGMA table_info(fishery_logs)")
    columns = [row["name"] for row in cursor.fetchall()]
    if "database_type" not in columns:
        cursor.execute("ALTER TABLE fishery_logs ADD COLUMN database_type TEXT REFERENCES database_categories(name) DEFAULT '拖網類漁業報表資料庫'")
    
    # 3. Create catch_records table
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

    # 4. Create ports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            county TEXT NOT NULL
        )
    """)

    # Seed default ports if empty
    cursor.execute("SELECT COUNT(*) FROM ports")
    if cursor.fetchone()[0] == 0:
        default_ports = [
            ("東港", "屏東縣"),
            ("南方澳", "宜蘭縣"),
            ("新港", "台東縣"),
            ("澎湖", "澎湖縣"),
            ("梧棲港", "台中市")
        ]
        cursor.executemany("INSERT INTO ports (name, county) VALUES (?, ?)", default_ports)

    # 5. Create vessels table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vessels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            registration_number TEXT
        )
    """)

    # Seed default vessels if empty
    cursor.execute("SELECT COUNT(*) FROM vessels")
    if cursor.fetchone()[0] == 0:
        default_vessels = [
            ("小綿洋", "CT4-1234"),
            ("聖漁豐", "CT3-5678"),
            ("新海龍", "CT2-8765"),
            ("聖漁豐168", "CT4-9999")
        ]
        cursor.executemany("INSERT INTO vessels (name, registration_number) VALUES (?, ?)", default_vessels)

    # 6. Create species (fish species) table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS species (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chinese_name TEXT NOT NULL UNIQUE,
            code TEXT,
            genus TEXT,
            species TEXT
        )
    """)

    # Seed default species if empty
    cursor.execute("SELECT COUNT(*) FROM species")
    if cursor.fetchone()[0] == 0:
        default_species = [
            ("黑鯪", "1", "Atrobucca", "nibe"),
            ("日本銀帶鰕", "3", "Spratelloides", "gracilis"),
            ("印度側帶小公魚", "4", "Stolephorus", "indicus"),
            ("其他下雜魚(含不全)", "5", "", ""),
            ("合齒魚科稚魚", "6", "Synodontidae", ""),
            ("貝瑞氏四盤耳烏賊", "7", "Euprymna", "berryi"),
            ("牛尾魚科稚魚", "8", "Platycephalidae", ""),
            ("鰺科", "9", "Carangidae", ""),
            ("小鱗脂眼鯡", "10", "Etrumeus", "micropus"),
            ("大棘大眼鯛", "1017", "Pristigenys", "niphonia"),
            ("臭肚魚", "12", "Siganus", "fuscescens"),
            ("加志", "13", "Pomadasys", "kaakan")
        ]
        cursor.executemany("INSERT INTO species (chinese_name, code, genus, species) VALUES (?, ?, ?, ?)", default_species)

    # 7. Create biological_parameters (Reproduction) table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS biological_parameters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_date TEXT NOT NULL,
            collection_id TEXT NOT NULL,
            port TEXT NOT NULL,
            vessel_name TEXT NOT NULL,
            form_code TEXT NOT NULL,
            species_name TEXT NOT NULL,
            sex TEXT,
            maturity TEXT,
            total_length_mm REAL,
            weight_g REAL,
            gsi REAL,
            remarks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Seed default biological parameters if empty
    cursor.execute("SELECT COUNT(*) FROM biological_parameters")
    if cursor.fetchone()[0] == 0:
        default_bio_records = [
            ("2011-01-17", "Tg-2Pr", "東港", "小綿洋", "1017", "大棘大眼鯛", "雄性", "稍有精液", 208.400, 144.35, 1.815, ""),
            ("2011-01-17", "Tg-6Pr", "東港", "小綿洋", "1017", "大棘大眼鯛", "雌性", "成熟", 224.500, 194.39, 5.129, ""),
            ("2011-01-17", "Tg-43Pr", "東港", "小綿洋", "1017", "大棘大眼鯛", "雌性", "成熟", 210.900, 170.62, 3.270, ""),
            ("2011-01-17", "Tg-12Pr", "東港", "小綿洋", "1017", "大棘大眼鯛", "雌性", "成熟", 215.800, 177.66, 3.726, ""),
            ("2011-01-17", "Tg-42Pr", "東港", "小綿洋", "1017", "大棘大眼鯛", "雄性", "", 207.600, 147.26, 1.440, ""),
            ("2011-01-17", "Tg-31Pr", "東港", "小綿洋", "1017", "大棘大眼鯛", "雄性", "稍有精液", 198.100, 149.68, 1.356, ""),
            ("2011-01-17", "Tg-10Pr", "東港", "小綿洋", "1017", "大棘大眼鯛", "雄性", "", 209.900, 156.16, 0.743, ""),
            ("2011-01-17", "Tg-29Pr", "東港", "小綿洋", "1017", "大棘大眼鯛", "雌性", "水卵", 219.700, 182.76, 6.457, ""),
            ("2011-01-17", "Tg-16Pr", "東港", "小綿洋", "1017", "大棘大眼鯛", "雌性", "成熟", 221.000, 190.32, 3.783, ""),
            ("2011-01-17", "Tg-25Pr", "東港", "小綿洋", "1017", "大棘大眼鯛", "雌性", "成熟", 215.600, 173.85, 3.457, "")
        ]
        cursor.executemany("""
            INSERT INTO biological_parameters (
                collection_date, collection_id, port, vessel_name, form_code, 
                species_name, sex, maturity, total_length_mm, weight_g, gsi, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, default_bio_records)
    
    conn.commit()
    conn.close()

# --- DATABASE CATEGORY CRUD ---
def get_database_categories() -> List[str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM database_categories ORDER BY name ASC")
    categories = [row["name"] for row in cursor.fetchall()]
    conn.close()
    return categories

def add_database_category(name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO database_categories (name) VALUES (?)", (name,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

# --- PARAMETER SETTING CRUD (Ports, Vessels, Species) ---
def get_ports() -> pd.DataFrame:
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM ports ORDER BY name ASC", conn)
    conn.close()
    return df

def add_port(name: str, county: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO ports (name, county) VALUES (?, ?)", (name, county))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

def delete_port(port_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ports WHERE id = ?", (int(port_id),))
    conn.commit()
    conn.close()

def get_vessels() -> pd.DataFrame:
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM vessels ORDER BY name ASC", conn)
    conn.close()
    return df

def add_vessel(name: str, registration_number: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO vessels (name, registration_number) VALUES (?, ?)", (name, registration_number))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

def delete_vessel(vessel_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vessels WHERE id = ?", (int(vessel_id),))
    conn.commit()
    conn.close()

def get_species() -> pd.DataFrame:
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM species ORDER BY id ASC", conn)
    conn.close()
    return df

def add_species(chinese_name: str, code: str, genus: str, species: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO species (chinese_name, code, genus, species) VALUES (?, ?, ?, ?)", 
                       (chinese_name, code, genus, species))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

def delete_species(species_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM species WHERE id = ?", (int(species_id),))
    conn.commit()
    conn.close()

# --- REPRODUCTION DATABASE CRUD (biological_parameters) ---
def get_biological_parameters(species: str = None, port: str = None, sex: str = None) -> pd.DataFrame:
    conn = get_db_connection()
    query = "SELECT * FROM biological_parameters WHERE 1=1"
    params = []
    
    if species:
        query += " AND species_name = ?"
        params.append(species)
    if port:
        query += " AND port = ?"
        params.append(port)
    if sex:
        query += " AND sex = ?"
        params.append(sex)
        
    query += " ORDER BY collection_date DESC, id DESC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def save_biological_parameter(record: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if record.get("id"):
            cursor.execute("""
                UPDATE biological_parameters 
                SET collection_date=?, collection_id=?, port=?, vessel_name=?, form_code=?, 
                    species_name=?, sex=?, maturity=?, total_length_mm=?, weight_g=?, gsi=?, remarks=?
                WHERE id=?
            """, (
                record["collection_date"], record["collection_id"], record["port"], record["vessel_name"], record["form_code"],
                record["species_name"], record.get("sex"), record.get("maturity"), record.get("total_length_mm"),
                record.get("weight_g"), record.get("gsi"), record.get("remarks"), int(record["id"])
            ))
            rec_id = int(record["id"])
        else:
            cursor.execute("""
                INSERT INTO biological_parameters (
                    collection_date, collection_id, port, vessel_name, form_code, 
                    species_name, sex, maturity, total_length_mm, weight_g, gsi, remarks
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record["collection_date"], record["collection_id"], record["port"], record["vessel_name"], record["form_code"],
                record["species_name"], record.get("sex"), record.get("maturity"), record.get("total_length_mm"),
                record.get("weight_g"), record.get("gsi"), record.get("remarks")
            ))
            rec_id = cursor.lastrowid
        conn.commit()
        return rec_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def delete_biological_parameter(rec_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM biological_parameters WHERE id = ?", (int(rec_id),))
    conn.commit()
    conn.close()

def save_biological_parameters_batch(records: List[Dict[str, Any]]):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for rec in records:
            cursor.execute("""
                INSERT INTO biological_parameters (
                    collection_date, collection_id, port, vessel_name, form_code, 
                    species_name, sex, maturity, total_length_mm, weight_g, gsi, remarks
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rec["collection_date"], rec["collection_id"], rec["port"], rec["vessel_name"], rec["form_code"],
                rec["species_name"], rec.get("sex"), rec.get("maturity"), rec.get("total_length_mm"),
                rec.get("weight_g"), rec.get("gsi"), rec.get("remarks")
            ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# --- FISHERY LOGS CRUD ---
def save_fishery_log(log_data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        gear_props = log_data.get("gear_properties", {})
        if isinstance(gear_props, str):
            try:
                gear_props = json.loads(gear_props)
            except Exception:
                pass
        gear_props_json = json.dumps(gear_props, ensure_ascii=False)
        
        db_type = log_data.get("database_type", "拖網類漁業報表資料庫")
        
        cursor.execute("""
            INSERT INTO fishery_logs (database_type, vessel_name, log_date, gear_type, gear_properties)
            VALUES (?, ?, ?, ?, ?)
        """, (
            db_type,
            log_data["vessel_name"],
            log_data["log_date"],
            log_data["gear_type"],
            gear_props_json
        ))
        log_id = cursor.lastrowid
        
        for record in log_data.get("catch_records", []):
            catch_props = record.get("catch_properties", {})
            if isinstance(catch_props, str):
                try:
                    catch_props = json.loads(catch_props)
                except Exception:
                    pass
            catch_props_json = json.dumps(catch_props, ensure_ascii=False)
            
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

def get_fishery_logs_list(database_type: str = None) -> pd.DataFrame:
    conn = get_db_connection()
    if database_type:
        query = """
            SELECT id, database_type, vessel_name, log_date, gear_type, created_at 
            FROM fishery_logs 
            WHERE database_type = ? 
            ORDER BY log_date DESC, id DESC
        """
        df = pd.read_sql_query(query, conn, params=(database_type,))
    else:
        query = """
            SELECT id, database_type, vessel_name, log_date, gear_type, created_at 
            FROM fishery_logs 
            ORDER BY log_date DESC, id DESC
        """
        df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_fishery_log_detail(log_id: int) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fishery_logs WHERE id = ?", (int(log_id),))
    log_row = cursor.fetchone()
    
    if not log_row:
        conn.close()
        return {}
        
    log_data = dict(log_row)
    try:
        log_data["gear_properties"] = json.loads(log_data["gear_properties"])
    except Exception:
        log_data["gear_properties"] = {}
        
    # Get catches
    cursor.execute("SELECT * FROM catch_records WHERE log_id = ?", (log_id,))
    catches = []
    for row in cursor.fetchall():
        catch_dict = dict(row)
        try:
            catch_dict["catch_properties"] = json.loads(catch_dict["catch_properties"])
        except Exception:
            catch_dict["catch_properties"] = {}
        catches.append(catch_dict)
        
    log_data["catch_records"] = catches
    conn.close()
    return log_data

def delete_fishery_logs(log_ids: List[int]):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Enable foreign keys for cascade delete
        cursor.execute("PRAGMA foreign_keys = ON")
        placeholders = ",".join("?" for _ in log_ids)
        cursor.execute(f"DELETE FROM fishery_logs WHERE id IN ({placeholders})", [int(lid) for lid in log_ids])
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# --- STATISTICS RETRIEVAL ---
def get_species_yield_data(database_type: str = None) -> pd.DataFrame:
    conn = get_db_connection()
    if database_type:
        query = """
            SELECT c.species_standard_name, SUM(c.weight_kg) as total_weight_kg
            FROM catch_records c
            JOIN fishery_logs l ON c.log_id = l.id
            WHERE c.weight_kg IS NOT NULL AND l.database_type = ?
            GROUP BY c.species_standard_name
            ORDER BY total_weight_kg DESC
        """
        df = pd.read_sql_query(query, conn, params=(database_type,))
    else:
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

def get_gear_distribution_data(database_type: str = None) -> pd.DataFrame:
    conn = get_db_connection()
    if database_type:
        query = """
            SELECT l.gear_type, COUNT(DISTINCT l.id) as log_count, SUM(c.weight_kg) as total_weight_kg
            FROM fishery_logs l
            LEFT JOIN catch_records c ON l.id = c.log_id
            WHERE l.database_type = ?
            GROUP BY l.gear_type
            ORDER BY log_count DESC
        """
        df = pd.read_sql_query(query, conn, params=(database_type,))
    else:
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
            "database_type": "拖網類漁業報表資料庫",
            "gear_properties": {"mesh_size_inch": 2.0, "net_length_m": 120, "tow_duration_hr": 3.5},
            "catches": [
                {"species_raw_name": "白帶", "species_standard_name": "肥帶鰏", "weight_kg": 145.5, "count_individual": 80, "props": {"size_group": "大"}},
                {"species_raw_name": "鯖魚", "species_standard_name": "花腹鯖", "weight_kg": 230.0, "count_individual": 450, "props": {"quality": "優"}},
                {"species_raw_name": "秋刀", "species_standard_name": "秋刀魚", "weight_kg": 85.0, "count_individual": 200, "props": {}}
            ]
        },
        {
            "vessel_name": "小綿洋",
            "log_date": "2026-05-12",
            "gear_type": "延繩釣",
            "database_type": "釣具類漁業報表資料庫",
            "gear_properties": {"total_hook_hours": 8.0, "water_depth_m": 85, "bait_type": "秋刀魚"},
            "catches": [
                {"species_raw_name": "如志", "species_standard_name": "加志", "weight_kg": 320.0, "count_individual": 40, "props": {"fork_length_mean_mm": 350}},
                {"species_raw_name": "臭肚", "species_standard_name": "臭肚魚", "weight_kg": 115.0, "count_individual": 150, "props": {}}
            ]
        },
        {
            "vessel_name": "新海龍",
            "log_date": "2026-05-15",
            "gear_type": "一支釣",
            "database_type": "釣具類漁業報表資料庫",
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
            "database_type": "拖網類漁業報表資料庫",
            "gear_properties": {"mesh_size_inch": 2.0, "net_length_m": 120, "tow_duration_hr": 4.0},
            "catches": [
                {"species_raw_name": "白帶", "species_standard_name": "肥帶鰏", "weight_kg": 210.0, "count_individual": 120, "props": {}},
                {"species_raw_name": "臭肚", "species_standard_name": "臭肚魚", "weight_kg": 95.0, "count_individual": 110, "props": {}}
            ]
        }
    ]
    
    try:
        # Re-initialize dynamic tables first
        init_db()
        for log in sample_logs:
            gear_props_json = json.dumps(log["gear_properties"], ensure_ascii=False)
            cursor.execute("""
                INSERT INTO fishery_logs (database_type, vessel_name, log_date, gear_type, gear_properties)
                VALUES (?, ?, ?, ?, ?)
            """, (log["database_type"], log["vessel_name"], log["log_date"], log["gear_type"], gear_props_json))
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
