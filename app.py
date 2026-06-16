import streamlit as st
import pandas as pd
import json
import os
import io
import plotly.express as px
from fishery_schema import FisheryLogBatchSchema, FisheryLogSchema, CatchDetail, BiologicalParameterBatch, BiologicalParameterRecord
import database
import gemini_parser

api_key_env = os.environ.get("GEMINI_API_KEY", "")

# Page configuration
st.set_page_config(
    page_title="多元漁業資訊標準及智慧化系統 (DFIS)",
    page_icon="🐟",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom high-contrast deep-ocean CSS styling
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Noto+Sans+TC:wght@300;400;500;700&display=swap');

/* Main layouts and colors */
html, body, [data-testid="stAppViewContainer"] {
    font-family: 'Outfit', 'Noto Sans TC', -apple-system, BlinkMacSystemFont, sans-serif;
    background: linear-gradient(135deg, #070d19 0%, #02040a 100%);
    color: #ffffff; /* pure white for high readability */
}

[data-testid="stHeader"] {
    background-color: rgba(0,0,0,0);
}

/* Glassmorphic Container Cards with high contrast border */
.custom-card {
    background: rgba(15, 23, 42, 0.7);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(14, 165, 233, 0.3); /* bright border */
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 10px 30px 0 rgba(0, 0, 0, 0.5);
    transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
}
.custom-card:hover {
    transform: translateY(-3px);
    border-color: rgba(56, 189, 248, 0.7);
    box-shadow: 0 15px 35px 0 rgba(14, 165, 233, 0.25);
}

/* Header style */
.main-title {
    font-size: 2.8rem;
    font-weight: 700;
    background: linear-gradient(135deg, #38bdf8 0%, #0ea5e9 50%, #3b82f6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 5px;
    text-align: center;
}
.subtitle {
    font-size: 1.2rem;
    color: #cbd5e1; /* bright grey */
    text-align: center;
    margin-bottom: 30px;
}

/* Form and Input Elements overrides for high contrast visibility */
div[data-baseweb="input"], div[data-baseweb="select"] {
    background-color: #0f172a !important;
    border: 1px solid #0284c7 !important;
    border-radius: 6px !important;
}
input, select, textarea {
    color: #ffffff !important;
}
label {
    color: #ffffff !important;
    font-weight: 600 !important;
}

/* Ensure selectbox dropdown options have high contrast dark background and white text */
div[data-baseweb="popover"], [data-testid="stSelectbox"] div[role="listbox"] {
    background-color: #0f172a !important;
}
ul[role="listbox"], [role="listbox"] ul {
    background-color: #0f172a !important;
    border: 1px solid #0284c7 !important;
}
li[role="option"], [role="option"] {
    color: #ffffff !important;
    background-color: #0f172a !important;
}
li[role="option"]:hover, li[role="option"][aria-selected="true"] {
    background-color: #0284c7 !important;
    color: #ffffff !important;
}

/* Button style overrides */
div.stButton > button {
    background: linear-gradient(135deg, #0284c7 0%, #2563eb 100%);
    color: #ffffff !important;
    border: 1px solid #38bdf8;
    border-radius: 8px;
    padding: 12px 28px;
    font-weight: 600;
    font-size: 1rem;
    letter-spacing: 0.5px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
    width: 100%;
}
div.stButton > button:hover {
    background: linear-gradient(135deg, #0ea5e9 0%, #3b82f6 100%);
    box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
    transform: translateY(-2px);
    color: #ffffff !important;
}

/* Sidebar Custom Styling */
[data-testid="stSidebar"] {
    background-color: #040914;
    border-right: 2px solid rgba(14, 165, 233, 0.2);
}

/* Section Header Icons */
.section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 1.6rem;
    font-weight: 700;
    color: #38bdf8;
    border-bottom: 2px solid rgba(56, 189, 248, 0.4);
    padding-bottom: 8px;
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

# Initialize Database
database.init_db()

# ----------------- SIDEBAR NAVIGATION -----------------
st.sidebar.markdown("<div style='text-align: center; padding: 15px 0;'><h2 style='color: #38bdf8; margin: 0;'>⚓ DFIS 控制台</h2></div>", unsafe_allow_html=True)

page_selection = st.sidebar.radio(
    "功能頁面導覽",
    [
        "🏠 系統首頁 (日誌解析 & 統計)",
        "⚙️ 參數設定 (魚種/船名/港口)",
        "🗃️ 漁撈資料管理與匯出",
        "🧬 生殖資料庫 (表單管理/分析)"
    ],
    index=0
)

# ----------------- PAGE 1: 🏠 系統首頁 -----------------
if page_selection == "🏠 系統首頁 (日誌解析 & 統計)":
    st.markdown('<div class="main-title">多元漁業資訊標準及智慧化系統</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">DFIS (Diverse Fishery Information Standard & Intelligent System) Prototype</div>', unsafe_allow_html=True)

    # 1. Target Database Category Pre-selection
    st.markdown('<div class="section-header">📁 步驟一：上傳原始報表或影像</div>', unsafe_allow_html=True)
    
    col_upload_left, col_upload_right = st.columns([1, 2])
    with col_upload_left:
        db_categories = database.get_database_categories()
        selected_target_db = st.selectbox(
            "預計上傳的目標資料庫分類",
            db_categories,
            index=1,
            help="先選定預計將這些資料儲存至哪一個庫房，這將作為 AI 辨識欄位的強約束條件。"
        )
    with col_upload_right:
        uploaded_file = st.file_uploader(
            "請上傳漁撈日誌、生物量測調查表（支援 PDF, DOCX 格式，或 PNG, JPG 掃描圖片）",
            type=["pdf", "docx", "png", "jpg", "jpeg", "webp"],
            help="拖曳或選擇檔案以進行 AI 欄位標準化提取。"
        )

    # Initialize States
    if "parsed_result" not in st.session_state:
        st.session_state.parsed_result = None
    if "last_filename" not in st.session_state:
        st.session_state.last_filename = None
    if "parsed_db_type" not in st.session_state:
        st.session_state.parsed_db_type = None
    if "last_target_db" not in st.session_state:
        st.session_state.last_target_db = selected_target_db

    # Reset parsed result if a new file is uploaded or target database selection changes
    if (uploaded_file is not None and st.session_state.last_filename != uploaded_file.name) or (selected_target_db != st.session_state.last_target_db):
        st.session_state.parsed_result = None
        st.session_state.last_filename = None
        st.session_state.parsed_db_type = None
        st.session_state.last_target_db = selected_target_db

    # Parse Action
    if uploaded_file is not None and st.session_state.parsed_result is None:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.markdown("### 📄 檔案上傳成功，請確認分析設定")
        
        file_size_kb = len(uploaded_file.getvalue()) / 1024
        st.write(f"📁 **已上傳檔案**: `{uploaded_file.name}` ({file_size_kb:.2f} KB)")
        
        col_db, col_btn = st.columns([2, 1])
        with col_db:
            db_categories = database.get_database_categories()
            try:
                def_idx = db_categories.index(selected_target_db)
            except ValueError:
                def_idx = 1
            selected_target_db = st.selectbox(
                "🎯 確認匯入目標資料庫",
                db_categories,
                index=def_idx,
                key="confirm_db_selection",
                help="請務必確認上傳的報表與此資料庫類型一致，AI 將依此規格進行欄位轉換與標準化。"
            )
        with col_btn:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            run_analysis = st.button("⚡ 執行 AI 分析", use_container_width=True, key="start_ai_analysis_btn")
            
        st.markdown('</div>', unsafe_allow_html=True)
            
        if run_analysis:
            file_bytes = uploaded_file.getvalue()
            api_key = st.session_state.get("api_key", "")
            model_choice = st.session_state.get("model_choice", "gemini-2.5-flash")
            
            if not api_key:
                st.error("❌ 找不到 Gemini API 金鑰。請於左下角「系統金鑰與模型設定」輸入金鑰，或於環境變數中設定 GEMINI_API_KEY。")
            else:
                with st.spinner(f"🧠 Gemini ({model_choice}) 正在解析上傳至『{selected_target_db}』的報表..."):
                    try:
                        parsed_data = gemini_parser.parse_document_with_gemini(
                            file_bytes=file_bytes,
                            file_name=uploaded_file.name,
                            mime_type=uploaded_file.type,
                            api_key=api_key,
                            target_database_type=selected_target_db,
                            model_name=model_choice
                        )
                        st.session_state.parsed_result = parsed_data
                        st.session_state.last_filename = uploaded_file.name
                        st.session_state.parsed_db_type = selected_target_db
                        st.session_state.last_target_db = selected_target_db
                        
                        # Clear local edit buffers
                        if "edited_batch" in st.session_state:
                            del st.session_state.edited_batch
                        if "edited_bio_batch" in st.session_state:
                            del st.session_state.edited_bio_batch
                            
                        st.success("✅ AI 報表欄位識別與標準化對齊完成！請在下方進行人工覆核。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 解析失敗: {e}")
                        st.session_state.parsed_result = None
                        st.session_state.last_filename = None
                        st.session_state.parsed_db_type = None

    # 2. Render Human Review / Editor based on Database Type
    if st.session_state.parsed_result is not None:
        col_hdr_left, col_hdr_right = st.columns([3, 1])
        with col_hdr_left:
            st.markdown('<div class="section-header">🌟 步驟二：人為修正與覆核面板 (Human-in-the-Loop)</div>', unsafe_allow_html=True)
        with col_hdr_right:
            if st.button("🔄 清除結果，重新分析", use_container_width=True, key="clear_results_btn"):
                st.session_state.parsed_result = None
                st.session_state.last_filename = None
                st.session_state.parsed_db_type = None
                st.rerun()
        
        parsed = st.session_state.parsed_result
        parsed_db = st.session_state.get("parsed_db_type", selected_target_db)
        
        # Scenario A: BIOLOGICAL PARAMETER DATABASE
        if parsed_db == "生物學參數資料庫" and isinstance(parsed, BiologicalParameterBatch):
            st.info("💡 偵測為『生物學參數資料庫』。已為您套用個體量測 Pydantic 結構，全長已自動換算成公厘 (mm)，體重換算成公克 (g)。請覆核下方表格。")
            
            # Initialize state
            if "edited_bio_batch" not in st.session_state or st.session_state.get("edited_bio_file") != st.session_state.last_filename:
                st.session_state.edited_bio_batch = []
                for rec in parsed.records:
                    st.session_state.edited_bio_batch.append({
                        "collection_date": rec.collection_date,
                        "collection_id": rec.collection_id,
                        "port": rec.port,
                        "vessel_name": rec.vessel_name,
                        "form_code": rec.form_code,
                        "species_name": rec.species_name,
                        "sex": rec.sex if rec.sex is not None else "",
                        "maturity": rec.maturity if rec.maturity is not None else "",
                        "total_length_mm": rec.total_length_mm if rec.total_length_mm is not None else 0.0,
                        "weight_g": rec.weight_g if rec.weight_g is not None else 0.0,
                        "gsi": rec.gsi if rec.gsi is not None else 0.0,
                        "remarks": rec.remarks if rec.remarks is not None else ""
                    })
                st.session_state.edited_bio_file = st.session_state.last_filename
                
            df_bio_editor = pd.DataFrame(st.session_state.edited_bio_batch)
            
            # Link standard lists from DB
            std_ports = database.get_ports()["name"].tolist()
            std_vessels = database.get_vessels()["name"].tolist()
            std_species = database.get_species()["chinese_name"].tolist()
            
            # Ensure parsed values are present in options to prevent selectbox failures
            for rec in st.session_state.edited_bio_batch:
                p = rec["port"]
                v = rec["vessel_name"]
                s = rec["species_name"]
                if p and p not in std_ports:
                    std_ports.append(p)
                if v and v not in std_vessels:
                    std_vessels.append(v)
                if s and s not in std_species:
                    std_species.append(s)
            
            # Show data editor
            edited_df = st.data_editor(
                df_bio_editor,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "collection_date": st.column_config.TextColumn("採集日期", required=True),
                    "collection_id": st.column_config.TextColumn("採集編號", required=True),
                    "port": st.column_config.SelectboxColumn("港口", options=std_ports, required=True),
                    "vessel_name": st.column_config.SelectboxColumn("船名", options=std_vessels, required=True),
                    "form_code": st.column_config.TextColumn("表格代碼", required=True),
                    "species_name": st.column_config.SelectboxColumn("魚種", options=std_species, required=True),
                    "sex": st.column_config.SelectboxColumn("性別", options=["雄性", "雌性", "無性別", ""]),
                    "maturity": st.column_config.TextColumn("成熟度"),
                    "total_length_mm": st.column_config.NumberColumn("全長 (mm)", min_value=0.0, format="%.2f"),
                    "weight_g": st.column_config.NumberColumn("體重 (g)", min_value=0.0, format="%.2f"),
                    "gsi": st.column_config.NumberColumn("生殖腺指數", min_value=0.0, format="%.3f"),
                    "remarks": st.column_config.TextColumn("備註")
                }
            )
            
            # Save button for bio parameters
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📂 確認無誤，落庫保存 (存入生殖資料庫)"):
                # Validate and Save
                records_to_save = []
                for idx, row in edited_df.iterrows():
                    records_to_save.append({
                        "collection_date": row["collection_date"],
                        "collection_id": row["collection_id"],
                        "port": row["port"],
                        "vessel_name": row["vessel_name"],
                        "form_code": row["form_code"],
                        "species_name": row["species_name"],
                        "sex": row["sex"] if row["sex"] else None,
                        "maturity": row["maturity"] if row["maturity"] else None,
                        "total_length_mm": float(row["total_length_mm"]) if pd.notna(row["total_length_mm"]) else None,
                        "weight_g": float(row["weight_g"]) if pd.notna(row["weight_g"]) else None,
                        "gsi": float(row["gsi"]) if pd.notna(row["gsi"]) else None,
                        "remarks": row["remarks"] if row["remarks"] else None
                    })
                
                try:
                    database.save_biological_parameters_batch(records_to_save)
                    st.success(f"🎉 成功寫入生殖資料庫！共新增 {len(records_to_save)} 筆個體生物學紀錄。")
                    st.session_state.parsed_result = None
                    st.session_state.last_filename = None
                    st.session_state.parsed_db_type = None
                    if "edited_bio_batch" in st.session_state:
                        del st.session_state.edited_bio_batch
                    st.rerun()
                except Exception as ex:
                    st.error(f"寫入失敗: {ex}")
                    
        # Scenario B: STANDARD FISHERY LOG BATCH
        elif isinstance(parsed, FisheryLogBatchSchema):
            st.info("💡 系統已依「每船每日獨立資料」進行批次拆分，並自動校正手寫劃除（如白帶魚手寫石姥）。請覆核下方分頁中的航次日誌紀錄。")
            logs_list = parsed.logs
            
            # Initialize edit buffer
            if "edited_batch" not in st.session_state or st.session_state.get("edited_batch_file") != st.session_state.last_filename:
                st.session_state.edited_batch = []
                for log in logs_list:
                    log_item = {
                        "vessel_name": log.vessel_name,
                        "log_date": log.log_date,
                        "gear_type": log.gear_type,
                        "database_type": parsed_db, # Enforce target db
                        "gear_properties": log.gear_properties,
                        "catch_records": []
                    }
                    for record in log.catch_records:
                        log_item["catch_records"].append({
                            "species_raw_name": record.species_raw_name,
                            "species_standard_name": record.species_standard_name,
                            "weight_kg": record.weight_kg if record.weight_kg is not None else 0.0,
                            "count_individual": record.count_individual if record.count_individual is not None else 0,
                            "catch_properties": json.dumps(record.catch_properties, ensure_ascii=False)
                        })
                    st.session_state.edited_batch.append(log_item)
                st.session_state.edited_batch_file = st.session_state.last_filename
                
            # Render Tabs
            tab_titles = [f"📋 紀錄 #{idx + 1} ({item['vessel_name']} - {item['log_date']})" for idx, item in enumerate(st.session_state.edited_batch)]
            tabs = st.tabs(tab_titles)
            
            for i, tab in enumerate(tabs):
                with tab:
                    log_item = st.session_state.edited_batch[i]
                    st.markdown("##### ⚓ 基本資訊設定")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    std_vessels = database.get_vessels()["name"].tolist()
                    if log_item["vessel_name"] and log_item["vessel_name"] not in std_vessels:
                        std_vessels.append(log_item["vessel_name"])
                    if not std_vessels:
                        std_vessels = [""]
                    try:
                        v_idx = std_vessels.index(log_item["vessel_name"])
                    except ValueError:
                        v_idx = 0
                        
                    with col1:
                        log_item["vessel_name"] = st.selectbox("船名", std_vessels, index=v_idx, key=f"v_name_{i}")
                    with col2:
                        log_item["log_date"] = st.text_input("作業日期", value=log_item["log_date"], key=f"l_date_{i}")
                    with col3:
                        log_item["gear_type"] = st.text_input("作業漁法", value=log_item["gear_type"], key=f"g_type_{i}")
                    with col4:
                        # Database Type selection
                        db_categories = database.get_database_categories()
                        if log_item["database_type"] not in db_categories:
                            db_categories.append(log_item["database_type"])
                        try:
                            def_idx = db_categories.index(log_item["database_type"])
                        except ValueError:
                            def_idx = 0
                        log_item["database_type"] = st.selectbox("歸屬資料庫", db_categories, index=def_idx, key=f"d_type_{i}")
                        
                    log_item["gear_properties_str"] = st.text_area(
                        "漁具動態屬性 (JSON)",
                        value=json.dumps(log_item["gear_properties"], ensure_ascii=False, indent=2),
                        height=80,
                        key=f"g_props_{i}"
                    )
                    
                    st.markdown("##### 🐟 漁獲與量測明細")
                    df_catch = pd.DataFrame(log_item["catch_records"])
                    
                    std_species = database.get_species()["chinese_name"].tolist()
                    for idx_c, row_c in df_catch.iterrows():
                        s_name = row_c["species_standard_name"]
                        if s_name and s_name not in std_species:
                            std_species.append(s_name)
                    if not std_species:
                        std_species = [""]
                        
                    edited_catch_df = st.data_editor(
                        df_catch,
                        num_rows="dynamic",
                        use_container_width=True,
                        key=f"catch_editor_{i}",
                        column_config={
                            "species_raw_name": st.column_config.TextColumn("原始魚種名稱", required=True),
                            "species_standard_name": st.column_config.SelectboxColumn("標準魚種名稱", options=std_species, required=True),
                            "weight_kg": st.column_config.NumberColumn("重量 (kg)", min_value=0.0, format="%.3f"),
                            "count_individual": st.column_config.NumberColumn("尾數/隻數", min_value=0, step=1),
                            "catch_properties": st.column_config.TextColumn("動態屬性 (JSON)")
                        }
                    )
                    log_item["edited_df"] = edited_catch_df

            # Bulk save button
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📂 確認無誤，落庫保存"):
                errors = []
                payloads = []
                for i, log_item in enumerate(st.session_state.edited_batch):
                    # Validate gear properties JSON
                    try:
                        g_props = json.loads(st.session_state[f"g_props_{i}"])
                    except Exception:
                        errors.append(f"❌ 紀錄 #{i + 1} 的漁具動態屬性非有效的 JSON 格式！")
                        continue
                        
                    # Validate catches from editor
                    edited_df = log_item["edited_df"] if "edited_df" in log_item else pd.DataFrame(log_item["catch_records"])
                    catches = []
                    for row_idx, row in edited_df.iterrows():
                        raw_name = row["species_raw_name"]
                        std_name = row["species_standard_name"]
                        weight_val = float(row["weight_kg"]) if pd.notna(row["weight_kg"]) else None
                        count_val = int(row["count_individual"]) if pd.notna(row["count_individual"]) else None
                        
                        props_str = row["catch_properties"]
                        props_dict = {}
                        if pd.notna(props_str) and str(props_str).strip():
                            try:
                                props_dict = json.loads(props_str)
                            except Exception:
                                errors.append(f"❌ 紀錄 #{i + 1} 第 {row_idx + 1} 行的漁獲『{std_name}』動態屬性非有效的 JSON 格式！")
                                
                        catches.append({
                            "species_raw_name": raw_name,
                            "species_standard_name": std_name,
                            "weight_kg": weight_val,
                            "count_individual": count_val,
                            "catch_properties": props_dict
                        })
                        
                    payloads.append({
                        "database_type": st.session_state[f"d_type_{i}"],
                        "vessel_name": st.session_state[f"v_name_{i}"],
                        "log_date": st.session_state[f"l_date_{i}"],
                        "gear_type": st.session_state[f"g_type_{i}"],
                        "gear_properties": g_props,
                        "catch_records": catches
                    })
                    
                if errors:
                    for err in errors:
                        st.error(err)
                else:
                    try:
                        saved_ids = [database.save_fishery_log(p) for p in payloads]
                        st.success(f"🎉 成功寫入資料庫！共新增 {len(saved_ids)} 筆作業日誌（產生的航次 ID: {', '.join(map(str, saved_ids))}）")
                        st.session_state.parsed_result = None
                        st.session_state.last_filename = None
                        if "edited_batch" in st.session_state:
                            del st.session_state.edited_batch
                        st.rerun()
                    except Exception as ex:
                        st.error(f"落庫存檔失敗: {ex}")
                        
        else:
            st.error("❌ 解析結果與預設目標資料庫架構不符，請重新上傳正確的檔案，或調整目標資料庫分類。")

    # 3. STATS DASHBOARD
    st.markdown('<div class="section-header">📊 統計看板：多元漁業大數據可視化</div>', unsafe_allow_html=True)
    
    # Filter categories at top of charts
    categories_filter = ["全部資料庫"] + database.get_database_categories()
    selected_db_view = st.selectbox("🔍 請選擇要檢視的資料庫分類看板：", categories_filter, index=0)
    
    db_filter = None if selected_db_view == "全部資料庫" else selected_db_view
    df_yield = database.get_species_yield_data(database_type=db_filter)
    df_gear = database.get_gear_distribution_data(database_type=db_filter)
    
    if df_yield.empty and df_gear.empty:
        st.markdown("<div style='text-align: center; padding: 30px; color: #94a3b8;'><h3>📭 該資料庫目前尚無任何紀錄數據。</h3></div>", unsafe_allow_html=True)
    else:
        # Metrics row
        total_yield_kg = df_yield["total_weight_kg"].sum() if not df_yield.empty else 0.0
        total_logs = int(df_gear["log_count"].sum()) if not df_gear.empty else 0
        unique_species = len(df_yield["species_standard_name"].unique()) if not df_yield.empty else 0
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.markdown(f'<div class="custom-card" style="text-align:center;"><span style="color:#94a3b8;">⚓ 累計日誌航次</span><h2 style="margin:5px 0 0 0; color:#38bdf8;">{total_logs} 航次</h2></div>', unsafe_allow_html=True)
        with col_m2:
            st.markdown(f'<div class="custom-card" style="text-align:center;"><span style="color:#94a3b8;">🐟 標準魚種品項</span><h2 style="margin:5px 0 0 0; color:#10b981;">{unique_species} 種</h2></div>', unsafe_allow_html=True)
        with col_m3:
            st.markdown(f'<div class="custom-card" style="text-align:center;"><span style="color:#94a3b8;">⚖️ 總產出量 (kg)</span><h2 style="margin:5px 0 0 0; color:#f59e0b;">{total_yield_kg:,.2f} kg</h2></div>', unsafe_allow_html=True)
            
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown('<div class="custom-card">', unsafe_allow_html=True)
            st.markdown("#### 🐟 各標準魚種總產量長條圖")
            if not df_yield.empty:
                fig_yield = px.bar(
                    df_yield, x="total_weight_kg", y="species_standard_name",
                    orientation="h", labels={"total_weight_kg": "總重量 (kg)", "species_standard_name": "標準化魚種"},
                    color="total_weight_kg", color_continuous_scale="ice", template="plotly_dark"
                )
                fig_yield.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10), height=380,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    coloraxis_showscale=False, yaxis=dict(autorange="reversed")
                )
                st.plotly_chart(fig_yield, use_container_width=True)
            else:
                st.write("尚無重量統計數據。")
            st.markdown('</div>', unsafe_allow_html=True)
            
        with col_c2:
            st.markdown('<div class="custom-card">', unsafe_allow_html=True)
            st.markdown("#### 🎣 不同漁法產出佔比圓餅圖")
            if not df_gear.empty:
                fig_gear = px.pie(
                    df_gear, values="total_weight_kg", names="gear_type", hole=0.45,
                    labels={"total_weight_kg": "產出重量 (kg)", "gear_type": "漁法"},
                    color_discrete_sequence=px.colors.sequential.Tealgrn_r, template="plotly_dark"
                )
                fig_gear.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10), height=380,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
                )
                st.plotly_chart(fig_gear, use_container_width=True)
            else:
                st.write("尚無漁撈漁法統計數據。")
            st.markdown('</div>', unsafe_allow_html=True)

