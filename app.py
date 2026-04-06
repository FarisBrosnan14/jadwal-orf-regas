import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import calendar
import gspread
from google.oauth2.service_account import Credentials

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Dashboard ORF Nusantara Regas", page_icon="⚓", layout="wide")

if 'selected_date' not in st.session_state:
    st.session_state.selected_date = datetime.now().date()

# --- LINK DATA ---
URL_DATABASE = "https://docs.google.com/spreadsheets/d/1HuIrvhzm7xzXXbX5Foy2XPms7NLzFyttgH58Ez31pj0/edit?gid=172132710#gid=172132710" 
URL_IZIN = "https://docs.google.com/spreadsheets/d/1mdr7InOGhuVwLCpgPW-fDVOMw38XvELlXK9sxJymMYU/edit?gid=1951809577#gid=1951809577"
LINK_GFORM = "https://forms.gle/KB9CkfEsLB4yY9MK9"

# --- KONEKSI BACA (READ-ONLY) ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=10)
def load_data():
    try:
        df_j = conn.read(spreadsheet=URL_DATABASE, ttl="0")
        df_i = conn.read(spreadsheet=URL_IZIN, ttl="0")
        return df_j, df_i
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

df_jadwal, df_izin = load_data()

# --- FUNGSI TULIS (WRITE) API KEY ---
def get_gspread_client():
    try:
        kredensial = dict(st.secrets["gcp_service_account"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(kredensial, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        return None

# Identifikasi Kolom Jadwal
def find_col(df, keywords):
    for col in df.columns:
        if any(key.upper() in str(col).upper() for key in keywords):
            return col
    return None

col_nama = find_col(df_jadwal, ['Nama', 'Operator', 'Unnamed'])
col_tgl = find_col(df_jadwal, ['Tanggal', 'Shift'])
col_status = find_col(df_jadwal, ['Status', 'Kode'])

# ==========================================
# HEADER UTAMA
# ==========================================
st.title("⚓ Sistem Penjadwalan Terpadu ORF")
st.caption("PT Nusantara Regas - Smart Dashboard")

tab_kalender, tab_operator, tab_manager = st.tabs(["📅 Kalender Jadwal", "🧑‍🔧 Portal Operator", "👨‍💼 Manager Admin"])

# ==========================================
# TAB 1: KALENDER JADWAL
# ==========================================
with tab_kalender:
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
        st.subheader(f"📌 Shift: {tgl.strftime('%d %B %Y')}")
        
        if not df_jadwal.empty and col_nama and col_tgl:
            df_jadwal['Tgl_DT'] = pd.to_datetime(df_jadwal[col_tgl], errors='coerce').dt.date
            hari_ini = df_jadwal[df_jadwal['Tgl_DT'] == tgl].copy()
            
            if not df_izin.empty and 'Status Approval' in df_izin.columns:
                df_izin_bersih = df_izin.dropna(subset=['Nama Lengkap Operator'])
                izin_sah = df_izin_bersih[df_izin_bersih['Status Approval'].astype(str).str.upper() == 'APPROVED']
                
                if not izin_sah.empty:
                    # Normalisasi pembacaan tanggal (mengantisipasi format DD/MM/YYYY)
                    izin_sah['M_Izin'] = pd.to_datetime(izin_sah['Tanggal Mulai Izin'], dayfirst=True, errors='coerce').dt.date
                    izin_sah['S_Izin'] = pd.to_datetime(izin_sah['Tanggal Selesai Izin'], dayfirst=True, errors='coerce').dt.date
                    sedang_izin = izin_sah[(izin_sah['M_Izin'] <= tgl) & (izin_sah['S_Izin'] >= tgl)]
                    
                    for _, row in sedang_izin.iterrows():
                        # PERBAIKAN: Normalisasi Nama (Hapus titik, hapus spasi berlebih, huruf kecil semua)
                        nama_i = str(row['Nama Lengkap Operator']).replace(".", "").strip().lower()
                        pengganti = str(row.get('Nama Lengkap Operator Pengganti', row.get('Nama Operator Pengganti', 'Pengganti'))).strip().title()
                        jenis_izin = row.get('Jenis Izin yang Diajukan', 'Izin')
                        waktu_izin = row.get('Shift Izin', '')
                        
                        teks_shift = f" ({waktu_izin})" if waktu_izin else ""
                        
                        # Pencocokan nama pintar di kalender
                        match_idx = hari_ini[col_nama].astype(str).str.replace(".", "").str.strip().str.lower() == nama_i
                        if match_idx.any():
                            hari_ini.loc[match_idx, col_status] = f"❌ {jenis_izin}{teks_shift} (Ganti: {pengganti})"

            tampil = hari_ini[hari_ini[col_status].astype(str).str.upper().isin(['PG', 'MLM']) | hari_ini[col_status].astype(str).str.contains('❌')]
            
            if not tampil.empty:
                df_view = tampil[[col_nama, col_status]].copy()
                df_view.columns = ["Nama Operator", "Shift/Status"]
                st.dataframe(df_view, width='stretch', hide_index=True)
            else:
                st.info("Semua operator Off / Tidak ada jadwal.")
        else:
            st.warning("Data jadwal belum tersedia.")

# ==========================================
# TAB 2: PORTAL OPERATOR
# ==========================================
with tab_operator:
    st.subheader("🔍 Cari Rekan Pengganti")
    st.write("Silakan cek ketersediaan rekan yang **OFF** sebelum mengajukan izin.")
    
    tgl_izin = st.date_input("Rencana Tanggal Izin:", datetime.now().date(), key="tgl_izin_op")
    
    if not df_jadwal.empty and col_nama and col_tgl:
        df_j_cek = df_jadwal.copy()
        df_j_cek['Tgl_DT'] = pd.to_datetime(df_j_cek[col_tgl], errors='coerce').dt.date
        jadwal_tgl_itu = df_j_cek[df_j_cek['Tgl_DT'] == tgl_izin]
        
        staf_jaga = set(jadwal_tgl_itu[jadwal_tgl_itu[col_status].astype(str).str.upper().isin(['PG', 'MLM'])][col_nama].astype(str).str.strip())
        semua_staf = set(df_jadwal[col_nama].dropna().astype(str).unique()) - {"Belum ada data", "None"}
        
        tersedia = sorted(list(semua_staf - staf_jaga))
        
        if tersedia:
            st.success(f"✅ Ada **{len(tersedia)}** personel yang OFF pada tanggal tersebut:")
            st.write(", ".join(tersedia))
            st.info("Ingat nama salah satu rekan di atas dan masukkan ke dalam Form Izin.")
            st.link_button("📝 Isi Google Form Izin Sekarang", LINK_GFORM, type="primary")
        else:
            st.error("Semua personel sedang bertugas di tanggal tersebut. Silakan koordinasi dengan Manager.")

# ==========================================
# TAB 3: MANAGER ADMIN
# ==========================================
with tab_manager:
    pin = st.text_input("Masukkan PIN Manager:", type="password", key="pin_mgr")
    if pin == "regas123":
        st.success("Akses Manager Terbuka!")
        st.divider()
        
        st.subheader("🔔 Menunggu Persetujuan (Pending Approval)")
        
        client = get_gspread_client()
        if client is None:
            st.warning("⚠️ Mode API Key belum diaktifkan di Streamlit Secrets. Tombol Approve belum bisa digunakan.")
        
        if not df_izin.empty and 'Status Approval' in df_izin.columns:
            df_izin_valid = df_izin.dropna(subset=['Nama Lengkap Operator'])
            pending_df = df_izin_valid[df_izin_valid['Status Approval'].isna() | (df_izin_valid['Status Approval'] == "")]
            
            if not pending_df.empty:
                for idx, row in pending_df.iterrows():
                    nama_pemohon = row['Nama Lengkap Operator']
                    nama_pengganti = row.get('Nama Lengkap Operator Pengganti', row.get('Nama Operator Pengganti', 'Tidak Ada'))
                    
                    alasan = row.get('Alasan Izin', '-')
                    shift_izin = row.get('Shift Izin', 'Tidak disebutkan')
                    
                    with st.container(border=True):
                        st.markdown(f"**{nama_pemohon}** mengajukan **{row.get('Jenis Izin yang Diajukan', 'Izin')}**")
                        st.write(f"📅 Tanggal: {row.get('Tanggal Mulai Izin', '-')} s/d {row.get('Tanggal Selesai Izin', '-')}")
                        st.write(f"⏰ Shift Izin: **{shift_izin}**")
                        st.write(f"🔄 Pengganti: **{nama_pengganti}**")
                        st.write(f"📝 Alasan: {alasan}")
                        
                        col_btn1, col_btn2 = st.columns([1, 4])
                        with col_btn1:
                            if st.button("✅ Approve", key=f"app_{idx}"):
                                if client:
                                    try:
                                        sheet_izin = client.open_by_key("1mdr7InOGhuVwLCpgPW-fDVOMw38XvELlXK9sxJymMYU").sheet1
                                        col_status_idx = df_izin.columns.get_loc('Status Approval') + 1
                                        baris_gsheets = int(idx) + 2 
                                        
                                        sheet_izin.update_cell(baris_gsheets, col_status_idx, "APPROVED")
                                        
                                        load_data.clear() 
                                        st.success("Berhasil di-Approve!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Gagal menulis ke Sheets: {e}")
                                else:
                                    st.error("API Key belum disetting.")
                        
                        with col_btn2:
                            if st.button("❌ Reject", key=f"rej_{idx}"):
                                if client:
                                    try:
                                        sheet_izin = client.open_by_key("1mdr7InOGhuVwLCpgPW-fDVOMw38XvELlXK9sxJymMYU").sheet1
                                        col_status_idx = df_izin.columns.get_loc('Status Approval') + 1
                                        baris_gsheets = int(idx) + 2 
                                        
                                        sheet_izin.update_cell(baris_gsheets, col_status_idx, "REJECTED")
                                        
                                        load_data.clear()
                                        st.success("Izin Ditolak.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Gagal menulis ke Sheets: {e}")
            else:
                st.info("✨ Semua pengajuan izin sudah diproses. Tidak ada antrean.")
        else:
            st.info("Belum ada data form izin atau kolom 'Status Approval' belum terbaca.")
            
    elif pin != "":
        st.error("PIN Salah!")
