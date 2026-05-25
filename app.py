import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import base64
import re
import time
from PIL import Image

# =====================================================================
# 1. KONFIGURASI UTAMA
# =====================================================================
try:
    favicon = Image.open("logo-pertaminaregasv2.png")
except:
    favicon = "⚡"

st.set_page_config(page_title="Dashboard Distribusi Gas NR", page_icon=favicon, layout="wide", initial_sidebar_state="collapsed")

ID_SHEET_JADWAL = "1HuIrvhzm7xzXXbX5Foy2XPms7NLzFyttgH58Ez31pj0"
ID_SHEET_IZIN = "1mdr7InOGhuVwLCpgPW-fDVOMw38XvELlXK9sxJymMYU"
URL_JADWAL = f"https://docs.google.com/spreadsheets/d/{ID_SHEET_JADWAL}/edit#gid=0"
URL_IZIN = f"https://docs.google.com/spreadsheets/d/{ID_SHEET_IZIN}/edit"
URL_GFORM = "https://forms.gle/KB9CkfEsLB4yY9MK9"
PIN_MANAGER = "regas123"
DAFTAR_MANAJER = ["-- Pilih Nama Anda --", "Yosep Zulkarnain", "Ade Imat", "Benny Sulistio", "Ibrahim"]

EVENT_KALENDER = {
    "01-01": "Tahun Baru Masehi", "02-08": "Isra Mikraj", "02-10": "Imlek", "03-11": "Nyepi",
    "03-29": "Wafat Isa Al Masih", "03-31": "Paskah", "04-10": "Idul Fitri", "04-11": "Idul Fitri",
    "05-01": "Hari Buruh", "05-09": "Kenaikan Isa Al Masih", "05-23": "Waisak", "06-01": "Lahir Pancasila",
    "06-17": "Idul Adha", "07-07": "Tahun Baru Islam", "08-17": "HUT RI", "09-16": "Maulid Nabi", "12-25": "Natal"
}

# =====================================================================
# INISIALISASI MEMORI SESI (LOGIN & SSO TRACKING)
# =====================================================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_role = ""
    st.session_state.user_name = ""

    if "auth" in st.query_params:
        try:
            token = st.query_params["auth"]
            decoded = base64.b64decode(token).decode("utf-8")
            role, name = decoded.split("::")
            st.session_state.logged_in = True
            st.session_state.user_role = role
            st.session_state.user_name = name
        except:
            pass

if 'last_seen_todo' not in st.session_state:
    st.session_state.last_seen_todo = ""


# =====================================================================
# 2. UTILITIES & AI PARSER (ANTI-ERROR & FUZZY MATCH)
# =====================================================================
@st.cache_data
def get_base64_image(file_name):
    try:
        with open(file_name, 'rb') as f: return base64.b64encode(f.read()).decode()
    except: return None

def find_col(df, keywords, exclude=None, default=None):
    if exclude is None: exclude = []
    if df.empty: return default
    for col in df.columns:
        col_str = str(col).lower()
        if any(kw in col_str for kw in keywords) and not any(ex in col_str for ex in exclude):
            return col
    return default

def get_val(row, keywords, exclude=None, default='-', fallback_idx=None):
    if exclude is None: exclude = []
    # 1. Cari lewat nama header
    for col in row.index:
        col_str = str(col).lower()
        if any(kw in col_str for kw in keywords) and not any(ex in col_str for ex in exclude):
            val = row[col]
            if isinstance(val, pd.Series): val = val.iloc[0]
            val_str = str(val).strip()
            if val_str and val_str.lower() not in ['nan', 'none', 'null']:
                return val_str
    # 2. Paksa lewat indeks urutan kolom Excel
    if fallback_idx is not None and fallback_idx < len(row):
        val = row.iloc[fallback_idx]
        if isinstance(val, pd.Series): val = val.iloc[0]
        val_str = str(val).strip()
        if val_str and val_str.lower() not in ['nan', 'none', 'null']:
            return val_str
    return default

