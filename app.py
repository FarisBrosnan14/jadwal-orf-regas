import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import base64
import os

# =====================================================================
# 1. KONFIGURASI UTAMA & KONSTANTA
# =====================================================================
st.set_page_config(page_title="NR ORF Command", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

ID_SHEET_JADWAL = "1HuIrvhzm7xzXXbX5Foy2XPms7NLzFyttgH58Ez31pj0"
ID_SHEET_IZIN = "1mdr7InOGhuVwLCpgPW-fDVOMw38XvELlXK9sxJymMYU"

URL_JADWAL = f"https://docs.google.com/spreadsheets/d/{ID_SHEET_JADWAL}/edit#gid=0"
URL_IZIN = f"https://docs.google.com/spreadsheets/d/{ID_SHEET_IZIN}/edit"
URL_GFORM = "https://forms.gle/KB9CkfEsLB4yY9MK9"

PIN_MANAGER = "regas123"
DAFTAR_MANAJER = ["-- Pilih Nama Anda --", "Yosep Zulkarnain", "Ade Imat", "Benny Sulistio", "Ibrahim"]

# Database Sederhana untuk Hari Libur / Event Nasional (Bisa ditambah)
EVENT_KALENDER = {
    "01-01": "Tahun Baru Masehi",
    "02-08": "Isra Mikraj Nabi Muhammad",
    "02-10": "Tahun Baru Imlek",
    "03-11": "Hari Suci Nyepi",
    "03-29": "Wafat Isa Al Masih",
    "03-31": "Hari Paskah",
    "04-10": "Hari Raya Idul Fitri",
    "04-11": "Hari Raya Idul Fitri",
    "05-01": "Hari Buruh Internasional",
    "05-09": "Kenaikan Isa Al Masih",
    "05-23": "Hari Raya Waisak",
    "06-01": "Hari Lahir Pancasila",
    "06-17": "Hari Raya Idul Adha",
    "07-07": "Tahun Baru Islam",
    "08-17": "Hari Kemerdekaan RI 🇮🇩",
    "09-16": "Maulid Nabi Muhammad SAW",
    "12-25": "Hari Raya Natal"
}


# =====================================================================
# 2. FUNGSI BANTUAN (UTILITIES)
# =====================================================================
def get_base64_image(file_name):
    try:
        with open(file_name, 'rb') as f: return base64.b64encode(f.read()).decode()
    except Exception: return None

def find_col(df, keywords, default_name):
    if df.empty: return default_name
    for col in df.columns:
        if any(kw in str(col).lower() for kw in keywords): return col
    return default_name

def generate_html_card(row, col_reason, col_proof, delay):
    alasan = str(row.get(col_reason, '-')).strip()
    if alasan.lower() in ['nan', '']: alasan = 'Tidak ada keterangan'
    
    bukti = str(row.get(col_proof, '')).strip()
    if bukti.startswith('http'):
        bukti_html = f"<a href='{bukti}' target='_blank' class='link-hover' style='color:#38bdf8; text-decoration:none; display:inline-flex; align-items:center;'><span class='material-symbols-rounded' style='font-size:16px; margin-right:4px;'>attach_file</span> Buka Dokumen</a>"
    else:
        bukti_html = "<span style='color:#64748b; font-style:italic; display:inline-flex; align-items:center;'><span class='material-symbols-rounded' style='font-size:16px; margin-right:4px;'>description_off</span> Tidak ada lampiran</span>"

    return f"""
    <div style='animation: slideInRight 0.4s cubic-bezier(0.16, 1, 0.3, 1) {delay}s both;'>
        <div style='display:flex; align-items:center; gap:8px;'>
            <span class='material-symbols-rounded' style='color:#38bdf8; font-size:20px;'>person</span>
            <b style='font-size:16px; color:#ffffff;'>{row['Nama Lengkap Operator']}</b> 
            <span style='color:#94a3b8; font-weight:500; font-size:13px;'>({row.get('Jenis Izin yang Diajukan', 'Izin')})</span>
        </div>
        <div style='font-size:14px; margin-top:12px; color:#e2e8f0; display:flex; align-items:center; gap:6px;'>
            <span class='material-symbols-rounded' style='font-size:16px; color:#94a3b8;'>calendar_month</span> 
            {row['Tanggal Mulai Izin']} s/d {row['Tanggal Selesai Izin']}
            <span style='color:#64748b;'>|</span>
            <span class='material-symbols-rounded' style='font-size:16px; color:#94a3b8;'>schedule</span> Shift: {row.get('Shift Izin', 'Pg')}
        </div>
        <div style='margin-top:12px; background: rgba(255,255,255,0.03); border-left: 3px solid #64748b; padding: 12px; border-radius: 6px; transition: background 0.3s;'>
            <div style='font-size:13px; color:#cbd5e1; margin-bottom:8px; line-height:1.5;'>
                <div style='display:flex; align-items:center; gap:4px; margin-bottom:4px; color:#94a3b8;'>
                    <span class='material-symbols-rounded' style='font-size:14px;'>notes</span> <b>Alasan / Keterangan:</b>
                </div>
                {alasan}
            </div>
            <div style='font-size:13px; margin-top:8px; border-top:1px dashed rgba(255,255,255,0.1); padding-top:8px;'>{bukti_html}</div>
        </div>
        <div style='font-size:13px; color:#fca5a5; font-weight:600; margin-top:12px; margin-bottom:4px; background: rgba(239,68,68,0.15); padding: 6px 10px; border-radius: 6px; display:inline-flex; align-items:center; gap:6px;'>
            <span class='material-symbols-rounded' style='font-size:16px;'>sync_alt</span> 
            Pengganti: {row.get('Nama Lengkap Operator Pengganti', '-')}
        </div>
    </div>
    """


# =====================================================================
# 3. LAYANAN DATABASE (GSPREAD)
# =====================================================================
def get_client():
    try:
        creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception: return None

@st.cache_data(ttl=2) 
def load_all_data():
    client = get_client()
    df_j, df_i, df_k = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    if not client: return df_j, df_i, df_k

    try:
        ws_j = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual").get_all_values()
        if len(ws_j) > 1:
            df_j = pd.DataFrame(ws_j[1:], columns=ws_j[0])
            if 'Nama Operator' in df_j.columns: df_j = df_j[df_j['Nama Operator'].astype(str).str.strip() != '']

        ws_i = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0).get_all_values()
        if len(ws_i) > 1:
            df_i = pd.DataFrame(ws_i[1:], columns=ws_i[0])
            if 'Nama Lengkap Operator' in df_i.columns:
                df_i = df_i[df_i['Nama Lengkap Operator'].astype(str).str.strip() != '']
                df_i = df_i[~df_i['Nama Lengkap Operator'].astype(str).str.lower().isin(['nan', 'none', 'null'])]

        try:
            for ws in client.open_by_key(ID_SHEET_JADWAL).worksheets() + client.open_by_key(ID_SHEET_IZIN).worksheets():
                if 'data' in ws.title.lower() and 'operator' in ws.title.lower():
                    raw_k = ws.get_all_values()
                    if raw_k:
                        temp_df = pd.DataFrame(raw_k)
                        header_idx = next((i for i, r in temp_df.iterrows() if any('nama' in str(v).lower() and 'operator' in str(v).lower() for v in r.values)), -1)
                        if header_idx != -1: df_k = pd.DataFrame(temp_df.values[header_idx+1:], columns=[str(h).strip() for h in temp_df.iloc[header_idx]])
                    break
        except Exception: pass
    except Exception: pass
    return df_j, df_i, df_k

