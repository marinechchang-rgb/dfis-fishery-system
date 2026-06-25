import sqlite3
import json
import os
import pandas as pd
import urllib.parse as urlparse
import uuid
from typing import Dict, Any, List

from dfis_registry import infer_bio_template_code, infer_database_category_code, infer_form_template_code

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fishery_standard.db")

DB_URL = os.environ.get("DATABASE_URL")
PG_HOST = os.environ.get("PGHOST")
PG_DATABASE = os.environ.get("PGDATABASE", "postgres")
PG_USER = os.environ.get("PGUSER", "postgres")
PG_PASSWORD = os.environ.get("PGPASSWORD")
PG_PORT = os.environ.get("PGPORT", 5432)

try:
    import streamlit as st
    if hasattr(st, "secrets"):
        if "DATABASE_URL" in st.secrets:
            DB_URL = st.secrets["DATABASE_URL"]
        if "PGHOST" in st.secrets:
            PG_HOST = st.secrets["PGHOST"]
        if "PGDATABASE" in st.secrets:
            PG_DATABASE = st.secrets["PGDATABASE"]
        if "PGUSER" in st.secrets:
            PG_USER = st.secrets["PGUSER"]
        if "PGPASSWORD" in st.secrets:
            PG_PASSWORD = st.secrets["PGPASSWORD"]
        if "PGPORT" in st.secrets:
            PG_PORT = st.secrets["PGPORT"]
except Exception:
    pass

# --- STREAMLIT CACHING HELPERS ---
try:
    import streamlit as st
    if hasattr(st, "cache_data"):
        cache_data = st.cache_data
    else:
        def cache_data(func=None, **kwargs):
            if func is not None:
                return func
            def decorator(f):
                return f
            return decorator
except Exception:
    def cache_data(func=None, **kwargs):
        if func is not None:
            return func
        def decorator(f):
            return f
        return decorator

def clear_db_cache():
    try:
        import streamlit as st
        if hasattr(st, "cache_data") and hasattr(st.cache_data, "clear"):
            st.cache_data.clear()
    except Exception:
        pass


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _safe_json_loads(value: Any, fallback: Any):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return fallback
    if value is None:
        return fallback
    return value


def _safe_json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False)

IS_POSTGRES = DB_URL is not None or PG_HOST is not None

# Helper to format placeholders for PostgreSQL
def query_fmt(query: str) -> str:
    if IS_POSTGRES:
        return query.replace("?", "%s")
    return query

# Override pandas read_sql_query for PostgreSQL compatibility
_raw_read_sql_query = pd.read_sql_query
def compat_read_sql_query(sql, con, *args, **kwargs):
    if IS_POSTGRES:
        sql = sql.replace("?", "%s")
    return _raw_read_sql_query(sql, con, *args, **kwargs)
pd.read_sql_query = compat_read_sql_query

class CompatCursor:
    def __init__(self, cursor, is_postgres):
        self.cursor = cursor
        self.is_postgres = is_postgres
        self._lastrowid = None
        
    def execute(self, query, params=None):
        if self.is_postgres:
            query = query.replace("?", "%s")
            # If it's an insert query, append RETURNING id unless the table doesn't have an id column
            is_insert = query.strip().upper().startswith("INSERT")
            appended_returning = False
            if is_insert and "RETURNING" not in query.upper():
                import re
                if not re.search(r'\b(database_categories|form_templates)\b', query, re.IGNORECASE):
                    query += " RETURNING id"
                    appended_returning = True
                
            if params is not None:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
                
            if is_insert and appended_returning:
                try:
                    row = self.cursor.fetchone()
                    if row:
                        self._lastrowid = row[0]
                except Exception:
                    pass
        else:
            if params is not None:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)
                
    def executemany(self, query, params_list):
        if self.is_postgres:
            query = query.replace("?", "%s")
        self.cursor.executemany(query, params_list)
        
    @property
    def lastrowid(self):
        if self.is_postgres:
            return self._lastrowid
        return self.cursor.lastrowid
        
    def __getattr__(self, name):
        return getattr(self.cursor, name)

DB_CONN_WARNING = None

def get_db_connection():
    global IS_POSTGRES, DB_CONN_WARNING
    """Returns a connection to the SQLite or PostgreSQL database."""
    if IS_POSTGRES:
        import psycopg2
        import psycopg2.extras
        try:
            if DB_URL:
                db_url = DB_URL
                if db_url.startswith("postgres://"):
                    db_url = db_url.replace("postgres://", "postgresql://", 1)
                conn = psycopg2.connect(db_url, connect_timeout=3)
            else:
                conn = psycopg2.connect(
                    host=PG_HOST,
                    database=PG_DATABASE,
                    user=PG_USER,
                    password=PG_PASSWORD,
                    port=int(PG_PORT),
                    connect_timeout=3
                )
            return conn
        except Exception as e:
            # Fallback to SQLite
            DB_CONN_WARNING = str(e)
            IS_POSTGRES = False
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def get_cursor(conn):
    if IS_POSTGRES:
        import psycopg2.extras
        raw_cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    else:
        raw_cursor = conn.cursor()
    return CompatCursor(raw_cursor, IS_POSTGRES)

