import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import base64
import os
import re
from PIL import Image

# =====================================================================
# 1. KONFIGURASI UTAMA & KONSTANTA
# =====================================================================
try:
    favicon = Image.open("logo-pertaminaregasv2.png")
except:
    favicon = "⚡"

st.set_page_config(page_title="NR ORF Command", page_icon=favicon, layout="wide", initial_sidebar_state="collapsed")

ID_SHEET_JADWAL = "1HuIrvhzm7xzXXbX5Foy2XPms7NLzFyttgH58Ez31pj0"
ID_SHEET_IZIN = "1mdr7InOGhuVwLCpgPW-fDVOMw38XvELlXK9sxJymMYU"

URL_JADWAL = f"https://docs.google.com/spreadsheets/d/{ID_SHEET_JADWAL}/edit#gid=0"
URL_IZIN = f"https://docs.google.com/spreadsheets/d/{ID_SHEET_IZIN}/edit"
URL_GFORM = "https://forms.gle/KB9CkfEsLB4yY9MK9"

PIN_MANAGER = "regas123"
DAFTAR_MANAJER = ["-- Pilih Nama Anda --", "Yosep Zulkarnain", "Ade Imat", "Benny Sulistio", "Ibrahim"]

EVENT_KALENDER = {
    "01-01": "Tahun Baru Masehi",
    "02-08": "Isra Mikraj Nabi Muhammad",
    "02-10": "Tahun Baru Imlek",
    "03-11": "Hari Suci Nyepi",
    "03-29": "Wafat Isa Al Masih",
    "03-31": "Hari Paskah",
    "04-10": "Hari Raya Idul Fitri",
    "04-11": "Hari Raya Idul Fitri",
    "05-01": "Hari Buruh Internasional",
    "05-09": "Kenaikan Isa Al Masih",
    "05-23": "Hari Raya Waisak",
    "06-01": "Hari Lahir Pancasila",
    "06-17": "Hari Raya Idul Adha",
    "07-07": "Tahun Baru Islam",
    "08-17": "Hari Kemerdekaan RI 🇮🇩",
    "09-16": "Maulid Nabi Muhammad SAW",
    "12-25": "Hari Raya Natal"
}


# =====================================================================
# 2. FUNGSI BANTUAN (UTILITIES & NLP PARSER)
# =====================================================================
def get_base64_image(file_name):
    try:
        with open(file_name, 'rb') as f: return base64.b64encode(f.read()).decode()
    except Exception: return None

def find_col(df, keywords, default_name):
    if df.empty: return default_name
    for col in df.columns:
        if any(kw in str(col).lower() for kw in keywords): return col
    return default_name

def parse_natural_language_schedule(text, df_j):
    text = text.lower()
    today = datetime.now()
    nama_ditemukan = None
    if not df_j.empty and 'Nama Operator' in df_j.columns:
        daftar_nama = df_j['Nama Operator'].dropna().astype(str).tolist()
        for nama in daftar_nama:
            nama_bersih = nama.replace('*', '').strip().lower()
            if nama_bersih in text or nama_bersih.split()[0] in text:
                nama_ditemukan = nama
                break
    
    status_baru = None
    if any(k in text for k in ["sakit", "jatuh sakit"]): status_baru = "SAKIT"
    elif any(k in text for k in ["cuti", "libur"]): status_baru = "CUTI"
    elif "off" in text: status_baru = "OFF"
    elif any(k in text for k in ["dinas", "pd", "perjalanan dinas"]): status_baru = "PD"
    elif "pagi" in text: status_baru = "PG"
    elif "malam" in text: status_baru = "MLM"
    
    tanggal_mulai, tanggal_selesai = None, None
    if "hari ini" in text: tanggal_mulai = tanggal_selesai = today
    elif "besok" in text: tanggal_mulai = tanggal_selesai = today + timedelta(days=1)
    elif "lusa" in text: tanggal_mulai = tanggal_selesai = today + timedelta(days=2)
    else:
        match_rentang = re.search(r'(\d{1,2})\s*(?:-|sampai|s/d)\s*(\d{1,2})', text)
        match_tunggal = re.search(r'(\d{1,2})', text)
        bulan_ini, tahun_ini = today.month, today.year
        try:
            if match_rentang:
                t_aw, t_ak = int(match_rentang.group(1)), int(match_rentang.group(2))
                if 1 <= t_aw <= 31 and 1 <= t_ak <= 31:
                    tanggal_mulai, tanggal_selesai = datetime(tahun_ini, bulan_ini, t_aw), datetime(tahun_ini, bulan_ini, t_ak)
            elif match_tunggal:
                tgl = int(match_tunggal.group(1))
                if 1 <= tgl <= 31: tanggal_mulai = tanggal_selesai = datetime(tahun_ini, bulan_ini, tgl)
        except ValueError: pass

    return {"nama": nama_ditemukan, "status": status_baru, "tgl_mulai": tanggal_mulai, "tgl_selesai": tanggal_selesai}

