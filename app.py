import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import calendar

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Dashboard ORF - Nusantara Regas", page_icon="⚓", layout="wide")

if 'selected_date' not in st.session_state:
    st.session_state.selected_date = datetime.now().date()

# --- LINK VIP (GID) ---
URL_TAB_DATABASE = "https://docs.google.com/spreadsheets/d/1HuIrvhzm7xzXXbX5Foy2XPms7NLzFyttgH58Ez31pj0/edit?gid=172132710#gid=172132710" 
URL_TAB_IZIN = "https://docs.google.com/spreadsheets/d/1mdr7InOGhuVwLCpgPW-fDVOMw38XvELlXK9sxJymMYU/edit?gid=1951809577#gid=1951809577"

conn = st.connection("gsheets", type=GSheetsConnection)

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.title("🔐 Akses Sistem")
mode_akses = st.sidebar.radio("Masuk Sebagai:", ["🧑‍🔧 Operator (View Only)", "👨‍💼 Manager (Edit)"])

is_manager = False
if mode_akses == "👨‍💼 Manager (Edit)":
    pin = st.sidebar.text_input("Masukkan PIN Manager:", type="password")
    if pin == "regas123":
        is_manager = True
        st.sidebar.success("Akses Manager Dibuka!")
        st.sidebar.link_button("Buka Spreadsheet Master", URL_TAB_DATABASE)
    elif pin != "":
        st.sidebar.error("PIN Salah!")

st.sidebar.divider()
LINK_GFORM_ISI = "https://forms.gle/zXzVwYvN1j1w7z9R9"
st.sidebar.link_button("📝 Isi Izin/Cuti (GForm)", LINK_GFORM_ISI, type="primary")

# ==========================================
# PROSES DATA
# ==========================================
st.title("📅 Dashboard Jadwal Jaga ORF")

# --- BACA DATA (ANTI-ERROR) ---
try:
    df_jadwal = conn.read(spreadsheet=URL_TAB_DATABASE, ttl="0")
except Exception as e:
    st.error(f"Gagal membaca data Jadwal Utama: {e}")
    st.stop()

try:
    df_izin = conn.read(spreadsheet=URL_TAB_IZIN, ttl="0")
except:
    df_izin = pd.DataFrame()

# --- IDENTIFIKASI KOLOM ---
def find_col(df, keywords):
    for col in df.columns:
        if any(key.upper() in str(col).upper() for key in keywords):
            return col
    return None

col_nama = find_col(df_jadwal, ['Nama', 'Operator', 'Unnamed'])
col_tgl = find_col(df_jadwal, ['Tanggal', 'Shift'])
col_status = find_col(df_jadwal, ['Status', 'Kode'])

if not col_nama or not col_tgl:
    st.warning("Menunggu data jadwal diisi oleh Manager...")
    st.stop()

st.divider()

# --- LAYOUT KALENDER ---
col_kiri, col_kanan = st.columns([1.5, 2])

with col_kiri:
    c1, c2 = st.columns(2)
    with c1:
        nama_bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        pilih_bulan = st.selectbox("Bulan", range(1, 13), format_func=lambda x: nama_bulan[x-1], index=st.session_state.selected_date.month - 1)
    with c2:
        pilih_tahun = st.selectbox("Tahun", range(2024, 2030), index=range(2024, 2030).index(st.session_state.selected_date.year))
    
    cal = calendar.monthcalendar(pilih_tahun, pilih_bulan)
    cols = st.columns(7)
    for i, h in enumerate(["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]):
        cols[i].markdown(f"<div style='text-align:center;font-weight:bold'>{h}</div>", unsafe_allow_html=True)
    
    for minggu in cal:
        cols = st.columns(7)
        for i, tanggal in enumerate(minggu):
            if tanggal != 0:
                curr_date = datetime(pilih_tahun, pilih_bulan, tanggal).date()
                is_selected = (curr_date == st.session_state.selected_date)
                if cols[i].button(str(tanggal), key=f"d_{tanggal}", type="primary" if is_selected else "secondary", use_container_width=True):
                    st.session_state.selected_date = curr_date
                    st.rerun()

with col_kanan:
    tgl = st.session_state.selected_date
    st.subheader(f"📌 Jadwal: {tgl.strftime('%d %B %Y')}")
    
    df_jadwal['Tgl_DT'] = pd.to_datetime(df_jadwal[col_tgl], errors='coerce').dt.date
    hari_ini = df_jadwal[df_jadwal['Tgl_DT'] == tgl].copy()
    
    # Cek Izin
    if not df_izin.empty and 'Nama Lengkap Operator' in df_izin.columns:
        df_izin['M_Izin'] = pd.to_datetime(df_izin['Tanggal Mulai Izin'], errors='coerce').dt.date
        df_izin['S_Izin'] = pd.to_datetime(df_izin['Tanggal Selesai Izin'], errors='coerce').dt.date
        sedang_izin = df_izin[(df_izin['M_Izin'] <= tgl) & (df_izin['S_Izin'] >= tgl)]
        
        for _, row in sedang_izin.iterrows():
            nama_i = str(row['Nama Lengkap Operator']).strip().lower()
            hari_ini.loc[hari_ini[col_nama].str.strip().str.lower() == nama_i, col_status] = f"❌ {row['Jenis Izin yang Diajukan']}"

    # Tampilkan yang masuk / izin
    tampil = hari_ini[hari_ini[col_status].astype(str).str.upper().isin(['PG', 'MLM']) | hari_ini[col_status].astype(str).str.contains('❌')]
    
    if not tampil.empty:
        df_view = tampil[[col_nama, col_status]].copy()
        df_view.columns = ["Nama Operator", "Shift/Status"]
        st.dataframe(df_view, width='stretch', hide_index=True)
    else:
        st.info("Semua operator Off / Tidak ada jadwal.")
    
    # Mode Manager
    if is_manager:
        st.divider()
        st.caption("🔍 Personel Tersedia (Standby/Off):")
        semua = set(df_jadwal[col_nama].unique()) - {"Belum ada data", None}
        sibuk = set(hari_ini[hari_ini[col_status].astype(str).str.upper().isin(['PG', 'MLM'])][col_nama].str.strip())
        tersedia = sorted(list(semua - sibuk))
        if tersedia:
            for n in tersedia: st.write(f"✅ {n}")
        else:
            st.write("Semua personil sedang bertugas/izin.")