def parse_natural_language_schedule(text, df_j):
    text = text.lower()
    today = datetime.now()
    nama_ditemukan = None
    if not df_j.empty and 'Nama Operator' in df_j.columns:
        for nama in df_j['Nama Operator'].dropna().astype(str).tolist():
            nama_bersih = nama.replace('*', '').strip().lower()
            if nama_bersih in text or nama_bersih.split()[0] in text:
                nama_ditemukan = nama
                break
    
    status_baru = "SAKIT" if any(k in text for k in ["sakit"]) else "CUTI" if any(k in text for k in ["cuti", "libur"]) else "OFF" if "off" in text else "PD" if any(k in text for k in ["dinas", "pd"]) else "PG" if "pagi" in text else "MLM" if "malam" in text else None
    tanggal_mulai, tanggal_selesai = None, None
    
    if "hari ini" in text: tanggal_mulai = tanggal_selesai = today
    elif "besok" in text: tanggal_mulai = tanggal_selesai = today + timedelta(days=1)
    elif "lusa" in text: tanggal_mulai = tanggal_selesai = today + timedelta(days=2)
    else:
        match_r = re.search(r'(\d{1,2})\s*(?:-|sampai|s/d)\s*(\d{1,2})', text)
        match_t = re.search(r'(\d{1,2})', text)
        b, t = today.month, today.year
        try:
            if match_r:
                aw, ak = int(match_r.group(1)), int(match_r.group(2))
                if 1<=aw<=31 and 1<=ak<=31: tanggal_mulai, tanggal_selesai = datetime(t, b, aw), datetime(t, b, ak)
            elif match_t:
                tgl = int(match_t.group(1))
                if 1<=tgl<=31: tanggal_mulai = tanggal_selesai = datetime(t, b, tgl)
        except: pass
    return {"nama": nama_ditemukan, "status": status_baru, "tgl_mulai": tanggal_mulai, "tgl_selesai": tanggal_selesai}

def generate_izin_card_html(row, delay=0.0):
    nama = get_val(row, ['nama', 'pengaju', 'operator', 'lengkap'], exclude=['pengganti', 'ganti', 'backup'], default='Tidak Diketahui', fallback_idx=1)
    jenis = get_val(row, ['jenis', 'kategori', 'izin'], default='Izin', fallback_idx=2)
    tgl_mulai = get_val(row, ['mulai', 'dari'], default='-', fallback_idx=3)
    tgl_selesai = get_val(row, ['selesai', 'sampai'], default='-', fallback_idx=4)
    shift = get_val(row, ['shift'], default='Pg', fallback_idx=5)
    bukti = get_val(row, ['bukti', 'upload', 'dokumen'], default='', fallback_idx=6)
    pengganti = get_val(row, ['pengganti', 'backup', 'ganti'], default='-', fallback_idx=7)
    alasan = get_val(row, ['alasan', 'keterangan'], default='Tidak ada keterangan', fallback_idx=8)
    
    bukti_html = f"<a href='{bukti}' target='_blank' style='color:#38bdf8;'>Buka Dokumen</a>" if bukti.startswith('http') else "<span style='color:#64748b;'>Tidak ada lampiran</span>"
    
    return f"""
    <div style='animation: slideInRight 0.4s cubic-bezier(0.16, 1, 0.3, 1) {delay}s both;'>
        <div style='display:flex; align-items:center; gap:8px;'><span class='material-symbols-rounded' style='color:#38bdf8;'>person</span><b style='font-size:16px; color:#fff;'>{nama}</b> <span style='color:#94a3b8; font-size:12px;'>({jenis})</span></div>
        <div style='font-size:14px; margin-top:12px; color:#e2e8f0;'>📅 {tgl_mulai} s/d {tgl_selesai} | ⏱️ Shift: {shift}</div>
        <div style='margin-top:12px; background: rgba(255,255,255,0.03); border-left: 3px solid #64748b; padding: 12px; border-radius: 6px;'>
            <div style='font-size:13px; color:#cbd5e1;'><b>Alasan:</b> {alasan}</div>
            <div style='font-size:13px; margin-top:8px; border-top:1px dashed rgba(255,255,255,0.1); padding-top:8px;'>{bukti_html}</div>
        </div>
        <div style='font-size:13px; color:#fca5a5; font-weight:600; margin-top:12px; margin-bottom:4px; background: rgba(239,68,68,0.15); padding: 6px 10px; border-radius: 6px; display:inline-block;'>🔄 Pengganti: {pengganti}</div>
    </div>
    """

def check_active(date_str):
    if '|' in date_str:
        try:
            s, e = date_str.split('|')
            d_s = datetime.strptime(s, "%Y-%m-%d").date()
            d_e = datetime.strptime(e, "%Y-%m-%d").date()
            return d_s <= datetime.now().date() <= d_e
        except: return True
    return True

