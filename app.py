import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import calendar

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Dashboard ORF - Nusantara Regas", page_icon="⚓", layout="wide")

if 'selected_date' not in st.session_state:
    st.session_state.selected_date = datetime.now().date()

# --- LINK BARU YANG BAPAK BERIKAN ---
URL_JADWAL = "https://docs.google.com/spreadsheets/d/1HuIrvhzm7xzXXbX5Foy2XPms7NLzFyttgH58Ez31pj0/edit?usp=sharing"
URL_IZIN = "https://docs.google.com/spreadsheets/d/1mdr7InOGhuVwLCpgPW-fDVOMw38XvELlXK9sxJymMYU/edit?usp=sharing"

conn = st.connection("gsheets", type=GSheetsConnection)

# ==========================================
# SIDEBAR: AKSES & LINK
# ==========================================
st.sidebar.title("🔐 Akses Sistem")
mode_akses = st.sidebar.radio("Masuk Sebagai:", ["🧑‍🔧 Operator (View Only)", "👨‍💼 Manager (Edit)"])

is_manager = False
if mode_akses == "👨‍💼 Manager (Edit)":
    pin = st.sidebar.text_input("Masukkan PIN Manager:", type="password")
    if pin == "regas123": # Bapak bisa ganti PIN ini sesuka hati
        is_manager = True
        st.sidebar.success("Akses Manager Dibuka!")
        st.sidebar.markdown("### ⚙️ Manajemen Jadwal")
        st.sidebar.link_button("Buka Spreadsheet Master", URL_JADWAL, type="secondary")
    elif pin != "":
        st.sidebar.error("PIN Salah!")

st.sidebar.divider()
st.sidebar.markdown("### 📝 Link Pengajuan")
# Silakan isi link Google Form Bapak di bawah ini
LINK_GFORM_ISI = "https://forms.gle/..." 
st.sidebar.link_button("Buka Google Form Izin/Cuti", LINK_GFORM_ISI, type="primary")

# ==========================================
# TAMPILAN UTAMA
# ==========================================
st.title("📅 Dashboard Jadwal Jaga ORF")

# --- PROSES AMBIL DATA (MODE DETEKTIF) ---
df_jadwal = pd.DataFrame()
df_izin = pd.DataFrame()

try:
    # Membaca tab 'Database' hasil rumus otomatis Bapak
    df_jadwal = conn.read(spreadsheet=URL_JADWAL, worksheet="Database", ttl="0") 
except Exception as e:
    st.error(f"❌ KENDALA JADWAL UTAMA: {e}")
    st.info("Pastikan nama tab di Google Sheets adalah 'Database' dan akses sudah 'Anyone with the link'.")
    st.stop()

try:
    df_izin = conn.read(spreadsheet=URL_IZIN, ttl="0")
except Exception as e:
    st.warning(f"⚠️ KENDALA DATA IZIN: {e}. Menampilkan jadwal saja tanpa data izin.")

# Identifikasi Kolom Otomatis
def find_col(df, keywords):
    for col in df.columns:
        if any(key.upper() in str(col).upper() for key in keywords):
            return col
    return None

col_nama = find_col(df_jadwal, ['Nama', 'Operator', 'Unnamed'])
col_tgl = find_col(df_jadwal, ['Tanggal', 'Shift'])
col_status = find_col(df_jadwal, ['Status', 'Kode'])

# --- TAMPILAN KALENDER & INFO ---
col_kiri, col_kanan = st.columns([1.5, 2])