def init_db():
    """Initializes the database schema if tables do not exist."""
    conn = get_db_connection()
    cursor = get_cursor(conn)
    
    if IS_POSTGRES:
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
            cursor.execute("INSERT INTO database_categories (name) VALUES ('休閒船釣漁業資料庫') ON CONFLICT (name) DO NOTHING")
        
        # 2. Create fishery_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fishery_logs (
                id SERIAL PRIMARY KEY,
                database_type TEXT DEFAULT '拖網類漁業報表資料庫',
                vessel_name TEXT NOT NULL,
                log_date TEXT NOT NULL,
                gear_type TEXT NOT NULL,
                gear_properties TEXT, -- JSON string
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Check if database_type column exists (migration helper)
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='fishery_logs' AND column_name='database_type'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE fishery_logs ADD COLUMN database_type TEXT DEFAULT '拖網類漁業報表資料庫'")
        
        # 3. Create catch_records table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS catch_records (
                id SERIAL PRIMARY KEY,
                log_id INTEGER NOT NULL,
                species_raw_name TEXT NOT NULL,
                species_standard_name TEXT NOT NULL,
                weight_kg REAL,
                count_individual INTEGER,
                catch_properties TEXT
            )
        """)
        cursor.execute("ALTER TABLE catch_records ADD COLUMN IF NOT EXISTS operation_id TEXT")
        cursor.execute("ALTER TABLE catch_records ADD COLUMN IF NOT EXISTS sequence_no INTEGER")
        cursor.execute("ALTER TABLE catch_records ADD COLUMN IF NOT EXISTS size_bucket TEXT")
        cursor.execute("ALTER TABLE catch_records ADD COLUMN IF NOT EXISTS remarks TEXT")

        # 4. Create ports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ports (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                county TEXT NOT NULL
            )
        """)

        # Seed default ports if empty
        cursor.execute("SELECT COUNT(*) FROM ports")
        if cursor.fetchone()[0] == 0:
            default_ports = [
                ("東港", "港東"),
                ("南方澳", "宜蘭縣"),
                ("新港", "台東縣"),
                ("澎湖", "澎湖縣"),
                ("梧棲港", "台中市")
            ]
            cursor.executemany("INSERT INTO ports (name, county) VALUES (?, ?)", default_ports)

        # 5. Create vessels table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vessels (
                id SERIAL PRIMARY KEY,
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
                id SERIAL PRIMARY KEY,
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
                id SERIAL PRIMARY KEY,
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
        cursor.execute("ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS sample_batch_id TEXT")
        cursor.execute("ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS sequence_no INTEGER")
        cursor.execute("ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS specimen_no TEXT")
        cursor.execute("ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS species_standard_name TEXT")
        cursor.execute("ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS fork_length_mm REAL")
        cursor.execute("ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS net_group TEXT")
        cursor.execute("ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS net_set_no TEXT")
        cursor.execute("ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS site_name TEXT")
        cursor.execute("ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS total_weight_kg REAL")
        cursor.execute("ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS discard_weight_kg REAL")
        cursor.execute("ALTER TABLE biological_parameters ADD COLUMN IF NOT EXISTS background_properties TEXT")

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
    else:
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
        cursor.execute("PRAGMA table_info(catch_records)")
        catch_columns = [row["name"] for row in cursor.fetchall()]
        if "operation_id" not in catch_columns:
            cursor.execute("ALTER TABLE catch_records ADD COLUMN operation_id TEXT")
        if "sequence_no" not in catch_columns:
            cursor.execute("ALTER TABLE catch_records ADD COLUMN sequence_no INTEGER")
        if "size_bucket" not in catch_columns:
            cursor.execute("ALTER TABLE catch_records ADD COLUMN size_bucket TEXT")
        if "remarks" not in catch_columns:
            cursor.execute("ALTER TABLE catch_records ADD COLUMN remarks TEXT")

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
        cursor.execute("PRAGMA table_info(biological_parameters)")
        bio_columns = [row["name"] for row in cursor.fetchall()]
        if "sample_batch_id" not in bio_columns:
            cursor.execute("ALTER TABLE biological_parameters ADD COLUMN sample_batch_id TEXT")
        if "sequence_no" not in bio_columns:
            cursor.execute("ALTER TABLE biological_parameters ADD COLUMN sequence_no INTEGER")
        if "specimen_no" not in bio_columns:
            cursor.execute("ALTER TABLE biological_parameters ADD COLUMN specimen_no TEXT")
        if "species_standard_name" not in bio_columns:
            cursor.execute("ALTER TABLE biological_parameters ADD COLUMN species_standard_name TEXT")
        if "fork_length_mm" not in bio_columns:
            cursor.execute("ALTER TABLE biological_parameters ADD COLUMN fork_length_mm REAL")
        if "net_group" not in bio_columns:
            cursor.execute("ALTER TABLE biological_parameters ADD COLUMN net_group TEXT")
        if "net_set_no" not in bio_columns:
            cursor.execute("ALTER TABLE biological_parameters ADD COLUMN net_set_no TEXT")
        if "site_name" not in bio_columns:
            cursor.execute("ALTER TABLE biological_parameters ADD COLUMN site_name TEXT")
        if "total_weight_kg" not in bio_columns:
            cursor.execute("ALTER TABLE biological_parameters ADD COLUMN total_weight_kg REAL")
        if "discard_weight_kg" not in bio_columns:
            cursor.execute("ALTER TABLE biological_parameters ADD COLUMN discard_weight_kg REAL")
        if "background_properties" not in bio_columns:
            cursor.execute("ALTER TABLE biological_parameters ADD COLUMN background_properties TEXT")

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
            
    _init_shadow_schema(cursor)

    conn.commit()
    conn.close()