# =====================================================================
# 3. DATABASE DENGAN GHOST ROW KILLER & EXACT SYNC
# =====================================================================
@st.cache_resource
def get_client():
    try:
        creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except: return None

@st.cache_data(ttl=3600)
def load_kontak_data():
    client = get_client()
    df_k = pd.DataFrame()
    if not client: return df_k
    try:
        for ws in client.open_by_key(ID_SHEET_JADWAL).worksheets() + client.open_by_key(ID_SHEET_IZIN).worksheets():
            if 'data' in ws.title.lower() and 'operator' in ws.title.lower():
                raw_k = ws.get_all_values()
                if raw_k:
                    # Cari header row dengan mencoba baris 1-5
                    header_row = 0
                    for i in range(min(5, len(raw_k))):
                        if any('nama' in str(v).lower() for v in raw_k[i]):
                            header_row = i
                            break
                    headers = [str(h).strip() if str(h).strip() else f"Col_{j}" for j, h in enumerate(raw_k[header_row])]
                    df_k = pd.DataFrame(raw_k[header_row+1:], columns=headers)
                break
    except: pass
    return df_k

@st.cache_data(ttl=15)
def load_jadwal_izin_data():
    client = get_client()
    df_j, df_i = pd.DataFrame(), pd.DataFrame()
    if not client: return df_j, df_i
    
    try:
        ws_j_data = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual").get_all_values()
        if len(ws_j_data) > 1:
            headers_j = [str(h).strip() if str(h).strip() else f"Col_{i}" for i, h in enumerate(ws_j_data[0])]
            df_j = pd.DataFrame(ws_j_data[1:], columns=headers_j)
            df_j = df_j.map(lambda x: str(x).strip() if isinstance(x, str) else x)
            if 'Nama Operator' in df_j.columns:
                df_j = df_j[df_j['Nama Operator'] != '']
    except: pass

    try:
        ws_i_data = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0).get_all_values()
        if len(ws_i_data) > 1:
            headers_i = [str(h).strip() if str(h).strip() else f"Col_{i}" for i, h in enumerate(ws_i_data[0])]
            df_i = pd.DataFrame(ws_i_data[1:], columns=headers_i)
            df_i = df_i.replace(r'^\s*$', np.nan, regex=True).dropna(thresh=2).fillna('')
            if len(df_i.columns) > 0:
                col_waktu = df_i.columns[0]
                df_i = df_i[df_i[col_waktu].astype(str).str.strip() != '']
    except: pass
    return df_j, df_i

@st.cache_data(ttl=60)
def fetch_todo_from_sheet():
    client = get_client()
    default_data = {"main_msg": "", "main_msg_date": "", "todo_date": "", "tasks": {}, "last_updated": ""}
    if not client: return default_data
    try:
        sh = client.open_by_key(ID_SHEET_JADWAL)
        try: ws = sh.worksheet("To_Do_List")
        except: ws = sh.add_worksheet(title="To_Do_List", rows=100, cols=3)
        records = ws.get_all_records()
        for r in records:
            t = str(r.get("Target", ""))
            if t == "PENGUMUMAN_UTAMA":
                default_data["main_msg"] = str(r.get("Task", ""))
                default_data["main_msg_date"] = str(r.get("Comment", ""))
            elif t == "TODO_DATE":
                default_data["todo_date"] = str(r.get("Task", ""))
            elif t == "LAST_UPDATED":
                default_data["last_updated"] = str(r.get("Task", ""))
            elif t:
                default_data["tasks"][t] = {"task": str(r.get("Task", "")), "comment": str(r.get("Comment", ""))}
        return default_data
    except: return default_data

def push_todo_to_sheet(main_msg, msg_date, todo_date, tasks_dict):
    client = get_client()
    if not client: return False
    try:
        sh = client.open_by_key(ID_SHEET_JADWAL)
        try: ws = sh.worksheet("To_Do_List")
        except: ws = sh.add_worksheet(title="To_Do_List", rows=100, cols=3)
        existing_data = fetch_todo_from_sheet()
        ws.clear()
        time.sleep(0.5)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [["Target", "Task", "Comment"], ["PENGUMUMAN_UTAMA", main_msg, msg_date], ["TODO_DATE", todo_date, ""], ["LAST_UPDATED", timestamp, ""]]
        for op, task in tasks_dict.items():
            if task.strip(): rows.append([op, task.strip(), existing_data["tasks"].get(op, {}).get("comment", "")])
        try: ws.update(values=rows, range_name="A1")
        except: ws.update("A1", rows)
        fetch_todo_from_sheet.clear()
        return True
    except: return False