with col_kiri:
    c1, c2 = st.columns(2)
    with c1:
        nama_bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        pilih_bulan = st.selectbox("Bulan", range(1, 13), format_func=lambda x: nama_bulan[x-1], index=st.session_state.selected_date.month - 1)
    with c2:
        pilih_tahun = st.selectbox("Tahun", range(2024, 2030), index=range(2024, 2030).index(st.session_state.selected_date.year))
    
    cal = calendar.monthcalendar(pilih_tahun, pilih_bulan)
    kolom_hari = st.columns(7)
    for i, h in enumerate(["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]):
        kolom_hari[i].markdown(f"<div style='text-align: center; font-weight: bold;'>{h}</div>", unsafe_allow_html=True)
    
    for minggu in cal:
        kolom_tanggal = st.columns(7)
        for i, tanggal in enumerate(minggu):
            if tanggal == 0:
                kolom_tanggal[i].write("")
            else:
                is_selected = (tanggal == st.session_state.selected_date.day and pilih_bulan == st.session_state.selected_date.month and pilih_tahun == st.session_state.selected_date.year)
                if kolom_tanggal[i].button(str(tanggal), key=f"btn_{pilih_tahun}_{pilih_bulan}_{tanggal}", type="primary" if is_selected else "secondary", use_container_width=True):
                    st.session_state.selected_date = datetime(pilih_tahun, pilih_bulan, tanggal).date()
                    st.rerun()

with col_kanan:
    tgl_terpilih = st.session_state.selected_date
    st.subheader(f"📌 Detail Jadwal: {tgl_terpilih.strftime('%d %B %Y')}")
    
    if col_nama and col_tgl:
        df_jadwal['Tgl_Bantu'] = pd.to_datetime(df_jadwal[col_tgl], errors='coerce').dt.date
        data_hari_ini = df_jadwal[df_jadwal['Tgl_Bantu'] == tgl_terpilih].copy()
        
        # Integrasi Data Izin dari Google Form
        sedang_izin = pd.DataFrame()
        if not df_izin.empty and 'Tanggal Mulai Izin' in df_izin.columns:
            df_izin['Mulai'] = pd.to_datetime(df_izin['Tanggal Mulai Izin'], errors='coerce').dt.date
            df_izin['Selesai'] = pd.to_datetime(df_izin['Tanggal Selesai Izin'], errors='coerce').dt.date
            sedang_izin = df_izin[(df_izin['Mulai'] <= tgl_terpilih) & (df_izin['Selesai'] >= tgl_terpilih)]
            
            for _, row in sedang_izin.iterrows():
                n_izin = str(row['Nama Lengkap Operator']).strip().lower()
                j_izin = row['Jenis Izin yang Diajukan']
                data_hari_ini.loc[data_hari_ini[col_nama].str.strip().str.lower() == n_izin, col_status] = f"❌ {j_izin}"

        # Filter hanya yang bertugas atau yang sedang izin
        operator_aktif = data_hari_ini[data_hari_ini[col_status].astype(str).str.upper().isin(['PG', 'MLM']) | data_hari_ini[col_status].astype(str).str.contains('❌')]
        
        if not operator_aktif.empty:
            tabel_tampil = operator_aktif[[col_nama, col_status]].copy()
            tabel_tampil.rename(columns={col_nama: "Nama Operator", col_status: "Shift / Status"}, inplace=True)
            
            def detail_shift(shift):
                s = str(shift).upper()
                if s == 'PG': return 'Pg (07.00 - 19.00)'
                if s == 'MLM': return 'Mlm (19.00 - 07.00)'
                return shift
            
            tabel_tampil['Shift / Status'] = tabel_tampil['Shift / Status'].apply(detail_shift)
            st.dataframe(tabel_tampil, width='stretch', hide_index=True)
        else:
            st.warning("⚠️ Tidak ada jadwal tugas / Semua operator Off.")

        # FITUR KHUSUS MANAGER: CEK PERSONEL TERSEDIA
        if is_manager:
            st.divider()
            st.markdown("### 🔍 Personel Tersedia (Standby/Off)")
            semua_staf = set(df_jadwal[col_nama].dropna().unique())
            semua_staf = {str(x).strip() for x in semua_staf if x != "Belum ada data"}
            staf_sibuk_jaga = set(data_hari_ini[data_hari_ini[col_status].astype(str).str.upper().isin(['PG', 'MLM'])][col_nama].str.strip())
            staf_izin = set()
            if not sedang_izin.empty:
                staf_izin = set(sedang_izin['Nama Lengkap Operator'].str.strip())
            
            staf_available = sorted(list(semua_staf - staf_sibuk_jaga - staf_izin))
            
            if staf_available:
                for nama in staf_available:
                    st.markdown(f"- ✅ **{nama}**")
            else:
                st.caption("Semua personel sedang bertugas atau izin.")
    else:
        st.info("Menunggu data dari Google Sheets...")
