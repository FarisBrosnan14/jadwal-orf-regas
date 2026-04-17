import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import base64
import re
from PIL import Image

# =====================================================================
# 1. KONFIGURASI UTAMA
# =====================================================================
try:
    favicon = Image.open("pertamina.png")
except:
    favicon = "⚡"

st.set_page_config(page_title="NR ORF Command", page_icon=favicon, layout="wide", initial_sidebar_state="collapsed")

ID_SHEET_JADWAL = "1HuIrvhzm7xzXXbX5Foy2XPms7NLzFyttgH58Ez31pj0"
ID_SHEET_IZIN = "1mdr7InOGhuVwLCpgPW-fDVOMw38XvELlXK9sxJymMYU"
URL_JADWAL = f"https://docs.google.com/spreadsheets/d/{ID_SHEET_JADWAL}/edit#gid=0"
URL_IZIN = f"https://docs.google.com/spreadsheets/d/{ID_SHEET_IZIN}/edit"
URL_GFORM = "https://forms.gle/KB9CkfEsLB4yY9MK9"
PIN_MANAGER = "regas123"
DAFTAR_MANAJER = ["-- Pilih Nama Anda --", "Yosep Zulkarnain", "Ade Imat", "Benny Sulistio", "Ibrahim"]

EVENT_KALENDER = {
    "01-01": "Tahun Baru Masehi", "02-08": "Isra Mikraj", "02-10": "Imlek", "03-11": "Nyepi",
    "03-29": "Wafat Isa Al Masih", "03-31": "Paskah", "04-10": "Idul Fitri", "04-11": "Idul Fitri",
    "05-01": "Hari Buruh", "05-09": "Kenaikan Isa Al Masih", "05-23": "Waisak", "06-01": "Lahir Pancasila",
    "06-17": "Idul Adha", "07-07": "Tahun Baru Islam", "08-17": "HUT RI", "09-16": "Maulid Nabi", "12-25": "Natal"
}

# =====================================================================
# 2. UTILITIES & AI PARSER
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

def parse_natural_language_schedule(text, df_j):
    text = text.lower()
    today = datetime.now()
    nama_ditemukan = None
    if not df_j.empty and 'Nama Operator' in df_j.columns:
        for nama in df_j['Nama Operator'].dropna().astype(str).tolist():
            nama_bersih = nama.replace('*', '').strip().lower()
            if nama_bersih in text or nama_bersih.split()[0] in text:
                nama_ditemukan = nama
                break
    
    status_baru = "SAKIT" if any(k in text for k in ["sakit"]) else "CUTI" if any(k in text for k in ["cuti", "libur"]) else "OFF" if "off" in text else "PD" if any(k in text for k in ["dinas", "pd"]) else "PG" if "pagi" in text else "MLM" if "malam" in text else None
    tanggal_mulai, tanggal_selesai = None, None
    
    if "hari ini" in text: tanggal_mulai = tanggal_selesai = today
    elif "besok" in text: tanggal_mulai = tanggal_selesai = today + timedelta(days=1)
    elif "lusa" in text: tanggal_mulai = tanggal_selesai = today + timedelta(days=2)
    else:
        match_r = re.search(r'(\d{1,2})\s*(?:-|sampai|s/d)\s*(\d{1,2})', text)
        match_t = re.search(r'(\d{1,2})', text)
        b, t = today.month, today.year
        try:
            if match_r:
                aw, ak = int(match_r.group(1)), int(match_r.group(2))
                if 1<=aw<=31 and 1<=ak<=31: tanggal_mulai, tanggal_selesai = datetime(t, b, aw), datetime(t, b, ak)
            elif match_t:
                tgl = int(match_t.group(1))
                if 1<=tgl<=31: tanggal_mulai = tanggal_selesai = datetime(t, b, tgl)
        except: pass
    return {"nama": nama_ditemukan, "status": status_baru, "tgl_mulai": tanggal_mulai, "tgl_selesai": tanggal_selesai}