def reply_todo_operator(nama_operator, komentar, user_name):
    client = get_client()
    if not client: return False
    try:
        sh = client.open_by_key(ID_SHEET_JADWAL)
        ws = sh.worksheet("To_Do_List")
        records = ws.get_all_records()
        for i, r in enumerate(records):
            if str(r.get("Target", "")) == nama_operator:
                old_comment = str(r.get("Comment", ""))
                time_str = datetime.now().strftime("%H:%M")
                new_chat = f"<div style='margin-bottom:4px;'><span style='color:#94a3b8; font-size:11px;'>[{time_str}]</span> <b style='color:#38bdf8;'>{user_name}:</b> <span style='color:#e2e8f0;'>{komentar}</span></div>"
                ws.update_cell(i + 2, 3, f"{old_comment}{new_chat}" if old_comment else new_chat)
                fetch_todo_from_sheet.clear()
                return True
        return False
    except: return False

def load_all_data():
    df_j, df_i = load_jadwal_izin_data()
    df_k = load_kontak_data()
    return df_j, df_i, df_k

def execute_database_action(idx, row, action_type, approver_name, df_j, df_i):
    client = get_client()
    if not client: return st.error("Gagal terhubung.")
    try:
        sh_izin = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0)
        col_status = find_col(df_i, ['status', 'approval', 'appr'])
        if col_status: c_idx = list(df_i.columns).index(col_status) + 1
        else:
            c_idx = len(df_i.columns) + 1
            sh_izin.update_cell(1, c_idx, "Status Approval")
            
        status_text = f"APPROVED by {approver_name}" if action_type=="APPROVE" else f"REJECTED by {approver_name}" if action_type=="REJECT" else ""
        sh_izin.update_cell(int(idx)+2, c_idx, status_text)
        
        if action_type == "APPROVE" or (action_type == "UNDO" and "APPROVED" in str(get_val(row, ['status', 'approval']))):
            sh_aktual = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual")
            t_mulai = get_val(row, ['mulai', 'dari'], fallback_idx=3)
            t_selesai = get_val(row, ['selesai', 'sampai'], fallback_idx=4)
            d_start = pd.to_datetime(t_mulai, dayfirst=True).date()
            d_end = pd.to_datetime(t_selesai, dayfirst=True).date()
            app = str(get_val(row, ['nama', 'pengaju', 'operator', 'lengkap'], exclude=['pengganti'], fallback_idx=1)).strip().lower()
            sub = str(get_val(row, ['pengganti', 'backup'], fallback_idx=7)).strip().lower()
            jenis = str(get_val(row, ['jenis', 'kategori'], default='IZIN', fallback_idx=2)).upper()
            shift = str(get_val(row, ['shift'], default='PG', fallback_idx=5)).title()
            
            updates = []
            for d in pd.date_range(d_start, d_end):
                d_str = d.strftime('%Y-%m-%d')
                if d_str in df_j.columns:
                    c_date = list(df_j.columns).index(d_str) + 1
                    m_p = df_j[df_j.iloc[:,0].astype(str).str.strip().str.lower() == app]
                    if not m_p.empty: updates.append(gspread.Cell(int(m_p.index[0])+2, c_date, jenis if action_type == "APPROVE" else shift))
                    if sub and sub not in ['nan', 'tidak ada', '-', '']:
                        m_s = df_j[df_j.iloc[:,0].astype(str).str.strip().str.lower() == sub]
                        if not m_s.empty: updates.append(gspread.Cell(int(m_s.index[0])+2, c_date, shift if action_type == "APPROVE" else 'OFF'))
            if updates: sh_aktual.update_cells(updates)
        time.sleep(1.5)
        load_jadwal_izin_data.clear()
        st.rerun()
    except Exception as e: st.error(f"Error: {e}")

