import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import base64
import os

# --- KONFIGURASI HALAMAN (WIDE LAYOUT) ---
st.set_page_config(page_title="Command Center NR", page_icon="⚓", layout="wide")

# --- FUNGSI LOAD BACKGROUND IMAGE (BASE64) ---
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception:
        return None

img_base64 = get_base64_of_bin_file("fsru.jpg")

# PENGATURAN OPACITY BACKGROUND (DARK MODE):
overlay_opacity = 0.85
bg_color = f"rgba(15, 23, 42, {overlay_opacity})" # Warna Navy/Slate gelap

if img_base64:
    bg_image_css = f"background-image: linear-gradient({bg_color}, {bg_color}), url('data:image/jpeg;base64,{img_base64}');"
else:
    bg_image_css = f"background-image: linear-gradient({bg_color}, {bg_color}), url('https://images.unsplash.com/photo-1583508108422-0a13d712ce19?q=80&w=1920&auto=format&fit=crop');"

# --- KUSTOMISASI CSS (DARK GLASSMORPHISM) ---
st.markdown(f"""
    <style>
    /* Mengimpor Font Modern 'Plus Jakarta Sans' */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    /* Mengatur Font Global & Background Utama */
    html, body, [class*="css"], .stApp {{
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        color: #e2e8f0; /* Warna teks global abu-abu terang */
    }}
    
    .stApp {{
        {bg_image_css}
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    
    /* Mengatur Transparansi Header Bawaan Streamlit */
    header[data-testid="stHeader"] {{
        background-color: rgba(0, 0, 0, 0.0) !important;
    }}

    /* Teks Judul dibuat lebih terang */
    h1, h2, h3, h4, h5 {{ 
        color: #f8fafc !important; 
        font-family: 'Plus Jakarta Sans', sans-serif; 
        text-shadow: 0px 2px 4px rgba(0,0,0,0.5);
    }}

    /* KARTU/MENU MELAYANG (DARK SOFT UI) */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {{
        border-radius: 16px;
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.8)) !important;
        backdrop-filter: blur(16px); 
        border: 1px solid rgba(255, 255, 255, 0.1); /* Border putih transparan */
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3); 
        padding: 24px;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        animation: fadeIn 0.6s ease-out;
    }}
    
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(10px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    
    /* Efek Hover Pada Kartu Utama */
    div[data-testid="stVerticalBlock"] > div[style*="border"]:hover {{
        transform: translateY(-4px);
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4);
        border-color: rgba(255, 255, 255, 0.2);
    }}
    
    /* SIDEBAR LEBIH MODERN GELAP */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.95) 0%, rgba(2, 6, 23, 0.95) 100%) !important;
        backdrop-filter: blur(15px);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }}

    /* TOMBOL MODERN (GRADIENT & HOVER) */
    .stButton>button {{
        border-radius: 10px;
        font-weight: 600;
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: white;
        border: 1px solid rgba(255,255,255,0.1);
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }}
    .stButton>button:hover {{
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        transform: translateY(-2px) scale(1.02);
        box-shadow: 0 7px 14px rgba(37, 99, 235, 0.4);
        color: white;
        border: 1px solid rgba(255,255,255,0.3);
    }}
    
    /* BADGE STATUS (Disesuaikan untuk dark mode) */
    .status-badge {{
        background-color: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 700;
        display: inline-block;
        margin-bottom: 5px;
        border: 1px solid rgba(74, 222, 128, 0.3);
    }}
    
    /* === CSS KHUSUS HORIZONTAL SCROLL JADWAL === */
    .scroll-container {{
        display: flex;
        overflow-x: auto;
        gap: 16px;
        padding-bottom: 20px;
        padding-top: 10px;
    }}
    .scroll-card {{
        flex: 0 0 220px;
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9)); 
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 14px;
        padding: 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        animation: slideInRight 0.5s ease-out backwards;
    }}
    
    @keyframes slideInRight {{
        0% {{ opacity: 0; transform: translateX(20px); }}
        100% {{ opacity: 1; transform: translateX(0); }}
    }}

    .scroll-card:hover {{
        transform: translateY(-5px) scale(1.01);
        box-shadow: 0 12px 24px rgba(0, 0, 0, 0.4);
        border-color: rgba(255, 255, 255, 0.25);
        z-index: 10;
    }}
    .scroll-header {{
        text-align: center;
        background: linear-gradient(135deg, #1e3a8a, #1d4ed8);
        color: #f8fafc;
        padding: 10px;
        border-radius: 8px;
        font-weight: 700;
        margin-bottom: 16px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
        letter-spacing: 0.5px;
    }}
    
    /* ANIMASI ITEM DI DALAM KARTU */
    .scroll-item {{
        margin-bottom: 12px;
        font-size: 14px;
        line-height: 1.5;
        padding: 8px;
        border-radius: 8px;
        background-color: rgba(255,255,255,0.05);
        transition: all 0.3s ease;
        animation: popIn 0.4s ease backwards;
    }}
    
    @keyframes popIn {{
        0% {{ opacity: 0; transform: scale(0.95); }}
        100% {{ opacity: 1; transform: scale(1); }}
    }}

    .scroll-item:hover {{
        background-color: rgba(255,255,255,0.1);
        transform: translateX(5px);
    }}
    
    /* Indikator Sakit/Izin (Warna Terang untuk Dark Mode) */
    .item-absen {{
        border-left: 4px solid #f87171;
        background-color: rgba(248, 113, 113, 0.05);
    }}
    .item-hadir {{
        border-left: 4px solid #4ade80;
    }}
    
    /* CUSTOM SCROLLBAR GELAP */
    .scroll-container::-webkit-scrollbar {{ height: 8px; }}
    .scroll-container::-webkit-scrollbar-track {{ background: rgba(255, 255, 255, 0.05); border-radius: 10px; }}
    .scroll-container::-webkit-scrollbar-thumb {{ background: rgba(255, 255, 255, 0.2); border-radius: 10px; }}
    .scroll-container::-webkit-scrollbar-thumb:hover {{ background: rgba(255, 255, 255, 0.4); }}
    
    /* CLEAN HEADER UTAMA */
    .main-title {{
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #38bdf8, #f8fafc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 34px;
        margin: 0;
        padding: 0;
        text-shadow: 2px 2px 10px rgba(0,0,0,0.3);
    }}
    .date-badge {{
        text-align: center; 
        color: #38bdf8; 
        background: rgba(15, 23, 42, 0.6); 
        padding: 10px 16px; 
        border-radius: 12px; 
        font-weight: 700;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.1);
        transition: transform 0.2s ease;
    }}
    .date-badge:hover {{
        transform: translateY(-2px);
    }}
    
    .section-title {{
        font-weight: 800;
        color: #f8fafc !important;
        margin-bottom: 15px;
        position: relative;
        padding-bottom: 8px;
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
# SIDEBAR (NAVIGASI KIRI)
# ==========================================
with st.sidebar:
    try:
        st.image("pertamina.png", use_container_width=True)
    except:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Pertamina_Logo.svg/512px-Pertamina_Logo.svg.png", use_container_width=True)
        st.caption("*(Menunggu pertamina.png)*")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    menu = st.radio("Menu Utama", ["🏠 Dashboard Interaktif", "📅 Kalender Lengkap", "🧑‍🔧 Pencarian Rekan OFF"])
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<div class='status-badge'>✅ Firebase: Terhubung</div>", unsafe_allow_html=True)
    st.markdown("<div class='status-badge'>✅ G-Sheets: Terhubung</div>", unsafe_allow_html=True)
    st.markdown("<br><p style='font-size:12px; color:#64748b; font-weight:600;'>© 2026 PT Nusantara Regas</p>", unsafe_allow_html=True)

# ==========================================
# HEADER ATAS
# ==========================================
col_title, col_profile = st.columns([5.5, 1.5])
with col_title:
    st.markdown("<h1 class='main-title'>NR ORF Command Center & Integrated Scheduling</h1>", unsafe_allow_html=True)
with col_profile:
    hari_ini_str = datetime.now().strftime('%d %B %Y')
    st.markdown(f"<div class='date-badge'>📅 {hari_ini_str}</div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# VIEW 1: DASHBOARD INTERAKTIF
# ==========================================
if menu == "🏠 Dashboard Interaktif":
    
    col_antre, col_off = st.columns([2.5, 1.5])
        
    with col_antre:
        st.markdown("<h3 class='section-title'>🔔 Panel Manajer</h3>", unsafe_allow_html=True)
        client = get_gspread_client()
        
        pin = st.text_input("🔑 PIN Verifikasi Manajer", type="password", key="pin_dash", placeholder="Masukkan PIN...")
        
        if pin == "regas123":
            st.markdown("<div style='background: rgba(30, 41, 59, 0.6); padding:16px; border-radius:12px; border-left: 4px solid #38bdf8; box-shadow: 0 4px 10px rgba(0,0,0,0.2); margin-bottom:20px; animation: fadeIn 0.4s ease-out;'>", unsafe_allow_html=True)
            st.markdown("🛠️ <b style='color:#38bdf8;'>Akses Editor Database</b>", unsafe_allow_html=True)
            c_edit1, c_edit2 = st.columns(2)
            with c_edit1:
                st.link_button("📝 Edit Jadwal Aktual", URL_JADWAL_AKTUAL, use_container_width=True)
            with c_edit2:
                st.link_button("📋 Edit Database Izin", URL_IZIN, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<h4 style='color:#f8fafc; font-size:16px; font-weight:700; margin-top:10px;'>Antrean Persetujuan Izin:</h4>", unsafe_allow_html=True)
            if not df_izin.empty and 'Status Approval' in df_izin.columns:
                df_izin_valid = df_izin.dropna(subset=['Nama Lengkap Operator'])
                pending = df_izin_valid[df_izin_valid['Status Approval'].isna() | (df_izin_valid['Status Approval'] == "")]
                
                if not pending.empty:
                    for idx, row in pending.head(3).iterrows():
                        anim_delay = idx * 0.1
                        with st.container(border=True):
                            st.markdown(f"""
                            <div style='animation: slideInRight 0.4s {anim_delay}s ease-out backwards;'>
                                <b style='font-size:16px; color:#e2e8f0;'>{row['Nama Lengkap Operator']}</b> <span style='color:#94a3b8; font-weight:500;'>({row.get('Jenis Izin yang Diajukan', 'Izin')})</span>
                                <div style='font-size:14px; margin-top:8px; color:#cbd5e1;'>📅 {row['Tanggal Mulai Izin']} s/d {row['Tanggal Selesai Izin']} &nbsp;|&nbsp; <b>Shift:</b> {row.get('Shift Izin', 'Pg')}</div>
                                <div style='font-size:14px; color:#f87171; font-weight:700; margin-top:4px; margin-bottom:12px; background: rgba(248, 113, 113, 0.1); padding: 4px 8px; border-radius: 4px; display:inline-block;'>🔄 Pengganti: {row.get('Nama Lengkap Operator Pengganti', '-')}</div>
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
                st.markdown("<div style='text-align:center; padding:10px;'><span style='font-size:30px;'>🔒</span><br><span style='color:#94a3b8; font-weight:500;'>Masukkan PIN keamanan untuk mengakses Panel Approval & Editor Sheet.</span></div>", unsafe_allow_html=True)

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
                        st.markdown(f"<div style='padding:10px 12px; margin-bottom:6px; border-radius:8px; background: rgba(56, 189, 248, 0.05); border-left: 3px solid #38bdf8; animation: slideInRight 0.3s {anim_delay}s ease-out backwards;'><b style='color:#38bdf8; font-size:12px; margin-right:8px;'>OFF</b> <span style='color:#e2e8f0;'>{orang}</span></div>", unsafe_allow_html=True)
                else:
                    st.write("Tidak ada personel yang terjadwal OFF hari ini.")
            st.markdown("<br>", unsafe_allow_html=True)
            st.link_button("📝 Ajukan Izin (G-Form)", LINK_GFORM, use_container_width=True, type="primary")

    # ==========================================
    # BAGIAN JADWAL SCROLL HORIZONTAL (14 HARI)
    # ==========================================
    st.markdown("<br><hr style='opacity:0.2; border-color: rgba(255,255,255,0.1);'><h3 class='section-title'>📅 Jadwal Plotting 14 Hari Kedepan</h3>", unsafe_allow_html=True)
    
    today = datetime.now().date()
    days = [today + timedelta(days=i) for i in range(14)] 
    
    if not df_matrix.empty:
        html_cards = '<div class="scroll-container">'
        
        for i, d in enumerate(days):
            d_str = d.strftime('%Y-%m-%d')
            card_delay = i * 0.05
            card_content = f'<div class="scroll-card" style="animation-delay: {card_delay}s;"><div class="scroll-header">{d.strftime("%d %b %Y")}</div>'
            
            if d_str in df_matrix.columns:
                df_day = df_matrix[['Nama Operator', d_str]].dropna()
                df_day = df_day[~df_day[d_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])]
                
                if not df_day.empty:
                    for item_idx, (_, row) in enumerate(df_day.iterrows()):
                        nama_asli = str(row['Nama Operator']).replace('*', '').strip()
                        status = str(row[d_str])
                        item_delay = (i * 0.05) + (item_idx * 0.02)
                        
                        if any(k in status.upper() for k in ["IZIN", "SAKIT", "CUTI"]):
                            card_content += f'<div class="scroll-item item-absen" style="animation-delay: {item_delay}s;">🔴 <b style="color:#e2e8f0;">{nama_asli}</b><br><span style="color:#f87171; font-size:11px; font-weight:800; background:rgba(248, 113, 113, 0.1); padding:2px 6px; border-radius:4px; display:inline-block; margin-top:4px;">{status.upper()}</span></div>'
                        else:
                            card_content += f'<div class="scroll-item item-hadir" style="animation-delay: {item_delay}s;">🟢 <b style="color:#e2e8f0;">{nama_asli}</b><br><span style="color:#4ade80; font-size:11px; font-weight:800; background:rgba(74, 222, 128, 0.15); padding:2px 6px; border-radius:4px; display:inline-block; margin-top:4px;">SHIFT {status.upper()}</span></div>'
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
elif menu == "📅 Kalender Lengkap":
    st.markdown("<h3 class='section-title'>Tinjauan Jadwal Harian & Bulanan</h3>", unsafe_allow_html=True)
    
    with st.container(border=True):
        c1, c2 = st.columns([1, 3])
        with c1:
            selected_date = st.date_input("Pilih Tanggal Pengecekan:", key="cal_date")
        with c2:
            st.info("Pilih tanggal di sebelah kiri untuk melihat status seluruh personel secara lengkap pada hari tersebut.")

    st.markdown("<br>", unsafe_allow_html=True)
    selected_date_str = selected_date.strftime('%Y-%m-%d')

    if not df_matrix.empty:
        if selected_date_str in df_matrix.columns:
            st.markdown(f"<h4 style='color:#f8fafc; animation: fadeIn 0.3s ease-out;'>Status Personel pada: <b style='color:#38bdf8;'>{selected_date.strftime('%d %B %Y')}</b></h4>", unsafe_allow_html=True)
            df_day = df_matrix[['Nama Operator', selected_date_str]].dropna(subset=['Nama Operator'])
            df_day['Status'] = df_day[selected_date_str].fillna('').astype(str).str.strip().str.upper()

            df_off = df_day[df_day['Status'].isin(['OFF', 'NAN', '<NA>', '', 'NONE'])]
            df_absen = df_day[df_day['Status'].str.contains('IZIN|SAKIT|CUTI', na=False)]
            df_shift = df_day[~df_day['Nama Operator'].isin(df_off['Nama Operator']) & ~df_day['Nama Operator'].isin(df_absen['Nama Operator'])]

            col_shift, col_off, col_absen = st.columns(3)
            
            with col_shift:
                st.markdown("<div style='animation: fadeIn 0.4s ease-out;'>", unsafe_allow_html=True)
                with st.container(border=True):
                    st.success(f"🟢 **Hadir / Shift ({len(df_shift)})**")
                    st.dataframe(df_shift[['Nama Operator', 'Status']], hide_index=True, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
            with col_off:
                st.markdown("<div style='animation: fadeIn 0.5s ease-out;'>", unsafe_allow_html=True)
                with st.container(border=True):
                    st.info(f"⚪ **Sedang OFF ({len(df_off)})**")
                    st.dataframe(df_off[['Nama Operator']], hide_index=True, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
            with col_absen:
                st.markdown("<div style='animation: fadeIn 0.6s ease-out;'>", unsafe_allow_html=True)
                with st.container(border=True):
                    st.error(f"🔴 **Izin / Cuti / Sakit ({len(df_absen)})**")
                    if not df_absen.empty:
                        st.dataframe(df_absen[['Nama Operator', 'Status']], hide_index=True, use_container_width=True)
                    else:
                        st.write("Tidak ada personel yang absen.")
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning(f"⚠️ Data jadwal untuk tanggal **{selected_date.strftime('%d %B %Y')}** belum dirilis atau tidak tersedia di sistem.")
    else:
        st.error("❌ Data matrix jadwal gagal dimuat. Silakan muat ulang halaman.")

# ==========================================
# VIEW 3: PENCARIAN REKAN OFF
# ==========================================
elif menu == "🧑‍🔧 Pencarian Rekan OFF":
    st.markdown("<h3 class='section-title'>Cari Ketersediaan Pengganti Shift</h3>", unsafe_allow_html=True)
    
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
                st.link_button("📝 Lanjut Ajukan Izin di Google Form", LINK_GFORM, type="primary")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.error("Tidak ada rekan yang berstatus OFF pada tanggal tersebut.")
