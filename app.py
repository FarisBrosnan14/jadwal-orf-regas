import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import calendar
import gspread
from google.oauth2.service_account import Credentials

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ORF Nusantara Regas - Smart Scheduling", page_icon="⚓", layout="wide")

if 'selected_date' not in st.session_state:
    st.session_state.selected_date = datetime.now().date()

# --- LINK DATA & ID (PASTIKAN ID SESUAI) ---
ID_SHEET_JADWAL = "1HuIrvhzm7xzXXbX5Foy2XPms7NLzFyttgH58Ez31pj0"
ID_SHEET_IZIN = "1mdr7InOGhuVwLCpgPW-fDVOMw38XvELlXK9sxJymMYU"

# URL untuk pembacaan data
URL_JADWAL_AKTUAL = f"https://docs.google.com/spreadsheets/d/{ID_SHEET_JADWAL}/edit#gid=0"
URL_IZIN = f"https://docs.google.com/spreadsheets/d/{ID_SHEET_IZIN}/edit"
LINK_GFORM = "https://forms.gle/KB9CkfEsLB4yY9MK9"

# --- KONEKSI BACA (GSHEETS CONNECTION) ---
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

# --- FUNGSI TULIS (GSPREAD) ---
def get_gspread_client():
    try:
        kredensial = dict(st.secrets["gcp_service_account"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(kredensial, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Koneksi API Gagal: {e}")
        return None

# ==========================================
# HEADER UTAMA
# ==========================================
st.title("⚓ Sistem Penjadwalan Terpadu ORF")
st.caption("Dashboard Digitalisasi PT Nusantara Regas")

tab_kalender, tab_operator, tab_manager = st.tabs(["📅 Kalender Jadwal", "🧑‍🔧 Portal Operator", "👨‍💼 Manager Admin"])

# ==========================================
# TAB 1: KALENDER JADWAL (MENGUBAH MATRIKS JADI LIST)
# ==========================================
with tab_kalender:
    col_kiri, col_kanan = st.columns([1.5, 2])

    with col_kiri:
        c1, c2 = st.columns(2)
        with c1:
            nama_bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
            pilih_bulan = st.selectbox("Bulan", range(1, 13), format_func=lambda x: nama_bulan[x-1], index=st.session_state.selected_date.month - 1)
        with c2:
            pilih_tahun = st.selectbox("Tahun", range(2024, 2031), index=range(2024, 2031).index(st.session_state.selected_date.year))
        
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
        tgl_str = st.session_state.selected_date.strftime('%Y-%m-%d')
        st.subheader(f"📌 Status Shift: {st.session_state.selected_date.strftime('%d %B %Y')}")
        
        if not df_matrix.empty:
            if tgl_str in df_matrix.columns:
                # PERBAIKAN: Bersihkan baris kosong (NaN) di bawah tabel
                df_bersih = df_matrix.dropna(subset=['Nama Operator']).copy()
                
                df_view = df_bersih[['Nama Operator', tgl_str]].copy()
                df_view.columns = ["Nama Operator", "Shift/Status"]
                
                # PERBAIKAN: Jangan tampilkan yang sedang "Off" agar kalender fokus ke yang masuk/izin saja
                df_view = df_view[~df_view["Shift/Status"].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])]
                
                if not df_view.empty:
                    # Tambahkan icon silang merah untuk izin
                    df_view["Shift/Status"] = df_view["Shift/Status"].apply(lambda x: f"❌ {x}" if any(keyword in str(x).upper() for keyword in ["IZIN", "SAKIT", "CUTI"]) else x)
                    st.dataframe(df_view, width=600, hide_index=True)
                else:
                    st.info("Semua personel OFF pada tanggal ini.")
            else:
                st.info(f"Data jadwal untuk tanggal {tgl_str} belum diinput di Google Sheets.")
        else:
            st.warning("Data Jadwal Aktual tidak terbaca.")

# ==========================================
# TAB 2: PORTAL OPERATOR
# ==========================================
with tab_operator:
    st.subheader("🔍 Cek Rekan Tersedia (OFF)")
    tgl_cek = st.date_input("Pilih Tanggal Rencana Izin:", datetime.now().date())
    tgl_cek_str = tgl_cek.strftime('%Y-%m-%d')

    if not df_matrix.empty and tgl_cek_str in df_matrix.columns:
        # PERBAIKAN ERROR TYPE: Bersihkan nama kosong (NaN) agar .join() tidak error
        df_valid_names = df_matrix.dropna(subset=['Nama Operator'])
        
        # PERBAIKAN LOGIKA: Cari yang selnya berisi "Off", kosong, atau "NaN"
        kondisi_off = df_valid_names[tgl_cek_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])
        
        # Jadikan list string murni
        tersedia = df_valid_names[kondisi_off]["Nama Operator"].astype(str).tolist()
        
        if tersedia:
            st.success(f"Personel yang OFF di tanggal {tgl_cek_str}:")
            st.write(", ".join(tersedia))
            st.link_button("📝 Ajukan Izin di Google Form", LINK_GFORM, type="primary")
        else:
            st.error("Tidak ada rekan yang OFF di tanggal ini. Silakan hubungi Pak Dhana.")