# ----------------- PAGE 2: ⚙️ 參數設定 -----------------
elif page_selection == "⚙️ 參數設定 (魚種/船名/港口)":
    st.markdown('<div class="main-title">⚙️ 系統基本參數設定</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">管理您的魚種代碼、作業船隻與常用採集港口列表</div>', unsafe_allow_html=True)
    
    tab_species, tab_vessels, tab_ports = st.tabs(["🐟 魚種列表", "🚢 船名列表", "⚓ 港口列表"])
    
    # Species CRUD
    with tab_species:
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.markdown("### 🐟 魚種列表與對照代碼管理")
        df_species = database.get_species()
        
        # Display species table
        st.dataframe(
            df_species,
            column_config={
                "id": "#",
                "chinese_name": "中文名",
                "code": "代碼",
                "genus": "屬名",
                "species": "種名"
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Add & Delete layout
        col_add, col_del = st.columns(2)
        with col_add:
            st.markdown("#### ➕ 新增魚種")
            with st.form("add_species_form", clear_on_submit=True):
                new_ch_name = st.text_input("魚種中文名 (必填)")
                new_code = st.text_input("代碼")
                new_genus = st.text_input("屬名 (Genus)")
                new_species = st.text_input("種名 (Species)")
                if st.form_submit_button("確認新增"):
                    if not new_ch_name.strip():
                        st.error("中文名不可為空！")
                    else:
                        database.add_species(new_ch_name.strip(), new_code.strip(), new_genus.strip(), new_species.strip())
                        st.success(f"已成功新增魚種：{new_ch_name}")
                        st.rerun()
                        
        with col_del:
            st.markdown("#### 🗑️ 刪除魚種")
            if not df_species.empty:
                species_options = {f"{row['chinese_name']} (代碼: {row['code']})": row["id"] for _, row in df_species.iterrows()}
                selected_del_species = st.selectbox("請選擇欲刪除的魚種：", list(species_options.keys()))
                if st.button("確認刪除魚種", key="del_species_btn"):
                    sp_id = species_options[selected_del_species]
                    database.delete_species(sp_id)
                    st.success("魚種已成功刪除！")
                    st.rerun()
            else:
                st.info("尚無魚種資料可刪除。")
        st.markdown('</div>', unsafe_allow_html=True)
        
    # Vessels CRUD
    with tab_vessels:
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.markdown("### 🚢 作業船隻資料管理")
        df_vessels = database.get_vessels()
        
        st.dataframe(
            df_vessels,
            column_config={"id": "#", "name": "船隻名稱", "registration_number": "漁船統一編號/船籍編號"},
            hide_index=True,
            use_container_width=True
        )
        
        col_v_add, col_v_del = st.columns(2)
        with col_v_add:
            st.markdown("#### ➕ 新增船隻")
            with st.form("add_vessel_form", clear_on_submit=True):
                new_v_name = st.text_input("船隻名稱 (必填)")
                new_v_reg = st.text_input("編號/統一編號")
                if st.form_submit_button("確認新增船隻"):
                    if not new_v_name.strip():
                        st.error("船名不可為空！")
                    else:
                        database.add_vessel(new_v_name.strip(), new_v_reg.strip())
                        st.success(f"已成功新增船隻：{new_v_name}")
                        st.rerun()
                        
        with col_v_del:
            st.markdown("#### 🗑️ 刪除船隻")
            if not df_vessels.empty:
                vessel_options = {f"{row['name']} ({row['registration_number']})": row["id"] for _, row in df_vessels.iterrows()}
                selected_del_vessel = st.selectbox("請選擇欲刪除的船隻：", list(vessel_options.keys()))
                if st.button("確認刪除船隻", key="del_vessel_btn"):
                    v_id = vessel_options[selected_del_vessel]
                    database.delete_vessel(v_id)
                    st.success("船隻資料已刪除！")
                    st.rerun()
            else:
                st.info("尚無船隻資料。")
        st.markdown('</div>', unsafe_allow_html=True)

    # Ports CRUD
    with tab_ports:
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.markdown("### ⚓ 採樣港口資料管理")
        df_ports = database.get_ports()
        
        st.dataframe(
            df_ports,
            column_config={"id": "#", "name": "港口名稱", "county": "所屬縣市"},
            hide_index=True,
            use_container_width=True
        )
        
        col_p_add, col_p_del = st.columns(2)
        with col_p_add:
            st.markdown("#### ➕ 新增港口")
            with st.form("add_port_form", clear_on_submit=True):
                new_p_name = st.text_input("港口名稱 (必填)")
                new_p_county = st.text_input("所屬縣市 (必填)")
                if st.form_submit_button("確認新增港口"):
                    if not new_p_name.strip() or not new_p_county.strip():
                        st.error("欄位不可為空！")
                    else:
                        database.add_port(new_p_name.strip(), new_p_county.strip())
                        st.success(f"已新增港口：{new_p_name}")
                        st.rerun()
                        
        with col_p_del:
            st.markdown("#### 🗑️ 刪除港口")
            if not df_ports.empty:
                port_options = {f"{row['name']} ({row['county']})": row["id"] for _, row in df_ports.iterrows()}
                selected_del_port = st.selectbox("請選擇欲刪除的港口：", list(port_options.keys()))
                if st.button("確認刪除港口", key="del_port_btn"):
                    p_id = port_options[selected_del_port]
                    database.delete_port(p_id)
                    st.success("港口已刪除！")
                    st.rerun()
            else:
                st.info("尚無港口資料。")
        st.markdown('</div>', unsafe_allow_html=True)

# ----------------- PAGE 3: 🗃️ 漁撈資料管理與匯出 -----------------
elif page_selection == "🗃️ 漁撈資料管理與匯出":
    st.markdown('<div class="main-title">🗃️ 漁撈數位化紀錄管理</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">檢索已存檔的漁撈日誌表單，支援勾選、刪除及下載 Excel/CSV 檔案</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="custom-card">', unsafe_allow_html=True)
    
    # Filters
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        db_types = ["全部資料庫"] + database.get_database_categories()
        sel_db_type = st.selectbox("篩選資料庫分類", db_types)
    with col_f2:
        search_vessel = st.text_input("篩選漁船名稱 (輸入關鍵字)")
        
    db_filter = None if sel_db_type == "全部資料庫" else sel_db_type
    df_logs = database.get_fishery_logs_list(database_type=db_filter)
    
    # Filter by vessel name if typed
    if search_vessel.strip():
        df_logs = df_logs[df_logs["vessel_name"].str.contains(search_vessel.strip(), case=False, na=False)]
        
    if df_logs.empty:
        st.write("🔍 找不到符合條件的表單紀錄。")
    else:
        st.write(f"📂 共找到 {len(df_logs)} 筆作業紀錄表單。請於下方勾選需要管理的表單：")
        
        # Display with selection checkboxes using st.data_editor
        df_logs["選取"] = False
        # Move "選取" to the first column
        cols = ["選取"] + [c for c in df_logs.columns if c != "選取"]
        df_logs = df_logs[cols]
        
        edited_logs_df = st.data_editor(
            df_logs,
            key="logs_batch_editor",
            use_container_width=True,
            column_config={
                "選取": st.column_config.CheckboxColumn("選取", default=False),
                "id": "日誌 ID (航次 ID)",
                "database_type": "資料庫分類",
                "vessel_name": "船名",
                "log_date": "作業日期",
                "gear_type": "作業漁法",
                "created_at": "建立時間"
            },
            disabled=[c for c in df_logs.columns if c != "選取"],
            hide_index=True
        )
        
        selected_ids = edited_logs_df[edited_logs_df["選取"] == True]["id"].tolist()
        
        # Action Buttons row
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 3])
        
        with col_btn1:
            # Delete Action
            if st.button("🗑️ 刪除選取紀錄"):
                if not selected_ids:
                    st.warning("請先勾選欲刪除的紀錄！")
                else:
                    try:
                        database.delete_fishery_logs(selected_ids)
                        st.success(f"已成功刪除 {len(selected_ids)} 筆作業紀錄！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"刪除失敗: {e}")
                        
        with col_btn2:
            # Export Action
            if selected_ids:
                # Merge selected logs and catches into one flat dataframe for export
                export_data = []
                for lid in selected_ids:
                    detail = database.get_fishery_log_detail(lid)
                    metadata = {
                        "日誌 ID": detail["id"],
                        "資料庫分類": detail["database_type"],
                        "船名": detail["vessel_name"],
                        "作業日期": detail["log_date"],
                        "作業漁法": detail["gear_type"],
                        "漁具動態屬性": json.dumps(detail["gear_properties"], ensure_ascii=False)
                    }
                    for catch in detail.get("catch_records", []):
                        row = metadata.copy()
                        row.update({
                            "原始魚種名稱": catch["species_raw_name"],
                            "標準魚種名稱": catch["species_standard_name"],
                            "捕獲重量 (kg)": catch["weight_kg"],
                            "尾數/隻數": catch["count_individual"],
                            "個體量測屬性 (JSON)": json.dumps(catch["catch_properties"], ensure_ascii=False)
                        })
                        export_data.append(row)
                
                df_export = pd.DataFrame(export_data)
                
                # Convert to CSV (UTF-8-SIG for Windows Excel Chinese compatibility)
                csv_bytes = df_export.to_csv(index=False).encode('utf-8-sig')
                
                st.download_button(
                    label="📥 匯出選取紀錄 (CSV 檔)",
                    data=csv_bytes,
                    file_name="fishery_records_export.csv",
                    mime="text/csv",
                    help="匯出包含基本資料與魚種漁獲明細的扁平化表單試算表。"
                )
            else:
                st.button("📥 匯出選取紀錄 (CSV 檔)", disabled=True)
                
        # Detailed Viewer Section
        if len(selected_ids) == 1:
            st.markdown("---")
            st.markdown(f"### 🔍 單筆詳細檢視 (日誌 ID: {selected_ids[0]})")
            single_detail = database.get_fishery_log_detail(selected_ids[0])
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.write(f"**船名**: {single_detail['vessel_name']}")
                st.write(f"**作業日期**: {single_detail['log_date']}")
                st.write(f"**分類資料庫**: {single_detail['database_type']}")
            with col_d2:
                st.write(f"**作業漁法**: {single_detail['gear_type']}")
                st.write(f"**漁具參數 (JSON)**: `{json.dumps(single_detail['gear_properties'], ensure_ascii=False)}`")
                
            st.markdown("**🐟 漁獲明細清單**")
            df_detail_catches = pd.DataFrame(single_detail["catch_records"])[
                ["species_raw_name", "species_standard_name", "weight_kg", "count_individual", "catch_properties"]
            ]
            st.dataframe(
                df_detail_catches,
                column_config={
                    "species_raw_name": "原始魚種",
                    "species_standard_name": "標準化魚種",
                    "weight_kg": "捕獲重量 (kg)",
                    "count_individual": "尾數/隻數",
                    "catch_properties": "動態特徵"
                },
                hide_index=True,
                use_container_width=True
            )
            
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------- PAGE 4: 🧬 生殖資料庫 -----------------
elif page_selection == "🧬 生殖資料庫 (表單管理/分析)":
    st.markdown('<div class="main-title">🧬 生殖資料庫 (生物學參數)</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">管理與篩選分析魚類生殖參數表、個體體長與體重生物學大數據</div>', unsafe_allow_html=True)
    
    tab_bio_manage, tab_bio_filter, tab_bio_export = st.tabs(["📋 表單管理", "📊 篩選分析", "📥 資料匯出"])
    
    # 1. Tab: 表單管理
    with tab_bio_manage:
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.markdown("### 📋 採集與個體測量資料表單管理")
        
        # Add new record expander
        with st.expander("➕ 手動新增生物學個體測量紀錄"):
            with st.form("add_bio_record_form", clear_on_submit=True):
                std_ports = database.get_ports()["name"].tolist()
                if not std_ports:
                    std_ports = [""]
                std_vessels = database.get_vessels()["name"].tolist()
                if not std_vessels:
                    std_vessels = [""]
                std_species = database.get_species()["chinese_name"].tolist()
                if not std_species:
                    std_species = [""]

                col_a1, col_a2, col_a3, col_a4 = st.columns(4)
                with col_a1:
                    new_b_date = st.text_input("採集日期 (YYYY-MM-DD) *", placeholder="2026-06-16")
                    new_b_id = st.text_input("採集編號 *", placeholder="Tg-2Pr")
                with col_a2:
                    new_b_port = st.selectbox("港口 *", std_ports)
                    new_b_vessel = st.selectbox("船名 *", std_vessels)
                with col_a3:
                    new_b_form = st.text_input("表格代碼 *", placeholder="1017")
                    new_b_species = st.selectbox("魚種名稱 *", std_species)
                with col_a4:
                    new_b_sex = st.selectbox("性別", ["雄性", "雌性", "無性別", ""])
                    new_b_mat = st.text_input("成熟度", placeholder="成熟")
                    
                col_a5, col_a6, col_a7, col_a8 = st.columns(4)
                with col_a5:
                    new_b_length = st.number_input("全長 (mm)", min_value=0.0, format="%.2f")
                with col_a6:
                    new_b_weight = st.number_input("體重 (g)", min_value=0.0, format="%.2f")
                with col_a7:
                    new_b_gsi = st.number_input("生殖腺指數 (GSI)", min_value=0.0, format="%.3f")
                with col_a8:
                    new_b_rem = st.text_input("備註說明")
                    
                if st.form_submit_button("新增個體紀錄"):
                    if not new_b_date or not new_b_id or not new_b_port or not new_b_vessel or not new_b_form or not new_b_species:
                        st.error("星號 (*) 標示欄位為必填項目！")
                    else:
                        payload = {
                            "collection_date": new_b_date.strip(),
                            "collection_id": new_b_id.strip(),
                            "port": new_b_port.strip(),
                            "vessel_name": new_b_vessel.strip(),
                            "form_code": new_b_form.strip(),
                            "species_name": new_b_species.strip(),
                            "sex": new_b_sex if new_b_sex else None,
                            "maturity": new_b_mat.strip() if new_b_mat.strip() else None,
                            "total_length_mm": float(new_b_length) if new_b_length > 0 else None,
                            "weight_g": float(new_b_weight) if new_b_weight > 0 else None,
                            "gsi": float(new_b_gsi) if new_b_gsi > 0 else None,
                            "remarks": new_b_rem.strip() if new_b_rem.strip() else None
                        }
                        database.save_biological_parameter(payload)
                        st.success(f"🎉 成功寫入個體量測紀錄 {new_b_id}！")
                        st.rerun()
                        
        # Display main parameters list
        df_bio_all = database.get_biological_parameters()
        
        if df_bio_all.empty:
            st.write("暫無生物量測數據。")
        else:
            # Inline st.data_editor to edit items directly
            st.markdown("##### 💡 雙擊儲存格可直接修改文字與數字參數，勾選左側後點選下方刪除鈕即可刪除：")
            
            df_bio_all["選取"] = False
            cols_order = ["選取"] + [col for col in df_bio_all.columns if col != "選取"]
            df_bio_all = df_bio_all[cols_order]
            
            std_ports = database.get_ports()["name"].tolist()
            std_vessels = database.get_vessels()["name"].tolist()
            std_species = database.get_species()["chinese_name"].tolist()
            
            for idx_bp, row_bp in df_bio_all.iterrows():
                p = row_bp["port"]
                v = row_bp["vessel_name"]
                s = row_bp["species_name"]
                if p and p not in std_ports:
                    std_ports.append(p)
                if v and v not in std_vessels:
                    std_vessels.append(v)
                if s and s not in std_species:
                    std_species.append(s)
            
            if not std_ports:
                std_ports = [""]
            if not std_vessels:
                std_vessels = [""]
            if not std_species:
                std_species = [""]

            edited_bio_table = st.data_editor(
                df_bio_all,
                key="bio_db_editor",
                use_container_width=True,
                column_config={
                    "選取": st.column_config.CheckboxColumn("選取", default=False),
                    "id": "# ID",
                    "collection_date": st.column_config.TextColumn("採集日期", required=True),
                    "collection_id": st.column_config.TextColumn("採集編號", required=True),
                    "port": st.column_config.SelectboxColumn("港口", options=std_ports, required=True),
                    "vessel_name": st.column_config.SelectboxColumn("船名", options=std_vessels, required=True),
                    "form_code": st.column_config.TextColumn("新表代碼", required=True),
                    "species_name": st.column_config.SelectboxColumn("魚種", options=std_species, required=True),
                    "sex": st.column_config.SelectboxColumn("性別", options=["雄性", "雌性", "無性別", ""]),
                    "maturity": st.column_config.TextColumn("成熟度"),
                    "total_length_mm": st.column_config.NumberColumn("全長 (mm)", format="%.2f"),
                    "weight_g": st.column_config.NumberColumn("體重 (g)", format="%.2f"),
                    "gsi": st.column_config.NumberColumn("生殖腺指數", format="%.3f"),
                    "remarks": st.column_config.TextColumn("備註"),
                    "created_at": st.column_config.TextColumn("建立時間", disabled=True)
                },
                disabled=["id", "created_at"],
                hide_index=True
            )
            
            # Action Buttons: Update and Delete
            col_b_act1, col_b_act2 = st.columns([1, 4])
            with col_b_act1:
                # Delete Selected
                selected_bio_ids = edited_bio_table[edited_bio_table["選取"] == True]["id"].tolist()
                if st.button("🗑️ 刪除選取量測"):
                    if not selected_bio_ids:
                        st.warning("請先勾選欲刪除項目！")
                    else:
                        for bid in selected_bio_ids:
                            database.delete_biological_parameter(bid)
                        st.success(f"已刪除 {len(selected_bio_ids)} 筆生物量測紀錄！")
                        st.rerun()
            with col_b_act2:
                # Save edits
                if st.button("💾 保存表格中的修改項目", help="將您直接在表格中編輯後的文字與數字寫回資料庫"):
                    # We compare the edited dataframe with original and update changed records
                    saved_count = 0
                    for _, row in edited_bio_table.iterrows():
                        payload = {
                            "id": int(row["id"]),
                            "collection_date": str(row["collection_date"]),
                            "collection_id": str(row["collection_id"]),
                            "port": str(row["port"]),
                            "vessel_name": str(row["vessel_name"]),
                            "form_code": str(row["form_code"]),
                            "species_name": str(row["species_name"]),
                            "sex": row["sex"] if row["sex"] else None,
                            "maturity": row["maturity"] if row["maturity"] else None,
                            "total_length_mm": float(row["total_length_mm"]) if pd.notna(row["total_length_mm"]) else None,
                            "weight_g": float(row["weight_g"]) if pd.notna(row["weight_g"]) else None,
                            "gsi": float(row["gsi"]) if pd.notna(row["gsi"]) else None,
                            "remarks": row["remarks"] if row["remarks"] else None
                        }
                        database.save_biological_parameter(payload)
                        saved_count += 1
                    st.success(f"🎉 成功更新共 {saved_count} 筆個體生物學紀錄！")
                    st.rerun()
                    
        st.markdown('</div>', unsafe_allow_html=True)
        
    # 2. Tab: 篩選分析
    with tab_bio_filter:
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.markdown("### 📊 生殖資料庫篩選分析")
        
        df_bio_analysis = database.get_biological_parameters()
        
        if df_bio_analysis.empty:
            st.write("尚無分析數據。")
        else:
            col_an1, col_an2, col_an3 = st.columns(3)
            with col_an1:
                sp_list = ["全部魚種"] + list(df_bio_analysis["species_name"].unique())
                sel_sp = st.selectbox("魚種過濾", sp_list, key="an_sp")
            with col_an2:
                pt_list = ["全部港口"] + list(df_bio_analysis["port"].unique())
                sel_pt = st.selectbox("採樣港口過濾", pt_list, key="an_pt")
            with col_an3:
                sx_list = ["全部性別", "雄性", "雌性", "無性別"]
                sel_sx = st.selectbox("性別過濾", sx_list, key="an_sx")
                
            # Filter DataFrame
            df_filtered = df_bio_analysis.copy()
            if sel_sp != "全部魚種":
                df_filtered = df_filtered[df_filtered["species_name"] == sel_sp]
            if sel_pt != "全部港口":
                df_filtered = df_filtered[df_filtered["port"] == sel_pt]
            if sel_sx != "全部性別":
                df_filtered = df_filtered[df_filtered["sex"] == sel_sx]
                
            if df_filtered.empty:
                st.warning("篩選條件下無符合數據。")
            else:
                col_ch1, col_ch2 = st.columns(2)
                
                with col_ch1:
                    st.write("#### 📏 全長 (mm) 與體重 (g) 關係分佈散佈圖")
                    # Scatter plot length vs weight
                    fig_scatter = px.scatter(
                        df_filtered,
                        x="total_length_mm",
                        y="weight_g",
                        color="sex",
                        hover_data=["collection_id", "maturity", "gsi"],
                        labels={"total_length_mm": "全長 (mm)", "weight_g": "體重 (g)", "sex": "性別"},
                        color_discrete_map={"雄性": "#00f0ff", "雌性": "#ff007f", "無性別": "#aaaaaa"},
                        template="plotly_dark"
                    )
                    fig_scatter.update_layout(
                        margin=dict(l=10, r=10, t=10, b=10), height=350,
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)
                    
                with col_ch2:
                    st.write("#### 🥚 生殖腺指數 (GSI) 箱形分佈圖")
                    # GSI Box plot by maturity/sex
                    fig_box = px.box(
                        df_filtered,
                        x="sex",
                        y="gsi",
                        color="sex",
                        labels={"sex": "性別", "gsi": "生殖腺指數 (GSI)"},
                        color_discrete_map={"雄性": "#00f0ff", "雌性": "#ff007f", "無性別": "#aaaaaa"},
                        template="plotly_dark"
                    )
                    fig_box.update_layout(
                        margin=dict(l=10, r=10, t=10, b=10), height=350,
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
                    )
                    st.plotly_chart(fig_box, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    # 3. Tab: 資料匯出
    with tab_bio_export:
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.markdown("### 📥 條件式個體生殖資料篩選與匯出")
        
        df_bio_all = database.get_biological_parameters()
        if df_bio_all.empty:
            st.write("資料庫為空，無法匯出。")
        else:
            col_ex1, col_ex2, col_ex3 = st.columns(3)
            with col_ex1:
                exp_sp = st.multiselect("選取魚種 (多選)", list(df_bio_all["species_name"].unique()))
            with col_ex2:
                exp_pt = st.multiselect("選取採樣港口 (多選)", list(df_bio_all["port"].unique()))
            with col_ex3:
                exp_sex = st.multiselect("選取性別 (多選)", list(df_bio_all["sex"].unique()))
                
            # Filter
            df_exp_filtered = df_bio_all.copy()
            if exp_sp:
                df_exp_filtered = df_exp_filtered[df_exp_filtered["species_name"].isin(exp_sp)]
            if exp_pt:
                df_exp_filtered = df_exp_filtered[df_exp_filtered["port"].isin(exp_pt)]
            if exp_sex:
                df_exp_filtered = df_exp_filtered[df_exp_filtered["sex"].isin(exp_sex)]
                
            st.write(f"篩選過後共 {len(df_exp_filtered)} 筆量測明細記錄。")
            st.dataframe(
                df_exp_filtered,
                column_config={
                    "id": "#",
                    "collection_date": "採集日期",
                    "collection_id": "採集編號",
                    "port": "港口",
                    "vessel_name": "船名",
                    "form_code": "表格代碼",
                    "species_name": "魚種",
                    "sex": "性別",
                    "maturity": "成熟度",
                    "total_length_mm": "全長(mm)",
                    "weight_g": "體重(g)",
                    "gsi": "生殖腺指數",
                    "remarks": "備註"
                },
                hide_index=True,
                use_container_width=True
            )
            
            # Export download button
            csv_exp_bytes = df_exp_filtered.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📥 匯出篩選結果 (CSV 檔)",
                data=csv_exp_bytes,
                file_name="reproduction_records_export.csv",
                mime="text/csv",
                help="匯出篩選後的個體體長與生殖腺量測試算表檔案。"
            )
        st.markdown('</div>', unsafe_allow_html=True)


# ----------------- SIDEBAR BOTTOM CREDENTIALS EXPANDER -----------------
# Push expander to the bottom of the sidebar
st.sidebar.markdown("<br>" * 10, unsafe_allow_html=True)
with st.sidebar.expander("🔑 系統金鑰與模型設定"):
    # API key
    api_key_input = st.text_input(
        "Gemini API 金鑰",
        type="password",
        value=st.session_state.get("api_key", api_key_env),
        placeholder="金鑰 (若無設定環境變數)"
    )
    if api_key_input:
        st.session_state["api_key"] = api_key_input
    
    # Model Choice
    model_choice_box = st.selectbox(
        "AI 核心模型",
        ["gemini-2.5-flash", "gemini-2.5-pro"],
        index=0,
        help="預設使用 2.5-flash 以取得速度與精準的平衡。若報表複雜請切換至 2.5-pro。"
    )
    st.session_state["model_choice"] = model_choice_box
