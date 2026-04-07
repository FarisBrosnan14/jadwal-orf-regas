import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import base64
import os

# --- KONFIGURASI HALAMAN (WIDE LAYOUT) ---
st.set_page_config(page_title="Dashboard Nusantara Regas", page_icon="⚓", layout="wide")

# --- FUNGSI LOAD BACKGROUND IMAGE (BASE64) ---
# Fungsi ini akan mengubah file fsru.jpg menjadi background. 
# Jika file tidak ditemukan, otomatis pakai gambar online sebagai cadangan.
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception:
        return None

img_base64 = get_base64_of_bin_file("fsru.jpg")
if img_base64:
    bg_image_css = f"background-image: url('data:image/jpeg;base64,{img_base64}');"
else:
    bg_image_css = "background-image: url('https://images.unsplash.com/photo-1583508108422-0a13d712ce19?q=80&w=1920&auto=format&fit=crop');"

# --- KUSTOMISASI CSS (GLASSMORPHISM / MELAYANG) ---
st.markdown(f"""
    <style>
    /* Mengatur Background Utama Aplikasi */
    .stApp {{
        {bg_image_css}
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    
    /* Mengatur Transparansi Header Bawaan Streamlit */
    header[data-testid="stHeader"] {{
        background-color: rgba(255, 255, 255, 0.0) !important;
    }}

    /* Teks Judul dengan sedikit bayangan agar terbaca di background apapun */
    h1, h2, h3 {{ 
        color: #004D95; 
        font-family: 'Segoe UI', sans-serif; 
        text-shadow: 1px 1px 3px rgba(255,255,255,0.8);
    }}

    /* KARTU/MENU MELAYANG (GLASSMORPHISM) */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {{
        border-radius: 15px;
        background-color: rgba(255, 255, 255, 0.85) !important; /* Opacity 85% */
        backdrop-filter: blur(10px); /* Efek kaca buram */
        border: 1px solid rgba(255, 255, 255, 0.5);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.15); /* Bayangan melayang */
        padding: 20px;
    }}
    
    /* SIDEBAR TRANSPARAN */
    [data-testid="stSidebar"] {{
        background-color: rgba(248, 249, 250, 0.85) !important;
        backdrop-filter: blur(10px);
        border-right: 1px solid rgba(255, 255, 255, 0.4);
    }}

    .stButton>button {{
        border-radius: 8px;
        font-weight: bold;
    }}
    
    .status-badge {{
        background-color: rgba(230, 248, 235, 0.9);
        color: #008b45;
        padding: 5px 10px;
        border-radius: 15px;
        font-size: 12px;
        font-weight: bold;
        display: inline-block;
        margin-bottom: 5px;
        border: 1px solid #008b45;
    }}
    
    /* === CSS KHUSUS HORIZONTAL SCROLL JADWAL MELAYANG === */
    .scroll-container {{
        display: flex;
        overflow-x: auto;
        gap: 15px;
        padding-bottom: 15px;
    }}
    .scroll-card {{
        flex: 0 0 220px;
        background-color: rgba(255, 255, 255, 0.85); /* Kaca transparan */
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.5);
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }}
    .scroll-header {{
        text-align: center;
        background-color: rgba(0, 77, 149, 0.9);
        color: white;
        padding: 8px;
        border-radius: 6px;
        font-weight: bold;
        margin-bottom: 15px;
    }}
    .scroll-item {{
        margin-bottom: 10px;
        font-size: 14px;
        line-height: 1.4;
    }}
    .scroll-container::-webkit-scrollbar {{ height: 10px; }}
    .scroll-container::-webkit-scrollbar-track {{ background: rgba(241, 241, 241, 0.5); border-radius: 5px; }}
    .scroll-container::-webkit-scrollbar-thumb {{ background: rgba(193, 193, 193, 0.8); border-radius: 5px; }}
    .scroll-container::-webkit-scrollbar-thumb:hover {{ background: rgba(168, 168, 168, 1); }}
    
    /* Mengubah background container Markdown khusus Kalender Harian */
    .kalender-header {{
        background-color: rgba(255, 255, 255, 0.85);
        padding: 10px 15px;
        border-radius: 10px;
        display: inline-block;
        margin-bottom: 15px;
        backdrop-filter: blur(5px);
        border: 1px solid rgba(255,255,255,0.5);
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
        st.caption("*(Menunggu pertamina.png terupload)*")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    menu = st.radio("Menu Utama", ["🏠 Dashboard Interaktif", "📅 Kalender Lengkap", "🧑‍🔧 Pencarian Rekan OFF"])
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<div class='status-badge'>✅ Koneksi Firebase: Terhubung</div>", unsafe_allow_html=True)
    st.markdown("<div class='status-badge'>✅ Data G-Sheets: Terhubung</div>", unsafe_allow_html=True)
    st.caption("© 2026 PT Nusantara Regas")

# ==========================================
# HEADER ATAS
# ==========================================
col_title, col_profile = st.columns([4, 1])
with col_title:
    st.markdown("<h1 style='background-color: rgba(255,255,255,0.85); padding: 10px 20px; border-radius: 10px; display: inline-block; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.5);'>Sistem Penjadwalan Terpadu</h1>", unsafe_allow_html=True)
with col_profile:
    hari_ini_str = datetime.now().strftime('%d %B %Y')
    st.markdown(f"<div style='text-align:right; color:#004D95; background-color: rgba(255,255,255,0.85); padding: 10px; border-radius: 10px; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.5); font-weight: bold;'>📅 {hari_ini_str}</div>", unsafe_allow_html=True)

st.divider()

# ==========================================
# VIEW 1: DASHBOARD INTERAKTIF
# ==========================================
if menu == "🏠 Dashboard Interaktif":
    
    col_info, col_antre, col_off = st.columns([1, 1.5, 1.5])
    
    with col_info:
        with st.container(border=True):
            st.subheader("🚢 Status Operasional")
            st.success("🟢 FSRU Nusantara Regas 1 beroperasi normal.")
            st.info("⚓ Mode: Siaga / Standby")
            st.caption("Pastikan seluruh jadwal operator terisi untuk kelancaran bongkar muat.")
        
    with col_antre:
        st.subheader("🔔 Panel Manajer")
        client = get_gspread_client()
        
        pin = st.text_input("🔑 PIN Manager", type="password", key="pin_dash")
        
        if pin == "regas123":
            st.markdown("<div style='background-color:rgba(240, 247, 255, 0.9); padding:10px; border-radius:10px; border:1px solid #004D95;'>", unsafe_allow_html=True)
            st.markdown("🛠️ **Akses Editor Spreadsheet**")
            c_edit1, c_edit2 = st.columns(2)
            with c_edit1:
                st.link_button("📝 Edit Jadwal", URL_JADWAL_AKTUAL, use_container_width=True)
            with c_edit2:
                st.link_button("📋 Edit Data Izin", URL_IZIN, use_container_width=True)
            st.markdown("</div><br>", unsafe_allow_html=True)

            st.markdown("<div class='kalender-header'>**Antrean Persetujuan:**</div>", unsafe_allow_html=True)
            if not df_izin.empty and 'Status Approval' in df_izin.columns:
                df_izin_valid = df_izin.dropna(subset=['Nama Lengkap Operator'])
                pending = df_izin_valid[df_izin_valid['Status Approval'].isna() | (df_izin_valid['Status Approval'] == "")]
                
                if not pending.empty:
                    for idx, row in pending.head(3).iterrows():
                        with st.container(border=True):
                            st.markdown(f"**{row['Nama Lengkap Operator']}** ({row.get('Jenis Izin yang Diajukan', 'Izin')})")
                            st.caption(f"📅 {row['Tanggal Mulai Izin']} s/d {row['Tanggal Selesai Izin']} | Shift: {row.get('Shift Izin', 'Pg')}")
                            st.caption(f"🔄 Pengganti: {row.get('Nama Lengkap Operator Pengganti', '-')}")
                            
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
                    st.info("✨ Tidak ada antrean pending.")
            else:
                st.warning("Menunggu data izin.")
        else:
            with st.container(border=True):
                st.caption("Masukkan PIN untuk akses fitur Manajer (Approval & Editor).")

    with col_off:
        st.subheader("👥 Personel OFF Hari Ini")
        tgl_hari_ini_sys = datetime.now().strftime('%Y-%m-%d')
        
        if not df_matrix.empty and tgl_hari_ini_sys in df_matrix.columns:
            df_valid_names = df_matrix.dropna(subset=['Nama Operator'])
            kondisi_off = df_valid_names[tgl_hari_ini_sys].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])
            tersedia = df_valid_names[kondisi_off]["Nama Operator"].astype(str).tolist()
            
            with st.container(border=True):
                if tersedia:
                    for orang in tersedia:
                        st.markdown(f"🔹 {orang}")
                else:
                    st.write("Tidak ada personel OFF.")
            st.link_button("📝 Ajukan Izin (Google Form)", LINK_GFORM, use_container_width=True, type="primary")

    # ==========================================
    # BAGIAN JADWAL SCROLL HORIZONTAL (14 HARI)
    # ==========================================
    st.markdown("---")
    st.markdown("<div class='kalender-header'><h2>📅 Tinjauan Jadwal 14 Hari Kedepan</h2></div>", unsafe_allow_html=True)
    
    today = datetime.now().date()
    days = [today + timedelta(days=i) for i in range(14)] 
    
    if not df_matrix.empty:
        html_cards = '<div class="scroll-container">'
        
        for d in days:
            d_str = d.strftime('%Y-%m-%d')
            card_content = f'<div class="scroll-card"><div class="scroll-header">{d.strftime("%d/%m/%Y")}</div>'
            
            if d_str in df_matrix.columns:
                df_day = df_matrix[['Nama Operator', d_str]].dropna()
                df_day = df_day[~df_day[d_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])]
                
                if not df_day.empty:
                    for _, row in df_day.iterrows():
                        nama_asli = str(row['Nama Operator']).replace('*', '').strip()
                        status = str(row[d_str])
                        
                        if any(k in status.upper() for k in ["IZIN", "SAKIT", "CUTI"]):
                            card_content += f'<div class="scroll-item">❌ <b>{nama_asli}</b><br><span style="color:#d93025; font-size:12px; font-weight:bold;">{status}</span></div>'
                        else:
                            card_content += f'<div class="scroll-item">🔹 <b>{nama_asli}</b><br><span style="color:#008b45; font-size:12px; font-weight:bold;">Shift {status}</span></div>'
                else:
                    card_content += '<div class="scroll-item" style="color:#888;">Semua Personel OFF</div>'
            else:
                card_content += '<div class="scroll-item" style="color:#888;">Data belum dirilis</div>'
                
            card_content += '</div>'
            html_cards += card_content
            
        html_cards += '</div>' 
        st.markdown(html_cards, unsafe_allow_html=True)
    else:
        st.warning("Data Jadwal Aktual belum dimuat.")

# ==========================================
# VIEW 2: KALENDER LENGKAP
# ==========================================
elif menu == "📅 Kalender Lengkap":
    st.markdown("<div class='kalender-header'><h2>Tinjauan Jadwal Harian & Bulanan</h2></div>", unsafe_allow_html=True)
    
    with st.container(border=True):
        c1, c2 = st.columns([1, 2])
        with c1:
            selected_date = st.date_input("Pilih Tanggal Pengecekan:", key="cal_date")
        with c2:
            st.info("Gunakan Dashboard Interaktif untuk operasional harian.")

    st.markdown("---")
    selected_date_str = selected_date.strftime('%Y-%m-%d')

    if not df_matrix.empty:
        if selected_date_str in df_matrix.columns:
            st.markdown(f"<div class='kalender-header'><h3>Status Personel pada <b>{selected_date.strftime('%d %B %Y')}</b></h3></div>", unsafe_allow_html=True)
            df_day = df_matrix[['Nama Operator', selected_date_str]].dropna(subset=['Nama Operator'])
            df_day['Status'] = df_day[selected_date_str].fillna('').astype(str).str.strip().str.upper()

            df_off = df_day[df_day['Status'].isin(['OFF', 'NAN', '<NA>', '', 'NONE'])]
            df_absen = df_day[df_day['Status'].str.contains('IZIN|SAKIT|CUTI', na=False)]
            df_shift = df_day[~df_day['Nama Operator'].isin(df_off['Nama Operator']) & ~df_day['Nama Operator'].isin(df_absen['Nama Operator'])]

            col_shift, col_off, col_absen = st.columns(3)
            with col_shift:
                with st.container(border=True):
                    st.success(f"🟢 **Hadir / Shift ({len(df_shift)})**")
                    st.dataframe(df_shift[['Nama Operator', 'Status']], hide_index=True, use_container_width=True)
            with col_off:
                with st.container(border=True):
                    st.info(f"⚪ **Sedang OFF ({len(df_off)})**")
                    st.dataframe(df_off[['Nama Operator']], hide_index=True, use_container_width=True)
            with col_absen:
                with st.container(border=True):
                    st.error(f"🔴 **Izin / Cuti / Sakit ({len(df_absen)})**")
                    if not df_absen.empty:
                        st.dataframe(df_absen[['Nama Operator', 'Status']], hide_index=True, use_container_width=True)
                    else:
                        st.write("Tidak ada yang absen.")
        else:
            st.warning(f"⚠️ Data jadwal untuk tanggal **{selected_date.strftime('%d %B %Y')}** belum dirilis atau tidak tersedia.")
    else:
        st.error("❌ Data matrix jadwal gagal dimuat.")

# ==========================================
# VIEW 3: PENCARIAN REKAN OFF
# ==========================================
elif menu == "🧑‍🔧 Pencarian Rekan OFF":
    st.markdown("<div class='kalender-header'><h2>Cari Ketersediaan Pengganti</h2></div>", unsafe_allow_html=True)
    
    with st.container(border=True):
        tgl_cek = st.date_input("Pilih Tanggal Rencana Izin:")
        tgl_cek_str = tgl_cek.strftime('%Y-%m-%d')

        if not df_matrix.empty and tgl_cek_str in df_matrix.columns:
            df_valid_names = df_matrix.dropna(subset=['Nama Operator'])
            kondisi_off = df_valid_names[tgl_cek_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])
            tersedia = df_valid_names[kondisi_off]["Nama Operator"].astype(str).tolist()
            
            if tersedia:
                st.success(f"Terdapat **{len(tersedia)} personel** yang OFF di tanggal {tgl_cek_str}:")
                st.dataframe(pd.DataFrame({"Nama Personel (Status: OFF)": tersedia}), use_container_width=True, hide_index=True)
                st.link_button("📝 Lanjut Ajukan Izin di Google Form", LINK_GFORM, type="primary")
            else:
                st.error("Tidak ada rekan yang OFF di tanggal ini.")