# ==========================================
# TAB 3: MANAGER ADMIN (MATRIX COORDINATE UPDATE)
# ==========================================
with tab_manager:
    pin = st.text_input("PIN Manager:", type="password")
    if pin == "regas123":
        st.subheader("🔔 Menunggu Approval")
        
        client = get_gspread_client()
        
        if not df_izin.empty and 'Status Approval' in df_izin.columns:
            df_izin_valid = df_izin.dropna(subset=['Nama Lengkap Operator'])
            pending = df_izin_valid[df_izin_valid['Status Approval'].isna() | (df_izin_valid['Status Approval'] == "")]
            
            if not pending.empty:
                for idx, row in pending.iterrows():
                    with st.container(border=True):
                        st.write(f"**{row['Nama Lengkap Operator']}** minta **{row.get('Jenis Izin yang Diajukan', 'Izin')}**")
                        st.write(f"📅 {row['Tanggal Mulai Izin']} s/d {row['Tanggal Selesai Izin']} | Shift: {row.get('Shift Izin', 'PG')}")
                        st.write(f"🔄 Pengganti: {row.get('Nama Lengkap Operator Pengganti', 'Tidak Ada')}")
                        
                        if st.button("✅ Approve & Update Matriks", key=f"app_{idx}"):
                            if client:
                                try:
                                    # 1. Update Status Approval di Sheet Izin
                                    sh_izin = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0)
                                    col_app_idx = df_izin.columns.get_loc('Status Approval') + 1
                                    sh_izin.update_cell(int(idx)+2, col_app_idx, "APPROVED")
                                    
                                    # 2. Update Koordinat di Sheet Jadwal_Aktual
                                    sh_aktual = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual")
                                    
                                    # Parsing Tanggal
                                    d_start = pd.to_datetime(row['Tanggal Mulai Izin'], dayfirst=True).date()
                                    d_end = pd.to_datetime(row['Tanggal Selesai Izin'], dayfirst=True).date()
                                    date_range = pd.date_range(d_start, d_end)
                                    
                                    for d in date_range:
                                        d_str = d.strftime('%Y-%m-%d')
                                        if d_str in df_matrix.columns:
                                            col_idx = list(df_matrix.columns).index(d_str) + 1
                                            
                                            # A. Update Pemohon (Ganti jadi IZIN/CUTI)
                                            nama_p = str(row['Nama Lengkap Operator']).strip().lower()
                                            match_p = df_matrix[df_matrix.iloc[:,0].astype(str).str.strip().str.lower() == nama_p]
                                            if not match_p.empty:
                                                row_p_idx = int(match_p.index[0]) + 2
                                                sh_aktual.update_cell(row_p_idx, col_idx, str(row['Jenis Izin yang Diajukan']).upper())
                                            
                                            # B. Update Pengganti (Ganti jadi PG/MLM)
                                            nama_sub = str(row.get('Nama Lengkap Operator Pengganti', '')).strip().lower()
                                            if nama_sub and nama_sub not in ['nan', 'tidak ada', '']:
                                                match_sub = df_matrix[df_matrix.iloc[:,0].astype(str).str.strip().str.lower() == nama_sub]
                                                if not match_sub.empty:
                                                    row_sub_idx = int(match_sub.index[0]) + 2
                                                    sh_aktual.update_cell(row_sub_idx, col_idx, str(row.get('Shift Izin', 'PG')).title())
                                    
                                    load_data.clear()
                                    st.success(f"Sukses! Jadwal Aktual di Google Sheets telah direvisi otomatis.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Gagal update: {e}")
            else:
                st.info("Tidak ada antrean approval.")
    elif pin != "":
        st.error("PIN salah.")