def generate_html_card(row, col_reason, col_proof, delay):
    alasan = str(row.get(col_reason, '-')).strip()
    if alasan.lower() in ['nan', '']: alasan = 'Tidak ada keterangan'
    
    bukti = str(row.get(col_proof, '')).strip()
    if bukti.startswith('http'):
        bukti_html = f"<a href='{bukti}' target='_blank' class='link-hover' style='color:#38bdf8; text-decoration:none; display:inline-flex; align-items:center;'><span class='material-symbols-rounded' style='font-size:16px; margin-right:4px;'>attach_file</span> Buka Dokumen</a>"
    else:
        bukti_html = "<span style='color:#64748b; font-style:italic; display:inline-flex; align-items:center;'><span class='material-symbols-rounded' style='font-size:16px; margin-right:4px;'>description_off</span> Tidak ada lampiran</span>"

    return f"""
    <div style='animation: slideInRight 0.4s cubic-bezier(0.16, 1, 0.3, 1) {delay}s both;'>
        <div style='display:flex; align-items:center; gap:8px;'>
            <span class='material-symbols-rounded' style='color:#38bdf8; font-size:20px;'>person</span>
            <b style='font-size:16px; color:#ffffff;'>{row['Nama Lengkap Operator']}</b> 
            <span style='color:#94a3b8; font-weight:500; font-size:13px;'>({row.get('Jenis Izin yang Diajukan', 'Izin')})</span>
        </div>
        <div style='font-size:14px; margin-top:12px; color:#e2e8f0; display:flex; align-items:center; gap:6px;'>
            <span class='material-symbols-rounded' style='font-size:16px; color:#94a3b8;'>calendar_month</span> 
            {row['Tanggal Mulai Izin']} s/d {row['Tanggal Selesai Izin']}
            <span style='color:#64748b;'>|</span>
            <span class='material-symbols-rounded' style='font-size:16px; color:#94a3b8;'>schedule</span> Shift: {row.get('Shift Izin', 'Pg')}
        </div>
        <div style='margin-top:12px; background: rgba(255,255,255,0.03); border-left: 3px solid #64748b; padding: 12px; border-radius: 6px; transition: background 0.3s;'>
            <div style='font-size:13px; color:#cbd5e1; margin-bottom:8px; line-height:1.5;'>
                <div style='display:flex; align-items:center; gap:4px; margin-bottom:4px; color:#94a3b8;'>
                    <span class='material-symbols-rounded' style='font-size:14px;'>notes</span> <b>Alasan / Keterangan:</b>
                </div>
                {alasan}
            </div>
            <div style='font-size:13px; margin-top:8px; border-top:1px dashed rgba(255,255,255,0.1); padding-top:8px;'>{bukti_html}</div>
        </div>
        <div style='font-size:13px; color:#fca5a5; font-weight:600; margin-top:12px; margin-bottom:4px; background: rgba(239,68,68,0.15); padding: 6px 10px; border-radius: 6px; display:inline-flex; align-items:center; gap:6px;'>
            <span class='material-symbols-rounded' style='font-size:16px;'>sync_alt</span> 
            Pengganti: {row.get('Nama Lengkap Operator Pengganti', '-')}
        </div>
    </div>
    """