def execute_database_action(idx, row, action_type, approver_name, df_j):
    client = get_client()
    if not client: return st.error("Gagal terhubung ke database.")

    try:
        sh_izin = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0)
        col_status_idx = row.index.get_loc('Status Approval') + 1
        
        if action_type == "APPROVE": status_text = f"APPROVED by {approver_name}"
        elif action_type == "REJECT": status_text = f"REJECTED by {approver_name}"
        else: status_text = ""
        
        sh_izin.update_cell(int(idx)+2, col_status_idx, status_text)
        
        status_lama = str(row.get('Status Approval', '')).upper()
        if action_type == "APPROVE" or (action_type == "UNDO" and "APPROVED" in status_lama):
            sh_aktual = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual")
            d_start = pd.to_datetime(row['Tanggal Mulai Izin'], dayfirst=True).date()
            d_end = pd.to_datetime(row['Tanggal Selesai Izin'], dayfirst=True).date()
            
            applicant = str(row['Nama Lengkap Operator']).strip().lower()
            substitute = str(row.get('Nama Lengkap Operator Pengganti', '')).strip().lower()
            has_sub = substitute and substitute not in ['nan', 'tidak ada', '']
            
            batch_updates = []
            for d in pd.date_range(d_start, d_end):
                d_str = d.strftime('%Y-%m-%d')
                if d_str in df_j.columns:
                    col_date_idx = list(df_j.columns).index(d_str) + 1
                    val_app = str(row['Jenis Izin yang Diajukan']).upper() if action_type == "APPROVE" else str(row.get('Shift Izin', 'PG')).title()
                    val_sub = str(row.get('Shift Izin', 'PG')).title() if action_type == "APPROVE" else 'OFF'
                    
                    match_p = df_j[df_j.iloc[:,0].astype(str).str.strip().str.lower() == applicant]
                    if not match_p.empty: batch_updates.append(gspread.Cell(int(match_p.index[0])+2, col_date_idx, val_app))
                        
                    if has_sub:
                        match_sub = df_j[df_j.iloc[:,0].astype(str).str.strip().str.lower() == substitute]
                        if not match_sub.empty: batch_updates.append(gspread.Cell(int(match_sub.index[0])+2, col_date_idx, val_sub))
            
            if batch_updates: sh_aktual.update_cells(batch_updates)

        load_all_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Terjadi kesalahan API: {e}")


