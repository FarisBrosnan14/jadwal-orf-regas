import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import calendar

st.set_page_config(page_title="Dashboard ORF", page_icon="⚓", layout="wide")

if 'selected_date' not in st.session_state:
    st.session_state.selected_date = datetime.now().date()

# --- KONEKSI ---
URL_JADWAL = "https://docs.google.com/spreadsheets/d/1HuIrvhzm7xzXXbX5Foy2XPms7NLzFyttgH58Ez31pj0/edit?gid=0#gid=0"
URL_IZIN = "https://docs.google.com/spreadsheets/d/1mdr7InOGhuVwLCpgPW-fDVOMw38XvELlXK9sxJymMYU/edit?usp=sharing"

conn = st.connection("gsheets", type=GSheetsConnection)

st.title("📅 Dashboard Jadwal Jaga ORF")

# ==========================================
# MODE DETEKTIF: MENCARI SUMBER ERROR
# ==========================================
df_jadwal = pd.DataFrame()
df_izin = pd.DataFrame()

try:
    df_jadwal = conn.read(spreadsheet=URL_JADWAL, worksheet="Database", ttl="0") 
except Exception as e:
    st.error(f"❌ ERROR DI LINK JADWAL UTAMA: {e}")
    st.info("Pastikan: 1. Link diset 'Anyone with the link'. 2. Nama tab persis 'Database' (tanpa spasi di belakangnya).")
    st.stop()

try:
    # Membaca sheet pertama dari GForm (biasanya bernama 'Form Responses 1' atau 'Form Responses')
    df_izin = conn.read(spreadsheet=URL_IZIN, ttl="0")
except Exception as e:
    st.error(f"❌ ERROR DI LINK GOOGLE FORM IZIN: {e}")
    st.info("Pastikan link GForm ini juga sudah diset 'Anyone with the link can view'.")
    st.stop()

# Jika lolos pengecekan di atas, berarti koneksi aman!
st.success("✅ Koneksi ke kedua Database Berhasil!")

# Identifikasi kolom
def find_col(df, keywords):
    for col in df.columns:
        if any(key.upper() in str(col).upper() for key in keywords):
            return col
    return None

col_nama = find_col(df_jadwal, ['Nama', 'Operator', 'Unnamed'])
col_tgl = find_col(df_jadwal, ['Tanggal', 'Shift'])
col_status = find_col(df_jadwal, ['Status', 'Kode'])

st.divider()

# --- BAGIAN KALENDER ---
col_kiri, col_kanan = st.columns([1.5, 2])

with col_kiri:
    c1, c2 = st.columns(2)
    with c1:
        nama_bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        pilih_bulan = st.selectbox("Bulan", range(1, 13), format_func=lambda x: nama_bulan[x-1], index=st.session_state.selected_date.month - 1)
    with c2:
        pilih_tahun = st.selectbox("Tahun", range(2024, 2030), index=range(2024, 2030).index(st.session_state.selected_date.year))
    
    st.markdown("###")
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

# --- BAGIAN INFO JADWAL ---
with col_kanan:
    tgl_terpilih = st.session_state.selected_date
    st.subheader(f"📌 Jadwal: {tgl_terpilih.strftime('%d %B %Y')}")
    
    if not col_nama:
        st.warning("Menunggu data jadwal diisi oleh Manager...")
    else:
        df_jadwal['Tgl_Bantu'] = pd.to_datetime(df_jadwal[col_tgl], errors='coerce').dt.date
        data_hari_ini = df_jadwal[df_jadwal['Tgl_Bantu'] == tgl_terpilih].copy()
        
        # Cek Izin
        if not df_izin.empty and 'Tanggal Mulai Izin' in df_izin.columns:
            df_izin['Mulai'] = pd.to_datetime(df_izin['Tanggal Mulai Izin'], errors='coerce').dt.date
            df_izin['Selesai'] = pd.to_datetime(df_izin['Tanggal Selesai Izin'], errors='coerce').dt.date
            sedang_izin = df_izin[(df_izin['Mulai'] <= tgl_terpilih) & (df_izin['Selesai'] >= tgl_terpilih)]
            
            for _, row in sedang_izin.iterrows():
                n_izin = str(row['Nama Lengkap Operator']).strip().lower()
                j_izin = row['Jenis Izin yang Diajukan']
                data_hari_ini.loc[data_hari_ini[col_nama].str.strip().str.lower() == n_izin, col_status] = f"❌ {j_izin}"

        operator_aktif = data_hari_ini[data_hari_ini[col_status].str.upper().isin(['PG', 'MLM']) | data_hari_ini[col_status].astype(str).str.contains('❌')]
        
        if not operator_aktif.empty:
            tabel_tampil = operator_aktif[[col_nama, col_status]].copy()
            tabel_tampil.rename(columns={col_nama: "Nama Operator", col_status: "Shift / Status"}, inplace=True)
            st.dataframe(tabel_tampil, width='stretch', hide_index=True)
        else:
            st.warning("⚠️ Jadwal kosong / Semua operator Off.")