def clear_pending_requests(df_i):
    client = get_client()
    try:
        col_status = find_col(df_i, ['status', 'approval', 'appr'])
        if not col_status or col_status not in df_i.columns: return
        sh_izin = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0)
        pending_rows = df_i[df_i[col_status].astype(str).str.strip().str.lower().isin(["", "nan", "none", "null"])]
        indices = sorted([int(idx) + 2 for idx in pending_rows.index], reverse=True)
        for r in indices: sh_izin.delete_rows(r)
        load_jadwal_izin_data.clear()
        st.rerun()
    except: pass

def inject_custom_css(bg_base64, logo_base64, is_login=False):
    bg_img = f"url('data:image/jpeg;base64,{bg_base64}')" if bg_base64 else ""
    css = "<style>\n"
    css += "html, body, .stApp { font-family: 'Plus Jakarta Sans', sans-serif !important; color: #f8fafc; }\n"
    css += "[data-testid=\"collapsedControl\"] { display: none; }\n"
    css += ".block-container { max-width: 1200px !important; padding-top: 2rem !important; }\n"
    css += "header[data-testid=\"stHeader\"] { display: none !important; }\n"
    css += ".stMarkdown a.header-anchor, svg.icon-link { display: none !important; }\n" 
    
    if is_login:
        bg_overlay = "rgba(15,23,42,0.4), rgba(15,23,42,0.7)"
        css += f".stApp {{ background-image: linear-gradient({bg_overlay}), {bg_img} !important; background-size: cover; background-attachment: fixed; background-position: center; }}\n"
        css += """
        div[data-testid="stVerticalBlockBorderWrapper"],
        div[data-testid="stVerticalBlock"] > div[style*="border"] { background-color: rgba(15, 23, 42, 0.65) !important; backdrop-filter: blur(12px) !important; border: 1px solid rgba(255, 255, 255, 0.2) !important; border-radius: 16px !important; box-shadow: 0 20px 50px rgba(0,0,0,0.6) !important; padding: 30px !important; }
        .login-title { color: #ffffff !important; font-weight: 900 !important; text-align: center; font-size: 32px; margin-bottom: 5px; letter-spacing: 1px; }
        .login-subtitle { color: #e2e8f0 !important; text-align: center; margin-bottom: 30px; font-weight: 600; font-size: 14px; }
        label p, .stMarkdown p { color: #ffffff !important; font-weight: 700 !important; }
        div[data-baseweb="input"] > div, div[data-baseweb="select"] > div { background-color: #f1f5f9 !important; border: 2px solid #cbd5e1 !important; border-radius: 8px !important; min-height: 42px !important; }
        div[data-baseweb="input"] input, div[data-baseweb="select"] span { color: #0f172a !important; font-weight: 800 !important; font-size: 14px !important; -webkit-text-fill-color: #0f172a !important; }
        .stButton>button { background: linear-gradient(135deg, #0284c7, #0369a1) !important; border-radius: 10px !important; width: 100% !important; padding: 12px !important; color: #ffffff !important; font-weight: 800 !important; }
        .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 8px 15px rgba(2, 132, 199, 0.4); }
        """
    else:
        bg_overlay = "rgba(15,23,42,0.88), rgba(15,23,42,0.88)"
        css += f".stApp {{ background-image: linear-gradient({bg_overlay}), {bg_img} !important; background-size: cover; background-attachment: fixed; background-position: center; }}\n"
        css += """
        div[data-testid="stVerticalBlockBorderWrapper"], div[data-testid="stVerticalBlock"] > div[style*="border"] { border-radius: 16px; background: linear-gradient(145deg, rgba(30,41,59,0.7), rgba(15,23,42,0.9)) !important; border: 1px solid rgba(255,255,255,0.1) !important; padding: 24px; }
        .header-bar { background: #fff; border-radius: 16px; padding: 16px 32px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; border: 2px solid transparent; }
        .bell-active { animation: bellFlash 1.5s infinite; }
        @keyframes bellFlash { 0%, 100% { color: #1e293b; } 50% { color: #ef4444; } }
        """
    css += "</style>"
    st.markdown(css, unsafe_allow_html=True)