# =====================================================================
# 3. LAYANAN DATABASE (GSPREAD)
# =====================================================================
def get_client():
    try:
        creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception: return None

@st.cache_data(ttl=2) 
def load_all_data():
    client = get_client()
    df_j, df_i, df_k = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    if not client: return df_j, df_i, df_k

    try:
        ws_j = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual").get_all_values()
        if len(ws_j) > 1:
            df_j = pd.DataFrame(ws_j[1:], columns=ws_j[0])
            if 'Nama Operator' in df_j.columns: df_j = df_j[df_j['Nama Operator'].astype(str).str.strip() != '']

        ws_i = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0).get_all_values()
        if len(ws_i) > 1:
            df_i = pd.DataFrame(ws_i[1:], columns=ws_i[0])
            if 'Nama Lengkap Operator' in df_i.columns:
                df_i = df_i[df_i['Nama Lengkap Operator'].astype(str).str.strip() != '']
                df_i = df_i[~df_i['Nama Lengkap Operator'].astype(str).str.lower().isin(['nan', 'none', 'null'])]

        try:
            for ws in client.open_by_key(ID_SHEET_JADWAL).worksheets() + client.open_by_key(ID_SHEET_IZIN).worksheets():
                if 'data' in ws.title.lower() and 'operator' in ws.title.lower():
                    raw_k = ws.get_all_values()
                    if raw_k:
                        temp_df = pd.DataFrame(raw_k)
                        header_idx = next((i for i, r in temp_df.iterrows() if any('nama' in str(v).lower() and 'operator' in str(v).lower() for v in r.values)), -1)
                        if header_idx != -1: df_k = pd.DataFrame(temp_df.values[header_idx+1:], columns=[str(h).strip() for h in temp_df.iloc[header_idx]])
                    break
        except Exception: pass
    except Exception: pass
    return df_j, df_i, df_k

def execute_database_action(idx, row, action_type, approver_name, df_j):
    client = get_client()
    if not client: return st.error("Gagal terhubung ke database.")

    try:
        sh_izin = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0)
        col_status_idx = row.index.get_loc('Status Approval') + 1
        
        if action_type == "APPROVE": status_text = f"APPROVED by {approver_name}"
        elif action_type == "REJECT": status_text = f"REJECTED by {approver_name}"
        else: status_text = ""
        
        sh_izin.update_cell(int(idx)+2, col_status_idx, status_text)
        
        status_lama = str(row.get('Status Approval', '')).upper()
        if action_type == "APPROVE" or (action_type == "UNDO" and "APPROVED" in status_lama):
            sh_aktual = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual")
            d_start = pd.to_datetime(row['Tanggal Mulai Izin'], dayfirst=True).date()
            d_end = pd.to_datetime(row['Tanggal Selesai Izin'], dayfirst=True).date()
            
            applicant = str(row['Nama Lengkap Operator']).strip().lower()
            substitute = str(row.get('Nama Lengkap Operator Pengganti', '')).strip().lower()
            has_sub = substitute and substitute not in ['nan', 'tidak ada', '']
            
            batch_updates = []
            for d in pd.date_range(d_start, d_end):
                d_str = d.strftime('%Y-%m-%d')
                if d_str in df_j.columns:
                    col_date_idx = list(df_j.columns).index(d_str) + 1
                    val_app = str(row['Jenis Izin yang Diajukan']).upper() if action_type == "APPROVE" else str(row.get('Shift Izin', 'PG')).title()
                    val_sub = str(row.get('Shift Izin', 'PG')).title() if action_type == "APPROVE" else 'OFF'
                    
                    match_p = df_j[df_j.iloc[:,0].astype(str).str.strip().str.lower() == applicant]
                    if not match_p.empty: batch_updates.append(gspread.Cell(int(match_p.index[0])+2, col_date_idx, val_app))
                        
                    if has_sub:
                        match_sub = df_j[df_j.iloc[:,0].astype(str).str.strip().str.lower() == substitute]
                        if not match_sub.empty: batch_updates.append(gspread.Cell(int(match_sub.index[0])+2, col_date_idx, val_sub))
            
            if batch_updates: sh_aktual.update_cells(batch_updates)

        load_all_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Terjadi kesalahan API: {e}")