# =====================================================================
# 4. CSS PROFESIONAL & ANIMASI UI
# =====================================================================
def inject_custom_css(bg_base64):
    st.markdown("""<style>[data-testid="collapsedControl"] { display: none; } .block-container { padding-top: 2rem !important; }</style>""", unsafe_allow_html=True)
    bg_color = "rgba(15, 23, 42, 0.88)"
    bg_img = f"url('data:image/jpeg;base64,{bg_base64}')" if bg_base64 else "url('https://images.unsplash.com/photo-1583508108422-0a13d712ce19')"
    
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

    html, body, [class*="css"], .stApp {{ font-family: 'Plus Jakarta Sans', sans-serif !important; color: #f8fafc; }}
    .stApp {{ background-image: linear-gradient({bg_color}, {bg_color}), {bg_img}; background-size: cover; background-attachment: fixed; }}
    .block-container {{ max-width: 1200px !important; margin: 0 auto; }}
    header[data-testid="stHeader"] {{ display: none !important; }}
    
    .material-symbols-rounded {{ font-variation-settings: 'FILL' 1, 'wght' 500, 'GRAD' 0, 'opsz' 24; vertical-align: middle; }}

    div[data-testid="stVerticalBlock"] > div[style*="border"] {{
        border-radius: 16px; background: linear-gradient(145deg, rgba(30,41,59,0.7), rgba(15,23,42,0.9)) !important; backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 10px 30px rgba(0,0,0,0.4); padding: 24px; transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    }}
    div[data-testid="stVerticalBlock"] > div[style*="border"]:hover {{ transform: translateY(-4px); box-shadow: 0 15px 35px rgba(0,0,0,0.6); border-color: rgba(56, 189, 248, 0.3); }}

    .stButton>button {{ border-radius: 12px; font-weight: 700 !important; padding: 20px 10px !important; font-size: 15px !important; width: 100%; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important; letter-spacing: 0.3px; }}
    .stButton>button:hover {{ transform: translateY(-2px); filter: brightness(1.15); }}
    .stButton>button:active {{ transform: scale(0.96); }}
    button[kind="primary"] {{ background: linear-gradient(135deg, #0284c7, #0369a1) !important; color: white !important; border: 1px solid rgba(56,189,248,0.4) !important; box-shadow: 0 6px 15px rgba(2,132,199,0.4) !important; }}
    button[kind="secondary"] {{ background: rgba(30,41,59,0.8) !important; color: #e2e8f0 !important; border: 1px solid rgba(255,255,255,0.15) !important; box-shadow: 0 4px 6px rgba(0,0,0,0.2) !important; }}
    button[kind="secondary"]:hover {{ background: rgba(30,41,59,0.9) !important; color: #f8fafc !important; border: 1px solid rgba(255,255,255,0.3) !important; }}

    .header-bar {{ background-color: #ffffff; border-radius: 16px; padding: 16px 32px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }}
    .header-title {{ color: #004D95 !important; font-weight: 800; font-size: clamp(20px, 3vw, 28px) !important; text-align: center; flex-grow: 1; letter-spacing: -0.5px; text-shadow: none !important; margin:0; }}
    
    .notif-badge {{ position: absolute; top: -6px; right: -8px; background-color: #ef4444; color: white; border-radius: 50%; padding: 2px 6px; font-size: 11px; font-weight: 800; animation: pulseRed 2s infinite; }}
    @keyframes pulseRed {{ 0% {{ box-shadow: 0 0 0 0 rgba(239,68,68,0.6); }} 70% {{ box-shadow: 0 0 0 8px rgba(239,68,68,0); }} 100% {{ box-shadow: 0 0 0 0 rgba(239,68,68,0); }} }}

    details.off-personnel {{ background: rgba(255,255,255,0.03); border-left: 3px solid #38bdf8; border-radius: 8px; margin-bottom: 10px; transition: background 0.3s ease, transform 0.2s ease; }}
    details.off-personnel:hover {{ background: rgba(56,189,248,0.08); transform: translateX(4px); }}
    details.off-personnel summary {{ padding: 14px 16px; cursor: pointer; font-size: 14px; font-weight: 600; display: flex; align-items: center; list-style: none; }}
    details.off-personnel summary::-webkit-details-marker {{ display: none; }}
    .chevron-icon {{ transition: transform 0.3s ease; color: #94a3b8; font-size:18px; margin-left:auto; }}
    details.off-personnel[open] .chevron-icon {{ transform: rotate(180deg); color: #38bdf8; }}
    .off-details-content {{ padding: 0 16px 16px 16px; font-size: 14px; color:#cbd5e1; animation: dropDown 0.3s ease-out forwards; }}
    @keyframes dropDown {{ from {{ opacity:0; transform: translateY(-10px); }} to {{ opacity:1; transform: translateY(0); }} }}

    .scroll-container {{ display: flex; overflow-x: auto; gap: 14px; padding-bottom: 20px; padding-top: 10px; scroll-behavior: smooth; }}
    .scroll-card {{ flex: 0 0 210px; background: linear-gradient(145deg, rgba(30,41,59,0.9), rgba(15,23,42,0.95)); border: 1px solid rgba(255,255,255,0.1); border-radius: 14px; padding: 16px; transition: transform 0.3s; }}
    .scroll-card:hover {{ transform: translateY(-3px); border-color: rgba(255,255,255,0.3); }}
    .scroll-header {{ text-align: center; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 8px; font-weight: 700; margin-bottom: 14px; font-size: 13px; color:#94a3b8; border-bottom:2px solid #38bdf8; }}
    
    .status-badge {{ display:inline-flex; align-items:center; gap:6px; font-size:11px; font-weight:700; padding:4px 8px; border-radius:6px; margin-top:6px; }}
    .status-dot {{ width:8px; height:8px; border-radius:50%; }}
    .scroll-item {{ margin-bottom: 12px; font-size: 14px; padding: 10px; border-radius: 8px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); }}

    .section-title {{ font-weight: 800; margin-bottom: 20px; font-size: 20px; display:flex; align-items:center; gap:8px; }}
    .link-hover:hover {{ text-decoration: underline !important; filter: brightness(1.2); }}

    @media (max-width: 768px) {{ 
        .header-bar {{ flex-direction: column; gap: 16px; padding: 20px; }} 
        .header-title {{ font-size: 20px !important; }}
        .stButton>button {{ padding: 16px 10px !important; font-size: 14px !important; }} 
    }}
    </style>
    """, unsafe_allow_html=True)


# =====================================================================
# 5. KOMPONEN UI UTAMA & HUD WIDGET
# =====================================================================
def ui_header(logo_base64, pending_count):
    logo = f'<img src="data:image/png;base64,{logo_base64}" style="max-height: 50px;">' if logo_base64 else '<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Pertamina_Logo.svg/512px-Pertamina_Logo.svg.png" style="max-height: 50px;">'
    
    if pending_count > 0:
        notif = f'<div style="position:relative; margin-right:16px; cursor:pointer;" title="Ada {pending_count} ajuan"><span class="material-symbols-rounded" style="font-size:28px; color:#1e293b;">notifications_active</span><span class="notif-badge">{pending_count}</span></div>'
    else:
        notif = '<div style="position:relative; margin-right:16px; opacity:0.4;"><span class="material-symbols-rounded" style="font-size:28px; color:#1e293b;">notifications</span></div>'
        
    st.markdown(f"""
    <div class="header-bar">
        <div>{logo}</div>
        <h1 class="header-title">NR ORF Integrated Command</h1>
        <div style="display:flex; align-items:center;">{notif}</div>
    </div>
    """, unsafe_allow_html=True)

def ui_live_hud_widget():
    """WIDGET HUD JS: Jam Berdetik, Kalender Event, dan Cuaca ORF Muara Karang (Open-Meteo)"""
    hari_ini = datetime.now().strftime("%m-%d")
    event_hari_ini = EVENT_KALENDER.get(hari_ini, "Tidak ada event nasional")
    
    # Koordinat ORF Muara Karang, Jakarta Utara
    lat, lon = "-6.1115", "106.7932"
    
    components.html(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,600,1,0');
        body {{
            margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif;
            display: flex; justify-content: center; align-items: center;
        }}
        .hud-container {{
            display: flex; align-items: center; justify-content: space-between; gap: 15px;
            background: linear-gradient(145deg, rgba(30,41,59,0.9), rgba(15,23,42,1));
            border: 1px solid rgba(56,189,248,0.4); border-radius: 16px; 
            padding: 14px 24px; width: 100%; box-sizing: border-box;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5); color: #f8fafc;
            flex-wrap: wrap; transition: all 0.3s ease;
        }}
        .hud-container:hover {{ border-color: rgba(56,189,248,0.8); box-shadow: 0 12px 30px rgba(0,0,0,0.6); }}
        .hud-section {{ display: flex; align-items: center; gap: 10px; }}
        .clock {{ font-size: 26px; font-weight: 800; color: #38bdf8; font-variant-numeric: tabular-nums; letter-spacing: 1px; text-shadow: 0 0 12px rgba(56,189,248,0.4); }}
        .date {{ font-size: 15px; font-weight: 600; color: #e2e8f0; }}
        
        .weather-box {{
            display: flex; align-items: center; gap: 12px; background: rgba(255,255,255,0.05); 
            padding: 6px 16px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);
        }}
        .weather-stat {{ display: flex; align-items: center; gap: 4px; font-size: 13px; font-weight: 600; color: #e2e8f0; }}
        .weather-val {{ color: #4ade80; font-weight: 800; font-size: 14px; }}
        
        .event {{ font-size: 13px; font-weight: 700; color: #1e293b; background: #facc15; padding: 4px 12px; border-radius: 8px; box-shadow: 0 0 15px rgba(250,204,21,0.4); display:flex; align-items:center; gap:6px; }}
        
        @media (max-width: 850px) {{ 
            .hud-container {{ justify-content: center; flex-direction: column; text-align: center; gap: 12px; padding: 16px; }} 
            .border-left-divider {{ border-left: none !important; padding-left: 0 !important; border-top: 1px dashed rgba(255,255,255,0.2); padding-top: 12px; width: 100%; justify-content: center; }}
            .weather-box {{ width: 100%; justify-content: center; }}
        }}
    </style>
    <div class="hud-container">
        <div class="hud-section" style="flex-wrap: wrap; justify-content: center;">
            <span class="material-symbols-rounded" style="color:#38bdf8; font-size:30px;">schedule</span>
            <span class="clock" id="live-clock">--:--:--</span>
            <div style="width: 2px; height: 30px; background: rgba(255,255,255,0.2); margin: 0 8px;" class="hide-mobile"></div>
            <span class="date" id="live-date">Memuat Tanggal...</span>
        </div>
        
        <div class="hud-section border-left-divider" style="border-left: 2px solid rgba(255,255,255,0.1); padding-left: 15px;">
            <div class="weather-box" title="Cuaca ORF Muara Karang">
                <span class="material-symbols-rounded" id="w-icon" style="color:#facc15; font-size:24px;">partly_cloudy_day</span>
                <div style="display:flex; flex-direction:column; gap:2px;">
                    <span id="w-desc" style="font-size:11px; color:#cbd5e1; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">Memuat...</span>
                    <div style="display:flex; gap:10px;">
                        <span class="weather-stat" title="Suhu"><span class="material-symbols-rounded" style="font-size:14px; color:#f87171;">thermostat</span> <span id="w-temp" class="weather-val">--</span></span>
                        <span class="weather-stat" title="Kecepatan Angin"><span class="material-symbols-rounded" style="font-size:14px; color:#94a3b8;">air</span> <span id="w-wind" class="weather-val">--</span></span>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="hud-section border-left-divider" style="margin-left: auto;">
            <span class="event"><span class="material-symbols-rounded" style="font-size:16px;">campaign</span> {event_hari_ini}</span>
        </div>
    </div>
    
    <script>
        // Update Jam Tiap Detik
        function updateTime() {{
            const now = new Date();
            const optTime = {{ hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }};
            const optDate = {{ weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }};
            document.getElementById('live-clock').innerText = now.toLocaleTimeString('id-ID', optTime).replace(/\./g, ':');
            document.getElementById('live-date').innerText = now.toLocaleDateString('id-ID', optDate);
        }}
        setInterval(updateTime, 1000); updateTime();

        // Fetch Cuaca dari Open-Meteo untuk Muara Karang
        async function fetchWeather() {{
            try {{
                const res = await fetch('https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true');
                const data = await res.json();
                const cw = data.current_weather;
                
                document.getElementById('w-temp').innerText = cw.temperature + '°C';
                document.getElementById('w-wind').innerText = cw.windspeed + ' km/h';
                
                const code = cw.weathercode;
                let icon = 'partly_cloudy_day'; let desc = 'Berawan'; let color = '#facc15';
                
                if (code === 0) {{ icon = 'clear_day'; desc = 'Cerah'; }}
                else if (code > 0 && code <= 3) {{ icon = 'cloud'; desc = 'Berawan'; color = '#cbd5e1'; }}
                else if (code >= 45 && code <= 48) {{ icon = 'fog'; desc = 'Berkabut'; color = '#94a3b8'; }}
                else if (code >= 51 && code <= 67) {{ icon = 'rainy'; desc = 'Gerimis'; color = '#60a5fa'; }}
                else if (code >= 71 && code <= 77) {{ icon = 'rainy'; desc = 'Hujan'; color = '#3b82f6'; }}
                else if (code >= 80 && code <= 82) {{ icon = 'rainy'; desc = 'Hujan Lebat'; color = '#2563eb'; }}
                else if (code >= 95) {{ icon = 'thunderstorm'; desc = 'Badai Petir'; color = '#c084fc'; }}

                const iconEl = document.getElementById('w-icon');
                iconEl.innerText = icon; iconEl.style.color = color;
                document.getElementById('w-desc').innerText = desc;
            }} catch (err) {{
                document.getElementById('w-desc').innerText = "Cuaca Offline";
            }}
        }}
        fetchWeather();
        setInterval(fetchWeather, 600000); // Auto-update cuaca tiap 10 menit
    </script>
    """, height=125)

def ui_manager_panel(df_i, df_j):
    st.markdown("<h3 class='section-title'><span class='material-symbols-rounded' style='color:#38bdf8; font-size:28px;'>admin_panel_settings</span> Panel Manajer</h3>", unsafe_allow_html=True)
    
    if st.text_input("Kunci Keamanan", type="password", placeholder="Masukkan PIN Manajer...") != PIN_MANAGER:
        return st.markdown("<div style='border:1px solid rgba(255,255,255,0.1); border-radius:16px; background:rgba(15,23,42,0.6); padding:30px; text-align:center;'><span class='material-symbols-rounded' style='font-size:48px; color:#64748b; margin-bottom:10px;'>lock</span><br><span style='color:#cbd5e1; font-size:14px;'>Akses terkunci. Silakan masukkan PIN otoritas.</span></div>", unsafe_allow_html=True)

    approver_name = st.selectbox("Nama Approver:", DAFTAR_MANAJER)
    is_locked = approver_name == DAFTAR_MANAJER[0]
    if is_locked: st.info("Pilih Nama Anda terlebih dahulu untuk mengaktifkan tombol persetujuan.")
    
    st.markdown("<div style='background:rgba(15,23,42,0.6); padding:16px; border-radius:12px; border-left:4px solid #38bdf8; margin-bottom:24px; display:flex; align-items:center; gap:10px;'><span class='material-symbols-rounded' style='color:#38bdf8;'>database</span> <b style='color:#f8fafc;'>Akses Database Utama</b></div>", unsafe_allow_html=True)
    
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1: st.link_button("Edit Jadwal Aktual", URL_JADWAL, use_container_width=True)
    with c_btn2: st.link_button("Edit Database Izin", URL_IZIN, use_container_width=True)

    if df_i.empty or 'Status Approval' not in df_i.columns: return st.warning("Menunggu sinkronisasi data izin...")

    df_valid = df_i.dropna(subset=['Nama Lengkap Operator'])
    col_reason = find_col(df_i, ['alasan', 'keterangan'], 'Alasan Izin')
    col_proof = find_col(df_i, ['upload', 'bukti', 'dokumen'], 'Bukti Izin')

    # Bagian 1: Antrean Pending
    st.markdown("<h4 style='color:white; font-size:16px; margin-top:20px; display:flex; align-items:center; gap:6px;'><span class='material-symbols-rounded' style='font-size:20px; color:#facc15;'>pending_actions</span> Antrean Persetujuan</h4>", unsafe_allow_html=True)
    pending_df = df_valid[df_valid['Status Approval'].isna() | (df_valid['Status Approval'] == "")]
    
    if pending_df.empty: st.info("Tugas selesai. Tidak ada antrean izin saat ini.")
    else:
        for idx, row in pending_df.head(5).iterrows():
            with st.container(border=True):
                st.markdown(generate_html_card(row, col_reason, col_proof, idx*0.1), unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                if c1.button("✓ Setujui (Approve)", key=f"app_{idx}", type="primary", use_container_width=True, disabled=is_locked): execute_database_action(idx, row, "APPROVE", approver_name, df_j)
                if c2.button("✕ Tolak (Reject)", key=f"rej_{idx}", use_container_width=True, disabled=is_locked): execute_database_action(idx, row, "REJECT", approver_name, df_j)

    # Bagian 2: Riwayat Keputusan
    st.markdown("<hr style='opacity:0.1; margin: 30px 0;'><h4 style='color:white; font-size:16px; display:flex; align-items:center; gap:6px;'><span class='material-symbols-rounded' style='font-size:20px; color:#94a3b8;'>history</span> Riwayat Terakhir</h4>", unsafe_allow_html=True)
    history_df = df_valid[df_valid['Status Approval'].astype(str).str.upper().str.contains('APPROVED|REJECTED', regex=True, na=False)]
    
    if history_df.empty: st.info("Belum ada riwayat keputusan yang tercatat.")
    else:
        for idx, row in history_df.tail(5).iloc[::-1].iterrows():
            status = str(row['Status Approval']).upper()
            is_appr = "APPROVED" in status
            c_text, c_bg, icon = ("#4ade80", "rgba(34,197,94,0.15)", "check_circle") if is_appr else ("#fca5a5", "rgba(239,68,68,0.15)", "cancel")
            
            with st.container(border=True):
                st.markdown(f"""
                <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;'>
                    <div>
                        <b style='font-size:14px; color:white;'>{row['Nama Lengkap Operator']}</b><br>
                        <span style='font-size:12px; color:#94a3b8;'>{row['Tanggal Mulai Izin']} s/d {row['Tanggal Selesai Izin']}</span>
                    </div>
                    <div style='background:{c_bg}; color:{c_text}; padding:6px 12px; border-radius:8px; font-size:11px; font-weight:700; display:flex; align-items:center; gap:4px;'>
                        <span class='material-symbols-rounded' style='font-size:14px;'>{icon}</span> {status}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("⟲ Batalkan Keputusan", key=f"undo_{idx}", use_container_width=True, disabled=is_locked): execute_database_action(idx, row, "UNDO", approver_name, df_j)

def ui_off_tracker(df_j, df_k):
    st.markdown("<h3 class='section-title'><span class='material-symbols-rounded' style='color:#38bdf8; font-size:28px;'>group_off</span> Pencarian Personel OFF</h3>", unsafe_allow_html=True)
    tgl_cek = st.date_input("Pilih Tanggal Pengecekan:", value=datetime.now().date())
    tgl_str = tgl_cek.strftime('%Y-%m-%d')
    
    if df_j.empty or tgl_str not in df_j.columns:
        st.warning("Data jadwal belum dirilis untuk tanggal ini.")
        return st.link_button("Form Pengajuan", URL_GFORM, use_container_width=True, type="primary")

    valid_df = df_j.dropna(subset=['Nama Operator'])
    off_list = valid_df[valid_df[tgl_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])]["Nama Operator"].astype(str).tolist()
    
    with st.container(border=True):
        if not off_list: st.write("Seluruh personel bertugas hari ini.")
        else:
            col_n = find_col(df_k, ['nama', 'operator'], None)
            col_hp = find_col(df_k, ['contact', 'kontak', 'hp'], None)

            for i, name in enumerate(off_list):
                hp = "Tidak terdaftar"
                if col_n and col_hp and not df_k.empty:
                    clean_db = df_k[col_n].astype(str).str.replace('*','', regex=False).str.strip().str.lower()
                    target = str(name).replace('*','').strip().lower()
                    match = df_k[clean_db == target]
                    if match.empty: match = df_k[clean_db.str.contains(target, na=False)]
                    if not match.empty: hp = str(match.iloc[0][col_hp]).strip()

                st.markdown(f"""
                <details class="off-personnel" style="animation: slideInRight 0.3s {i*0.05}s ease-out backwards;">
                    <summary>
                        <div style='background:rgba(56,189,248,0.15); color:#38bdf8; padding:4px 8px; border-radius:4px; font-size:11px; margin-right:10px;'>OFF</div>
                        <span style="font-size:14px;">{name}</span>
                        <span class="material-symbols-rounded chevron-icon">expand_more</span>
                    </summary>
                    <div class="off-details-content">
                        <div style="display:flex; align-items:center; gap:8px; margin-top:8px;">
                            <span class="material-symbols-rounded" style="color:#94a3b8; font-size:18px;">call</span>
                            <span style="color:#94a3b8;">No. Handphone:</span> 
                            <b style="color:#e2e8f0; font-size:14px; letter-spacing:0.5px;">{hp}</b>
                        </div>
                    </div>
                </details>
                """, unsafe_allow_html=True)
                
    st.markdown("<br>", unsafe_allow_html=True)
    st.link_button("Ajukan Form Izin / Tukar Shift", URL_GFORM, use_container_width=True, type="primary")

def ui_timeline(df_j, df_i):
    st.markdown("<br><hr style='opacity:0.1;'><h3 class='section-title'><span class='material-symbols-rounded' style='color:#38bdf8; font-size:28px;'>view_timeline</span> Tinjauan 14 Hari Kedepan</h3>", unsafe_allow_html=True)
    if df_j.empty: return st.warning("Sedang menyinkronisasi jadwal...")

    subs_map = {}
    if not df_i.empty and 'Status Approval' in df_i.columns:
        for _, row in df_i[df_i['Status Approval'].astype(str).str.upper().str.contains('APPROVED', na=False)].iterrows():
            try:
                sub = str(row.get('Nama Lengkap Operator Pengganti', '')).strip().lower()
                if sub and sub not in ['nan', '']:
                    for d in pd.date_range(pd.to_datetime(row['Tanggal Mulai Izin'], dayfirst=True).date(), pd.to_datetime(row['Tanggal Selesai Izin'], dayfirst=True).date()):
                        subs_map.setdefault(d.strftime('%Y-%m-%d'), []).append(sub)
            except Exception: pass

    today = datetime.now().date()
    html = '<div class="scroll-container">'
    
    for i in range(14):
        d_obj = today + timedelta(days=i)
        d_str = d_obj.strftime('%Y-%m-%d')
        html += f'<div class="scroll-card"><div class="scroll-header">{d_obj.strftime("%d %b %Y")}</div>'
        
        if d_str in df_j.columns:
            day_df = df_j[['Nama Operator', d_str]].dropna()
            day_df = day_df[~day_df[d_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])]
            
            if not day_df.empty:
                for _, row in day_df.iterrows():
                    name = str(row['Nama Operator']).replace('*', '').strip()
                    status = str(row[d_str]).upper()
                    
                    if any(k in status for k in ["DINAS", "PD"]): 
                        badge = f'<div class="status-badge" style="background:rgba(249,115,22,0.15); color:#fdba74;"><div class="status-dot" style="background:#f97316;"></div>{status}</div>'
                    elif any(k in status for k in ["IZIN", "SAKIT", "CUTI"]): 
                        badge = f'<div class="status-badge" style="background:rgba(239,68,68,0.15); color:#fca5a5;"><div class="status-dot" style="background:#ef4444;"></div>{status}</div>'
                    elif name.lower() in subs_map.get(d_str, []): 
                        badge = f'<div class="status-badge" style="background:rgba(56,189,248,0.15); color:#7dd3fc;"><div class="status-dot" style="background:#38bdf8;"></div>SUB / {status}</div>'
                    else: 
                        badge = f'<div class="status-badge" style="background:rgba(34,197,94,0.15); color:#4ade80;"><div class="status-dot" style="background:#22c55e;"></div>SHIFT {status}</div>'
                        
                    html += f'<div class="scroll-item"><b style="color:#f8fafc; font-size:13px;">{name}</b><br>{badge}</div>'
            else: html += '<div class="scroll-item" style="text-align:center; color:#64748b; font-style:italic; border:none;">Semua OFF</div>'
        else: html += '<div class="scroll-item" style="text-align:center; color:#64748b; font-style:italic; border:none;">Data belum dirilis</div>'
        html += '</div>'
    st.markdown(html + '</div>', unsafe_allow_html=True)


# =====================================================================
# 6. ROUTER & MAIN EXECUTION
# =====================================================================
if __name__ == "__main__":
    inject_custom_css(get_base64_image("fsru.jpg"))
    df_j, df_i, df_k = load_all_data()

    pending_count = len(df_i.dropna(subset=['Nama Lengkap Operator'])[df_i['Status Approval'].isna() | (df_i['Status Approval'] == "")]) if not df_i.empty and 'Status Approval' in df_i.columns else 0

    ui_header(get_base64_image("pertamina.png"), pending_count)
    
    # -------------------------------------
    # RENDER WIDGET HUD REAL-TIME
    # -------------------------------------
    ui_live_hud_widget() 

    if 'active_menu' not in st.session_state: st.session_state.active_menu = "Dashboard"
    
    # Navigasi Profesional Tanpa Emoji
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: st.button("Dashboard Utama", type="primary" if st.session_state.active_menu == "Dashboard" else "secondary", on_click=lambda: st.session_state.update(active_menu="Dashboard"), use_container_width=True)
    with c2: st.button("Kalender Lengkap", type="primary" if st.session_state.active_menu == "Kalender" else "secondary", on_click=lambda: st.session_state.update(active_menu="Kalender"), use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if st.session_state.active_menu == "Dashboard":
        col_m, col_s = st.columns([2.5, 1.5])
        with col_m: ui_manager_panel(df_i, df_j)
        with col_s: ui_off_tracker(df_j, df_k)
        ui_timeline(df_j, df_i)
        
    elif st.session_state.active_menu == "Kalender":
        st.markdown("<h3 class='section-title'><span class='material-symbols-rounded' style='color:#38bdf8; font-size:28px;'>event_note</span> Pencarian Jadwal Spesifik</h3>", unsafe_allow_html=True)
        with st.container(border=True): tgl = st.date_input("Pilih Tanggal Pengecekan:").strftime('%Y-%m-%d')
        
        if df_j.empty or tgl not in df_j.columns:
            st.warning("⚠️ Data jadwal untuk tanggal ini belum tersedia.")
        else:
            st.markdown(f"<br><h4 style='color:white; font-size:18px; display:flex; align-items:center; gap:8px;'><span class='material-symbols-rounded' style='color:#94a3b8;'>check_circle</span> Status Personel: <b style='color:#38bdf8;'>{tgl}</b></h4>", unsafe_allow_html=True)
            df_day = df_j[['Nama Operator', tgl]].dropna().copy()
            df_day['Status'] = df_day[tgl].fillna('').astype(str).str.strip().str.upper()

            df_off = df_day[df_day['Status'].isin(['OFF', 'NAN', '', 'NONE'])]
            df_abs = df_day[df_day['Status'].str.contains('IZIN|SAKIT|CUTI|DINAS|PD', na=False)]
            df_hdr = df_day[~df_day['Nama Operator'].isin(df_off['Nama Operator']) & ~df_day['Nama Operator'].isin(df_abs['Nama Operator'])]

            for title, df_data, clr_border, clr_bg, show_sts in [("Hadir / Bertugas", df_hdr, "rgba(34,197,94,0.4)", "rgba(34,197,94,0.15)", True), ("Sedang OFF", df_off, "rgba(56,189,248,0.4)", "rgba(56,189,248,0.15)", False), ("Absen / Dinas Luar", df_abs, "rgba(239,68,68,0.4)", "rgba(239,68,68,0.15)", True)]:
                with st.container(border=True):
                    st.markdown(f"<div style='background:{clr_bg}; padding:12px; border-radius:8px; border:1px solid {clr_border}; margin-bottom:12px; display:flex; align-items:center; gap:8px;'><b style='color:white; font-size:15px;'>{title} ({len(df_data)})</b></div>", unsafe_allow_html=True)
                    if not df_data.empty: st.dataframe(df_data[['Nama Operator', 'Status']] if show_sts else df_data[['Nama Operator']], hide_index=True, use_container_width=True)
                    else: st.write("Tidak ada data pada kategori ini.")