# =====================================================================
# 5. HALAMAN LOGIN
# =====================================================================
def ui_login(df_j):
    logo_base64 = get_base64_image("logo-pertaminaregasv2.png")
    st.markdown("<div style='height: 5vh;'></div>", unsafe_allow_html=True)
    if logo_base64:
        st.markdown(f"<div style='display:flex; justify-content:center; margin-bottom:25px;'><img src='data:image/png;base64,{logo_base64}' style='max-height:80px; filter:drop-shadow(0 4px 6px rgba(0,0,0,0.3));'></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.container(border=True):
            st.markdown("<h2 class='login-title'>SISTEM LOGIN</h2>", unsafe_allow_html=True)
            st.markdown("<p class='login-subtitle'>Akses Terintegrasi Dashboard Distribusi Gas NR</p>", unsafe_allow_html=True)
            role = st.selectbox("Masuk Sebagai:", ["Operator", "Manajer"])
            if role == "Manajer":
                nama = st.selectbox("Nama Manajer:", DAFTAR_MANAJER)
                pin = st.text_input("PIN Keamanan:", type="password")
            else:
                op_list = sorted(df_j['Nama Operator'].dropna().astype(str).unique()) if 'Nama Operator' in df_j.columns else []
                nama = st.selectbox("Nama Operator:", ["-- Pilih Nama Anda --"] + op_list)
                pin = ""
            if st.button("Masuk Aplikasi", type="primary", use_container_width=True):
                if role == "Manajer" and pin != PIN_MANAGER: st.error("❌ PIN Salah!")
                elif nama == "-- Pilih Nama Anda --": st.error("❌ Pilih Nama!")
                else:
                    st.query_params["auth"] = base64.b64encode(f"{role}::{nama}".encode()).decode()
                    st.session_state.logged_in = True
                    st.session_state.user_role = role
                    st.session_state.user_name = nama
                    st.rerun()

# =====================================================================
# 6. RUNNER
# =====================================================================
if __name__ == "__main__":
    is_login_page = not st.session_state.get('logged_in', False)
    inject_custom_css(get_base64_image("orfmk2.jpg"), get_base64_image("logo-pertaminaregasv2.png"), is_login=is_login_page)
    df_j, df_i, df_k = load_all_data()

    if is_login_page: ui_login(df_j)
    else:
        # Hitung antrean (Non-Dummy)
        col_s = find_col(df_i, ['status', 'approval', 'appr'])
        col_n = find_col(df_i, ['nama', 'pengaju', 'operator', 'lengkap'])
        pending = 0
        if not df_i.empty and col_s and col_n:
            df_v = df_i[~df_i[col_n].astype(str).str.lower().isin(["", "nan", "none", "null"])]
            pending = len(df_v[df_v[col_s].astype(str).str.lower().isin(["", "nan", "none", "null"])])
            
        ui_header(get_base64_image("pertamina.png"), pending, (st.session_state.user_role == "Manajer"))
        ui_live_hud_widget() 
        ui_todo_widget()
        
        # Menu UI (Dashboard, Kalender, ManagerPanel)
        if 'menu' not in st.session_state: st.session_state.menu = "Dash"
        
        if st.session_state.user_role == "Manajer":
            c1, c2, c3 = st.columns(3)
            with c1: st.button("Dashboard Utama", type="primary" if st.session_state.menu=="Dash" else "secondary", on_click=lambda: st.session_state.update(menu="Dash"), use_container_width=True)
            with c2: st.button("Kalender Lengkap", type="primary" if st.session_state.menu=="Kal" else "secondary", on_click=lambda: st.session_state.update(menu="Kal"), use_container_width=True)
            with c3: st.button("Panel Manajer", type="primary" if st.session_state.menu=="Mgr" else "secondary", on_click=lambda: st.session_state.update(menu="Mgr"), use_container_width=True)
        else:
            c1, c2 = st.columns(2)
            with c1: st.button("Dashboard Utama", type="primary" if st.session_state.menu=="Dash" else "secondary", on_click=lambda: st.session_state.update(menu="Dash"), use_container_width=True)
            with c2: st.button("Kalender Lengkap", type="primary" if st.session_state.menu=="Kal" else "secondary", on_click=lambda: st.session_state.update(menu="Kal"), use_container_width=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.session_state.menu == "Dash":
            c_m, c_s = st.columns([2.5, 1.5])
            with c_m: ui_timeline(df_j, df_i)
            with c_s: ui_off_tracker(df_j, df_k)
        elif st.session_state.menu == "Kal": ui_kalender_lengkap(df_j)
        elif st.session_state.menu == "Mgr" and st.session_state.user_role == "Manajer": ui_manager_panel(df_i, df_j)
