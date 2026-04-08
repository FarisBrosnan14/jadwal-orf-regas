import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import base64
import os

# --- KONFIGURASI HALAMAN (WIDE LAYOUT & MOBILE OPTIMIZED) ---
st.set_page_config(page_title="NR ORF Integrated Command", page_icon="⚓", layout="wide", initial_sidebar_state="collapsed")

# Menyembunyikan tombol expand sidebar bawaan Streamlit
st.markdown("""
    <style>
        [data-testid="collapsedControl"] { display: none; }
        /* Menghilangkan padding atas bawaan streamlit agar header putih bisa lebih pas ke atas */
        .block-container { padding-top: 2rem !important; }
    </style>
""", unsafe_allow_html=True)

# --- FUNGSI LOAD ASSETS (BASE64) ---
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception:
        return None

img_base64 = get_base64_of_bin_file("fsru.jpg")
logo_base64 = get_base64_of_bin_file("pertamina.png")

# PENGATURAN OPACITY BACKGROUND:
overlay_opacity = 0.85
bg_color = f"rgba(15, 23, 42, {overlay_opacity})" 

if img_base64:
    bg_image_css = f"background-image: linear-gradient({bg_color}, {bg_color}), url('data:image/jpeg;base64,{img_base64}');"
else:
    bg_image_css = f"background-image: linear-gradient({bg_color}, {bg_color}), url('https://images.unsplash.com/photo-1583508108422-0a13d712ce19?q=80&w=1920&auto=format&fit=crop');"

