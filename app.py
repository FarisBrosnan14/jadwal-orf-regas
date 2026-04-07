import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import calendar
import gspread
from google.oauth2.service_account import Credentials

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="ORF Nusantara Regas - Smart Scheduling", page_icon="⚓", layout="wide")

# --- KUSTOMISASI TAMPILAN (CSS) ---
st.markdown("""
    <style>
    /* Mengubah warna teks judul menjadi biru korporat */
    h1, h2, h3 {
        color: #00569d; 
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    /* Memperhalus tampilan kotak container */
    div[data-testid="stVerticalBlock"] div[style*="border"] {
        border-radius: 12px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        border: 1px solid #e0e0e0;
    }
    /* Mempercantik tombol */
    .stButton>button {
        border-radius: 8px;
        font-weight: bold;
    }
    /* Panel samping lebih bersih */
    [data-testid="stSidebar"] {
        background-color: #f4f6f9;
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
        st.sidebar.error(f"Koneksi API Gagal: {e}")
        return None

# ==========================================
# SIDEBAR (PANEL SAMPING)
# ==========================================
with st.sidebar:
    # URL Gambar FSRU Nusantara Regas (Bapak bisa mengganti URL ini dengan foto FSRU yang lebih spesifik jika punya)
    st.image("https://images.unsplash.com/photo-1583508108422-0a13d712ce19?q=80&w=800&auto=format&fit=crop", caption="FSRU Nusantara Regas", use_container_width=True)
    st.markdown("---")
    st.markdown("### ⚓ Info Sistem")
    st.info(
        "**Smart Scheduling ORF**\n\n"
        "Sistem digitalisasi terpadu untuk pemantauan jadwal shift dan perizinan personel "
        "di Fasilitas Onshore Receiving Facility (ORF) PT Nusantara Regas."
    )
    st.markdown("---")
    st.caption("© 2026 PT Nusantara Regas")

# ==========================================
# HEADER UTAMA
# ==========================================
col_logo, col_title = st.columns([1, 8])
with col_logo:
    # URL Logo Pertamina dari Wikimedia
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Pertamina_Logo.svg/512px-Pertamina_Logo.svg.png", width=80)
with col_title:
    st.title("Sistem Penjadwalan Terpadu ORF")
    st.caption("Dashboard Digitalisasi Shift & Perizinan Personel")

st.divider()

# ==========================================
# TABS NAVIGASI
# ==========================================
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
            pilih_tahun = st.selectbox("Tahun", range(2024, 2031), index=range(2024, 2031).index(st.session_state.selected_date.year))
        
        cal = calendar.monthcalendar(pilih_tahun, pilih_bulan)
        cols = st.columns(7)
        for i, h in enumerate(["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]):
            cols[i].markdown(f"<div style='text-align:center;font-weight:bold; color:#00569d;'>{h}</div>", unsafe_allow_html=True)
        
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
                df_bersih = df_matrix.dropna(subset=['Nama Operator']).copy()
                df_view = df_bersih[['Nama Operator', tgl_str]].copy()
                df_view.columns = ["Nama Operator", "Shift/Status"]
                
                df_view = df_view[~df_view["Shift/Status"].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])]
                
                if not df_view.empty:
                    df_view["Shift/Status"] = df_view["Shift/Status"].apply(lambda x: f"❌ {x}" if any(keyword in str(x).upper() for keyword in ["IZIN", "SAKIT", "CUTI"]) else f"✅ {x}")
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
        df_valid_names = df_matrix.dropna(subset=['Nama Operator'])
        kondisi_off = df_valid_names[tgl_cek_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])
        tersedia = df_valid_names[kondisi_off]["Nama Operator"].astype(str).tolist()
        
        if tersedia:
            st.success(f"Terdapat **{len(tersedia)} personel** yang OFF di tanggal {tgl_cek_str}:")
            
            df_tersedia = pd.DataFrame({"Nama Personel (Status: OFF)": tersedia})
            st.dataframe(df_tersedia, use_container_width=True, hide_index=True)
            
            st.info("💡 Silakan ingat/salin nama rekan di atas untuk diisi pada form pengajuan pengganti.")
            st.link_button("📝 Ajukan Izin di Google Form", LINK_GFORM, type="primary")
        else:
            st.error("Tidak ada rekan yang OFF di tanggal ini. Silakan koordinasi dengan Manager.")

# ==========================================
# TAB 3: MANAGER ADMIN
# ==========================================
with tab_manager:
    pin = st.text_input("🔑 Masukkan PIN Manager:", type="password")
    if pin == "regas123":
        st.success("Akses Manager Terbuka!")
        st.subheader("🔔 Antrean Persetujuan Izin")
        
        client = get_gspread_client()
        
        if not df_izin.empty and 'Status Approval' in df_izin.columns:
            df_izin_valid = df_izin.dropna(subset=['Nama Lengkap Operator'])
            pending = df_izin_valid[df_izin_valid['Status Approval'].isna() | (df_izin_valid['Status Approval'] == "")]
            
            if not pending.empty:
                for idx, row in pending.iterrows():
                    with st.container(border=True):
                        st.markdown(f"#### {row['Nama Lengkap Operator']}")
                        st.write(f"**Mengajukan:** {row.get('Jenis Izin yang Diajukan', 'Izin')} | **Shift:** {row.get('Shift Izin', 'PG')}")
                        st.write(f"**Tanggal:** 📅 {row['Tanggal Mulai Izin']} s/d {row['Tanggal Selesai Izin']}")
                        st.write(f"**Rekan Pengganti:** 🔄 {row.get('Nama Lengkap Operator Pengganti', 'Tidak Ada')}")
                        
                        col_btn1, col_btn2 = st.columns([1, 4])
                        with col_btn1:
                            if st.button("✅ Approve", key=f"app_{idx}"):
                                if client:
                                    try:
                                        # Update Izin
                                        sh_izin = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0)
                                        col_app_idx = df_izin.columns.get_loc('Status Approval') + 1
                                        sh_izin.update_cell(int(idx)+2, col_app_idx, "APPROVED")
                                        
                                        # Update Jadwal Aktual Matriks
                                        sh_aktual = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual")
                                        d_start = pd.to_datetime(row['Tanggal Mulai Izin'], dayfirst=True).date()
                                        d_end = pd.to_datetime(row['Tanggal Selesai Izin'], dayfirst=True).date()
                                        date_range = pd.date_range(d_start, d_end)
                                        
                                        for d in date_range:
                                            d_str = d.strftime('%Y-%m-%d')
                                            if d_str in df_matrix.columns:
                                                col_idx = list(df_matrix.columns).index(d_str) + 1
                                                
                                                # Pemohon
                                                nama_p = str(row['Nama Lengkap Operator']).strip().lower()
                                                match_p = df_matrix[df_matrix.iloc[:,0].astype(str).str.strip().str.lower() == nama_p]
                                                if not match_p.empty:
                                                    sh_aktual.update_cell(int(match_p.index[0])+2, col_idx, str(row['Jenis Izin yang Diajukan']).upper())
                                                
                                                # Pengganti
                                                nama_sub = str(row.get('Nama Lengkap Operator Pengganti', '')).strip().lower()
                                                if nama_sub and nama_sub not in ['nan', 'tidak ada', '']:
                                                    match_sub = df_matrix[df_matrix.iloc[:,0].astype(str).str.strip().str.lower() == nama_sub]
                                                    if not match_sub.empty:
                                                        sh_aktual.update_cell(int(match_sub.index[0])+2, col_idx, str(row.get('Shift Izin', 'PG')).title())
                                        
                                        load_data.clear()
                                        st.success(f"Jadwal diperbarui!")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Gagal: {e}")
                        
                        with col_btn2:
                            if st.button("❌ Reject", type="secondary", key=f"rej_{idx}"):
                                if client:
                                    try:
                                        sh_izin = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0)
                                        col_app_idx = df_izin.columns.get_loc('Status Approval') + 1
                                        sh_izin.update_cell(int(idx)+2, col_app_idx, "REJECTED")
                                        load_data.clear()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Gagal: {e}")
            else:
                st.info("✨ Antrean approval kosong.")
    elif pin != "":
        st.error("PIN salah.")