def execute_smart_edit(nama, status, d_start, d_end, df_j):
    client = get_client()
    if not client: return st.error("Gagal terhubung ke database.")
    try:
        sh_aktual = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual")
        batch_updates = []
        match_p = df_j[df_j.iloc[:,0].astype(str).str.replace('*', '', regex=False).str.strip().str.lower() == nama.replace('*', '').strip().lower()]
        
        if not match_p.empty:
            row_idx = int(match_p.index[0]) + 2
            for d in pd.date_range(d_start, d_end):
                d_str = d.strftime('%Y-%m-%d')
                if d_str in df_j.columns:
                    col_idx = list(df_j.columns).index(d_str) + 1
                    batch_updates.append(gspread.Cell(row_idx, col_idx, status.upper()))
            
            if batch_updates: 
                sh_aktual.update_cells(batch_updates)
                load_all_data.clear()
                st.success(f"✅ Jadwal **{nama}** berhasil diubah menjadi **{status}**.")
                import time
                time.sleep(1.5)
                st.rerun()
        else: st.error("Nama tidak ditemukan di database.")
    except Exception as e: st.error(f"Gagal mengupdate jadwal: {e}")

def clear_pending_requests(df_i):
    client = get_client()
    if not client: return st.error("Gagal terhubung ke database.")
    try:
        sh_izin = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0)
        df_valid = df_i.dropna(subset=['Nama Lengkap Operator'])
        pending_rows = df_valid[df_valid['Status Approval'].isna() | (df_valid['Status Approval'] == "")]
        
        if pending_rows.empty:
            st.info("Tidak ada antrean yang bisa dihapus.")
            return
            
        indices_to_delete = sorted([int(idx) + 2 for idx in pending_rows.index], reverse=True)
        
        for row_num in indices_to_delete:
            sh_izin.delete_rows(row_num)
            
        load_all_data.clear()
        st.success(f"✅ Berhasil membersihkan {len(indices_to_delete)} antrean ajuan!")
        import time
        time.sleep(1.5)
        st.rerun()
    except Exception as e:
        st.error(f"Gagal menghapus antrean: {e}")


