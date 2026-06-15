import streamlit as st
import pandas as pd
import json
import os
import plotly.express as px
from schema import FisheryLogBatchSchema, FisheryLogSchema, CatchDetail
import database
import gemini_parser

# Page configuration
st.set_page_config(
    page_title="多元漁業資訊標準及智慧化系統 (DFIS)",
    page_icon="🐟",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom deep-ocean CSS styling
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Noto+Sans+TC:wght@300;400;500;700&display=swap');

/* Main layouts and colors */
html, body, [data-testid="stAppViewContainer"] {
    font-family: 'Outfit', 'Noto Sans TC', -apple-system, BlinkMacSystemFont, sans-serif;
    background: linear-gradient(135deg, #0b1528 0%, #030712 100%);
    color: #f1f5f9;
}

[data-testid="stHeader"] {
    background-color: rgba(0,0,0,0);
}

/* Glassmorphic Container Cards */
.custom-card {
    background: rgba(15, 23, 42, 0.45);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 10px 30px 0 rgba(0, 0, 0, 0.4);
    transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
}
.custom-card:hover {
    transform: translateY(-3px);
    border-color: rgba(14, 165, 233, 0.4);
    box-shadow: 0 15px 35px 0 rgba(14, 165, 233, 0.15);
}

/* Header style */
.main-title {
    font-size: 2.6rem;
    font-weight: 700;
    background: linear-gradient(135deg, #38bdf8 0%, #0284c7 50%, #2563eb 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 5px;
    text-align: center;
}
.subtitle {
    font-size: 1.1rem;
    color: #94a3b8;
    text-align: center;
    margin-bottom: 30px;
}

/* Button style overrides */
div.stButton > button {
    background: linear-gradient(135deg, #0284c7 0%, #2563eb 100%);
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 12px 28px;
    font-weight: 600;
    font-size: 1rem;
    letter-spacing: 0.5px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.3);
    width: 100%;
}
div.stButton > button:hover {
    background: linear-gradient(135deg, #0ea5e9 0%, #3b82f6 100%);
    box-shadow: 0 6px 20px rgba(59, 130, 246, 0.5);
    transform: translateY(-2px);
    color: #ffffff;
}
div.stButton > button:active {
    transform: translateY(1px);
}

/* Sidebar Custom Styling */
[data-testid="stSidebar"] {
    background-color: #080f1d;
    border-right: 1px solid rgba(255, 255, 255, 0.05);
}

/* Section Header Icons */
.section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 1.5rem;
    font-weight: 600;
    color: #38bdf8;
    border-bottom: 2px solid rgba(56, 189, 248, 0.2);
    padding-bottom: 8px;
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

# Initialize Database
database.init_db()

# Sidebar: System configuration
st.sidebar.markdown("### 🛠️ 系統設定")

# 1. API Key config
api_key_env = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
api_key_input = st.sidebar.text_input(
    "Gemini API Key",
    type="password",
    value=st.session_state.get("api_key", api_key_env),
    placeholder="輸入 API 金鑰 (若無設定環境變數)",
    help="提供您的 Gemini API Key。若系統環境變數中已設定 GEMINI_API_KEY，可留空。"
)

# Store API key in session state
if api_key_input:
    st.session_state["api_key"] = api_key_input
else:
    st.session_state["api_key"] = api_key_env

# 2. Model Selection
model_choice = st.sidebar.selectbox(
    "Gemini 模型選擇",
    ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.5-flash", "gemini-2.5-pro"],
    index=0,
    help="推薦使用穩定版 gemini-1.5-pro 或 gemini-1.5-flash 以確保提取品質與穩定度。若帳號支援亦可選擇最新的 2.5 系列模型。"
)

# 3. Dynamic Database Category Manager
st.sidebar.markdown("---")
st.sidebar.markdown("### 🗃️ 資料庫分類管理")
categories = database.get_database_categories()
st.sidebar.write("目前支援的資料庫分類：")
for cat in categories:
    st.sidebar.markdown(f"- **{cat}**")

new_cat_name = st.sidebar.text_input("新增自訂資料庫分類", placeholder="例如：圍網類漁業報表資料庫")
if st.sidebar.button("➕ 新增資料庫分類"):
    if new_cat_name.strip():
        if new_cat_name.strip() in categories:
            st.sidebar.warning("⚠️ 該資料庫分類已存在！")
        else:
            database.add_database_category(new_cat_name.strip())
            st.sidebar.success(f"🎉 已成功新增資料庫：{new_cat_name.strip()}")
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 範例數據操作")

# Seeding action
if st.sidebar.button("💡 匯入模擬範例數據", help="若資料庫為空，點擊此按鈕可快速匯入一些模擬的漁撈與生物量測紀錄。"):
    try:
        seeded = database.seed_sample_data()
        if seeded:
            st.sidebar.success("🎉 成功匯入範例數據！")
            st.rerun()
        else:
            st.sidebar.info("資料庫已有現存數據，跳過匯入。")
    except Exception as e:
        st.sidebar.error(f"匯入失敗: {e}")

# Main Layout Headers
st.markdown('<div class="main-title">多元漁業資訊標準及智慧化系統</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">DFIS (Diverse Fishery Information Standard & Intelligent System) Prototype</div>', unsafe_allow_html=True)

# ----------------- SECTION 1: UPLOAD & PARSING -----------------
st.markdown('<div class="section-header">📁 步驟一：上傳原始報表或影像</div>', unsafe_allow_html=True)

# Initialize Session States
if "parsed_result" not in st.session_state:
    st.session_state.parsed_result = None
if "last_filename" not in st.session_state:
    st.session_state.last_filename = None

uploaded_file = st.file_uploader(
    "請上傳漁撈日誌、生物量測調查表（支援 PDF, DOCX 格式，或 PNG, JPG 掃描圖片）",
    type=["pdf", "docx", "png", "jpg", "jpeg", "webp"],
    help="拖曳或選擇檔案以進行 AI 欄位標準化提取。"
)

# If a file is uploaded and it's new, trigger Gemini Parsing
if uploaded_file is not None:
    if st.session_state.last_filename != uploaded_file.name:
        file_bytes = uploaded_file.read()
        
        # Verify API Key
        current_api_key = st.session_state.get("api_key", "")
        if not current_api_key:
            st.error("❌ 找不到 Gemini API 金鑰。請在左側邊欄輸入 API 金鑰，或於伺服器設定環境變數 GEMINI_API_KEY。")
        else:
            with st.spinner("🧠 Gemini 正在以 Structured Outputs 技術進行多重作業拆分、手寫塗改校正與報表自動解析..."):
                try:
                    parsed_batch = gemini_parser.parse_document_with_gemini(
                        file_bytes=file_bytes,
                        file_name=uploaded_file.name,
                        mime_type=uploaded_file.type,
                        api_key=current_api_key,
                        model_name=model_choice
                    )
                    # Cache in state
                    st.session_state.parsed_result = parsed_batch
                    st.session_state.last_filename = uploaded_file.name
                    
                    # Clear edit state to force reload
                    if "edited_batch" in st.session_state:
                        del st.session_state.edited_batch
                        
                    st.success(f"✅ AI 報表解析完成！成功識別出 {len(parsed_batch.logs)} 筆作業日誌（包含多重日期/航次拆分），請於下方覆核。")
                except Exception as e:
                    st.error(f"❌ 解析失敗: {e}")
                    st.session_state.parsed_result = None
                    st.session_state.last_filename = None

# ----------------- SECTION 2: HUMAN REVIEW & EDITING (BATCH) -----------------
if st.session_state.parsed_result is not None:
    st.markdown('<div class="section-header">🌟 步驟二：人為修正與覆核面板 (Human-in-the-Loop)</div>', unsafe_allow_html=True)
    st.info("💡 系統已依照「每船每日獨立資料」進行批次拆分，並套用手寫劃除替代規則（如劃除 '白帶魚' 改為 '石姥'）。您可以在下方分頁分別修正各日記錄。")
    
    parsed_batch = st.session_state.parsed_result
    logs_list = parsed_batch.logs
    
    # Initialize the temporary editing buffer in session state to maintain state during inputs
    if "edited_batch" not in st.session_state or st.session_state.get("edited_batch_file") != st.session_state.last_filename:
        st.session_state.edited_batch = []
        for log in logs_list:
            log_item = {
                "vessel_name": log.vessel_name,
                "log_date": log.log_date,
                "gear_type": log.gear_type,
                "database_type": log.database_type,
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

    # Build Tab UI for batch logs
    tab_titles = []
    for idx, item in enumerate(st.session_state.edited_batch):
        tab_titles.append(f"📋 紀錄 #{idx + 1} ({item['vessel_name']} - {item['log_date']})")
        
    tabs = st.tabs(tab_titles)
    
    for i, tab in enumerate(tabs):
        with tab:
            log_item = st.session_state.edited_batch[i]
            
            st.markdown(f"#### ⚓ 1. 紀錄 #{i + 1} 基本資訊設定")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                log_item["vessel_name"] = st.text_input(
                    "漁船名稱 (vessel_name)",
                    value=log_item["vessel_name"],
                    key=f"v_name_{i}"
                )
            with col2:
                log_item["log_date"] = st.text_input(
                    "作業日期 (log_date)",
                    value=log_item["log_date"],
                    key=f"l_date_{i}",
                    help="格式：YYYY-MM-DD"
                )
            with col3:
                log_item["gear_type"] = st.text_input(
                    "作業漁法 (gear_type)",
                    value=log_item["gear_type"],
                    key=f"g_type_{i}"
                )
            with col4:
                # Choose database category (dynamic from database + fallback)
                db_categories = database.get_database_categories()
                if log_item["database_type"] not in db_categories:
                    db_categories.append(log_item["database_type"])
                
                # Render selectbox
                try:
                    default_idx = db_categories.index(log_item["database_type"])
                except ValueError:
                    default_idx = 0
                    
                log_item["database_type"] = st.selectbox(
                    "指定資料庫分類",
                    db_categories,
                    index=default_idx,
                    key=f"d_type_{i}",
                    help="請選擇本紀錄應歸入的資料庫類別"
                )
                
            st.markdown("##### ⚙️ 漁法/調查專屬參數 (gear_properties)")
            log_item["gear_properties_str"] = st.text_area(
                "漁具動態屬性 (JSON)",
                value=json.dumps(log_item["gear_properties"], ensure_ascii=False, indent=2),
                height=100,
                key=f"g_props_{i}",
                help="填寫該紀錄專屬參數，如經緯度、水深或拖網時間等。"
            )
            
            st.markdown("#### 🐟 2. 漁獲與量測指標明細")
            df_catch = pd.DataFrame(log_item["catch_records"])
            
            # Interactive st.data_editor
            edited_catch_df = st.data_editor(
                df_catch,
                num_rows="dynamic",
                use_container_width=True,
                key=f"catch_editor_{i}",
                column_config={
                    "species_raw_name": st.column_config.TextColumn(
                        "原始魚種名稱",
                        help="報表中的原有名稱(已排除手寫劃除，以手寫更新為準)",
                        required=True
                    ),
                    "species_standard_name": st.column_config.TextColumn(
                        "標準魚種名稱",
                        help="標準對齊中文俗名或學名",
                        required=True
                    ),
                    "weight_kg": st.column_config.NumberColumn(
                        "捕獲重量 (kg)",
                        help="請填寫換算成公斤(kg)後的數值。1台斤 = 0.6公斤",
                        min_value=0.0,
                        format="%.3f"
                    ),
                    "count_individual": st.column_config.NumberColumn(
                        "尾數/隻數",
                        help="捕獲的個體數量",
                        min_value=0,
                        step=1
                    ),
                    "catch_properties": st.column_config.TextColumn(
                        "個體量測與動態屬性 (JSON)",
                        help="請填入有效的 JSON 字串。例如單尾量測：{'fork_length_mm': 142.5}"
                    )
                }
            )
            # Store back the dataframe pointer
            log_item["edited_df"] = edited_catch_df

    # Batch save button
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📂 確認無誤，落庫保存", help="將以上所有分頁分拆好的航次紀錄整批寫入 SQLite 資料庫中"):
        errors = []
        payloads_to_save = []
        
        # Validate all tabs first
        for i, log_item in enumerate(st.session_state.edited_batch):
            # 1. Validate gear properties JSON
            gear_props_str = st.session_state[f"g_props_{i}"]
            try:
                gear_properties_dict = json.loads(gear_props_str)
            except Exception:
                errors.append(f"❌ 紀錄 #{i + 1} 的漁具動態屬性非有效的 JSON 格式！")
                continue
                
            # 2. Validate catches from editor
            # Read editor output (holds modifications)
            edited_df = log_item["edited_df"] if "edited_df" in log_item else pd.DataFrame(log_item["catch_records"])
            
            catches_list = []
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
                        errors.append(f"❌ 紀錄 #{i + 1} 表格中第 {row_idx + 1} 行的漁獲『{std_name}』動態屬性非有效的 JSON 格式！")
                        
                catches_list.append({
                    "species_raw_name": raw_name,
                    "species_standard_name": std_name,
                    "weight_kg": weight_val,
                    "count_individual": count_val,
                    "catch_properties": props_dict
                })
                
            payloads_to_save.append({
                "database_type": st.session_state[f"d_type_{i}"],
                "vessel_name": st.session_state[f"v_name_{i}"],
                "log_date": st.session_state[f"l_date_{i}"],
                "gear_type": st.session_state[f"g_type_{i}"],
                "gear_properties": gear_properties_dict,
                "catch_records": catches_list
            })
            
        if errors:
            for err in errors:
                st.error(err)
        else:
            # Commit batch to database
            try:
                inserted_ids = []
                for payload in payloads_to_save:
                    log_id = database.save_fishery_log(payload)
                    inserted_ids.append(log_id)
                st.success(f"🎉 成功寫入資料庫！共建立 {len(inserted_ids)} 筆獨立日誌，新增航次 ID 為: {', '.join(map(str, inserted_ids))}")
                
                # Clear session state
                st.session_state.parsed_result = None
                st.session_state.last_filename = None
                if "edited_batch" in st.session_state:
                    del st.session_state.edited_batch
                    
                # Refresh dashboard
                st.rerun()
            except Exception as ex:
                st.error(f"寫入資料庫失敗: {ex}")

# ----------------- SECTION 3: VISUALIZATION DASHBOARD -----------------
st.markdown('<div class="section-header">📊 統計看板：多元漁業大數據可視化</div>', unsafe_allow_html=True)

# Database Filter selector at dashboard level
categories_filter = ["全部資料庫"] + database.get_database_categories()
selected_db = st.selectbox(
    "🔍 請選擇要檢視的資料庫分類看板：",
    categories_filter,
    index=0
)

# Fetch stats based on selected database
db_filter_val = None if selected_db == "全部資料庫" else selected_db
df_yield = database.get_species_yield_data(database_type=db_filter_val)
df_gear = database.get_gear_distribution_data(database_type=db_filter_val)

if df_yield.empty and df_gear.empty:
    st.markdown(
        f"<div style='text-align: center; padding: 40px; color: #64748b;'>"
        f"<h3>📭 該資料庫分類 ({selected_db}) 尚無資料庫記錄</h3>"
        f"<p>請於上方解析新報表並歸類至此資料庫，或點選側邊欄的<strong>『匯入模擬範例數據』</strong>以載入統計資訊。</p>"
        f"</div>",
        unsafe_allow_html=True
    )
else:
    # KPI metrics row
    total_yield_kg = df_yield["total_weight_kg"].sum() if not df_yield.empty else 0.0
    total_logs = int(df_gear["log_count"].sum()) if not df_gear.empty else 0
    unique_species = len(df_yield["species_standard_name"].unique()) if not df_yield.empty else 0
    
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.markdown(f"""
        <div class="custom-card" style="text-align: center;">
            <span style="font-size: 1.1rem; color: #94a3b8;">⚓ 累計作業航次數 ({selected_db})</span>
            <h2 style="font-size: 2.2rem; color: #38bdf8; margin: 8px 0 0 0;">{total_logs} 航次</h2>
        </div>
        """, unsafe_allow_html=True)
    with col_m2:
        st.markdown(f"""
        <div class="custom-card" style="text-align: center;">
            <span style="font-size: 1.1rem; color: #94a3b8;">🐟 標準化魚種品項 ({selected_db})</span>
            <h2 style="font-size: 2.2rem; color: #10b981; margin: 8px 0 0 0;">{unique_species} 種</h2>
        </div>
        """, unsafe_allow_html=True)
    with col_m3:
        st.markdown(f"""
        <div class="custom-card" style="text-align: center;">
            <span style="font-size: 1.1rem; color: #94a3b8;">⚖️ 總產出量 (kg) ({selected_db})</span>
            <h2 style="font-size: 2.2rem; color: #f59e0b; margin: 8px 0 0 0;">{total_yield_kg:,.2f} kg</h2>
        </div>
        """, unsafe_allow_html=True)
        
    # Charts layouts
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown("<div class=\"custom-card\">", unsafe_allow_html=True)
        st.markdown("#### 🐟 各標準魚種總產量長條圖")
        if not df_yield.empty:
            fig_yield = px.bar(
                df_yield,
                x="total_weight_kg",
                y="species_standard_name",
                orientation="h",
                labels={"total_weight_kg": "總重量 (kg)", "species_standard_name": "標準化魚種"},
                color="total_weight_kg",
                color_continuous_scale="ice",
                template="plotly_dark"
            )
            fig_yield.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                height=380,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False,
                xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(autorange="reversed")
            )
            st.plotly_chart(fig_yield, use_container_width=True)
        else:
            st.info("尚無魚種產量重量數據。")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_chart2:
        st.markdown("<div class=\"custom-card\">", unsafe_allow_html=True)
        st.markdown("#### 🎣 不同漁法產出佔比圓餅圖")
        if not df_gear.empty:
            fig_gear = px.pie(
                df_gear,
                values="total_weight_kg",
                names="gear_type",
                hole=0.45,
                labels={"total_weight_kg": "產出重量 (kg)", "gear_type": "漁法類型"},
                color_discrete_sequence=px.colors.sequential.Tealgrn_r,
                template="plotly_dark"
            )
            fig_gear.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                height=380,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig_gear, use_container_width=True)
        else:
            st.info("尚無作業漁法統計數據。")
        st.markdown("</div>", unsafe_allow_html=True)