def generate_html_card(row, col_reason, col_proof, delay):
    alasan = str(row.get(col_reason, '-')).strip()
    if alasan.lower() in ['nan', '']: alasan = 'Tidak ada keterangan'
    bukti = str(row.get(col_proof, '')).strip()
    bukti_html = f"<a href='{bukti}' target='_blank' style='color:#38bdf8;'>Buka Dokumen</a>" if bukti.startswith('http') else "<span style='color:#64748b;'>Tidak ada lampiran</span>"
    return f"""
    <div style='animation: slideInRight 0.4s cubic-bezier(0.16, 1, 0.3, 1) {delay}s both;'>
        <div style='display:flex; align-items:center; gap:8px;'><span class='material-symbols-rounded' style='color:#38bdf8;'>person</span><b style='font-size:16px; color:#fff;'>{row['Nama Lengkap Operator']}</b></div>
        <div style='font-size:14px; margin-top:12px; color:#e2e8f0;'>📅 {row['Tanggal Mulai Izin']} s/d {row['Tanggal Selesai Izin']} | ⏱️ Shift: {row.get('Shift Izin', 'Pg')}</div>
        <div style='margin-top:12px; background: rgba(255,255,255,0.03); border-left: 3px solid #64748b; padding: 12px; border-radius: 6px;'>
            <div style='font-size:13px; color:#cbd5e1;'><b>Alasan:</b> {alasan}</div>
            <div style='font-size:13px; margin-top:8px; border-top:1px dashed rgba(255,255,255,0.1); padding-top:8px;'>{bukti_html}</div>
        </div>
        <div style='font-size:13px; color:#fca5a5; font-weight:600; margin-top:12px; margin-bottom:4px; background: rgba(239,68,68,0.15); padding: 6px 10px; border-radius: 6px; display:inline-block;'>🔄 Pengganti: {row.get('Nama Lengkap Operator Pengganti', '-')}</div>
    </div>
    """

# =====================================================================
# 3. DATABASE (GSPREAD)
# =====================================================================
def get_client():
    try:
        creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except: return None

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

        for ws in client.open_by_key(ID_SHEET_JADWAL).worksheets() + client.open_by_key(ID_SHEET_IZIN).worksheets():
            if 'data' in ws.title.lower() and 'operator' in ws.title.lower():
                raw_k = ws.get_all_values()
                if raw_k:
                    temp_df = pd.DataFrame(raw_k)
                    h_idx = next((i for i, r in temp_df.iterrows() if any('nama' in str(v).lower() and 'operator' in str(v).lower() for v in r.values)), -1)
                    if h_idx != -1: df_k = pd.DataFrame(temp_df.values[h_idx+1:], columns=[str(h).strip() for h in temp_df.iloc[h_idx]])
                break
    except: pass
    return df_j, df_i, df_k

def execute_database_action(idx, row, action_type, approver_name, df_j):
    client = get_client()
    if not client: return st.error("Gagal terhubung.")
    try:
        sh_izin = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0)
        c_idx = row.index.get_loc('Status Approval') + 1
        sh_izin.update_cell(int(idx)+2, c_idx, f"APPROVED by {approver_name}" if action_type=="APPROVE" else f"REJECTED by {approver_name}" if action_type=="REJECT" else "")
        
        stat = str(row.get('Status Approval', '')).upper()
        if action_type == "APPROVE" or (action_type == "UNDO" and "APPROVED" in stat):
            sh_aktual = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual")
            d_start, d_end = pd.to_datetime(row['Tanggal Mulai Izin'], dayfirst=True).date(), pd.to_datetime(row['Tanggal Selesai Izin'], dayfirst=True).date()
            app, sub = str(row['Nama Lengkap Operator']).strip().lower(), str(row.get('Nama Lengkap Operator Pengganti', '')).strip().lower()
            
            updates = []
            for d in pd.date_range(d_start, d_end):
                d_str = d.strftime('%Y-%m-%d')
                if d_str in df_j.columns:
                    c_date = list(df_j.columns).index(d_str) + 1
                    v_app = str(row['Jenis Izin yang Diajukan']).upper() if action_type == "APPROVE" else str(row.get('Shift Izin', 'PG')).title()
                    v_sub = str(row.get('Shift Izin', 'PG')).title() if action_type == "APPROVE" else 'OFF'
                    
                    m_p = df_j[df_j.iloc[:,0].astype(str).str.strip().str.lower() == app]
                    if not m_p.empty: updates.append(gspread.Cell(int(m_p.index[0])+2, c_date, v_app))
                    if sub and sub not in ['nan', 'tidak ada', '']:
                        m_s = df_j[df_j.iloc[:,0].astype(str).str.strip().str.lower() == sub]
                        if not m_s.empty: updates.append(gspread.Cell(int(m_s.index[0])+2, c_date, v_sub))
            if updates: sh_aktual.update_cells(updates)
        load_all_data.clear()
        st.rerun()
    except Exception as e: st.error(f"Error API: {e}")