# =====================================================================
# 4. CSS PROFESIONAL, SPLASH SCREEN, & ANIMASI UI
# =====================================================================
def inject_custom_css(bg_base64, logo_base64):
    st.markdown("""<style>[data-testid="collapsedControl"] { display: none; } .block-container { padding-top: 2rem !important; }</style>""", unsafe_allow_html=True)
    bg_color = "rgba(15, 23, 42, 0.88)"
    bg_img = f"url('data:image/jpeg;base64,{bg_base64}')" if bg_base64 else "url('https://images.unsplash.com/photo-1583508108422-0a13d712ce19')"
    logo_src = f"data:image/png;base64,{logo_base64}" if logo_base64 else "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Pertamina_Logo.svg/512px-Pertamina_Logo.svg.png"
    
    st.markdown(f"""
    <div id="splash-overlay">
        <div class="splash-content">
            <img src="{logo_src}" class="splash-logo" alt="Logo">
            <h2 class="splash-title">NR ORF COMMAND</h2>
            <div class="splash-fade-early">
                <div class="splash-subtitle">SINKRONISASI DATABASE...</div>
                <div class="loading-bar-container"><div class="loading-bar"></div></div>
            </div>
        </div>
    </div>

    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

    #splash-overlay {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 9999999; display: flex; justify-content: center; align-items: center; background: #ffffff; animation: overlayFade 2.5s cubic-bezier(0.8, 0, 0.2, 1) forwards; }}
    .splash-content {{ text-align: center; display: flex; flex-direction: column; align-items: center; animation: moveToHeader 2.5s cubic-bezier(0.8, 0, 0.2, 1) forwards; }}
    .splash-fade-early {{ animation: fadeOutEarly 2.5s cubic-bezier(0.8, 0, 0.2, 1) forwards; display: flex; flex-direction: column; align-items: center; width: 100%; }}
    .splash-logo {{ max-height: 70px; margin-bottom: 20px; animation: floatLogo 2s ease-in-out infinite alternate; }}
    
    /* DIUBAH MENJADI HITAM PEKAT AGAR KELIhatan JELAS DI LAYAR PUTIH */
    .splash-title {{ color: #0f172a; font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; font-size: 32px; letter-spacing: 2px; margin: 0; }}
    
    .splash-subtitle {{ color: #64748b; font-size: 13px; font-weight: 600; letter-spacing: 3px; margin-top: 15px; opacity: 0.8; }}
    .loading-bar-container {{ width: 200px; height: 4px; background: #e2e8f0; border-radius: 4px; margin-top: 20px; overflow: hidden; position: relative; }}
    .loading-bar {{ position: absolute; top: 0; left: 0; height: 100%; width: 40%; background: #38bdf8; border-radius: 4px; animation: loadingSwipe 1.2s ease-in-out infinite; box-shadow: 0 0 10px rgba(56,189,248,0.8); }}
    
    @keyframes overlayFade {{ 0%, 65% {{ opacity: 1; visibility: visible; backdrop-filter: blur(12px); background: #ffffff; }} 100% {{ opacity: 0; visibility: hidden; backdrop-filter: blur(0px); background: rgba(255,255,255,0); pointer-events: none; }} }}
    @keyframes moveToHeader {{ 0%, 65% {{ transform: translateY(0) scale(1); opacity: 1; }} 100% {{ transform: translateY(-42vh) scale(0.4); opacity: 0; }} }}
    @keyframes fadeOutEarly {{ 0%, 50% {{ opacity: 1; transform: translateY(0); }} 65%, 100% {{ opacity: 0; transform: translateY(10px); }} }}
    @keyframes floatLogo {{ 0% {{ transform: translateY(0px); filter: drop-shadow(0 5px 15px rgba(0,0,0,0.1)); }} 100% {{ transform: translateY(-10px); filter: drop-shadow(0 15px 25px rgba(0,0,0,0.15)); }} }}
    @keyframes loadingSwipe {{ 0% {{ left: -40%; }} 100% {{ left: 140%; }} }}

    html, body, [class*="css"], .stApp {{ font-family: 'Plus Jakarta Sans', sans-serif !important; color: #f8fafc; }}
    .stApp {{ background-image: linear-gradient({bg_color}, {bg_color}), {bg_img}; background-size: cover; background-attachment: fixed; }}
    .block-container {{ max-width: 1200px !important; margin: 0 auto; }}
    header[data-testid="stHeader"] {{ display: none !important; }}
    .material-symbols-rounded {{ font-variation-settings: 'FILL' 1, 'wght' 500, 'GRAD' 0, 'opsz' 24; vertical-align: middle; }}

    /* KONTRAST FORM INPUT */
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div, div[data-baseweb="datepicker"] > div {{ background-color: #f8fafc !important; border-radius: 8px !important; border: 2px solid transparent !important; transition: all 0.3s ease; min-height: 38px !important; }}
    div[data-baseweb="input"] > div:focus-within, div[data-baseweb="select"] > div:focus-within, div[data-baseweb="datepicker"] > div:focus-within {{ border: 2px solid #38bdf8 !important; box-shadow: 0 0 10px rgba(56, 189, 248, 0.3) !important; }}
    div[data-baseweb="input"] input, div[data-baseweb="select"] span, div[data-baseweb="select"] div[class*="singleValue"] {{ color: #0f172a !important; font-weight: 700 !important; font-size: 13px !important; }}
    div[data-baseweb="input"] input::placeholder {{ color: #94a3b8 !important; font-weight: 500 !important; }}
    div[data-baseweb="input"] svg, div[data-baseweb="select"] svg {{ color: #64748b !important; }}

    div[data-testid="stVerticalBlock"] > div[style*="border"] {{ border-radius: 16px; background: linear-gradient(145deg, rgba(30,41,59,0.7), rgba(15,23,42,0.9)) !important; backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 10px 30px rgba(0,0,0,0.4); padding: 24px; transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); }}
    div[data-testid="stVerticalBlock"] > div[style*="border"]:hover {{ transform: translateY(-4px); box-shadow: 0 15px 35px rgba(0,0,0,0.6); border-color: rgba(56, 189, 248, 0.3); }}

    .stButton>button {{ border-radius: 12px; font-weight: 700 !important; padding: 20px 10px !important; font-size: 15px !important; width: 100%; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important; letter-spacing: 0.3px; }}
    .stButton>button:hover {{ transform: translateY(-2px); filter: brightness(1.15); }}
    .stButton>button:active {{ transform: scale(0.96); }}
    button[kind="primary"] {{ background: linear-gradient(135deg, #0284c7, #0369a1) !important; color: white !important; border: 1px solid rgba(56,189,248,0.4) !important; box-shadow: 0 6px 15px rgba(2,132,199,0.4) !important; }}

    /* HEADER GLOWING & BEL ALERT */
    @keyframes headerGlowPulse {{
        0%   {{ box-shadow: 0 0 20px rgba(0, 77, 149, 0.6), inset 0 0 5px rgba(0, 77, 149, 0.1); border-color: rgba(0, 77, 149, 0.9); }} 
        33%  {{ box-shadow: 0 0 20px rgba(239, 68, 68, 0.6), inset 0 0 5px rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.9); }} 
        66%  {{ box-shadow: 0 0 20px rgba(130, 195, 65, 0.6), inset 0 0 5px rgba(130, 195, 65, 0.1); border-color: rgba(130, 195, 65, 0.9); }} 
        100% {{ box-shadow: 0 0 20px rgba(0, 77, 149, 0.6), inset 0 0 5px rgba(0, 77, 149, 0.1); border-color: rgba(0, 77, 149, 0.9); }} 
    }}
    .header-bar {{ background-color: #ffffff; border-radius: 16px; padding: 16px 32px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; border: 2px solid transparent; animation: fadeIn 0.5s ease-out 2s both, headerGlowPulse 6s ease-in-out 2.5s infinite; }}
    .header-title {{ color: #004D95 !important; font-weight: 800; font-size: clamp(20px, 3vw, 28px) !important; text-align: center; flex-grow: 1; letter-spacing: -0.5px; text-shadow: none !important; margin:0; }}
    
    @keyframes bellFlash {{ 0%, 100% {{ color: #1e293b; transform: scale(1); filter: none; }} 50% {{ color: #ef4444; transform: scale(1.1); filter: drop-shadow(0 0 8px rgba(239, 68, 68, 0.8)); }} }}
    .bell-active {{ animation: bellFlash 1.5s infinite; display: inline-block; }}
    .notif-badge {{ position: absolute; top: -6px; right: -8px; background-color: #ef4444; color: white; border-radius: 50%; padding: 2px 6px; font-size: 11px; font-weight: 800; }}

    /* HOME BUTTON */
    .home-btn {{ display: flex; align-items: center; gap: 6px; background: rgba(30,41,59,0.1); color: #0f172a; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 14px; border: 1px solid rgba(0,0,0,0.1); transition: all 0.2s ease; cursor: pointer; }}
    .home-btn:hover {{ background: rgba(56,189,248,0.2); color: #0284c7; border-color: #38bdf8; transform: translateY(-2px); }}

    /* AKORDEON PERSONEL OFF */
    details.off-personnel {{ background: rgba(255,255,255,0.03); border-left: 3px solid #38bdf8; border-radius: 8px; margin-bottom: 10px; transition: background 0.3s ease, transform 0.2s ease; }}
    details.off-personnel:hover {{ background: rgba(56,189,248,0.08); transform: translateX(4px); }}
    details.off-personnel summary {{ padding: 14px 16px; cursor: pointer; font-size: 14px; font-weight: 600; display: flex; align-items: center; list-style: none; }}
    details.off-personnel summary::-webkit-details-marker {{ display: none; }}
    .chevron-icon {{ transition: transform 0.3s ease; color: #94a3b8; font-size:18px; margin-left:auto; }}
    details.off-personnel[open] .chevron-icon {{ transform: rotate(180deg); color: #38bdf8; }}
    .off-details-content {{ padding: 0 16px 16px 16px; font-size: 14px; color:#cbd5e1; animation: dropDown 0.3s ease-out forwards; }}

    /* TIMELINE SCROLL HACK */
    div[data-testid="stForm"] div[data-testid="stHorizontalBlock"] {{ overflow-x: auto !important; flex-wrap: nowrap !important; scroll-snap-type: x mandatory; padding-bottom: 15px; gap: 15px; }}
    div[data-testid="stForm"] div[data-testid="column"] {{ min-width: 220px !important; flex: 0 0 220px !important; background: linear-gradient(145deg, rgba(30,41,59,0.9), rgba(15,23,42,0.95)); border: 1px solid rgba(255,255,255,0.1); border-radius: 14px; padding: 16px; scroll-snap-align: start; }}
    div[data-testid="stForm"] div[data-testid="column"]:first-child {{ border: 2px solid #38bdf8 !important; box-shadow: 0 0 20px rgba(56,189,248,0.3) !important; background: linear-gradient(145deg, rgba(20,50,85,0.9), rgba(15,23,42,0.95)) !important; }}

    .scroll-container {{ display: flex; overflow-x: auto; gap: 14px; padding-bottom: 20px; padding-top: 10px; scroll-behavior: smooth; scrollbar-width: none; }}
    .scroll-container::-webkit-scrollbar {{ display: none; }}
    .scroll-card {{ flex: 0 0 220px; background: linear-gradient(145deg, rgba(30,41,59,0.9), rgba(15,23,42,0.95)); border: 1px solid rgba(255,255,255,0.1); border-radius: 14px; padding: 16px; transition: transform 0.3s; scroll-snap-align: start; }}
    .scroll-card:hover {{ transform: translateY(-3px); border-color: rgba(255,255,255,0.3); }}
    .scroll-header {{ text-align: center; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 8px; font-weight: 700; margin-bottom: 14px; font-size: 13px; color:#94a3b8; border-bottom:2px solid #38bdf8; }}
    .today-card {{ border: 2px solid #38bdf8 !important; box-shadow: 0 0 20px rgba(56,189,248,0.3) !important; background: linear-gradient(145deg, rgba(20,50,85,0.9), rgba(15,23,42,0.95)) !important; transform: translateY(-3px); }}
    .today-header {{ background: linear-gradient(135deg, #0284c7, #38bdf8) !important; color: #ffffff !important; border-bottom: none !important; box-shadow: 0 4px 10px rgba(2,132,199,0.5); }}

    .status-badge {{ display:inline-flex; align-items:center; gap:6px; font-size:11px; font-weight:700; padding:4px 8px; border-radius:6px; margin-top:6px; width:100%; }}
    .status-dot {{ width:8px; height:8px; border-radius:50%; }}
    .scroll-item {{ margin-bottom: 12px; font-size: 14px; padding: 10px; border-radius: 8px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); }}
    
    /* NAV ARROW BUTTONS */
    .nav-arrow-btn {{ background: rgba(30,41,59,0.8); border: 1px solid rgba(56,189,248,0.4); color: #38bdf8; border-radius: 8px; padding: 6px 12px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s ease; }}
    .nav-arrow-btn:hover {{ background: rgba(56,189,248,0.2); transform: scale(1.05); color: #ffffff; border-color: #38bdf8; }}
    .nav-arrow-btn:active {{ transform: scale(0.95); }}

    .section-title {{ font-weight: 800; margin-bottom: 20px; font-size: 20px; display:flex; align-items:center; gap:8px; }}
    
    /* GAYA TAB STREAMLIT AGAR LEBIH KONTRAST */
    div[data-testid="stTabs"] button {{ font-family: 'Plus Jakarta Sans', sans-serif !important; font-weight: 600 !important; font-size: 16px !important; color: #94a3b8 !important; }}
    div[data-testid="stTabs"] button[aria-selected="true"] {{ color: #38bdf8 !important; }}
    
    @media (max-width: 768px) {{ .header-bar {{ flex-direction: column; gap: 16px; padding: 20px; align-items: center !important; }} .header-title {{ font-size: 20px !important; }} .stButton>button {{ padding: 16px 10px !important; font-size: 14px !important; }} }}
    </style>
    """, unsafe_allow_html=True)


