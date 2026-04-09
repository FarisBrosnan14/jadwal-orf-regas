import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import base64
import os

# ==========================================
# 1. CONFIGURATION & CONSTANTS
# ==========================================
APP_TITLE = "NR ORF Integrated Command"
PAGE_ICON = "⚓"
PIN_MANAGER = "regas123"

# Google Sheets IDs
SHEET_ID_SCHEDULE = "1HuIrvhzm7xzXXbX5Foy2XPms7NLzFyttgH58Ez31pj0"
SHEET_ID_LEAVE = "1mdr7InOGhuVwLCpgPW-fDVOMw38XvELlXK9sxJymMYU"

# URLs
URL_SCHEDULE = f"https://docs.google.com/spreadsheets/d/{SHEET_ID_SCHEDULE}/edit#gid=0"
URL_LEAVE = f"https://docs.google.com/spreadsheets/d/{SHEET_ID_LEAVE}/edit"
URL_GFORM = "https://forms.gle/KB9CkfEsLB4yY9MK9"

# Approver List
APPROVERS = ["-- Pilih Nama Anda --", "Yosep Zulkarnain", "Ade Imat", "Benny Sulistio", "Ibrahim"]


# ==========================================
# 2. UTILITY FUNCTIONS
# ==========================================
def get_base64_image(file_name: str) -> str:
    """Membaca file gambar lokal dan mengonversinya ke format base64."""
    try:
        with open(file_name, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None

def get_matching_column(df: pd.DataFrame, keywords: list, default: str) -> str:
    """Mencari nama kolom di DataFrame berdasarkan kemiripan kata kunci (Fuzzy Match)."""
    if df.empty: return default
    for col in df.columns:
        if any(kw in str(col).lower() for kw in keywords):
            return col
    return default


# ==========================================
# 3. DATA ACCESS LAYER (SERVICES)
# ==========================================
def init_gspread_client():
    """Inisialisasi koneksi ke Google API via Service Account."""
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception:
        return None

@st.cache_data(ttl=2) 
def load_all_data():
    """Menarik dan membersihkan seluruh data dari Google Sheets."""
    client = init_gspread_client()
    schedule_df, leave_df, operator_df = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    if not client:
        return schedule_df, leave_df, operator_df

    try:
        # Load Schedule
        raw_schedule = client.open_by_key(SHEET_ID_SCHEDULE).worksheet("Jadwal_Aktual").get_all_values()
        if len(raw_schedule) > 1:
            schedule_df = pd.DataFrame(raw_schedule[1:], columns=raw_schedule[0])
            if 'Nama Operator' in schedule_df.columns:
                schedule_df = schedule_df[schedule_df['Nama Operator'].astype(str).str.strip() != '']

        # Load Leaves (Izin)
        raw_leave = client.open_by_key(SHEET_ID_LEAVE).get_worksheet(0).get_all_values()
        if len(raw_leave) > 1:
            leave_df = pd.DataFrame(raw_leave[1:], columns=raw_leave[0])
            if 'Nama Lengkap Operator' in leave_df.columns:
                leave_df = leave_df[leave_df['Nama Lengkap Operator'].astype(str).str.strip() != '']
                leave_df = leave_df[~leave_df['Nama Lengkap Operator'].astype(str).str.lower().isin(['nan', 'none', 'null'])]

        # Load Operator Data (Pemindai Baris Otomatis Lintas Sheet)
        try:
            sheet_target = None
            spreadsheet_jadwal = client.open_by_key(SHEET_ID_SCHEDULE)
            for ws in spreadsheet_jadwal.worksheets():
                if 'data' in ws.title.lower() and 'operator' in ws.title.lower():
                    sheet_target = ws
                    break
            
            if not sheet_target:
                spreadsheet_izin = client.open_by_key(SHEET_ID_LEAVE)
                for ws in spreadsheet_izin.worksheets():
                    if 'data' in ws.title.lower() and 'operator' in ws.title.lower():
                        sheet_target = ws
                        break

            if sheet_target:
                raw_operator = sheet_target.get_all_values()
                if len(raw_operator) > 0:
                    temp_df = pd.DataFrame(raw_operator)
                    header_idx = -1
                    for i, row in temp_df.iterrows():
                        if any('nama' in str(v).lower() and 'operator' in str(v).lower() for v in row.values):
                            header_idx = i
                            break
                    if header_idx != -1:
                        headers = temp_df.iloc[header_idx].astype(str).str.strip().tolist()
                        operator_df = pd.DataFrame(temp_df.values[header_idx+1:], columns=headers)
        except Exception:
            pass # Abaikan jika sheet Data_Operator belum dibuat

    except Exception as e:
        st.error(f"Gagal memuat data dari database: {e}")
        
    return schedule_df, leave_df, operator_df


# ==========================================
# 4. BUSINESS LOGIC (CONTROLLERS)
# ==========================================
def process_leave_approval(action: str, row_index: int, row_data: pd.Series, schedule_df: pd.DataFrame, approver_name: str):
    """Menangani logika Approve/Reject Izin dan mengupdate Spreadsheet."""
    client = init_gspread_client()
    if not client: return

    sheet_leave = client.open_by_key(SHEET_ID_LEAVE).get_worksheet(0)
    col_status_idx = row_data.index.get_loc('Status Approval') + 1
    
    # Update Status
    status_text = f"{action.upper()} by {approver_name}"
    sheet_leave.update_cell(int(row_index) + 2, col_status_idx, status_text)
    
    # Update Jadwal Aktual jika APPROVED
    if action.upper() == "APPROVED":
        sheet_schedule = client.open_by_key(SHEET_ID_SCHEDULE).worksheet("Jadwal_Aktual")
        d_start = pd.to_datetime(row_data['Tanggal Mulai Izin'], dayfirst=True).date()
        d_end = pd.to_datetime(row_data['Tanggal Selesai Izin'], dayfirst=True).date()
        
        for d in pd.date_range(d_start, d_end):
            d_str = d.strftime('%Y-%m-%d')
            if d_str in schedule_df.columns:
                col_date_idx = list(schedule_df.columns).index(d_str) + 1
                
                # Update pemohon izin
                applicant_name = str(row_data['Nama Lengkap Operator']).strip().lower()
                match_p = schedule_df[schedule_df.iloc[:,0].astype(str).str.strip().str.lower() == applicant_name]
                if not match_p.empty: 
                    sheet_schedule.update_cell(int(match_p.index[0])+2, col_date_idx, str(row_data['Jenis Izin yang Diajukan']).upper())
                
                # Update pengganti
                sub_name = str(row_data.get('Nama Lengkap Operator Pengganti', '')).strip().lower()
                if sub_name and sub_name not in ['nan', 'tidak ada', '']:
                    match_sub = schedule_df[schedule_df.iloc[:,0].astype(str).str.strip().str.lower() == sub_name]
                    if not match_sub.empty: 
                        sheet_schedule.update_cell(int(match_sub.index[0])+2, col_date_idx, str(row_data.get('Shift Izin', 'PG')).title())
    
    load_all_data.clear()
    st.rerun()

def undo_leave_approval(row_index: int, row_data: pd.Series, schedule_df: pd.DataFrame, status_lama: str):
    """Membatalkan keputusan persetujuan dan mengembalikan jadwal ke semula."""
    client = init_gspread_client()
    if not client: return
    
    sheet_leave = client.open_by_key(SHEET_ID_LEAVE).get_worksheet(0)
    col_status_idx = row_data.index.get_loc('Status Approval') + 1
    
    # Kosongkan status
    sheet_leave.update_cell(int(row_index) + 2, col_status_idx, "")
    
    # Revert jadwal jika sebelumnya APPROVED
    if "APPROVED" in status_lama:
        sheet_schedule = client.open_by_key(SHEET_ID_SCHEDULE).worksheet("Jadwal_Aktual")
        d_start = pd.to_datetime(row_data['Tanggal Mulai Izin'], dayfirst=True).date()
        d_end = pd.to_datetime(row_data['Tanggal Selesai Izin'], dayfirst=True).date()
        
        for d in pd.date_range(d_start, d_end):
            d_str = d.strftime('%Y-%m-%d')
            if d_str in schedule_df.columns:
                col_date_idx = list(schedule_df.columns).index(d_str) + 1
                
                # Kembalikan shift pemohon
                applicant_name = str(row_data['Nama Lengkap Operator']).strip().lower()
                match_p = schedule_df[schedule_df.iloc[:,0].astype(str).str.strip().str.lower() == applicant_name]
                if not match_p.empty: 
                    sheet_schedule.update_cell(int(match_p.index[0])+2, col_date_idx, str(row_data.get('Shift Izin', 'PG')).title())
                
                # Kembalikan status OFF untuk pengganti
                sub_name = str(row_data.get('Nama Lengkap Operator Pengganti', '')).strip().lower()
                if sub_name and sub_name not in ['nan', 'tidak ada', '']:
                    match_sub = schedule_df[schedule_df.iloc[:,0].astype(str).str.strip().str.lower() == sub_name]
                    if not match_sub.empty: 
                        sheet_schedule.update_cell(int(match_sub.index[0])+2, col_date_idx, 'OFF')

    load_all_data.clear()
    st.rerun()


# ==========================================
# 5. UI COMPONENTS & CSS STYLING
# ==========================================
def inject_custom_css(bg_base64: str):
    """Menyuntikkan pengaturan tampilan CSS yang Responsif untuk Laptop & Mobile."""
    bg_color = "rgba(15, 23, 42, 0.85)"
    bg_css = f"background-image: linear-gradient({bg_color}, {bg_color}), url('data:image/jpeg;base64,{bg_base64}');" if bg_base64 else f"background-image: linear-gradient({bg_color}, {bg_color}), url('https://images.unsplash.com/photo-1583508108422-0a13d712ce19?q=80&w=1920&auto=format&fit=crop');"

    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"], .stApp {{ font-family: 'Plus Jakarta Sans', sans-serif !important; color: #f8fafc; }}
    
    /* GLOBAL BACKGROUND */
    .stApp {{ {bg_css} background-size: cover; background-position: center; background-attachment: fixed; }}
    
    /* RESPONSIVE LAYOUT CONTAINER: Mencegah melebar ekstrem di Monitor Laptop/Ultrawide */
    .block-container {{
        max-width: 1200px !important; 
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        margin: 0 auto;
    }}
    
    header[data-testid="stHeader"] {{ background-color: rgba(0, 0, 0, 0.0) !important; display: none; }}
    h2, h3, h4, h5 {{ color: #ffffff !important; text-shadow: 0px 2px 4px rgba(0,0,0,0.8); }}
    
    /* ====================================
       TOP BAR (HEADER PUTIH)
       ==================================== */
    .header-bar {{ 
        background-color: #ffffff; 
        border-radius: 16px; 
        padding: 15px 30px; 
        display: flex; 
        align-items: center; 
        justify-content: space-between; 
        margin-bottom: 30px; 
        box-shadow: 0 8px 25px rgba(0,0,0,0.3); 
    }}
    .header-logo {{ max-height: 55px; display: block; transition: all 0.3s; }}
    .header-title {{ 
        color: #004D95 !important; 
        font-weight: 800; 
        /* Fluid Typography: Menyesuaikan ukuran berdasarkan lebar layar */
        font-size: clamp(20px, 3vw, 32px) !important; 
        margin: 0; 
        text-align: center; 
        flex-grow: 1; 
        text-shadow: none !important; 
        letter-spacing: -0.5px; 
    }}
    .header-date {{ background-color: #f8fafc; color: #0f172a !important; padding: 10px 18px; border-radius: 12px; font-weight: 700; border: 1px solid #e2e8f0; font-size: 14px; white-space: nowrap; }}
    
    /* NOTIFIKASI LONCENG */
    .notif-wrapper {{ position: relative; display: inline-block; margin-right: 15px; cursor: help; }}
    .notif-bell {{ font-size: 24px; }}
    .notif-badge {{ position: absolute; top: -5px; right: -8px; background-color: #ef4444; color: white; border-radius: 50%; padding: 2px 7px; font-size: 11px; font-weight: 800; box-shadow: 0 2px 5px rgba(239,68,68,0.5); animation: pulseRed 2s infinite; }}
    @keyframes pulseRed {{ 0% {{ transform: scale(1); box-shadow: 0 0 0 0 rgba(239,68,68,0.7); }} 70% {{ transform: scale(1.1); box-shadow: 0 0 0 8px rgba(239,68,68,0); }} 100% {{ transform: scale(1); box-shadow: 0 0 0 0 rgba(239,68,68,0); }} }}
    
    /* ====================================
       MEDIA QUERIES (KHUSUS MOBILE / HP)
       ==================================== */
    @media (max-width: 768px) {{ 
        .block-container {{ padding-top: 1rem !important; padding-left: 1rem !important; padding-right: 1rem !important; }}
        .header-bar {{ flex-direction: column; gap: 12px; padding: 20px 15px; }} 
        .header-logo {{ max-height: 45px; }}
        .notif-wrapper {{ margin-right: 10px; margin-bottom: 5px; }}
        
        /* Tombol menjadi lebih compact di layar kecil */
        .stButton>button {{ padding: 15px 10px !important; font-size: 14px !important; }}
    }}

    /* ====================================
       KARTU MELAYANG & NAVIGASI
       ==================================== */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {{ border-radius: 16px; background: linear-gradient(145deg, rgba(30,41,59,0.8), rgba(15,23,42,0.9)) !important; backdrop-filter: blur(16px); border: 1px solid rgba(255,255,255,0.15); box-shadow: 0 10px 30px rgba(0,0,0,0.5); padding: 20px; animation: fadeIn 0.5s ease-out; }}
    @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    
    .stButton>button {{ border-radius: 12px; font-weight: 800 !important; padding: 20px 10px; font-size: 16px; transition: all 0.2s ease; height: auto !important; width: 100%; display: flex; justify-content: center; align-items: center; }}
    button[kind="primary"] {{ background: linear-gradient(135deg, #0284c7, #0369a1) !important; color: #ffffff !important; border: 1px solid rgba(56,189,248,0.5) !important; box-shadow: 0 6px 15px rgba(2,132,199,0.5) !important; }}
    button[kind="secondary"] {{ background: rgba(30,41,59,0.7) !important; color: #94a3b8 !important; border: 1px solid rgba(255,255,255,0.1) !important; box-shadow: 0 4px 6px rgba(0,0,0,0.2) !important; }}
    button[kind="secondary"]:hover {{ background: rgba(30,41,59,0.9) !important; color: #f8fafc !important; border: 1px solid rgba(255,255,255,0.3) !important; }}
    
    /* ====================================
       ACCORDION MENU INFO PERSONEL OFF
       ==================================== */
    details.off-personnel {{ background: rgba(56,189,248,0.05); border-left: 3px solid #38bdf8; border-radius: 8px; margin-bottom: 8px; transition: all 0.3s ease; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
    details.off-personnel summary {{ padding: 12px 15px; cursor: pointer; font-size: 14px; font-weight: 600; color: #f8fafc; list-style: none; display: flex; align-items: center; }}
    details.off-personnel summary::-webkit-details-marker {{ display: none; }}
    details.off-personnel[open] {{ background: rgba(56,189,248,0.1); box-shadow: 0 4px 10px rgba(0,0,0,0.2); }}
    .off-details-content {{ padding: 10px 15px 15px 15px; border-top: 1px dashed rgba(255,255,255,0.1); font-size: 14px; color: #e2e8f0; animation: fadeIn 0.3s ease-in-out; }}

    /* ====================================
       HORIZONTAL SCROLL JADWAL 14 HARI
       ==================================== */
    .scroll-container {{ display: flex; overflow-x: auto; gap: 12px; padding-bottom: 15px; padding-top: 10px; -webkit-overflow-scrolling: touch; }}
    .scroll-card {{ flex: 0 0 200px; background: linear-gradient(145deg, rgba(30,41,59,0.9), rgba(15,23,42,0.95)); border: 1px solid rgba(255,255,255,0.15); border-radius: 14px; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); animation: slideInRight 0.5s ease-out backwards; }}
    @keyframes slideInRight {{ 0% {{ opacity: 0; transform: translateX(20px); }} 100% {{ opacity: 1; transform: translateX(0); }} }}
    .scroll-header {{ text-align: center; background: linear-gradient(135deg, #1e3a8a, #1d4ed8); color: #ffffff; padding: 8px; border-radius: 8px; font-weight: 700; margin-bottom: 12px; font-size: 14px; }}
    .scroll-item {{ margin-bottom: 10px; font-size: 13px; line-height: 1.5; padding: 8px; border-radius: 8px; background-color: rgba(255,255,255,0.05); animation: popIn 0.4s ease backwards; color: #ffffff; }}
    @keyframes popIn {{ 0% {{ opacity: 0; transform: scale(0.95); }} 100% {{ opacity: 1; transform: scale(1); }} }}
    
    /* INDIKATOR STATUS JADWAL */
    .item-absen {{ border-left: 4px solid #ef4444; background-color: rgba(239,68,68,0.15); }}
    .item-dinas {{ border-left: 4px solid #f97316; background-color: rgba(249,115,22,0.15); }}
    .item-hadir {{ border-left: 4px solid #22c55e; background-color: rgba(34,197,94,0.1); }}
    .item-pengganti {{ border-left: 4px solid #38bdf8; background-color: rgba(56,189,248,0.15); }}
    
    .scroll-container::-webkit-scrollbar {{ height: 4px; }} 
    .scroll-container::-webkit-scrollbar-track {{ background: rgba(255,255,255,0.05); border-radius: 10px; }}
    .scroll-container::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,0.3); border-radius: 10px; }}
    
    .section-title {{ font-weight: 800; color: #ffffff !important; margin-bottom: 15px; position: relative; padding-bottom: 8px; font-size: 20px; }}
    .section-title::after {{ content: ''; position: absolute; left: 0; bottom: 0; width: 40px; height: 4px; background: linear-gradient(90deg, #38bdf8, transparent); border-radius: 2px; }}
    .standby-box {{ background: rgba(15,23,42,0.85); padding: 16px; border-radius: 12px; border-left: 4px solid #38bdf8; box-shadow: 0 4px 10px rgba(0,0,0,0.4); margin-bottom: 20px; color: #ffffff; }}
    
    /* Mencegah tabrak padding antar kolom di Streamlit */
    [data-testid="column"] {{ padding: 0 8px !important; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

def render_top_header(logo_base64: str, pending_count: int):
    """Menampilkan header putih utama dengan notifikasi."""
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" class="header-logo">' if logo_base64 else '<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Pertamina_Logo.svg/512px-Pertamina_Logo.svg.png" class="header-logo">'
    date_str = datetime.now().strftime('%d %b %Y')
    
    notif_html = f'<div class="notif-wrapper" title="Ada {pending_count} ajuan menunggu"><span class="notif-bell">🔔</span><span class="notif-badge">{pending_count}</span></div>' if pending_count > 0 else '<div class="notif-wrapper" style="opacity: 0.3;" title="Tidak ada antrean"><span class="notif-bell">🔔</span></div>'
    
    header_code = f'<div class="header-bar"><div>{logo_html}</div><h1 class="header-title">{APP_TITLE}</h1><div style="display: flex; align-items: center;">{notif_html}<div class="header-date">📅 {date_str}</div></div></div>'
    st.markdown(header_code, unsafe_allow_html=True)

def render_manager_panel(leave_df: pd.DataFrame, schedule_df: pd.DataFrame):
    """Merender panel verifikasi PIN, persetujuan antrean, dan riwayat."""
    st.markdown("<h3 class='section-title'>🔔 Panel Manajer</h3>", unsafe_allow_html=True)
    pin = st.text_input("🔑 PIN Verifikasi Manajer", type="password", key="pin_dash", placeholder="Masukkan PIN...")
    
    if pin != PIN_MANAGER:
        with st.container(border=True):
            st.markdown("<div style='text-align:center; padding:5px;'><span style='font-size:24px;'>🔒</span><br><span style='color:#cbd5e1; font-weight:500; font-size:14px;'>Masukkan PIN keamanan untuk mengakses Panel Approval & Editor Sheet.</span></div>", unsafe_allow_html=True)
        return

    # Panel Keamanan Terbuka
    approver_name = st.selectbox("👨‍💼 Nama Manajer / Approver:", APPROVERS)
    is_locked = approver_name == APPROVERS[0]
    if is_locked:
        st.info("⚠️ Silakan pilih Nama Anda terlebih dahulu untuk membuka kunci persetujuan.")
    
    st.markdown("<div class='standby-box'>🛠️ <b style='color:#38bdf8;'>Akses Editor Database</b>", unsafe_allow_html=True)
    st.link_button("📝 Edit Jadwal Aktual", URL_SCHEDULE, use_container_width=True)
    st.link_button("📋 Edit Database Izin", URL_LEAVE, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if leave_df.empty or 'Status Approval' not in leave_df.columns:
        st.warning("Menunggu sinkronisasi data izin...")
        return

    # Kolom Dinamis Google Form
    col_reason = get_matching_column(leave_df, ['alasan', 'keterangan', 'keperluan'], 'Alasan Izin')
    col_proof = get_matching_column(leave_df, ['upload', 'dokumen', 'bukti', 'file'], 'Bukti Izin')

    leave_valid_df = leave_df.dropna(subset=['Nama Lengkap Operator'])
    
    # 1. TAB ANTREAN PENDING
    st.markdown("<h4 style='color:#ffffff; font-size:16px; font-weight:700; margin-top:10px;'>Antrean Persetujuan Izin:</h4>", unsafe_allow_html=True)
    pending_df = leave_valid_df[leave_valid_df['Status Approval'].isna() | (leave_valid_df['Status Approval'] == "")]
    
    if pending_df.empty:
        st.info("✨ Tidak ada antrean persetujuan izin saat ini.")
    else:
        for idx, row in pending_df.head(5).iterrows():
            reason_text = str(row.get(col_reason, '-')).strip()
            if reason_text.lower() in ['nan', '']: reason_text = 'Tidak ada keterangan'
            
            proof_link = str(row.get(col_proof, '')).strip()
            proof_html = f"<a href='{proof_link}' target='_blank' style='color:#38bdf8; text-decoration:none; font-weight:700;'>📎 Buka Lampiran Dokumen</a>" if proof_link.startswith('http') else "<span style='color:#64748b; font-style:italic;'>Tidak ada file bukti terlampir</span>"

            with st.container(border=True):
                html_card = f"""<div style='animation: slideInRight 0.4s ease-out backwards;'><b style='font-size:16px; color:#ffffff;'>{row['Nama Lengkap Operator']}</b> <span style='color:#cbd5e1; font-weight:500;'>({row.get('Jenis Izin yang Diajukan', 'Izin')})</span><div style='font-size:14px; margin-top:8px; color:#e2e8f0;'>📅 {row['Tanggal Mulai Izin']} s/d {row['Tanggal Selesai Izin']}</div><div style='font-size:14px; color:#e2e8f0; margin-top:2px;'><b>Shift:</b> {row.get('Shift Izin', 'Pg')}</div><div style='margin-top:10px; background: rgba(255,255,255,0.05); border-left: 3px solid #94a3b8; padding: 10px; border-radius: 4px;'><div style='font-size:13px; color:#cbd5e1; margin-bottom:5px;'><b>📝 Alasan / Keterangan:</b><br>{reason_text}</div><div style='font-size:13px;'>{proof_html}</div></div><div style='font-size:14px; color:#fca5a5; font-weight:700; margin-top:12px; margin-bottom:12px; background: rgba(239, 68, 68, 0.2); padding: 4px 8px; border-radius: 4px; display:inline-block;'>🔄 Pengganti: {row.get('Nama Lengkap Operator Pengganti', '-')}</div></div>"""
                st.markdown(html_card, unsafe_allow_html=True)
                
                c_app, c_rej = st.columns(2)
                with c_app:
                    if st.button("✅ Approve", key=f"app_{idx}", type="primary", use_container_width=True, disabled=is_locked):
                        process_leave_approval("APPROVED", idx, row, schedule_df, approver_name)
                with c_rej:
                    if st.button("❌ Reject", key=f"rej_{idx}", use_container_width=True, disabled=is_locked):
                        process_leave_approval("REJECTED", idx, row, schedule_df, approver_name)

    # 2. TAB RIWAYAT KEPUTUSAN (UNDO)
    st.markdown("<hr style='opacity:0.2; border-color: rgba(255,255,255,0.2);'>", unsafe_allow_html=True)
    st.markdown("<h4 style='color:#ffffff; font-size:16px; font-weight:700;'>Riwayat Keputusan Terakhir:</h4>", unsafe_allow_html=True)
    
    history_df = leave_valid_df[leave_valid_df['Status Approval'].astype(str).str.upper().str.contains('APPROVED|REJECTED', regex=True, na=False)]
    if history_df.empty:
        st.info("Belum ada riwayat keputusan.")
    else:
        for idx, row in history_df.tail(5).iloc[::-1].iterrows():
            status_lama = str(row['Status Approval']).upper()
            is_appr = "APPROVED" in status_lama
            c_text, c_bg = ("#4ade80", "rgba(34, 197, 94, 0.2)") if is_appr else ("#fca5a5", "rgba(239, 68, 68, 0.2)")
            
            with st.container(border=True):
                st.markdown(f"<div style='display:flex; justify-content:space-between; align-items:center;'><div><b style='font-size:14px; color:#ffffff;'>{row['Nama Lengkap Operator']}</b><div style='font-size:12px; color:#cbd5e1;'>{row['Tanggal Mulai Izin']} s/d {row['Tanggal Selesai Izin']}</div></div><div style='background:{c_bg}; color:{c_text}; padding:4px 10px; border-radius:6px; font-size:11px; font-weight:800;'>{status_lama}</div></div>", unsafe_allow_html=True)
                if st.button("↩️ Batalkan Keputusan", key=f"undo_{idx}", use_container_width=True, disabled=is_locked):
                    undo_leave_approval(idx, row, schedule_df, status_lama)

def render_off_personnel_search(schedule_df: pd.DataFrame, operator_df: pd.DataFrame):
    """Merender fitur pencarian personel OFF interaktif."""
    st.markdown("<h3 class='section-title'>👥 Cari Personel OFF</h3>", unsafe_allow_html=True)
    
    target_date = st.date_input("Pilih Tanggal Pengecekan:", value=datetime.now().date())
    target_date_str = target_date.strftime('%Y-%m-%d')
    
    if schedule_df.empty or target_date_str not in schedule_df.columns:
        with st.container(border=True):
            st.warning("Data jadwal untuk tanggal ini belum tersedia di sistem.")
            st.link_button("📝 Form Pengajuan Izin / Tukar Shift", URL_GFORM, use_container_width=True, type="primary")
        return

    valid_names_df = schedule_df.dropna(subset=['Nama Operator'])
    is_off_condition = valid_names_df[target_date_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])
    off_personnel_list = valid_names_df[is_off_condition]["Nama Operator"].astype(str).tolist()
    
    with st.container(border=True):
        st.markdown(f"<div style='margin-bottom:12px; color:#94a3b8; font-size:13px; font-weight:600;'>Status OFF pada: <span style='color:#38bdf8;'>{target_date.strftime('%d %b %Y')}</span></div>", unsafe_allow_html=True)
        
        if not off_personnel_list:
            st.write("Tidak ada personel yang terjadwal OFF pada tanggal ini.")
        else:
            col_nama = get_matching_column(operator_df, ['nama', 'operator'], None)
            col_kontak = get_matching_column(operator_df, ['contact', 'kontak', 'hp', 'telepon'], None)

            for i, name in enumerate(off_personnel_list):
                contact_info = "(Data belum ada)"
                
                if col_nama and col_kontak and not operator_df.empty:
                    clean_db_names = operator_df[col_nama].astype(str).str.replace('*', '', regex=False).str.strip().str.lower()
                    target_name_clean = str(name).replace('*', '').strip().lower()
                    
                    match_op = operator_df[clean_db_names == target_name_clean]
                    if match_op.empty:
                        match_op = operator_df[clean_db_names.str.contains(target_name_clean, na=False)]

                    if not match_op.empty:
                        val_con = str(match_op.iloc[0][col_kontak]).strip()
                        if val_con and val_con.lower() not in ['nan', 'none', '']:
                            contact_info = val_con
                
                html_acc = f'<details class="off-personnel" style="animation: slideInRight 0.3s {i * 0.05}s ease-out backwards;"><summary><b style="color:#38bdf8; font-size:12px; margin-right:8px;">OFF</b><span>{name}</span><span style="margin-left:auto; font-size:10px; color:#94a3b8; border: 1px solid rgba(255,255,255,0.2); padding: 2px 6px; border-radius: 4px;">▼ Kontak</span></summary><div class="off-details-content"><div><span style="color:#94a3b8;">📞 No. Handphone:</span> <b style="color:#38bdf8; font-size:15px;">{contact_info}</b></div></div></details>'
                st.markdown(html_acc, unsafe_allow_html=True)
                
    st.markdown("<br>", unsafe_allow_html=True)
    st.link_button("📝 Form Pengajuan Izin / Tukar Shift", URL_GFORM, use_container_width=True, type="primary")

def render_14_days_outlook(schedule_df: pd.DataFrame, leave_df: pd.DataFrame):
    """Merender timeline scroll horizontal untuk 14 hari ke depan."""
    st.markdown("<br><hr style='opacity:0.2; border-color: rgba(255,255,255,0.2);'><h3 class='section-title'>📅 Tinjauan 14 Hari Kedepan</h3>", unsafe_allow_html=True)
    
    if schedule_df.empty:
        st.warning("Data Jadwal Aktual sedang disinkronisasi...")
        return

    # Extract active substitutes mapped by date
    substitutes_by_date = {}
    if not leave_df.empty and 'Status Approval' in leave_df.columns:
        approved_leaves = leave_df[leave_df['Status Approval'].astype(str).str.upper().str.contains('APPROVED', na=False)]
        for _, row in approved_leaves.iterrows():
            try:
                sub_name = str(row.get('Nama Lengkap Operator Pengganti', '')).strip().lower()
                if sub_name and sub_name not in ['nan', 'tidak ada', '']:
                    d_start = pd.to_datetime(row['Tanggal Mulai Izin'], dayfirst=True).date()
                    d_end = pd.to_datetime(row['Tanggal Selesai Izin'], dayfirst=True).date()
                    for d in pd.date_range(d_start, d_end):
                        d_str = d.strftime('%Y-%m-%d')
                        substitutes_by_date.setdefault(d_str, []).append(sub_name)
            except Exception:
                pass

    today = datetime.now().date()
    days = [today + timedelta(days=i) for i in range(14)]
    html_cards = '<div class="scroll-container">'
    
    for i, date_obj in enumerate(days):
        d_str = date_obj.strftime('%Y-%m-%d')
        card_content = f'<div class="scroll-card" style="animation-delay: {i * 0.05}s;"><div class="scroll-header">{date_obj.strftime("%d %b %Y")}</div>'
        
        if d_str in schedule_df.columns:
            day_df = schedule_df[['Nama Operator', d_str]].dropna()
            day_df = day_df[~day_df[d_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])]
            subs_today = substitutes_by_date.get(d_str, [])
            
            if not day_df.empty:
                for item_idx, (_, row) in enumerate(day_df.iterrows()):
                    clean_name = str(row['Nama Operator']).replace('*', '').strip()
                    lower_name = clean_name.lower()
                    status = str(row[d_str]).upper()
                    delay = (i * 0.05) + (item_idx * 0.02)
                    
                    if any(k in status for k in ["DINAS", "PD"]):
                        card_content += f'<div class="scroll-item item-dinas" style="animation-delay: {delay}s;">🟠 <b>{clean_name}</b><br><span style="color:#fdba74; font-size:11px; font-weight:800; background:rgba(249,115,22,0.3); padding:2px 6px; border-radius:4px; display:inline-block; margin-top:4px;">{status}</span></div>'
                    elif any(k in status for k in ["IZIN", "SAKIT", "CUTI"]):
                        card_content += f'<div class="scroll-item item-absen" style="animation-delay: {delay}s;">🔴 <b>{clean_name}</b><br><span style="color:#fca5a5; font-size:11px; font-weight:800; background:rgba(239,68,68,0.3); padding:2px 6px; border-radius:4px; display:inline-block; margin-top:4px;">{status}</span></div>'
                    elif lower_name in subs_today:
                        card_content += f'<div class="scroll-item item-pengganti" style="animation-delay: {delay}s;">🔵 <b>{clean_name}</b><br><span style="color:#7dd3fc; font-size:11px; font-weight:800; background:rgba(56,189,248,0.2); padding:2px 6px; border-radius:4px; display:inline-block; margin-top:4px;">PENGGANTI SHIFT {status}</span></div>'
                    else:
                        card_content += f'<div class="scroll-item item-hadir" style="animation-delay: {delay}s;">🟢 <b>{clean_name}</b><br><span style="color:#4ade80; font-size:11px; font-weight:800; background:rgba(34,197,94,0.3); padding:2px 6px; border-radius:4px; display:inline-block; margin-top:4px;">SHIFT {status}</span></div>'
            else:
                card_content += '<div class="scroll-item" style="color:#94a3b8; font-style:italic; text-align:center; background:none; border:none; box-shadow:none;">Semua Personel OFF</div>'
        else:
            card_content += '<div class="scroll-item" style="color:#94a3b8; font-style:italic; text-align:center; background:none; border:none; box-shadow:none;">Data belum dirilis</div>'
            
        html_cards += card_content + '</div>'
        
    html_cards += '</div>' 
    st.markdown(html_cards, unsafe_allow_html=True)

def render_full_calendar(schedule_df: pd.DataFrame):
    """Merender tabel rekapitulasi status seluruh personel pada tanggal tertentu."""
    st.markdown("<h3 class='section-title'>Pencarian Jadwal Spesifik</h3>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.info("Pilih tanggal untuk melihat rekapitulasi status seluruh personel.")
        selected_date = st.date_input("Pilih Tanggal:", key="cal_date")

    st.markdown("<br>", unsafe_allow_html=True)
    date_str = selected_date.strftime('%Y-%m-%d')

    if schedule_df.empty:
        st.error("❌ Data matrix jadwal gagal dimuat. Silakan muat ulang halaman.")
        return

    if date_str not in schedule_df.columns:
        st.warning(f"⚠️ Data jadwal untuk tanggal **{selected_date.strftime('%d %B %Y')}** belum dirilis atau tidak tersedia di sistem.")
        return

    st.markdown(f"<h4 style='color:#ffffff; animation: fadeIn 0.3s ease-out; font-size:18px;'>Status Personel pada: <b style='color:#38bdf8;'>{selected_date.strftime('%d %B %Y')}</b></h4>", unsafe_allow_html=True)
    
    day_df = schedule_df[['Nama Operator', date_str]].dropna(subset=['Nama Operator']).copy()
    day_df['Status'] = day_df[date_str].fillna('').astype(str).str.strip().str.upper()

    df_off = day_df[day_df['Status'].isin(['OFF', 'NAN', '<NA>', '', 'NONE'])]
    df_absen = day_df[day_df['Status'].str.contains('IZIN|SAKIT|CUTI|DINAS|PD', na=False)]
    df_shift = day_df[~day_df['Nama Operator'].isin(df_off['Nama Operator']) & ~day_df['Nama Operator'].isin(df_absen['Nama Operator'])]

    def _render_table_block(title: str, df_data: pd.DataFrame, border_color: str, bg_color: str, show_status: bool = True):
        st.markdown("<div style='animation: fadeIn 0.4s ease-out;'>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(f"<div style='background-color: {bg_color}; padding: 10px; border-radius: 8px; margin-bottom: 10px; border: 1px solid {border_color};'><b style='color: #ffffff;'>{title} ({len(df_data)})</b></div>", unsafe_allow_html=True)
            if not df_data.empty:
                cols_to_show = ['Nama Operator', 'Status'] if show_status else ['Nama Operator']
                st.dataframe(df_data[cols_to_show], hide_index=True, use_container_width=True)
            else:
                st.write("Tidak ada data pada kategori ini.")
        st.markdown("</div><br>", unsafe_allow_html=True)

    _render_table_block("🟢 Hadir / Shift", df_shift, "rgba(34, 197, 94, 0.4)", "rgba(34, 197, 94, 0.2)")
    _render_table_block("⚪ Sedang OFF", df_off, "rgba(56, 189, 248, 0.4)", "rgba(56, 189, 248, 0.2)", show_status=False)
    _render_table_block("🔴 Absen / Cuti / Dinas", df_absen, "rgba(239, 68, 68, 0.4)", "rgba(239, 68, 68, 0.2)")


# ==========================================
# 6. MAIN APPLICATION LOOP
# ==========================================
def main():
    # Load Assets & CSS
    img_base64 = get_base64_image("fsru.jpg")
    logo_base64 = get_base64_image("pertamina.png")
    inject_custom_css(img_base64)

    # Load Data
    schedule_df, leave_df, operator_df = load_all_data()

    # Calculate Pending Leaves for Notification
    pending_count = 0
    if not leave_df.empty and 'Status Approval' in leave_df.columns:
        pending_df = leave_df.dropna(subset=['Nama Lengkap Operator'])
        pending_count = len(pending_df[pending_df['Status Approval'].isna() | (pending_df['Status Approval'] == "")])

    # Render App Header
    render_top_header(logo_base64, pending_count)

    # Navigation State
    if 'active_menu' not in st.session_state:
        st.session_state.active_menu = "Dashboard"

    nav_c1, nav_c2 = st.columns(2)
    with nav_c1:
        st.button("🏠 Dashboard", type="primary" if st.session_state.active_menu == "Dashboard" else "secondary", on_click=lambda: st.session_state.update(active_menu="Dashboard"), use_container_width=True)
    with nav_c2:
        st.button("📅 Kalender Lengkap", type="primary" if st.session_state.active_menu == "Kalender" else "secondary", on_click=lambda: st.session_state.update(active_menu="Kalender"), use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # View Router
    if st.session_state.active_menu == "Dashboard":
        col_main, col_side = st.columns([2.5, 1.5])
        with col_main:
            render_manager_panel(leave_df, schedule_df)
        with col_side:
            render_off_personnel_search(schedule_df, operator_df)
            
        render_14_days_outlook(schedule_df, leave_df)
        
    elif st.session_state.active_menu == "Kalender":
        render_full_calendar(schedule_df)

# Bootstrap Application
if __name__ == "__main__":
    main()