def execute_smart_edit(nama, status, d_start, d_end, df_j):
    client = get_client()
    try:
        sh_aktual = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual")
        updates = []
        match_p = df_j[df_j.iloc[:,0].astype(str).str.replace('*', '', regex=False).str.strip().str.lower() == nama.replace('*', '').strip().lower()]
        if not match_p.empty:
            r_idx = int(match_p.index[0]) + 2
            for d in pd.date_range(d_start, d_end):
                d_str = d.strftime('%Y-%m-%d')
                if d_str in df_j.columns: updates.append(gspread.Cell(r_idx, list(df_j.columns).index(d_str) + 1, status.upper()))
            if updates: 
                sh_aktual.update_cells(updates)
                load_all_data.clear()
                import time; time.sleep(1)
                st.rerun()
    except: pass

def clear_pending_requests(df_i):
    client = get_client()
    try:
        sh_izin = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0)
        df_valid = df_i.dropna(subset=['Nama Lengkap Operator'])
        pending_rows = df_valid[df_valid['Status Approval'].isna() | (df_valid['Status Approval'] == "")]
        if pending_rows.empty: return st.info("Tidak ada antrean.")
        indices = sorted([int(idx) + 2 for idx in pending_rows.index], reverse=True)
        for r in indices: sh_izin.delete_rows(r)
        load_all_data.clear()
        import time; time.sleep(1)
        st.rerun()
    except Exception as e: st.error(f"Error: {e}")