# =====================================================================
# 5. KOMPONEN UI UTAMA & HUD WIDGET
# =====================================================================
def ui_header(logo_base64, pending_count):
    logo = f'<img src="data:image/png;base64,{logo_base64}" style="max-height: 50px;">' if logo_base64 else '<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Pertamina_Logo.svg/512px-Pertamina_Logo.svg.png" style="max-height: 50px;">'
    
    if pending_count > 0:
        notif = f'<div style="position:relative; margin-right:16px; cursor:pointer;" title="Ada {pending_count} ajuan menunggu!"><span class="material-symbols-rounded bell-active" style="font-size:28px;">notifications_active</span><span class="notif-badge">{pending_count}</span></div>'
    else:
        notif = '<div style="position:relative; margin-right:16px; opacity:0.4;"><span class="material-symbols-rounded" style="font-size:28px; color:#1e293b;">notifications</span></div>'
        
    st.markdown(f"""
    <div class="header-bar">
        <div style="display:flex; align-items:center; gap:20px;">
            <form action="javascript:window.location.reload(true)"><button type="submit" class="home-btn" title="Refresh Dashboard"><span class="material-symbols-rounded" style="font-size:20px;">home</span></button></form>
            <div>{logo}</div>
        </div>
        <h1 class="header-title">NR ORF Integrated Command</h1>
        <div style="display:flex; align-items:center;">{notif}</div>
    </div>
    """, unsafe_allow_html=True)

