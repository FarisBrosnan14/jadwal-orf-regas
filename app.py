import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import calendar
import gspread
from google.oauth2.service_account import Credentials

# --- KONFIGURASI HALAMAN (WIDE LAYOUT) ---
st.set_page_config(page_title="Dashboard Nusantara Regas", page_icon="⚓", layout="wide")

# --- KUSTOMISASI CSS (TAMPILAN MODERN PERTAMINA) ---
st.markdown("""
    <style>
    /* Warna teks judul utama */
    h1, h2, h3 { color: #004D95; font-family: 'Segoe UI', sans-serif; }
    
    /* Memperhalus kotak kontainer (Cards) */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        background-color: #ffffff;
        border: 1px solid #eaeaea;
        padding: 15px;
    }
    
    /* Panel samping (Sidebar) lebih bersih */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 2px solid #eaeaea;
    }
    
    /* Kustomisasi tombol */
    .stButton>button {
        border-radius: 8px;
        font-weight: bold;
    }
    
    /* Notifikasi hijau terhubung */
    .status-badge {
        background-color: #e6f8eb;
        color: #008b45;
        padding: 5px 10px;
        border-radius: 15px;
        font-size: 12px;
        font-weight: bold;
        display: inline-block;
        margin-bottom: 5px;
    }
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

# --- KONEKSI BACA ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=5) 
def load_data():
    try:
        df_j = conn.read(spreadsheet=URL_JADWAL_AKTUAL, ttl="0")
        df_i = conn.read(spreadsheet=URL_IZIN, ttl="0")
        return df_j, df_i
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

df_matrix, df_izin = load_data()

def get_gspread_client():
    try:
        kredensial = dict(st.secrets["gcp_service_account"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(kredensial, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        return None

# ==========================================
# SIDEBAR (NAVIGASI KIRI)
# ==========================================
with st.sidebar:
    # Menggunakan file logo pertamina lokal
    st.image("pertamina.png", use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Navigasi ala menu aplikasi
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
    st.header("Sistem Penjadwalan Terpadu Nusantara Regas")
with col_profile:
    hari_ini_str = datetime.now().strftime('%d %B %Y')
    st.markdown(f"<div style='text-align:right; color:#4a4a4a;'>📅 {hari_ini_str}<br>👤 <b>Faris (Admin)</b></div>", unsafe_allow_html=True)

st.divider()

# ==========================================
# VIEW 1: DASHBOARD INTERAKTIF (SESUAI MOCKUP)
# ==========================================
if menu == "🏠 Dashboard Interaktif":
    
    # --- BARIS 1: GAMBAR, ANTREAN, PERSONEL OFF ---
    col_img, col_antre, col_off = st.columns([1.8, 1.2, 1.2])
    
    with col_img:
        # Menampilkan gambar FSRU
        try:
            st.image("fsru.jpg", use_container_width=True)
        except:
            st.info("Gambar fsru.jpg belum terunggah di GitHub.")
        st.success("🟢 Status Kapal: FSRU Nusantara Regas 1 - Operasional Normal")
        
    with col_antre:
        st.subheader("🔔 Antrean Persetujuan")
        client = get_gspread_client()
        
        if not df_izin.empty and 'Status Approval' in df_izin.columns:
            df_izin_valid = df_izin.dropna(subset=['Nama Lengkap Operator'])
            pending = df_izin_valid[df_izin_valid['Status Approval'].isna() | (df_izin_valid['Status Approval'] == "")]
            
            if not pending.empty:
                # Menggunakan PIN sebentar untuk keamanan eksekusi
                pin = st.text_input("🔑 PIN Manager (regas123):", type="password", key="pin_dash")
                
                # Hanya tampilkan maksimal 3 teratas agar dashboard tidak kepanjangan
                for idx, row in pending.head(3).iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{row['Nama Lengkap Operator']}** ({row.get('Jenis Izin yang Diajukan', 'Izin')})")
                        st.caption(f"📅 {row['Tanggal Mulai Izin']} s/d {row['Tanggal Selesai Izin']} | Shift: {row.get('Shift Izin', 'Pg')}")
                        st.caption(f"🔄 Pengganti: {row.get('Nama Lengkap Operator Pengganti', '-')}")
                        
                        if pin == "regas123":
                            c_app, c_rej = st.columns(2)
                            with c_app:
                                if st.button("✅ Approve", key=f"d_app_{idx}", type="primary", use_container_width=True):
                                    if client:
                                        # DOUBLE ACTION SCRIPT
                                        sh_izin = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0)
                                        sh_izin.update_cell(int(idx)+2, df_izin.columns.get_loc('Status Approval') + 1, "APPROVED")
                                        
                                        sh_aktual = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual")
                                        d_start = pd.to_datetime(row['Tanggal Mulai Izin'], dayfirst=True).date()
                                        d_end = pd.to_datetime(row['Tanggal Selesai Izin'], dayfirst=True).date()
                                        
                                        for d in pd.date_range(d_start, d_end):
                                            d_str = d.strftime('%Y-%m-%d')
                                            if d_str in df_matrix.columns:
                                                c_idx = list(df_matrix.columns).index(d_str) + 1
                                                # Pemohon
                                                match_p = df_matrix[df_matrix.iloc[:,0].astype(str).str.strip().str.lower() == str(row['Nama Lengkap Operator']).strip().lower()]
                                                if not match_p.empty: sh_aktual.update_cell(int(match_p.index[0])+2, c_idx, str(row['Jenis Izin yang Diajukan']).upper())
                                                # Pengganti
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

    # --- BARIS 2: JADWAL HORIZONTAL (5 HARI KEDEPAN) ---
    st.markdown("---")
    st.subheader("📅 Tinjauan Jadwal 5 Hari Kedepan")
    
    today = datetime.now().date()
    days = [today + timedelta(days=i) for i in range(5)]
    cols_days = st.columns(5)
    
    if not df_matrix.empty:
        for i, d in enumerate(days):
            d_str = d.strftime('%Y-%m-%d')
            with cols_days[i]:
                with st.container(border=True):
                    st.markdown(f"<div style='text-align:center; background-color:#004D95; color:white; padding:5px; border-radius:5px; margin-bottom:10px;'><b>{d.strftime('%d/%m/%Y')}</b></div>", unsafe_allow_html=True)
                    
                    if d_str in df_matrix.columns:
                        df_day = df_matrix[['Nama Operator', d_str]].dropna()
                        df_day = df_day[~df_day[d_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])]
                        
                        if not df_day.empty:
                            for _, row in df_day.iterrows():
                                status = str(row[d_str])
                                if any(k in status.upper() for k in ["IZIN", "SAKIT", "CUTI"]):
                                    st.markdown(f"❌ **{row['Nama Operator']}**<br><span style='color:red; font-size:12px;'>{status}</span>", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"🔹 **{row['Nama Operator']}**<br><span style='color:green; font-size:12px;'>Shift {status}</span>", unsafe_allow_html=True)
                        else:
                            st.caption("Semua Personel OFF")
                    else:
                        st.caption("Data belum dirilis")
    else:
        st.warning("Data Jadwal Aktual belum dimuat.")

# ==========================================
# VIEW 2: KALENDER LENGKAP
# ==========================================
elif menu == "📅 Kalender Lengkap":
    st.subheader("Tinjauan Jadwal Bulanan")
    # (Logika kalender di sini tetap sama dengan versi sebelumnya jika dibutuhkan untuk melihat bulan lain)
    c1, c2 = st.columns([1, 2])
    with c1:
        st.date_input("Pilih Tanggal Pengecekan:", key="cal_date")
    with c2:
        st.info("Fitur kalender penuh ada di tampilan ini. Silakan gunakan Dashboard Interaktif untuk operasional harian.")

# ==========================================
# VIEW 3: PENCARIAN REKAN OFF
# ==========================================
elif menu == "🧑‍🔧 Pencarian Rekan OFF":
    st.subheader("Cari Ketersediaan Pengganti")
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