# =====================================================================
# 4. CSS INJECTION
# =====================================================================
def inject_custom_css(bg_base64, logo_base64):
    bg_img = f"url('data:image/jpeg;base64,{bg_base64}')" if bg_base64 else ""
    logo_src = f"data:image/png;base64,{logo_base64}" if logo_base64 else ""
    
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0');
    
    /* Splash Screen Force White Background, Black Text, and Perfect Centering */
    #splash-overlay {{ 
        position: fixed; 
        top: 0; left: 0; width: 100vw; height: 100vh; 
        z-index: 999999; 
        display: flex; 
        flex-direction: column;
        justify-content: center; 
        align-items: center; 
        background: #ffffff !important; 
        animation: overlayFade 2.5s forwards; 
        margin: 0 !important;
        padding: 0 !important;
    }}
    .splash-content {{ 
        text-align: center; 
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        animation: moveToHeader 2.5s forwards; 
    }}
    .splash-fade-early {{ animation: fadeOutEarly 2.5s forwards; }}
    .splash-logo {{ max-height: 70px; margin-bottom: 20px; animation: floatLogo 2s infinite alternate; }}
    .splash-title {{ color: #000000 !important; font-family: 'Plus Jakarta Sans', sans-serif !important; font-weight: 900 !important; font-size: 32px !important; letter-spacing: 2px !important; margin: 0 !important; line-height: 1.2 !important; }}
    .splash-subtitle {{ color: #64748b; font-size: 13px; font-weight: 600; letter-spacing: 3px; margin-top: 15px; opacity: 0.8; }}
    .loading-bar-container {{ width: 200px; height: 4px; background: #e2e8f0; border-radius: 4px; margin-top: 20px; overflow: hidden; position: relative; }}
    .loading-bar {{ position: absolute; height: 100%; width: 40%; background: #38bdf8; animation: loadingSwipe 1.2s infinite; }}
    
    @keyframes overlayFade {{ 0%, 65% {{ opacity: 1; visibility: visible; background: #ffffff; }} 100% {{ opacity: 0; visibility: hidden; pointer-events: none; }} }}
    @keyframes moveToHeader {{ 0%, 65% {{ transform: translateY(0) scale(1); opacity: 1; }} 100% {{ transform: translateY(-42vh) scale(0.4); opacity: 0; }} }}
    @keyframes fadeOutEarly {{ 0%, 50% {{ opacity: 1; transform: translateY(0); }} 65%, 100% {{ opacity: 0; transform: translateY(10px); }} }}
    @keyframes floatLogo {{ 0% {{ transform: translateY(0px); filter: drop-shadow(0 5px 15px rgba(0,0,0,0.1)); }} 100% {{ transform: translateY(-10px); filter: drop-shadow(0 15px 25px rgba(0,0,0,0.15)); }} }}
    @keyframes loadingSwipe {{ 0% {{ left: -40%; }} 100% {{ left: 140%; }} }}
    
    html, body, .stApp {{ font-family: 'Plus Jakarta Sans', sans-serif !important; color: #f8fafc; }}
    .stApp {{ background-image: linear-gradient(rgba(15,23,42,0.88), rgba(15,23,42,0.88)), {bg_img}; background-size: cover; background-attachment: fixed; }}
    .block-container {{ max-width: 1200px !important; padding-top: 2rem !important; }} header[data-testid="stHeader"] {{ display: none !important; }}
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {{ background-color: #f8fafc !important; border-radius: 8px !important; min-height: 38px !important; border: 2px solid transparent !important; }}
    div[data-baseweb="input"] input, div[data-baseweb="select"] span {{ color: #0f172a !important; font-weight: 700 !important; font-size: 13px !important; }}
    div[data-testid="stVerticalBlock"] > div[style*="border"] {{ border-radius: 16px; background: linear-gradient(145deg, rgba(30,41,59,0.7), rgba(15,23,42,0.9)) !important; border: 1px solid rgba(255,255,255,0.1); padding: 24px; transition: all 0.3s; }}
    .stButton>button {{ border-radius: 12px; font-weight: 700 !important; width: 100%; transition: all 0.2s; }}
    button[kind="primary"] {{ background: linear-gradient(135deg, #0284c7, #0369a1) !important; color: white !important; border: none !important; }}
    
    @keyframes headerGlow {{ 0%, 100% {{ box-shadow: 0 0 20px rgba(0,77,149,0.6); border-color: rgba(0,77,149,0.9); }} 33% {{ box-shadow: 0 0 20px rgba(239,68,68,0.6); border-color: rgba(239,68,68,0.9); }} 66% {{ box-shadow: 0 0 20px rgba(130,195,65,0.6); border-color: rgba(130,195,65,0.9); }} }}
    .header-bar {{ background: #fff; border-radius: 16px; padding: 16px 32px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; animation: fadeIn 0.5s 2s both, headerGlow 6s infinite; border: 2px solid transparent; }}
    @keyframes bellFlash {{ 0%, 100% {{ color: #1e293b; transform: scale(1); }} 50% {{ color: #ef4444; transform: scale(1.1); filter: drop-shadow(0 0 8px rgba(239,68,68,0.8)); }} }}
    .bell-active {{ animation: bellFlash 1.5s infinite; }}
    .home-btn {{ display: flex; background: rgba(30,41,59,0.1); color: #0f172a; padding: 8px 16px; border-radius: 8px; border: 1px solid rgba(0,0,0,0.1); cursor: pointer; text-decoration: none; }}
    
    /* CSS Timeline Visual Original & Interaktif */
    .scroll-container {{ display: flex; overflow-x: auto; gap: 14px; padding-bottom: 20px; padding-top: 10px; scroll-behavior: smooth; scrollbar-width: none; }}
    .scroll-container::-webkit-scrollbar {{ display: none; }}
    
    /* Kartu Hover & Active States */
    .scroll-card {{ 
        flex: 0 0 220px; 
        background: linear-gradient(145deg, rgba(30,41,59,0.9), rgba(15,23,42,0.95)); 
        border: 1px solid rgba(255,255,255,0.1); 
        border-radius: 14px; 
        padding: 16px; 
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); 
        scroll-snap-align: start; 
        cursor: pointer;
    }}
    .scroll-card:hover {{ 
        transform: translateY(-5px); 
        border-color: rgba(56, 189, 248, 0.5); 
        box-shadow: 0 10px 25px rgba(56, 189, 248, 0.2); 
    }}
    .scroll-card:active {{ 
        transform: scale(0.98) translateY(-2px); 
        box-shadow: 0 5px 15px rgba(56, 189, 248, 0.4); 
    }}
    
    .today-card {{ border: 2px solid #38bdf8 !important; box-shadow: 0 0 20px rgba(56,189,248,0.3) !important; background: linear-gradient(145deg, rgba(20,50,85,0.9), rgba(15,23,42,0.95)) !important; transform: translateY(-3px); }}
    .today-card:hover {{ transform: translateY(-8px); box-shadow: 0 15px 30px rgba(56, 189, 248, 0.4) !important; }}
    .today-card:active {{ transform: scale(0.98); }}
    
    .scroll-header {{ text-align: center; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 8px; font-weight: 700; margin-bottom: 14px; font-size: 13px; color:#94a3b8; border-bottom:2px solid #38bdf8; transition: all 0.3s; }}
    .scroll-card:hover .scroll-header {{ background: rgba(56, 189, 248, 0.1); color: #fff; }}
    .today-header {{ background: linear-gradient(135deg, #0284c7, #38bdf8) !important; color: #ffffff !important; border-bottom: none !important; box-shadow: 0 4px 10px rgba(2,132,199,0.5); }}
    
    .scroll-item {{ margin-bottom: 12px; font-size: 14px; padding: 10px; border-radius: 8px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); transition: all 0.2s; }}
    .scroll-item:hover {{ background: rgba(255,255,255,0.08); border-color: rgba(255,255,255,0.2); transform: translateX(2px); }}
    .status-badge {{ display:inline-flex; align-items:center; gap:6px; font-size:11px; font-weight:700; padding:4px 8px; border-radius:6px; margin-top:6px; width: 100%; box-sizing: border-box; }}
    .status-dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; }}
    
    .nav-arrow-btn {{ background: rgba(30,41,59,0.8); border: 1px solid rgba(56,189,248,0.4); color: #38bdf8; border-radius: 8px; padding: 6px 12px; cursor: pointer; transition: all 0.2s; }}
    .nav-arrow-btn:hover {{ background: rgba(56,189,248,0.2); color: #fff; }}
    </style>
    """, unsafe_allow_html=True)

    if 'splash_shown' not in st.session_state:
        st.session_state.splash_shown = True
        st.markdown(f"""
        <div id="splash-overlay">
            <div class="splash-content">
                <img src="{logo_src}" class="splash-logo" alt="Logo">
                <h2 class="splash-title">NR ORF COMMAND</h2>
                <div class="splash-fade-early">
                    <div class="splash-subtitle">SINKRONISASI DATABASE...</div>
                    <div class="loading-bar-container"><div class="loading-bar"></div></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


def ui_header(logo_base64, pending_count):
    logo = f'<img src="data:image/png;base64,{logo_base64}" style="max-height: 50px;">' if logo_base64 else ''
    notif = f'<div style="position:relative;" title="Ada {pending_count} antrean!"><span class="material-symbols-rounded bell-active" style="font-size:28px;">notifications_active</span><span style="position:absolute; top:-6px; right:-8px; background:#ef4444; color:white; border-radius:50%; padding:2px 6px; font-size:11px; font-weight:800;">{pending_count}</span></div>' if pending_count > 0 else '<div style="opacity:0.4;"><span class="material-symbols-rounded" style="font-size:28px; color:#1e293b;">notifications</span></div>'
    st.markdown(f"""
    <div class="header-bar">
        <div style="display:flex; align-items:center; gap:20px;">
            <form action="javascript:window.location.reload()"><button type="submit" class="home-btn" title="Home"><span class="material-symbols-rounded">home</span></button></form>
            <div>{logo}</div>
        </div>
        <h1 style="color:#004D95; font-weight:800; font-size:clamp(18px, 3vw, 24px); margin:0;">NR ORF Integrated Command</h1>
        <div>{notif}</div>
    </div>
    """, unsafe_allow_html=True)

def ui_live_hud_widget():
    hari_ini = datetime.now().strftime("%m-%d")
    evt = EVENT_KALENDER.get(hari_ini, "Tidak ada event")
    components.html(f"""
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@600;800&family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,600,1,0" rel="stylesheet">
    <style>
        body {{ margin:0; padding:5px; font-family:'Plus Jakarta Sans'; overflow:hidden; }}
        .hud-container {{ display:flex; align-items:center; gap:20px; background:linear-gradient(145deg, #1e293b, #0f172a); border:1px solid rgba(56,189,248,0.4); border-radius:16px; padding:12px 20px; color:#f8fafc; overflow-x:auto; scrollbar-width:none; }}
        .hud-container::-webkit-scrollbar {{ display:none; }}
        .section {{ display:flex; align-items:center; gap:12px; flex:0 0 auto; border-left: 2px solid rgba(255,255,255,0.1); padding-left: 20px; }}
        .section:first-child {{ border:none; padding-left:0; }}
        .box {{ display:flex; align-items:center; gap:12px; background:rgba(255,255,255,0.05); padding:6px 14px; border-radius:10px; position:relative; }}
        .clock {{ font-size:26px; font-weight:800; color:#38bdf8; text-shadow:0 0 12px rgba(56,189,248,0.4); }}
        .val {{ color:#4ade80; font-weight:800; font-size:14px; }}
    </style>
    <div class="hud-container">
        <div class="section">
            <span class="material-symbols-rounded" style="color:#38bdf8; font-size:30px;">schedule</span>
            <span class="clock" id="clock">--:--:--</span><div style="width:2px; height:30px; background:rgba(255,255,255,0.2);"></div><span id="date" style="font-weight:600;">Memuat...</span>
        </div>
        <div class="section">
            <div class="box"><span class="material-symbols-rounded" id="compass" style="color:#f87171; font-size:26px; transition:transform 0.2s;">navigation</span>
                <div><div id="loc" style="font-size:11px; font-weight:700; color:#cbd5e1;">Mencari GPS...</div><span class="val" id="deg" style="color:#38bdf8;">--°</span></div>
            </div>
        </div>
        <div class="section">
            <div class="box"><span class="material-symbols-rounded" id="w-icon" style="color:#facc15; font-size:26px;">partly_cloudy_day</span>
                <div><div id="w-desc" style="font-size:11px; font-weight:700; color:#cbd5e1;">Memuat...</div>
                <span class="material-symbols-rounded" style="font-size:12px; color:#f87171;">thermostat</span><span class="val" id="w-temp" style="margin-right:8px;">--</span>
                <span class="material-symbols-rounded" style="font-size:12px; color:#94a3b8;">air</span><span class="val" id="w-wind">--</span></div>
            </div>
        </div>
        <div class="section"><span style="font-size:13px; font-weight:700; color:#1e293b; background:#facc15; padding:6px 14px; border-radius:8px;">📢 {evt}</span></div>
    </div>
    <script>
        function ut(){{ const d=new Date(); document.getElementById('clock').innerText=d.toLocaleTimeString('id-ID'); document.getElementById('date').innerText=d.toLocaleDateString('id-ID',{{weekday:'short',day:'numeric',month:'short'}}); }}
        setInterval(ut, 1000); ut();
        navigator.geolocation.getCurrentPosition(async function(pos){{
            try {{
                const r = await fetch('https://api.open-meteo.com/v1/forecast?latitude='+pos.coords.latitude+'&longitude='+pos.coords.longitude+'&current_weather=true');
                const cw = (await r.json()).current_weather;
                document.getElementById('w-temp').innerText = cw.temperature + '°C'; document.getElementById('w-wind').innerText = cw.windspeed + ' km/h'; document.getElementById('loc').innerText = "Titik Koordinat";
                let i='partly_cloudy_day', d='Berawan'; if(cw.weathercode===0){{i='clear_day'; d='Cerah';}} else if(cw.weathercode>50){{i='rainy'; d='Hujan';}}
                document.getElementById('w-icon').innerText = i; document.getElementById('w-desc').innerText = d;
            }}catch(e){{}}
        }});
        window.addEventListener('deviceorientation', function(e){{ if(e.webkitCompassHeading){{ document.getElementById('deg').innerText=Math.round(e.webkitCompassHeading)+'°'; document.getElementById('compass').style.transform='rotate(-'+e.webkitCompassHeading+'deg)'; }} }});
    </script>
    """, height=90)


# =====================================================================
# 5. HALAMAN MANAJER
# =====================================================================
def ui_manager_panel(df_i, df_j):
    st.markdown("<h3 style='font-weight:800;'><span class='material-symbols-rounded' style='color:#38bdf8;'>admin_panel_settings</span> Panel Manajer</h3>", unsafe_allow_html=True)
    if 'is_manager' not in st.session_state: st.session_state.is_manager = False
    is_locked = st.text_input("Kunci Keamanan", type="password", placeholder="Masukkan PIN Manajer...") != PIN_MANAGER
    st.session_state.is_manager = not is_locked

    if is_locked: return st.error("Akses terkunci.")
    app_name = st.selectbox("Nama Approver:", DAFTAR_MANAJER)
    is_name_locked = app_name == DAFTAR_MANAJER[0]

    t_edit, t_izin = st.tabs(["⚙️ Panel Edit & AI", "📋 Panel Persetujuan"])
    
    with t_edit:
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1: st.link_button("Edit Jadwal Aktual", URL_JADWAL, use_container_width=True)
        with c2: st.link_button("Edit Database Izin", URL_IZIN, use_container_width=True)
        
        st.markdown("<hr><b style='color:#38bdf8;'>🤖 Asisten Jadwal Pintar</b><br><small>Contoh: 'Tolong besok Haerul di set off'</small>", unsafe_allow_html=True)
        perintah = st.text_input("Ketik perintah:", key="cmd")
        if st.button("Kirim Perintah", type="primary"):
            p = parse_natural_language_schedule(perintah, df_j)
            if p['nama'] and p['status'] and p['tgl_mulai']:
                st.session_state.ai_parsed = p
            else: st.error("Perintah tidak lengkap. Sebutkan Nama, Tanggal, dan Status.")
        
        if st.session_state.get('ai_parsed'):
            p = st.session_state.ai_parsed
            st.warning(f"Yakin ubah jadwal **{p['nama']}** ke **{p['status']}** tanggal {p['tgl_mulai'].strftime('%d %b')}?")
            if st.button("Ya, Eksekusi"): 
                execute_smart_edit(p['nama'], p['status'], p['tgl_mulai'], p['tgl_selesai'], df_j)
                st.session_state.ai_parsed = None

    with t_izin:
        if df_i.empty: return st.warning("Data kosong")
        df_v = df_i.dropna(subset=['Nama Lengkap Operator'])
        pend_df = df_v[df_v['Status Approval'].isna() | (df_v['Status Approval'] == "")]
        
        c1, c2 = st.columns([2,1])
        with c1: st.markdown("<b>Antrean Persetujuan</b>", unsafe_allow_html=True)
        with c2: 
            if not pend_df.empty and st.button("🗑️ Hapus Semua Antrean"): clear_pending_requests(df_i)
        
        if pend_df.empty: st.info("Tidak ada antrean izin.")
        else:
            for idx, r in pend_df.head(5).iterrows():
                with st.container(border=True):
                    st.write(f"**{r['Nama Lengkap Operator']}** - {r['Tanggal Mulai Izin']} ({r.get('Shift Izin','PG')})")
                    ca, cb = st.columns(2)
                    if ca.button("✓ Approve", key=f"a_{idx}", disabled=is_name_locked, type="primary"): execute_database_action(idx, r, "APPROVE", app_name, df_j)
                    if cb.button("✕ Reject", key=f"r_{idx}", disabled=is_name_locked): execute_database_action(idx, r, "REJECT", app_name, df_j)


# =====================================================================
# 6. HALAMAN UTAMA (TIMELINE & TRACKER)
# =====================================================================
def ui_timeline(df_j, df_i):
    st.markdown("<hr style='opacity:0.2;'>", unsafe_allow_html=True)
    st.markdown("""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <h3 style='margin:0; font-weight:800;'><span class='material-symbols-rounded' style='color:#38bdf8;'>view_timeline</span> Tinjauan 14 Hari Kedepan</h3>
        <div style="display:flex; gap:10px;">
            <button class="nav-arrow-btn" onclick="document.querySelector('.scroll-container').scrollBy({left: -300, behavior: 'smooth'})"><span class="material-symbols-rounded">arrow_back_ios_new</span></button>
            <button class="nav-arrow-btn" onclick="document.querySelector('.scroll-container').scrollBy({left: 300, behavior: 'smooth'})"><span class="material-symbols-rounded">arrow_forward_ios</span></button>
        </div>
    </div>
    """, unsafe_allow_html=True)

    today = datetime.now().date()
    subs = {}
    if not df_i.empty and 'Status Approval' in df_i.columns:
        for _, r in df_i[df_i['Status Approval'].astype(str).str.contains('APPROVED', na=False, case=False)].iterrows():
            sub = str(r.get('Nama Lengkap Operator Pengganti', '')).strip().lower()
            if sub and sub not in ['nan','']:
                for d in pd.date_range(pd.to_datetime(r['Tanggal Mulai Izin'], dayfirst=True).date(), pd.to_datetime(r['Tanggal Selesai Izin'], dayfirst=True).date()): subs.setdefault(d.strftime('%Y-%m-%d'), []).append(sub)

    html = '<div class="scroll-container">'
    for i in range(14):
        d_str = (today + timedelta(days=i)).strftime('%Y-%m-%d')
        h_cls = "today-header" if i==0 else "scroll-header"
        c_cls = "scroll-card today-card" if i==0 else "scroll-card"
        txt = f"⭐ HARI INI - {d_str}" if i==0 else d_str
        
        html += f'<div class="{c_cls}"><div class="{h_cls}">{txt}</div>'
        if d_str in df_j.columns:
            day_df = df_j[['Nama Operator', d_str]].dropna()
            day_df = day_df[~day_df[d_str].astype(str).str.lower().isin(['off', 'nan', ''])]
            for _, r in day_df.iterrows():
                n = str(r['Nama Operator']).replace('*','').strip()
                s = str(r[d_str]).upper()
                
                c_bg = "rgba(249,115,22,0.15)" if "PD" in s else "rgba(239,68,68,0.15)" if any(x in s for x in ["SAKIT","CUTI","IZIN"]) else "rgba(56,189,248,0.15)" if n.lower() in subs.get(d_str,[]) else "rgba(34,197,94,0.15)"
                c_txt = "#fdba74" if "PD" in s else "#fca5a5" if any(x in s for x in ["SAKIT","CUTI","IZIN"]) else "#7dd3fc" if n.lower() in subs.get(d_str,[]) else "#4ade80"
                c_dot = "#f97316" if "PD" in s else "#ef4444" if any(x in s for x in ["SAKIT","CUTI","IZIN"]) else "#38bdf8" if n.lower() in subs.get(d_str,[]) else "#22c55e"
                
                badge_html = f'<div class="status-badge" style="background:{c_bg}; color:{c_txt};"><div class="status-dot" style="background:{c_dot};"></div>SHIFT {s}</div>'
                html += f'<div class="scroll-item"><b style="color:#f8fafc; font-size:14px;">{n}</b><br>{badge_html}</div>'
        else: html += '<div class="scroll-item" style="color:#64748b; text-align:center;">Belum dirilis</div>'
        html += '</div>'
    st.markdown(html + '</div>', unsafe_allow_html=True)

# =====================================================================
# MAIN RUNNER
# =====================================================================
if __name__ == "__main__":
    inject_custom_css(get_base64_image("fsru.jpg"), get_base64_image("pertamina.png"))
    df_j, df_i, df_k = load_all_data()

    pc = len(df_i.dropna(subset=['Nama Lengkap Operator'])[df_i['Status Approval'].isna() | (df_i['Status Approval'] == "")]) if not df_i.empty and 'Status Approval' in df_i.columns else 0
    ui_header(get_base64_image("pertamina.png"), pc)
    ui_live_hud_widget()

    if 'menu' not in st.session_state: st.session_state.menu = "Dash"
    c1, c2 = st.columns(2)
    with c1: st.button("Dashboard Utama", type="primary" if st.session_state.menu=="Dash" else "secondary", on_click=lambda: st.session_state.update(menu="Dash"), use_container_width=True)
    with c2: st.button("Panel Manajer", type="primary" if st.session_state.menu=="Mgr" else "secondary", on_click=lambda: st.session_state.update(menu="Mgr"), use_container_width=True)

    if st.session_state.menu == "Dash":
        ui_timeline(df_j, df_i)
    else:
        ui_manager_panel(df_i, df_j)