def ui_live_hud_widget():
    hari_ini = datetime.now().strftime("%m-%d")
    event_hari_ini = EVENT_KALENDER.get(hari_ini, "Tidak ada event nasional")
    fallback_lat, fallback_lon = "-6.1115", "106.7932"
    
    components.html(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,600,1,0');
        body {{ margin: 0; padding: 5px; font-family: 'Plus Jakarta Sans', sans-serif; overflow: hidden; }}
        .hud-container {{ display: flex; align-items: center; justify-content: flex-start; gap: 20px; background: linear-gradient(145deg, rgba(30,41,59,0.9), rgba(15,23,42,1)); border: 1px solid rgba(56,189,248,0.4); border-radius: 16px; padding: 12px 20px; box-sizing: border-box; box-shadow: 0 8px 20px rgba(0,0,0,0.4); color: #f8fafc; flex-wrap: nowrap; overflow-x: auto; -webkit-overflow-scrolling: touch; scrollbar-width: none; }}
        .hud-container::-webkit-scrollbar {{ display: none; }}
        .hud-section {{ display: flex; align-items: center; gap: 12px; flex: 0 0 auto; }}
        .clock {{ font-size: 26px; font-weight: 800; color: #38bdf8; font-variant-numeric: tabular-nums; letter-spacing: 1px; text-shadow: 0 0 12px rgba(56,189,248,0.4); }}
        .date {{ font-size: 15px; font-weight: 600; color: #e2e8f0; }}
        .box-hud {{ display: flex; align-items: center; gap: 12px; background: rgba(255,255,255,0.05); padding: 6px 14px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); position: relative; cursor: pointer; }}
        .stat-group {{ display: flex; align-items: center; gap: 4px; font-size: 13px; font-weight: 600; color: #e2e8f0; }}
        .stat-val {{ color: #4ade80; font-weight: 800; font-size: 14px; }}
        .event {{ font-size: 13px; font-weight: 700; color: #1e293b; background: #facc15; padding: 6px 14px; border-radius: 8px; box-shadow: 0 0 15px rgba(250,204,21,0.4); display:flex; align-items:center; gap:6px; }}
        #loc-status {{ position: absolute; top: -6px; right: -6px; background: #3b82f6; width: 14px; height: 14px; border-radius: 50%; border: 2px solid #0f172a; display: flex;