def _init_shadow_schema(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS form_templates (
            template_code TEXT PRIMARY KEY,
            template_name_zh TEXT NOT NULL,
            data_domain TEXT NOT NULL,
            gear_family TEXT,
            source_file_name TEXT,
            is_active INTEGER DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS import_batches (
            id TEXT PRIMARY KEY,
            database_category_code TEXT,
            form_template_code TEXT,
            source_channel TEXT DEFAULT 'upload',
            import_status TEXT DEFAULT 'saved',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_extraction_runs (
            id TEXT PRIMARY KEY,
            batch_id TEXT,
            provider_name TEXT,
            model_name TEXT,
            prompt_version TEXT,
            schema_version TEXT,
            run_status TEXT DEFAULT 'success',
            raw_response TEXT,
            normalized_payload TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fishery_operations (
            id TEXT PRIMARY KEY,
            legacy_log_id INTEGER UNIQUE,
            batch_id TEXT,
            database_category_code TEXT,
            form_template_code TEXT,
            vessel_name TEXT,
            vessel_registration_no TEXT,
            owner_name TEXT,
            observer_name TEXT,
            operation_date TEXT NOT NULL,
            departure_time TEXT,
            return_time TEXT,
            start_time TEXT,
            end_time TEXT,
            gear_type TEXT NOT NULL,
            remarks TEXT,
            gear_properties TEXT,
            review_status TEXT DEFAULT 'needs_review',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operation_locations (
            id TEXT PRIMARY KEY,
            operation_id TEXT NOT NULL,
            location_role TEXT NOT NULL,
            sequence_no INTEGER,
            location_name TEXT,
            latitude REAL,
            longitude REAL,
            depth_m REAL,
            extra_properties TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bio_sample_batches (
            id TEXT PRIMARY KEY,
            source_record_key TEXT UNIQUE,
            form_template_code TEXT,
            vessel_name TEXT,
            operation_date TEXT,
            site_name TEXT,
            port_name TEXT,
            net_group TEXT,
            net_set_no TEXT,
            total_weight_kg REAL,
            discard_weight_kg REAL,
            background_properties TEXT,
            review_status TEXT DEFAULT 'needs_review',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS biological_measurements (
            id TEXT PRIMARY KEY,
            sample_batch_id TEXT NOT NULL,
            legacy_biological_id INTEGER,
            sequence_no INTEGER,
            specimen_no TEXT,
            species_raw_name TEXT,
            species_standard_name TEXT,
            fork_length_mm REAL,
            total_length_mm REAL,
            weight_g REAL,
            sex TEXT,
            maturity TEXT,
            gsi REAL,
            remarks TEXT,
            measurement_properties TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS field_definitions (
            id TEXT PRIMARY KEY,
            form_template_code TEXT,
            field_key TEXT NOT NULL,
            field_scope TEXT NOT NULL,
            label_zh TEXT NOT NULL,
            data_type TEXT NOT NULL,
            unit_name TEXT,
            is_required INTEGER DEFAULT 0,
            target_table TEXT NOT NULL,
            target_column TEXT,
            json_path TEXT,
            notes TEXT
        )
    """)
    _seed_form_templates(cursor)


def _seed_form_templates(cursor):
    rows = [
        ("TN_COASTAL_GILLNET_001", "台南將軍沿海場域標本船作業調查表109.03.31", "fishery", "gillnet", "台南將軍沿海場域標本船作業調查表109.03.31.docx", "沿海網具作業調查母版"),
        ("SW_HOOK_001", "釣具類作業報表(擷取1頁)_114.09.16", "fishery", "hook_and_line", "釣具類作業報表(擷取1頁)_114.09.16.docx", "西南海域釣具類作業母版"),
        ("TW_LONGLINE_001", "延繩釣漁撈作業報表-高雄熊麻吉 -", "fishery", "longline", "延繩釣漁撈作業報表-高雄熊麻吉 -.docx", "延繩釣與一支釣混合母版"),
        ("BIO_MESH_001", "網目比較實驗室紀錄表", "biology", "lab_measurement", "網目比較實驗室紀錄表.docx", "生物學量測母版"),
    ]
    for row in rows:
        if IS_POSTGRES:
            cursor.execute("""
                INSERT INTO form_templates (template_code, template_name_zh, data_domain, gear_family, source_file_name, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (template_code) DO NOTHING
            """, row)
        else:
            cursor.execute("""
                INSERT OR IGNORE INTO form_templates (template_code, template_name_zh, data_domain, gear_family, source_file_name, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, row)


def _upsert_import_batch(cursor, batch_id: str, database_category_code: str, form_template_code: str, notes: str = ""):
    if IS_POSTGRES:
        cursor.execute("""
            INSERT INTO import_batches (id, database_category_code, form_template_code, notes)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (id) DO NOTHING
        """, (batch_id, database_category_code, form_template_code, notes))
    else:
        cursor.execute("""
            INSERT OR IGNORE INTO import_batches (id, database_category_code, form_template_code, notes)
            VALUES (?, ?, ?, ?)
        """, (batch_id, database_category_code, form_template_code, notes))


def _delete_shadow_catches_for_operation(cursor, operation_id: str):
    cursor.execute("DELETE FROM catch_records WHERE operation_id = ?", (operation_id,))


def _persist_fishery_operation_shadow(cursor, log_id: int, log_data: Dict[str, Any]):
    operation_id = _new_uuid()
    batch_id = _new_uuid()
    database_category_code = infer_database_category_code(log_data.get("database_type", ""))
    form_template_code = infer_form_template_code(log_data)
    _upsert_import_batch(cursor, batch_id, database_category_code, form_template_code, f"legacy_log_id={log_id}")

    gear_props = _safe_json_loads(log_data.get("gear_properties"), {})
    cursor.execute("""
        INSERT INTO fishery_operations (
            id, legacy_log_id, batch_id, database_category_code, form_template_code,
            vessel_name, vessel_registration_no, owner_name, observer_name,
            operation_date, departure_time, return_time, start_time, end_time,
            gear_type, remarks, gear_properties
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        operation_id,
        log_id,
        batch_id,
        database_category_code,
        form_template_code,
        log_data.get("vessel_name"),
        log_data.get("vessel_registration_no"),
        log_data.get("owner_name"),
        log_data.get("observer_name"),
        log_data.get("log_date"),
        log_data.get("departure_time"),
        log_data.get("return_time"),
        log_data.get("start_time"),
        log_data.get("end_time"),
        log_data.get("gear_type"),
        log_data.get("remarks"),
        _safe_json_dumps(gear_props),
    ))

    for index, location in enumerate(log_data.get("operation_locations", []), start=1):
        loc = _safe_json_loads(location, {})
        cursor.execute("""
            INSERT INTO operation_locations (
                id, operation_id, location_role, sequence_no, location_name,
                latitude, longitude, depth_m, extra_properties
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            _new_uuid(),
            operation_id,
            loc.get("location_role", f"spot_{index}"),
            loc.get("sequence_no", index),
            loc.get("location_name"),
            loc.get("latitude"),
            loc.get("longitude"),
            loc.get("depth_m"),
            _safe_json_dumps(loc.get("extra_properties", {})),
        ))

    return operation_id


def _persist_bio_shadow(cursor, batch_id: str, record: Dict[str, Any], legacy_record_id: int = None):
    source_record_key = f"{record.get('collection_id', '')}|{record.get('vessel_name', '')}|{record.get('collection_date', '')}"
    form_template_code = infer_bio_template_code(record)
    background_properties = _safe_json_loads(record.get("background_properties"), {})

    if IS_POSTGRES:
        cursor.execute("""
            INSERT INTO bio_sample_batches (
                id, source_record_key, form_template_code, vessel_name, operation_date, site_name, port_name,
                net_group, net_set_no, total_weight_kg, discard_weight_kg, background_properties
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source_record_key) DO NOTHING
        """, (
            batch_id,
            source_record_key,
            form_template_code,
            record.get("vessel_name"),
            record.get("collection_date"),
            record.get("site_name"),
            record.get("port"),
            record.get("net_group"),
            record.get("net_set_no"),
            record.get("total_weight_kg"),
            record.get("discard_weight_kg"),
            _safe_json_dumps(background_properties),
        ))
    else:
        cursor.execute("""
            INSERT OR IGNORE INTO bio_sample_batches (
                id, source_record_key, form_template_code, vessel_name, operation_date, site_name, port_name,
                net_group, net_set_no, total_weight_kg, discard_weight_kg, background_properties
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            batch_id,
            source_record_key,
            form_template_code,
            record.get("vessel_name"),
            record.get("collection_date"),
            record.get("site_name"),
            record.get("port"),
            record.get("net_group"),
            record.get("net_set_no"),
            record.get("total_weight_kg"),
            record.get("discard_weight_kg"),
            _safe_json_dumps(background_properties),
        ))

    cursor.execute("""
        INSERT INTO biological_measurements (
            id, sample_batch_id, legacy_biological_id, sequence_no, specimen_no,
            species_raw_name, species_standard_name, fork_length_mm, total_length_mm,
            weight_g, sex, maturity, gsi, remarks, measurement_properties
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        _new_uuid(),
        batch_id,
        legacy_record_id,
        record.get("sequence_no"),
        record.get("specimen_no"),
        record.get("species_name"),
        record.get("species_standard_name"),
        record.get("fork_length_mm"),
        record.get("total_length_mm"),
        record.get("weight_g"),
        record.get("sex"),
        record.get("maturity"),
        record.get("gsi"),
        record.get("remarks"),
        _safe_json_dumps(background_properties),
    ))


def _cleanup_bio_shadow(cursor, legacy_record_id: int, sample_batch_id: str = None):
    cursor.execute("DELETE FROM biological_measurements WHERE legacy_biological_id = ?", (legacy_record_id,))
    if sample_batch_id:
        cursor.execute("SELECT COUNT(*) FROM biological_measurements WHERE sample_batch_id = ?", (sample_batch_id,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("DELETE FROM bio_sample_batches WHERE id = ?", (sample_batch_id,))


# --- DATABASE CATEGORY CRUD ---
@cache_data
def get_database_categories() -> List[str]:
    conn = get_db_connection()
    cursor = get_cursor(conn)
    cursor.execute("SELECT name FROM database_categories ORDER BY name ASC")
    categories = [row["name"] for row in cursor.fetchall()]
    conn.close()
    return categories

def add_database_category(name: str):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        cursor.execute("INSERT INTO database_categories (name) VALUES (?)", (name,))
        conn.commit()
        clear_db_cache()
    except Exception:
        pass
    finally:
        conn.close()

# --- PARAMETER SETTING CRUD (Ports, Vessels, Species) ---
@cache_data
def get_ports() -> pd.DataFrame:
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM ports ORDER BY name ASC", conn)
    conn.close()
    return df

def add_port(name: str, county: str):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        cursor.execute("INSERT INTO ports (name, county) VALUES (?, ?)", (name, county))
        conn.commit()
        clear_db_cache()
    except Exception:
        pass
    finally:
        conn.close()

def update_port(port_id: int, name: str, county: str):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        cursor.execute("UPDATE ports SET name = ?, county = ? WHERE id = ?", (name, county, int(port_id)))
        conn.commit()
        clear_db_cache()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def delete_port(port_id: int):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    cursor.execute("DELETE FROM ports WHERE id = ?", (int(port_id),))
    conn.commit()
    clear_db_cache()
    conn.close()

def ensure_port_exists(name: str) -> bool:
    """Ensures a port exists in the ports table. If not, auto-registers it with county '未指定'."""
    if not name or name.strip() == "":
        return False
    name = name.strip()
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        cursor.execute("SELECT id FROM ports WHERE name = ?", (name,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO ports (name, county) VALUES (?, ?)", (name, "未指定"))
            conn.commit()
            clear_db_cache()
            return True
        return False
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

@cache_data
def get_vessels() -> pd.DataFrame:
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM vessels ORDER BY name ASC", conn)
    conn.close()
    return df

def add_vessel(name: str, registration_number: str):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        cursor.execute("INSERT INTO vessels (name, registration_number) VALUES (?, ?)", (name, registration_number))
        conn.commit()
        clear_db_cache()
    except Exception:
        pass
    finally:
        conn.close()

def update_vessel(vessel_id: int, name: str, registration_number: str):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        cursor.execute("UPDATE vessels SET name = ?, registration_number = ? WHERE id = ?", (name, registration_number, int(vessel_id)))
        conn.commit()
        clear_db_cache()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def delete_vessel(vessel_id: int):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    cursor.execute("DELETE FROM vessels WHERE id = ?", (int(vessel_id),))
    conn.commit()
    clear_db_cache()
    conn.close()

def ensure_vessel_exists(name: str) -> bool:
    """Ensures a vessel exists in the vessels table. If not, auto-registers it with registration_number '未指定'."""
    if not name or name.strip() == "":
        return False
    name = name.strip()
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        cursor.execute("SELECT id FROM vessels WHERE name = ?", (name,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO vessels (name, registration_number) VALUES (?, ?)", (name, "未指定"))
            conn.commit()
            clear_db_cache()
            return True
        return False
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

@cache_data
def get_species() -> pd.DataFrame:
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM species ORDER BY id ASC", conn)
    conn.close()
    return df

def add_species(chinese_name: str, code: str, genus: str, species: str):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        cursor.execute("INSERT INTO species (chinese_name, code, genus, species) VALUES (?, ?, ?, ?)", 
                       (chinese_name, code, genus, species))
        conn.commit()
        clear_db_cache()
    except Exception:
        pass
    finally:
        conn.close()

def update_species(species_id: int, chinese_name: str, code: str, genus: str, species: str):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        cursor.execute("UPDATE species SET chinese_name = ?, code = ?, genus = ?, species = ? WHERE id = ?", 
                       (chinese_name, code, genus, species, int(species_id)))
        conn.commit()
        clear_db_cache()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def delete_species(species_id: int):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    cursor.execute("DELETE FROM species WHERE id = ?", (int(species_id),))
    conn.commit()
    clear_db_cache()
    conn.close()

def ensure_species_exists(chinese_name: str) -> bool:
    """Ensures a species exists in the species table. If not, auto-registers it with empty code/genus/species."""
    if not chinese_name or chinese_name.strip() == "":
        return False
    chinese_name = chinese_name.strip()
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        cursor.execute("SELECT id FROM species WHERE chinese_name = ?", (chinese_name,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO species (chinese_name, code, genus, species) VALUES (?, ?, ?, ?)", (chinese_name, "", "", ""))
            conn.commit()
            clear_db_cache()
            return True
        return False
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

# --- REPRODUCTION DATABASE CRUD (biological_parameters) ---
@cache_data
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
    cursor = get_cursor(conn)
    try:
        sample_batch_id = record.get("sample_batch_id") or _new_uuid()
        background_properties_json = _safe_json_dumps(_safe_json_loads(record.get("background_properties"), {}))
        if record.get("id"):
            cursor.execute("SELECT sample_batch_id FROM biological_parameters WHERE id = ?", (int(record["id"]),))
            existing = cursor.fetchone()
            if existing and existing[0]:
                sample_batch_id = existing[0]
            cursor.execute("""
                UPDATE biological_parameters 
                SET collection_date=?, collection_id=?, port=?, vessel_name=?, form_code=?, 
                    species_name=?, sex=?, maturity=?, total_length_mm=?, weight_g=?, gsi=?, remarks=?,
                    sample_batch_id=?, sequence_no=?, specimen_no=?, species_standard_name=?, fork_length_mm=?,
                    net_group=?, net_set_no=?, site_name=?, total_weight_kg=?, discard_weight_kg=?, background_properties=?
                WHERE id=?
            """, (
                record["collection_date"], record["collection_id"], record["port"], record["vessel_name"], record["form_code"],
                record["species_name"], record.get("sex"), record.get("maturity"), record.get("total_length_mm"),
                record.get("weight_g"), record.get("gsi"), record.get("remarks"),
                sample_batch_id, record.get("sequence_no"), record.get("specimen_no"), record.get("species_standard_name"),
                record.get("fork_length_mm"), record.get("net_group"), record.get("net_set_no"), record.get("site_name"),
                record.get("total_weight_kg"), record.get("discard_weight_kg"), background_properties_json,
                int(record["id"])
            ))
            rec_id = int(record["id"])
            _cleanup_bio_shadow(cursor, rec_id, sample_batch_id)
        else:
            cursor.execute("""
                INSERT INTO biological_parameters (
                    collection_date, collection_id, port, vessel_name, form_code, 
                    species_name, sex, maturity, total_length_mm, weight_g, gsi, remarks,
                    sample_batch_id, sequence_no, specimen_no, species_standard_name, fork_length_mm,
                    net_group, net_set_no, site_name, total_weight_kg, discard_weight_kg, background_properties
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record["collection_date"], record["collection_id"], record["port"], record["vessel_name"], record["form_code"],
                record["species_name"], record.get("sex"), record.get("maturity"), record.get("total_length_mm"),
                record.get("weight_g"), record.get("gsi"), record.get("remarks"),
                sample_batch_id, record.get("sequence_no"), record.get("specimen_no"), record.get("species_standard_name"),
                record.get("fork_length_mm"), record.get("net_group"), record.get("net_set_no"), record.get("site_name"),
                record.get("total_weight_kg"), record.get("discard_weight_kg"), background_properties_json
            ))
            rec_id = cursor.lastrowid
        _persist_bio_shadow(cursor, sample_batch_id, record, rec_id)
        conn.commit()
        clear_db_cache()
        return rec_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def delete_biological_parameter(rec_id: int):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    cursor.execute("SELECT sample_batch_id FROM biological_parameters WHERE id = ?", (int(rec_id),))
    row = cursor.fetchone()
    sample_batch_id = row[0] if row else None
    _cleanup_bio_shadow(cursor, int(rec_id), sample_batch_id)
    cursor.execute("DELETE FROM biological_parameters WHERE id = ?", (int(rec_id),))
    conn.commit()
    clear_db_cache()
    conn.close()

def save_biological_parameters_batch(records: List[Dict[str, Any]]):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        batch_groups = {}
        for rec in records:
            group_key = f"{rec.get('collection_id', '')}|{rec.get('vessel_name', '')}|{rec.get('collection_date', '')}"
            batch_groups.setdefault(group_key, _new_uuid())
            cursor.execute("""
                INSERT INTO biological_parameters (
                    collection_date, collection_id, port, vessel_name, form_code, 
                    species_name, sex, maturity, total_length_mm, weight_g, gsi, remarks,
                    sample_batch_id, sequence_no, specimen_no, species_standard_name, fork_length_mm,
                    net_group, net_set_no, site_name, total_weight_kg, discard_weight_kg, background_properties
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rec["collection_date"], rec["collection_id"], rec["port"], rec["vessel_name"], rec["form_code"],
                rec["species_name"], rec.get("sex"), rec.get("maturity"), rec.get("total_length_mm"),
                rec.get("weight_g"), rec.get("gsi"), rec.get("remarks"),
                batch_groups[group_key], rec.get("sequence_no"), rec.get("specimen_no"), rec.get("species_standard_name"),
                rec.get("fork_length_mm"), rec.get("net_group"), rec.get("net_set_no"), rec.get("site_name"),
                rec.get("total_weight_kg"), rec.get("discard_weight_kg"),
                _safe_json_dumps(_safe_json_loads(rec.get("background_properties"), {}))
            ))
            legacy_record_id = cursor.lastrowid
            _persist_bio_shadow(cursor, batch_groups[group_key], rec, legacy_record_id)
        conn.commit()
        clear_db_cache()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# --- FISHERY LOGS CRUD ---
def save_fishery_log(log_data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        gear_props = _safe_json_loads(log_data.get("gear_properties"), {})
        gear_props_json = _safe_json_dumps(gear_props)
        
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
        operation_id = _persist_fishery_operation_shadow(cursor, log_id, log_data)
        
        for index, record in enumerate(log_data.get("catch_records", []), start=1):
            catch_props = _safe_json_loads(record.get("catch_properties"), {})
            catch_props_json = _safe_json_dumps(catch_props)
            
            cursor.execute("""
                INSERT INTO catch_records (
                    log_id, operation_id, sequence_no, species_raw_name, species_standard_name,
                    weight_kg, count_individual, catch_properties, size_bucket, remarks
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_id,
                operation_id,
                index,
                record["species_raw_name"],
                record["species_standard_name"],
                record.get("weight_kg"),
                record.get("count_individual"),
                catch_props_json,
                record.get("size_bucket"),
                record.get("remarks"),
            ))
            
        conn.commit()
        clear_db_cache()
        return log_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

@cache_data
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

@cache_data
def get_fishery_log_detail(log_id: int) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = get_cursor(conn)
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
    cursor.execute("SELECT * FROM catch_records WHERE log_id = ? ORDER BY COALESCE(sequence_no, id)", (log_id,))
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
    cursor = get_cursor(conn)
    try:
        # Enable foreign keys for cascade delete
        if not IS_POSTGRES:
            cursor.execute("PRAGMA foreign_keys = ON")
        placeholders = ",".join("?" for _ in log_ids)
        cursor.execute(f"SELECT id FROM fishery_operations WHERE legacy_log_id IN ({placeholders})", [int(lid) for lid in log_ids])
        operation_ids = [row[0] for row in cursor.fetchall()]
        if operation_ids:
            op_placeholders = ",".join("?" for _ in operation_ids)
            cursor.execute(f"DELETE FROM operation_locations WHERE operation_id IN ({op_placeholders})", operation_ids)
            cursor.execute(f"DELETE FROM catch_records WHERE operation_id IN ({op_placeholders})", operation_ids)
            cursor.execute(f"DELETE FROM fishery_operations WHERE id IN ({op_placeholders})", operation_ids)
        placeholders = ",".join("?" for _ in log_ids)
        cursor.execute(f"DELETE FROM fishery_logs WHERE id IN ({placeholders})", [int(lid) for lid in log_ids])
        conn.commit()
        clear_db_cache()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# --- STATISTICS RETRIEVAL ---
@cache_data
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

@cache_data
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
    cursor = get_cursor(conn)
    
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
        clear_db_cache()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()



# --- Supabase compatibility override for Streamlit Cloud ---
_legacy_init_db = init_db
_legacy_get_database_categories = get_database_categories
_legacy_add_database_category = add_database_category

def _compat_is_modern_supabase_schema(cursor):
    return IS_POSTGRES and _postgres_table_has_column(cursor, "database_categories", "category_name_zh")

def init_db():
    if not IS_POSTGRES:
        return _legacy_init_db()

    conn = get_db_connection()
    cursor = get_cursor(conn)
    if not _compat_is_modern_supabase_schema(cursor):
        conn.close()
        return _legacy_init_db()

    try:
        cursor.execute("ALTER TABLE database_categories ADD COLUMN IF NOT EXISTS name TEXT")
        cursor.execute("UPDATE database_categories SET name = COALESCE(name, category_name_zh)")
        cursor.execute("""
            INSERT INTO database_categories (category_code, category_name_zh, description, name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (category_code) DO NOTHING
        """, ("RECREATIONAL_FISHERY", "休閒船釣漁業資料庫", "legacy compatibility seed", "休閒船釣漁業資料庫"))

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fishery_logs (
                id SERIAL PRIMARY KEY,
                database_type TEXT DEFAULT '拖網類漁業報表資料庫',
                vessel_name TEXT NOT NULL,
                log_date TEXT NOT NULL,
                gear_type TEXT NOT NULL,
                gear_properties TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS species (
                id SERIAL PRIMARY KEY,
                chinese_name TEXT NOT NULL UNIQUE,
                code TEXT,
                genus TEXT,
                species TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS biological_parameters (
                id SERIAL PRIMARY KEY,
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
        cursor.execute("ALTER TABLE catch_records ADD COLUMN IF NOT EXISTS log_id INTEGER")
        cursor.execute("ALTER TABLE catch_records ADD COLUMN IF NOT EXISTS catch_properties TEXT")
        cursor.execute("ALTER TABLE catch_records ADD COLUMN IF NOT EXISTS operation_id TEXT")
        cursor.execute("ALTER TABLE catch_records ADD COLUMN IF NOT EXISTS sequence_no INTEGER")
        cursor.execute("ALTER TABLE catch_records ADD COLUMN IF NOT EXISTS size_bucket TEXT")
        cursor.execute("ALTER TABLE catch_records ADD COLUMN IF NOT EXISTS remarks TEXT")
        _init_shadow_schema(cursor)
        conn.commit()
    finally:
        conn.close()

def get_database_categories() -> List[str]:
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        if _compat_is_modern_supabase_schema(cursor):
            cursor.execute("""
                SELECT COALESCE(name, category_name_zh) AS name
                FROM database_categories
                ORDER BY COALESCE(name, category_name_zh) ASC
            """)
            return [row["name"] for row in cursor.fetchall()]
        return _legacy_get_database_categories()
    finally:
        conn.close()

def add_database_category(name: str):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        if _compat_is_modern_supabase_schema(cursor):
            category_code = infer_database_category_code(name) or f"CUSTOM_{uuid.uuid4().hex[:8].upper()}"
            cursor.execute("""
                INSERT INTO database_categories (category_code, category_name_zh, description, name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (category_code) DO NOTHING
            """, (category_code, name, "user added category", name))
            conn.commit()
            clear_db_cache()
            return
    finally:
        conn.close()
    return _legacy_add_database_category(name)



def _postgres_table_has_column(cursor, table_name: str, column_name: str) -> bool:
    if not IS_POSTGRES:
        return False
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = ?
          AND column_name = ?
        """,
        (table_name, column_name),
    )
    return cursor.fetchone() is not None