# --- KUSTOMISASI CSS (DARK GLASSMORPHISM & WHITE HEADER) ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"], .stApp {{
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        color: #f8fafc; 
    }}
    
    .stApp {{
        {bg_image_css}
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    
    header[data-testid="stHeader"] {{ background-color: rgba(0, 0, 0, 0.0) !important; }}

    h2, h3, h4, h5 {{ 
        color: #ffffff !important; 
        font-family: 'Plus Jakarta Sans', sans-serif; 
        text-shadow: 0px 2px 4px rgba(0,0,0,0.8); 
    }}

    /* ========================================================
       TOP HEADER PUTIH (LOGO + JUDUL + TANGGAL)
       ======================================================== */
    .header-bar {{
        background-color: #ffffff;
        border-radius: 16px;
        padding: 15px 30px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 30px;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
    }}
    
    .header-logo {{
        max-height: 60px; /* Ukuran Logo Proporsional */
        display: block;
    }}
    
    .header-title {{
        color: #004D95 !important; /* Biru Pertamina */
        font-weight: 800;
        font-size: 32px;
        margin: 0;
        text-align: center;
        flex-grow: 1;
        text-shadow: none !important; /* Hapus bayangan agar teks rapi di atas putih */
        letter-spacing: -0.5px;
    }}
    
    .header-date {{
        background-color: #f1f5f9;
        color: #0f172a !important;
        padding: 10px 20px;
        border-radius: 10px;
        font-weight: 700;
        border: 1px solid #cbd5e1;
        font-size: 15px;
        white-space: nowrap;
    }}

    /* Responsif untuk Layar HP */
    @media (max-width: 768px) {{
        .header-bar {{
            flex-direction: column;
            gap: 15px;
            padding: 20px 15px;
        }}
        .header-title {{
            font-size: 22px;
        }}
    }}
    /* ======================================================== */

    /* KARTU MELAYANG (DARK SOFT UI) */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {{
        border-radius: 16px;
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9)) !important; 
        backdrop-filter: blur(16px); 
        border: 1px solid rgba(255, 255, 255, 0.15); 
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5); 
        padding: 20px; 
        animation: fadeIn 0.5s ease-out;
    }}
    
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(10px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    
    /* TOMBOL CHUNKY (BESAR & RESPONSIF) */
    .stButton>button {{
        border-radius: 12px;
        font-weight: 800 !important;
        padding: 20px 10px !important; 
        font-size: 16px !important; 
        transition: all 0.2s ease;
        height: auto !important;
        width: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
    }}
    
    button[kind="primary"] {{
        background: linear-gradient(135deg, #0284c7, #0369a1) !important;
        color: #ffffff !important;
        border: 1px solid rgba(56, 189, 248, 0.5) !important;
        box-shadow: 0 6px 15px rgba(2, 132, 199, 0.5) !important;
    }}
    
    button[kind="secondary"] {{
        background: rgba(30, 41, 59, 0.7) !important;
        color: #94a3b8 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2) !important;
    }}
    
    button[kind="secondary"]:hover {{
        background: rgba(30, 41, 59, 0.9) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
    }}
    
    /* === CSS HORIZONTAL SCROLL JADWAL === */
    .scroll-container {{
        display: flex;
        overflow-x: auto;
        gap: 12px; 
        padding-bottom: 15px;
        padding-top: 10px;
        -webkit-overflow-scrolling: touch; 
    }}
    .scroll-card {{
        flex: 0 0 200px; 
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.95)); 
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 14px;
        padding: 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        animation: slideInRight 0.5s ease-out backwards;
    }}
    
    @keyframes slideInRight {{
        0% {{ opacity: 0; transform: translateX(20px); }}
        100% {{ opacity: 1; transform: translateX(0); }}
    }}

    .scroll-header {{
        text-align: center;
        background: linear-gradient(135deg, #1e3a8a, #1d4ed8);
        color: #ffffff;
        padding: 8px;
        border-radius: 8px;
        font-weight: 700;
        margin-bottom: 12px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
        font-size: 14px;
    }}
    
    .scroll-item {{
        margin-bottom: 10px;
        font-size: 13px; 
        line-height: 1.5;
        padding: 8px;
        border-radius: 8px;
        background-color: rgba(255,255,255,0.05);
        animation: popIn 0.4s ease backwards;
        color: #ffffff; 
    }}
    
    @keyframes popIn {{
        0% {{ opacity: 0; transform: scale(0.95); }}
        100% {{ opacity: 1; transform: scale(1); }}
    }}
    
    /* INDIKATOR STATUS JADWAL (MERAH, ORANYE, HIJAU, BIRU) */
    .item-absen {{ border-left: 4px solid #ef4444; background-color: rgba(239, 68, 68, 0.15); }}
    .item-absen b {{ color: #ffffff !important; }}
    
    .item-dinas {{ border-left: 4px solid #f97316; background-color: rgba(249, 115, 22, 0.15); }}
    .item-dinas b {{ color: #ffffff !important; }}
    
    .item-hadir {{ border-left: 4px solid #22c55e; background-color: rgba(34, 197, 94, 0.1); }}
    .item-hadir b {{ color: #ffffff !important; }}
    
    .item-pengganti {{ border-left: 4px solid #38bdf8; background-color: rgba(56, 189, 248, 0.15); }}
    .item-pengganti b {{ color: #ffffff !important; }}
    
    /* SCROLLBAR GELAP DI MOBILE */
    .scroll-container::-webkit-scrollbar {{ height: 4px; }} 
    .scroll-container::-webkit-scrollbar-track {{ background: rgba(255, 255, 255, 0.05); border-radius: 10px; }}
    .scroll-container::-webkit-scrollbar-thumb {{ background: rgba(255, 255, 255, 0.3); border-radius: 10px; }}
    
    .section-title {{
        font-weight: 800;
        color: #ffffff !important;
        margin-bottom: 15px;
        position: relative;
        padding-bottom: 8px;
        font-size: 20px; 
    }}
    .section-title::after {{
        content: '';
        position: absolute;
        left: 0;
        bottom: 0;
        width: 40px;
        height: 4px;
        background: linear-gradient(90deg, #38bdf8, transparent);
        border-radius: 2px;
    }}
    
    .standby-box {{
        background: rgba(15, 23, 42, 0.85); 
        padding: 16px; 
        border-radius: 12px; 
        border-left: 4px solid #38bdf8; 
        box-shadow: 0 4px 10px rgba(0,0,0,0.4); 
        margin-bottom: 20px; 
        animation: fadeIn 0.4s ease-out;
        color: #ffffff; 
    }}
    
    [data-testid="column"] {{
        padding: 0 5px !important;
    }}
    </style>
    """, unsafe_allow_html=True)

if 'selected_date' not in st.session_state:
    st.session_state.selected_date = datetime.now().date()

# --- LINK DATA & ID ---
ID_SHEET_JADWAL = "1HuIrvhzm7xzXXbX5Foy2XPms7NLzFyttgH58Ez31pj0"
ID_SHEET_IZIN = "1mdr7InOGhuVwLCpgPW-fDVOMw38XvELlXK9sxJymMYU"

URL_JADWAL_AKTUAL = f"https://docs.google.com/spreadsheets/d/{ID_SHEET_JADWAL}/edit#gid=0"
URL_IZIN = f"https://docs.google.com/spreadsheets/d/{ID_SHEET_IZIN}/edit"
LINK_GFORM = "https://forms.gle/KB9CkfEsLB4yY9MK9"

# --- FUNGSI KONEKSI GSPREAD (REAL-TIME API) ---
def get_gspread_client():
    try:
        kredensial = dict(st.secrets["gcp_service_account"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(kredensial, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        return None

@st.cache_data(ttl=2) 
def load_data():
    try:
        client = get_gspread_client()
        if client:
            data_j = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual").get_all_values()
            df_j = pd.DataFrame(data_j[1:], columns=data_j[0]) if len(data_j) > 1 else pd.DataFrame(columns=data_j[0] if data_j else [])
            
            if 'Nama Operator' in df_j.columns:
                df_j = df_j[df_j['Nama Operator'].astype(str).str.strip() != '']
            
            data_i = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0).get_all_values()
            df_i = pd.DataFrame(data_i[1:], columns=data_i[0]) if len(data_i) > 1 else pd.DataFrame(columns=data_i[0] if data_i else [])
            
            return df_j, df_i
        return pd.DataFrame(), pd.DataFrame()
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

df_matrix, df_izin = load_data()


# ==========================================
# TOP HEADER BERSATU (PUTIH SOLID)
# ==========================================
if logo_base64:
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" class="header-logo">'
else:
    logo_html = '<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Pertamina_Logo.svg/512px-Pertamina_Logo.svg.png" class="header-logo">'

hari_ini_str = datetime.now().strftime('%d %b %Y')

# Merender Blok Putih di Paling Atas
st.markdown(f"""
    <div class="header-bar">
        <div>
            {logo_html}
        </div>
        <h1 class="header-title">NR ORF Integrated Command</h1>
        <div class="header-date">📅 {hari_ini_str}</div>
    </div>
""", unsafe_allow_html=True)


# ==========================================
# NAVIGASI CUSTOM (CHUNKY BUTTONS)
# ==========================================
if 'active_menu' not in st.session_state:
    st.session_state.active_menu = "🏠 Dashboard"

def set_menu(menu_name):
    st.session_state.active_menu = menu_name

nav_c1, nav_c2, nav_c3 = st.columns(3)

with nav_c1:
    st.button("🏠 Dashboard", 
              type="primary" if st.session_state.active_menu == "🏠 Dashboard" else "secondary", 
              on_click=set_menu, args=("🏠 Dashboard",), use_container_width=True)
with nav_c2:
    st.button("📅 Kalender", 
              type="primary" if st.session_state.active_menu == "📅 Kalender" else "secondary", 
              on_click=set_menu, args=("📅 Kalender",), use_container_width=True)
with nav_c3:
    st.button("🧑‍🔧 Cek OFF", 
              type="primary" if st.session_state.active_menu == "🧑‍🔧 Cek OFF" else "secondary", 
              on_click=set_menu, args=("🧑‍🔧 Cek OFF",), use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)
menu = st.session_state.active_menu


# ==========================================
# VIEW 1: DASHBOARD INTERAKTIF
# ==========================================
if menu == "🏠 Dashboard":
    
    col_antre, col_off = st.columns([2.5, 1.5])
        
    with col_antre:
        st.markdown("<h3 class='section-title'>🔔 Panel Manajer</h3>", unsafe_allow_html=True)
        client = get_gspread_client()
        
        pin = st.text_input("🔑 PIN Verifikasi Manajer", type="password", key="pin_dash", placeholder="Masukkan PIN...")
        
        if pin == "regas123":
            st.markdown("<div class='standby-box'>", unsafe_allow_html=True)
            st.markdown("🛠️ <b style='color:#38bdf8;'>Akses Editor Database</b>", unsafe_allow_html=True)
            
            st.link_button("📝 Edit Jadwal Aktual di Spreadsheet", URL_JADWAL_AKTUAL, use_container_width=True)
            st.link_button("📋 Edit Database Izin di Spreadsheet", URL_IZIN, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<h4 style='color:#ffffff; font-size:16px; font-weight:700; margin-top:10px;'>Antrean Persetujuan Izin:</h4>", unsafe_allow_html=True)
            if not df_izin.empty and 'Status Approval' in df_izin.columns:
                df_izin_valid = df_izin.dropna(subset=['Nama Lengkap Operator'])
                pending = df_izin_valid[df_izin_valid['Status Approval'].isna() | (df_izin_valid['Status Approval'] == "")]
                
                if not pending.empty:
                    for idx, row in pending.head(3).iterrows():
                        anim_delay = idx * 0.1
                        with st.container(border=True):
                            st.markdown(f"""
                            <div style='animation: slideInRight 0.4s {anim_delay}s ease-out backwards;'>
                                <b style='font-size:16px; color:#ffffff;'>{row['Nama Lengkap Operator']}</b> <span style='color:#cbd5e1; font-weight:500;'>({row.get('Jenis Izin yang Diajukan', 'Izin')})</span>
                                <div style='font-size:14px; margin-top:8px; color:#e2e8f0;'>📅 {row['Tanggal Mulai Izin']} s/d {row['Tanggal Selesai Izin']}</div>
                                <div style='font-size:14px; color:#e2e8f0; margin-top:2px;'><b>Shift:</b> {row.get('Shift Izin', 'Pg')}</div>
                                <div style='font-size:14px; color:#fca5a5; font-weight:700; margin-top:8px; margin-bottom:12px; background: rgba(239, 68, 68, 0.2); padding: 4px 8px; border-radius: 4px; display:inline-block;'>🔄 Pengganti: {row.get('Nama Lengkap Operator Pengganti', '-')}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            c_app, c_rej = st.columns(2)
                            with c_app:
                                if st.button("✅ Approve", key=f"d_app_{idx}", type="primary", use_container_width=True):
                                    if client:
                                        sh_izin = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0)
                                        sh_izin.update_cell(int(idx)+2, df_izin.columns.get_loc('Status Approval') + 1, "APPROVED")
                                        
                                        sh_aktual = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual")
                                        d_start = pd.to_datetime(row['Tanggal Mulai Izin'], dayfirst=True).date()
                                        d_end = pd.to_datetime(row['Tanggal Selesai Izin'], dayfirst=True).date()
                                        
                                        for d in pd.date_range(d_start, d_end):
                                            d_str = d.strftime('%Y-%m-%d')
                                            if d_str in df_matrix.columns:
                                                c_idx = list(df_matrix.columns).index(d_str) + 1
                                                match_p = df_matrix[df_matrix.iloc[:,0].astype(str).str.strip().str.lower() == str(row['Nama Lengkap Operator']).strip().lower()]
                                                if not match_p.empty: sh_aktual.update_cell(int(match_p.index[0])+2, c_idx, str(row['Jenis Izin yang Diajukan']).upper())
                                                nama_sub = str(row.get('Nama Lengkap Operator Pengganti', '')).strip().lower()
                                                if nama_sub and nama_sub not in ['nan', 'tidak ada', '']:
                                                    match_sub = df_matrix[df_matrix.iloc[:,0].astype(str).str.strip().str.lower() == nama_sub]
                                                    if not match_sub.empty: sh_aktual.update_cell(int(match_sub.index[0])+2, c_idx, str(row.get('Shift Izin', 'PG')).title())
                                        load_data.clear()
                                        st.rerun()
                            with c_rej:
                                if st.button("❌ Reject", key=f"d_rej_{idx}", use_container_width=True):
                                    if client:
                                        client.open_by_key(ID_SHEET_IZIN).get_worksheet(0).update_cell(int(idx)+2, df_izin.columns.get_loc('Status Approval') + 1, "REJECTED")
                                        load_data.clear()
                                        st.rerun()
                else:
                    st.info("✨ Tidak ada antrean persetujuan izin saat ini.")
            else:
                st.warning("Menunggu sinkronisasi data izin...")
        else:
            with st.container(border=True):
                st.markdown("<div style='text-align:center; padding:5px;'><span style='font-size:24px;'>🔒</span><br><span style='color:#cbd5e1; font-weight:500; font-size:14px;'>Masukkan PIN keamanan untuk mengakses Panel Approval & Editor Sheet.</span></div>", unsafe_allow_html=True)

    with col_off:
        st.markdown("<h3 class='section-title'>👥 Personel OFF Hari Ini</h3>", unsafe_allow_html=True)
        tgl_hari_ini_sys = datetime.now().strftime('%Y-%m-%d')
        
        if not df_matrix.empty and tgl_hari_ini_sys in df_matrix.columns:
            df_valid_names = df_matrix.dropna(subset=['Nama Operator'])
            kondisi_off = df_valid_names[tgl_hari_ini_sys].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])
            tersedia = df_valid_names[kondisi_off]["Nama Operator"].astype(str).tolist()
            
            with st.container(border=True):
                if tersedia:
                    for i, orang in enumerate(tersedia):
                        anim_delay = i * 0.05
                        st.markdown(f"<div style='padding:8px 12px; margin-bottom:6px; border-radius:8px; background: rgba(56, 189, 248, 0.1); border-left: 3px solid #38bdf8; animation: slideInRight 0.3s {anim_delay}s ease-out backwards;'><b style='color:#38bdf8; font-size:12px; margin-right:8px;'>OFF</b> <span style='color:#ffffff; font-weight: 500;'>{orang}</span></div>", unsafe_allow_html=True)
                else:
                    st.write("Tidak ada personel yang terjadwal OFF hari ini.")
        st.markdown("<br>", unsafe_allow_html=True)
        st.link_button("📝 Form Pengajuan Izin / Tukar Shift", LINK_GFORM, use_container_width=True, type="primary")

    # ==========================================
    # BAGIAN JADWAL SCROLL HORIZONTAL (14 HARI)
    # ==========================================
    st.markdown("<br><hr style='opacity:0.2; border-color: rgba(255,255,255,0.2);'><h3 class='section-title'>📅 Tinjauan 14 Hari Kedepan</h3>", unsafe_allow_html=True)
    
    today = datetime.now().date()
    days = [today + timedelta(days=i) for i in range(14)] 
    
    if not df_matrix.empty:
        # 1. AMBIL DATA PENGGANTI DARI DATABASE IZIN
        pengganti_dict = {} 
        if not df_izin.empty and 'Status Approval' in df_izin.columns:
            df_izin_app = df_izin[df_izin['Status Approval'].astype(str).str.upper() == 'APPROVED']
            for _, row in df_izin_app.iterrows():
                try:
                    nama_pengganti = str(row.get('Nama Lengkap Operator Pengganti', '')).strip().lower()
                    if nama_pengganti and nama_pengganti not in ['nan', 'tidak ada', '']:
                        d_start = pd.to_datetime(row['Tanggal Mulai Izin'], dayfirst=True).date()
                        d_end = pd.to_datetime(row['Tanggal Selesai Izin'], dayfirst=True).date()
                        for d in pd.date_range(d_start, d_end):
                            d_str = d.strftime('%Y-%m-%d')
                            if d_str not in pengganti_dict:
                                pengganti_dict[d_str] = []
                            pengganti_dict[d_str].append(nama_pengganti)
                except:
                    pass

        html_cards = '<div class="scroll-container">'
        
        for i, d in enumerate(days):
            d_str = d.strftime('%Y-%m-%d')
            card_delay = i * 0.05
            card_content = f'<div class="scroll-card" style="animation-delay: {card_delay}s;"><div class="scroll-header">{d.strftime("%d %b %Y")}</div>'
            
            if d_str in df_matrix.columns:
                df_day = df_matrix[['Nama Operator', d_str]].dropna()
                df_day = df_day[~df_day[d_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])]
                
                pengganti_hari_ini = pengganti_dict.get(d_str, [])
                
                if not df_day.empty:
                    for item_idx, (_, row) in enumerate(df_day.iterrows()):
                        nama_asli = str(row['Nama Operator']).replace('*', '').strip()
                        nama_lower = nama_asli.lower()
                        status = str(row[d_str])
                        item_delay = (i * 0.05) + (item_idx * 0.02)
                        
                        # LOGIKA HIGHLIGHT WARNA (Ditambah Oranye untuk Perjalanan Dinas)
                        if any(k in status.upper() for k in ["DINAS", "PD"]):
                            card_content += f'<div class="scroll-item item-dinas" style="animation-delay: {item_delay}s;">🟠 <b style="color:#e2e8f0;">{nama_asli}</b><br><span style="color:#fdba74; font-size:11px; font-weight:800; background:rgba(249, 115, 22, 0.3); padding:2px 6px; border-radius:4px; display:inline-block; margin-top:4px;">{status.upper()}</span></div>'
                        elif any(k in status.upper() for k in ["IZIN", "SAKIT", "CUTI"]):
                            card_content += f'<div class="scroll-item item-absen" style="animation-delay: {item_delay}s;">🔴 <b style="color:#e2e8f0;">{nama_asli}</b><br><span style="color:#fca5a5; font-size:11px; font-weight:800; background:rgba(239, 68, 68, 0.3); padding:2px 6px; border-radius:4px; display:inline-block; margin-top:4px;">{status.upper()}</span></div>'
                        elif nama_lower in pengganti_hari_ini:
                            card_content += f'<div class="scroll-item item-pengganti" style="animation-delay: {item_delay}s;">🔵 <b style="color:#e2e8f0;">{nama_asli}</b><br><span style="color:#7dd3fc; font-size:11px; font-weight:800; background:rgba(56, 189, 248, 0.2); padding:2px 6px; border-radius:4px; display:inline-block; margin-top:4px;">PENGGANTI SHIFT {status.upper()}</span></div>'
                        else:
                            card_content += f'<div class="scroll-item item-hadir" style="animation-delay: {item_delay}s;">🟢 <b style="color:#e2e8f0;">{nama_asli}</b><br><span style="color:#4ade80; font-size:11px; font-weight:800; background:rgba(34, 197, 94, 0.3); padding:2px 6px; border-radius:4px; display:inline-block; margin-top:4px;">SHIFT {status.upper()}</span></div>'
                else:
                    card_content += '<div class="scroll-item" style="color:#94a3b8; font-style:italic; text-align:center; background:none; border:none; box-shadow:none;">Semua Personel OFF</div>'
            else:
                card_content += '<div class="scroll-item" style="color:#94a3b8; font-style:italic; text-align:center; background:none; border:none; box-shadow:none;">Data belum dirilis</div>'
                
            card_content += '</div>'
            html_cards += card_content
            
        html_cards += '</div>' 
        st.markdown(html_cards, unsafe_allow_html=True)
    else:
        st.warning("Data Jadwal Aktual sedang disinkronisasi...")

# ==========================================
# VIEW 2: KALENDER LENGKAP
# ==========================================
elif menu == "📅 Kalender":
    st.markdown("<h3 class='section-title'>Pencarian Jadwal Spesifik</h3>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.info("Pilih tanggal untuk melihat status seluruh personel.")
        selected_date = st.date_input("Pilih Tanggal Pengecekan:", key="cal_date")

    st.markdown("<br>", unsafe_allow_html=True)
    selected_date_str = selected_date.strftime('%Y-%m-%d')

    if not df_matrix.empty:
        if selected_date_str in df_matrix.columns:
            st.markdown(f"<h4 style='color:#ffffff; animation: fadeIn 0.3s ease-out; font-size:18px;'>Status Personel pada: <b style='color:#38bdf8;'>{selected_date.strftime('%d %B %Y')}</b></h4>", unsafe_allow_html=True)
            df_day = df_matrix[['Nama Operator', selected_date_str]].dropna(subset=['Nama Operator'])
            df_day['Status'] = df_day[selected_date_str].fillna('').astype(str).str.strip().str.upper()

            df_off = df_day[df_day['Status'].isin(['OFF', 'NAN', '<NA>', '', 'NONE'])]
            # Menggabungkan Izin, Sakit, Cuti, dan Dinas dalam satu pengecekan untuk ringkasan absen
            df_absen = df_day[df_day['Status'].str.contains('IZIN|SAKIT|CUTI|DINAS|PD', na=False)]
            df_shift = df_day[~df_day['Nama Operator'].isin(df_off['Nama Operator']) & ~df_day['Nama Operator'].isin(df_absen['Nama Operator'])]

            st.markdown("<div style='animation: fadeIn 0.4s ease-out;'>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("<div style='background-color: rgba(34, 197, 94, 0.2); padding: 10px; border-radius: 8px; margin-bottom: 10px; border: 1px solid rgba(34, 197, 94, 0.4);'><b style='color: #ffffff;'>🟢 Hadir / Shift (" + str(len(df_shift)) + ")</b></div>", unsafe_allow_html=True)
                st.dataframe(df_shift[['Nama Operator', 'Status']], hide_index=True, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<div style='animation: fadeIn 0.5s ease-out; margin-top:15px;'>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("<div style='background-color: rgba(56, 189, 248, 0.2); padding: 10px; border-radius: 8px; margin-bottom: 10px; border: 1px solid rgba(56, 189, 248, 0.4);'><b style='color: #ffffff;'>⚪ Sedang OFF (" + str(len(df_off)) + ")</b></div>", unsafe_allow_html=True)
                st.dataframe(df_off[['Nama Operator']], hide_index=True, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<div style='animation: fadeIn 0.6s ease-out; margin-top:15px;'>", unsafe_allow_html=True)
            with st.container(border=True):
                # Menambahkan label "Dinas" pada tabel absensi
                st.markdown("<div style='background-color: rgba(239, 68, 68, 0.2); padding: 10px; border-radius: 8px; margin-bottom: 10px; border: 1px solid rgba(239, 68, 68, 0.4);'><b style='color: #ffffff;'>🔴 Absen / Cuti / Dinas (" + str(len(df_absen)) + ")</b></div>", unsafe_allow_html=True)
                if not df_absen.empty:
                    st.dataframe(df_absen[['Nama Operator', 'Status']], hide_index=True, use_container_width=True)
                else:
                    st.write("Tidak ada personel yang absen atau dinas luar.")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning(f"⚠️ Data jadwal untuk tanggal **{selected_date.strftime('%d %B %Y')}** belum dirilis atau tidak tersedia di sistem.")
    else:
        st.error("❌ Data matrix jadwal gagal dimuat. Silakan muat ulang halaman.")

# ==========================================
# VIEW 3: PENCARIAN REKAN OFF
# ==========================================
elif menu == "🧑‍🔧 Cek OFF":
    st.markdown("<h3 class='section-title'>Ketersediaan Pengganti Shift</h3>", unsafe_allow_html=True)
    
    with st.container(border=True):
        tgl_cek = st.date_input("Pilih Tanggal Rencana Izin / Tukar Shift:")
        tgl_cek_str = tgl_cek.strftime('%Y-%m-%d')

        if not df_matrix.empty and tgl_cek_str in df_matrix.columns:
            df_valid_names = df_matrix.dropna(subset=['Nama Operator'])
            kondisi_off = df_valid_names[tgl_cek_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])
            tersedia = df_valid_names[kondisi_off]["Nama Operator"].astype(str).tolist()
            
            if tersedia:
                st.markdown("<div style='animation: slideInRight 0.4s ease-out;'>", unsafe_allow_html=True)
                st.success(f"Ditemukan **{len(tersedia)} personel** yang sedang OFF di tanggal {tgl_cek_str}:")
                st.dataframe(pd.DataFrame({"Nama Personel (Status: OFF)": tersedia}), use_container_width=True, hide_index=True)
                st.markdown("<br>", unsafe_allow_html=True)
                st.link_button("📝 Lanjut Ajukan Izin (G-Form)", LINK_GFORM, type="primary", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.error("Tidak ada rekan yang berstatus OFF pada tanggal tersebut.")
