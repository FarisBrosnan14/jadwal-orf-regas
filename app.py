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
# 2. UTILITIES & AI PARSER (ANTI-ERROR & POSITIONAL FALLBACK)
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
    for col in row.index:
        col_str = str(col).lower()
        if any(kw in col_str for kw in keywords) and not any(ex in col_str for ex in exclude):
            val = row[col]
            if isinstance(val, pd.Series): val = val.iloc[0]
            val_str = str(val).strip()
            if val_str and val_str.lower() not in ['nan', 'none', 'null']:
                return val_str
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

def check_active_date(date_str):
    if '|' in date_str:
        try:
            s, e = date_str.split('|')
            d_s = datetime.strptime(s, "%Y-%m-%d").date()
            d_e = datetime.strptime(e, "%Y-%m-%d").date()
            return d_s <= datetime.now().date() <= d_e
        except: return True
    return True

def get_date_tuple(date_str):
    if '|' in date_str:
        try:
            s, e = date_str.split('|')
            return [datetime.strptime(s, "%Y-%m-%d").date(), datetime.strptime(e, "%Y-%m-%d").date()]
        except: pass
    return [datetime.now().date(), datetime.now().date() + timedelta(days=7)]

def format_date_output(date_input):
    if isinstance(date_input, tuple) or isinstance(date_input, list):
        if len(date_input) == 2: return f"{date_input[0].strftime('%Y-%m-%d')}|{date_input[1].strftime('%Y-%m-%d')}"
        elif len(date_input) == 1: return f"{date_input[0].strftime('%Y-%m-%d')}|{date_input[0].strftime('%Y-%m-%d')}"
    try: return f"{date_input.strftime('%Y-%m-%d')}|{date_input.strftime('%Y-%m-%d')}"
    except: return f"{datetime.now().strftime('%Y-%m-%d')}|{datetime.now().strftime('%Y-%m-%d')}"


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
                    headers = [str(h).strip() if str(h).strip() else f"Col_{i}" for i, h in enumerate(raw_k[0])]
                    df_k = pd.DataFrame(raw_k[1:], columns=headers)
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
# 6. HEADER & TO-DO WIDGET (LOGIKA ANIMASI CERDAS)
# =====================================================================
def ui_header(logo_base64, pending_count, is_manager):
    logo = f'<img src="data:image/png;base64,{logo_base64}" style="max-height: 50px;">' if logo_base64 else ''
    if is_manager and pending_count > 0:
        notif = f'<div id="bell-notif-btn" style="position:relative; cursor:pointer; transition: transform 0.2s;" title="Klik untuk buka Antrean Izin!"><span class="material-symbols-rounded bell-active" style="font-size:28px;">notifications_active</span><span style="position:absolute; top:-6px; right:-8px; background:#ef4444; color:white; border-radius:50%; padding:2px 6px; font-size:11px; font-weight:800;">{pending_count}</span></div>'
    elif pending_count > 0:
        notif = f'<div style="position:relative;" title="Ada {pending_count} antrean!"><span class="material-symbols-rounded bell-active" style="font-size:28px;">notifications_active</span><span style="position:absolute; top:-6px; right:-8px; background:#ef4444; color:white; border-radius:50%; padding:2px 6px; font-size:11px; font-weight:800;">{pending_count}</span></div>'
    else:
        notif = f'<div style="opacity:0.4;"><span class="material-symbols-rounded" style="font-size:28px; color:#1e293b;">notifications</span></div>'
    
    c_space, c_btn = st.columns([10, 2])
    with c_btn:
        if st.button("🚪 Keluar", use_container_width=True):
            st.query_params.clear() 
            st.session_state.clear()
            st.rerun()

    st.markdown(f"""
    <div class="header-bar" style="margin-top:-10px;">
        <div style="display:flex; align-items:center; gap:20px;">
            <form action="javascript:window.location.reload()"><button type="submit" class="home-btn" title="Home"><span class="material-symbols-rounded">home</span></button></form>
            <div>{logo}</div>
        </div>
        <div style="flex-grow:1; text-align:center;">
            <h1 style="color:#004D95; font-weight:800; font-size:clamp(16px, 3vw, 24px); margin:0;">Dashboard Distribusi Gas NR</h1>
            <span style="font-size:12px; color:#64748b; font-weight:600;">Halo, {st.session_state.user_name} ({st.session_state.user_role})</span>
        </div>
        <div>{notif}</div>
    </div>
    """, unsafe_allow_html=True)

    if is_manager and pending_count > 0:
        components.html("""
        <script>
            setTimeout(() => {
                const pDoc = window.parent.document;
                const bell = pDoc.getElementById('bell-notif-btn');
                if(bell) {
                    bell.onclick = function() {
                        const btns = Array.from(pDoc.querySelectorAll('button'));
                        const mgrBtn = btns.find(b => b.innerText.includes('Panel Manajer'));
                        if(mgrBtn) {
                            mgrBtn.click();
                            setTimeout(() => {
                                const tabs = Array.from(pDoc.querySelectorAll('button[data-baseweb=\\'tab\\']'));
                                const izinTab = tabs.find(t => t.innerText.includes('Persetujuan Izin'));
                                if(izinTab) izinTab.click();
                            }, 500);
                        }
                    };
                }
            }, 1000);
        </script>
        """, height=0, width=0)

def ui_live_hud_widget():
    hari_ini = datetime.now().strftime("%m-%d")
    evt = EVENT_KALENDER.get(hari_ini, "Tidak ada event")
    components.html(f"""
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@600;800&family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,600,1,0" rel="stylesheet">
    <style>
        body {{ margin:0; padding:5px; font-family:'Plus Jakarta Sans'; overflow:hidden; }}
        .hud-container {{ display:flex; align-items:center; gap:20px; background:linear-gradient(145deg, #1e293b, #0f172a); border:1px solid rgba(56,189,248,0.4); border-radius:16px; padding:12px 20px; color:#f8fafc; overflow-x:auto; scrollbar-width:none; }}
        .hud-container::-webkit-scrollbar {{ display:none; }}
        .section {{ display:flex; align-items:center; gap:12px; flex:0 0 auto; border-left: 2px solid rgba(255,255,255,0.1); padding-left: 20px; }}
        .section:first-child {{ border:none; padding-left:0; }}
        .box {{ display:flex; align-items:center; gap:12px; background:rgba(255,255,255,0.05); padding:6px 14px; border-radius:10px; position:relative; cursor: pointer; transition: 0.2s; }}
        .box:hover {{ background:rgba(56,189,248,0.1); }}
        .clock {{ font-size:26px; font-weight:800; color:#38bdf8; text-shadow:0 0 12px rgba(56,189,248,0.4); font-variant-numeric: tabular-nums; }}
        .val {{ color:#4ade80; font-weight:800; font-size:14px; }}
        .event {{ font-size: 13px; font-weight: 700; color: #1e293b; background: #facc15; padding: 6px 14px; border-radius: 8px; box-shadow: 0 0 15px rgba(250,204,21,0.4); display:flex; align-items:center; gap:6px; }}
        #loc-status {{ position: absolute; top: -6px; right: -6px; background: #3b82f6; width: 14px; height: 14px; border-radius: 50%; border: 2px solid #0f172a; display: flex; align-items: center; justify-content: center; }}
    </style>
    <div class="hud-container">
        <div class="section">
            <span class="material-symbols-rounded" style="color:#38bdf8; font-size:30px;">schedule</span>
            <span class="clock" id="clock">--:--:--</span><div style="width:2px; height:30px; background:rgba(255,255,255,0.2);"></div><span id="date" style="font-weight:600;">Memuat...</span>
        </div>
        <div class="section">
            <div class="box" id="compass-box" title="Klik untuk aktifkan sensor kompas">
                <span class="material-symbols-rounded" id="compass" style="color:#f87171; font-size:26px; transition:transform 0.1s ease-out;">navigation</span>
                <div><div id="loc" style="font-size:11px; font-weight:700; color:#cbd5e1;">Mencari GPS...</div><span class="val" id="deg" style="color:#38bdf8;">--°</span></div>
            </div>
        </div>
        <div class="section">
            <div class="box"><span class="material-symbols-rounded" id="w-icon" style="color:#facc15; font-size:26px;">partly_cloudy_day</span>
                <div id="loc-status"><span class="material-symbols-rounded" style="font-size:10px; color:white;" id="loc-icon">location_searching</span></div>
                <div><div id="w-desc" style="font-size:11px; font-weight:700; color:#cbd5e1;">Memuat...</div>
                <span class="material-symbols-rounded" style="font-size:12px; color:#f87171;">thermostat</span><span class="val" id="w-temp" style="margin-right:8px;">--</span>
                <span class="material-symbols-rounded" style="font-size:12px; color:#94a3b8;">air</span><span class="val" id="w-wind">--</span></div>
            </div>
        </div>
        <div class="section"><span class="event"><span class="material-symbols-rounded" style="font-size:16px;">campaign</span> {evt}</span></div>
    </div>
    
    <script>
        function updateTime() {{
            var d = new Date();
            var hrs = String(d.getHours()).padStart(2, '0');
            var min = String(d.getMinutes()).padStart(2, '0');
            var sec = String(d.getSeconds()).padStart(2, '0');
            document.getElementById('clock').innerText = hrs + ':' + min + ':' + sec;
            var options = {{ weekday: 'short', day: 'numeric', month: 'short' }};
            document.getElementById('date').innerText = d.toLocaleDateString('id-ID', options);
        }}
        setInterval(updateTime, 1000); updateTime();

        function fetchWeather(lat, lon) {{
            fetch('https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=' + lat + '&longitude=' + lon + '&localityLanguage=id')
            .then(res => res.json())
            .then(data => {{
                let locName = data.locality || data.city || (lat.toFixed(2) + ", " + lon.toFixed(2));
                document.getElementById('loc').innerText = locName;
            }}).catch(() => {{ document.getElementById('loc').innerText = "Titik Koordinat"; }});
        }}
        if(navigator.geolocation) {{
            navigator.geolocation.watchPosition(
                function(pos) {{ 
                    document.getElementById('loc-status').style.background = '#22c55e';
                    document.getElementById('loc-icon').innerText = 'my_location';
                    fetchWeather(pos.coords.latitude, pos.coords.longitude); 
                }},
                function(err) {{ 
                    document.getElementById('loc-status').style.background = '#ef4444';
                    document.getElementById('loc-icon').innerText = 'location_off';
                    fetchWeather(-6.200000, 106.816666); 
                }},
                {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
            );
        }} else {{ fetchWeather(-6.200000, 106.816666); }}
    </script>
    """, height=90)

def ui_todo_widget():
    td = fetch_todo_from_sheet()
    
    # 1. EVALUASI APAKAH ADA KONTEN YANG VALID (TIDAK EXPIRED DAN TIDAK KOSONG)
    is_msg_active = check_active_date(td.get('main_msg_date', ''))
    is_todo_active = check_active_date(td.get('todo_date', ''))
    
    has_active_msg = is_msg_active and bool(td.get('main_msg', '').strip())
    
    has_active_tasks = False
    if is_todo_active:
        for op, data in td['tasks'].items():
            if data.get('task', '').strip():
                has_active_tasks = True
                break
                
    has_visible_content = has_active_msg or has_active_tasks
    
    # 2. LOGIKA ANIMASI "BARU" CERDAS (Hanya nge-blink jika ada konten valid yang ditampilkan)
    is_new = False
    if has_visible_content and td['last_updated'] and td['last_updated'] != st.session_state.last_seen_todo:
        is_new = True
        components.html("""
        <script>
            setTimeout(() => {
                const pDoc = window.parent.document;
                const expanders = pDoc.querySelectorAll('div[data-testid="stExpander"]');
                if(expanders.length > 0) {
                    expanders[0].classList.add("todo-updated-animation");
                    const summaryText = expanders[0].querySelector("summary p");
                    if(summaryText) summaryText.classList.add("todo-updated-text");
                }
            }, 500);
        </script>
        """, height=0, width=0)
    
    st.markdown("<div style='margin-top:-10px;'></div>", unsafe_allow_html=True)
    expander_title = "📢 PENGUMUMAN & TO-DO LIST HARI INI ✨ BARU" if is_new else "📢 PENGUMUMAN & TO-DO LIST HARI INI"
    
    with st.expander(expander_title):
        if is_new:
            st.session_state.last_seen_todo = td['last_updated']
            
        if has_active_msg:
            st.markdown(f"<div style='background:rgba(56,189,248,0.15); border-left:4px solid #38bdf8; padding:12px 16px; border-radius:8px; margin-bottom:15px;'><b style='color:#38bdf8; font-size:15px;'><span class='material-symbols-rounded' style='font-size:18px; vertical-align:text-bottom;'>campaign</span> Pesan Utama:</b><br><span style='color:#f8fafc; line-height:1.5;'>{td['main_msg']}</span></div>", unsafe_allow_html=True)
        
        if is_todo_active:
            for op, data in td['tasks'].items():
                task_text = data.get('task', '')
                comment_text = data.get('comment', '')
                
                if task_text.strip():
                    st.markdown(f"<div style='background:rgba(255,255,255,0.05); padding:12px; border-radius:8px 8px 0 0; border:1px solid rgba(255,255,255,0.1); border-bottom:none; display:flex; gap:10px; position: relative; z-index: 1;'><span class='material-symbols-rounded' style='color:#4ade80;'>check_circle</span><div style='width:100%;'><b style='color:#4ade80;'>{op}</b><br><span style='color:#cbd5e1; font-size:14px; line-height:1.5;'>{task_text}</span></div></div>", unsafe_allow_html=True)
                    
                    with st.expander(f"💬 Diskusi & Progress"):
                        if comment_text:
                            st.markdown(f"<div style='padding:10px 12px; border-left:3px solid #facc15; background:rgba(0, 0, 0, 0.2); margin-bottom:12px; border-radius:4px; max-height: 200px; overflow-y: auto;'>{comment_text}</div>", unsafe_allow_html=True)
                        
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            reply_msg = st.text_input(f"Balas {op}", placeholder=f"Ketik pesan sebagai {st.session_state.user_name}...", label_visibility="collapsed", key=f"reply_msg_{op}")
                        with c2:
                            if st.button("Kirim", key=f"btn_reply_{op}", use_container_width=True):
                                if reply_msg.strip():
                                    if reply_todo_operator(op, reply_msg, st.session_state.user_name):
                                        st.success("Terkirim!")
                                        time.sleep(1)
                                        st.rerun()
                                else:
                                    st.error("Isi pesan!")
                                    
                    st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)
        
        if not has_visible_content:
            st.info("Belum ada instruksi atau tugas spesifik dari Manajer untuk hari ini.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        components.html("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700&display=swap');
            body { margin: 0; padding: 0; background: transparent; overflow: hidden; }
            button { width: 100%; background: transparent; border: 1px solid rgba(56, 189, 248, 0.4); color: #38bdf8; border-radius: 8px; padding: 8px 0; font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 700; font-size: 14px; cursor: pointer; transition: all 0.2s ease; }
            button:hover { background: rgba(56, 189, 248, 0.1); border-color: #38bdf8; color: #ffffff; }
            button:active { transform: scale(0.95); background: rgba(56, 189, 248, 0.2); }
        </style>
        <button onclick="const pDoc = window.parent.document; const mainExp = pDoc.querySelector('div[data-testid=\\'stExpander\\'] details'); if(mainExp && mainExp.hasAttribute('open')) { mainExp.querySelector('summary').click(); }">⬆️ Tutup Daftar Tugas</button>
        """, height=40)


# =====================================================================
# 7. HALAMAN UTAMA & 8. PANEL MANAJER (Sama Seperti Sebelumnya)
# =====================================================================
def ui_timeline(df_j, df_i):
    st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <h3 class='section-title' style='margin-bottom: 0;'><span class='material-symbols-rounded' style='color:#38bdf8; font-size:28px;'>view_timeline</span> Tinjauan 14 Hari Kedepan</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col_l, col_r = st.columns([1, 1])
    with col_l:
        components.html("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700&display=swap');
            body { margin: 0; padding: 0; background: transparent; overflow: hidden; }
            button { width: 100%; background: transparent; border: 1px solid rgba(56, 189, 248, 0.4); color: #38bdf8; border-radius: 8px; padding: 8px 0; font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 700; font-size: 14px; cursor: pointer; transition: all 0.2s ease; }
            button:hover { background: rgba(56, 189, 248, 0.1); border-color: #38bdf8; color: #ffffff; }
            button:active { transform: scale(0.95); background: rgba(56, 189, 248, 0.3); }
        </style>
        <button onclick="window.parent.document.querySelector('.scroll-container').scrollBy({left: -320, behavior: 'smooth'});">
        ⬅️ Geser Kiri</button>
        """, height=40)
    with col_r:
        components.html("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700&display=swap');
            body { margin: 0; padding: 0; background: transparent; overflow: hidden; }
            button { width: 100%; background: transparent; border: 1px solid rgba(56, 189, 248, 0.4); color: #38bdf8; border-radius: 8px; padding: 8px 0; font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 700; font-size: 14px; cursor: pointer; transition: all 0.2s ease; }
            button:hover { background: rgba(56, 189, 248, 0.1); border-color: #38bdf8; color: #ffffff; }
            button:active { transform: scale(0.95); background: rgba(56, 189, 248, 0.3); }
        </style>
        <button onclick="window.parent.document.querySelector('.scroll-container').scrollBy({left: 320, behavior: 'smooth'});">
        Geser Kanan ➡️</button>
        """, height=40)
    
    if df_j.empty: return st.warning("Sedang menyinkronisasi jadwal...")

    today = datetime.now().date()
    subs_map = {}
    if not df_i.empty:
        col_status = find_col(df_i, ['status', 'approval', 'appr'])
        if col_status and col_status in df_i.columns:
            appr_df = df_i[df_i[col_status].astype(str).str.upper().str.contains('APPROVED', na=False)]
            for _, row in appr_df.iterrows():
                try:
                    sub = str(get_val(row, ['pengganti', 'backup'], fallback_idx=7)).strip().lower()
                    if sub and sub not in ['nan', '-']:
                        tgl_m = get_val(row, ['mulai', 'dari'], default=today.strftime('%d/%m/%Y'), fallback_idx=3)
                        tgl_s = get_val(row, ['selesai', 'sampai'], default=today.strftime('%d/%m/%Y'), fallback_idx=4)
                        for d in pd.date_range(pd.to_datetime(tgl_m, dayfirst=True).date(), pd.to_datetime(tgl_s, dayfirst=True).date()):
                            subs_map.setdefault(d.strftime('%Y-%m-%d'), []).append(sub)
                except Exception: pass

    html = '<div class="scroll-container">'
    for i in range(14):
        d_obj = today + timedelta(days=i)
        d_str = d_obj.strftime('%Y-%m-%d')
        
        is_today = (i == 0)
        card_class = "scroll-card today-card" if is_today else "scroll-card"
        header_class = "scroll-header today-header" if is_today else "scroll-header"
        date_text = f"⭐ HARI INI - {d_obj.strftime('%d %b %Y')}" if is_today else d_obj.strftime("%d %b %Y")
        
        html += f'<div class="{card_class}"><div class="{header_class}">{date_text}</div>'
        
        if d_str in df_j.columns:
            day_df = df_j[['Nama Operator', d_str]].dropna()
            day_df = day_df[~day_df[d_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])]
            
            if not day_df.empty:
                for _, row in day_df.iterrows():
                    name = str(row['Nama Operator']).replace('*', '').strip()
                    status = str(row[d_str]).upper()
                    
                    if any(k in status for k in ["DINAS", "PD"]): 
                        badge = f'<div class="status-badge" style="background:rgba(249,115,22,0.15); color:#fdba74;"><div class="status-dot" style="background:#f97316;"></div>{status}</div>'
                    elif any(k in status for k in ["IZIN", "SAKIT", "CUTI"]): 
                        badge = f'<div class="status-badge" style="background:rgba(239,68,68,0.15); color:#fca5a5;"><div class="status-dot" style="background:#ef4444;"></div>{status}</div>'
                    elif name.lower() in subs_map.get(d_str, []): 
                        badge = f'<div class="status-badge" style="background:rgba(56,189,248,0.15); color:#7dd3fc;"><div class="status-dot" style="background:#38bdf8;"></div>SUB / {status}</div>'
                    else: 
                        badge = f'<div class="status-badge" style="background:rgba(34,197,94,0.15); color:#4ade80;"><div class="status-dot" style="background:#22c55e;"></div>SHIFT {status}</div>'
                        
                    html += f'<div class="scroll-item"><b style="color:#f8fafc; font-size:14px;">{name}</b><br>{badge}</div>'
            else: 
                html += '<div class="scroll-item" style="text-align:center; color:#64748b; font-style:italic; border:none;">Semua OFF</div>'
        else: 
            html += '<div class="scroll-item" style="text-align:center; color:#64748b; font-style:italic; border:none;">Data belum dirilis</div>'
        
        html += '</div>'
    st.markdown(html + '</div>', unsafe_allow_html=True)
    st.markdown("<hr style='opacity:0.1;'>", unsafe_allow_html=True)


def ui_off_tracker(df_j, df_k):
    st.markdown("<h3 class='section-title'><span class='material-symbols-rounded' style='color:#38bdf8; font-size:28px;'>group_off</span> Pencarian Personel OFF</h3>", unsafe_allow_html=True)
    tgl_cek = st.date_input("Pilih Tanggal Pengecekan:", value=datetime.now().date())
    tgl_str = tgl_cek.strftime('%Y-%m-%d')
    
    if df_j.empty or tgl_str not in df_j.columns:
        st.warning("Data jadwal belum dirilis untuk tanggal ini.")
        return st.link_button("Form Pengajuan", URL_GFORM, use_container_width=True, type="primary")

    valid_df = df_j.dropna(subset=['Nama Operator'])
    off_list = valid_df[valid_df[tgl_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])]["Nama Operator"].astype(str).tolist()
    
    with st.container(border=True):
        if not off_list: st.write("Seluruh personel bertugas hari ini.")
        else:
            col_n = find_col(df_k, ['nama', 'operator'], None)
            col_hp = find_col(df_k, ['contact', 'kontak', 'hp'], None)

            for i, name in enumerate(off_list):
                hp = "Tidak terdaftar"
                if col_n and col_hp and not df_k.empty:
                    clean_db = df_k[col_n].astype(str).str.replace('*','', regex=False).str.strip().str.lower()
                    target = str(name).replace('*','').strip().lower()
                    match = df_k[clean_db == target]
                    if match.empty: match = df_k[clean_db.str.contains(target, na=False)]
                    if not match.empty: hp = str(match.iloc[0][col_hp]).strip()

                st.markdown(f"<details class='off-personnel' style='animation: slideInRight 0.3s {i*0.05}s ease-out backwards;'><summary><div style='background:rgba(56,189,248,0.15); color:#38bdf8; padding:4px 8px; border-radius:4px; font-size:11px; margin-right:10px;'>OFF</div><span style='font-size:14px;'>{name}</span><span class='material-symbols-rounded chevron-icon'>expand_more</span></summary><div class='off-details-content'><div style='display:flex; align-items:center; gap:8px; margin-top:8px;'><span class='material-symbols-rounded' style='color:#94a3b8; font-size:18px;'>call</span><span style='color:#94a3b8;'>No. Handphone:</span> <b style='color:#e2e8f0; font-size:14px; letter-spacing:0.5px;'>{hp}</b></div></div></details>", unsafe_allow_html=True)
                
    st.markdown("<br>", unsafe_allow_html=True)
    st.link_button("Ajukan Form Izin / Tukar Shift", URL_GFORM, use_container_width=True, type="primary")

def ui_kalender_lengkap(df_j):
    st.markdown("<h3 class='section-title'><span class='material-symbols-rounded' style='color:#38bdf8; font-size:28px;'>event_note</span> Pencarian Jadwal Spesifik</h3>", unsafe_allow_html=True)
    with st.container(border=True): tgl = st.date_input("Pilih Tanggal Pengecekan:", key="tgl_lengkap").strftime('%Y-%m-%d')
    
    if df_j.empty or tgl not in df_j.columns:
        st.warning("⚠️ Data jadwal untuk tanggal ini belum tersedia.")
    else:
        st.markdown(f"<br><h4 style='color:white; font-size:18px; display:flex; align-items:center; gap:8px;'><span class='material-symbols-rounded' style='color:#94a3b8;'>check_circle</span> Status Personel: <b style='color:#38bdf8;'>{tgl}</b></h4>", unsafe_allow_html=True)
        df_day = df_j[['Nama Operator', tgl]].dropna().copy()
        df_day['Status'] = df_day[tgl].fillna('').astype(str).str.strip().str.upper()

        df_off = df_day[df_day['Status'].isin(['OFF', 'NAN', '', 'NONE'])]
        df_abs = df_day[df_day['Status'].str.contains('IZIN|SAKIT|CUTI|DINAS|PD', na=False)]
        df_hdr = df_day[~df_day['Nama Operator'].isin(df_off['Nama Operator']) & ~df_day['Nama Operator'].isin(df_abs['Nama Operator'])]

        for title, df_data, clr_border, clr_bg, show_sts in [("Hadir / Bertugas", df_hdr, "rgba(34,197,94,0.4)", "rgba(34,197,94,0.15)", True), ("Sedang OFF", df_off, "rgba(56,189,248,0.4)", "rgba(56,189,248,0.15)", False), ("Absen / Dinas Luar", df_abs, "rgba(239,68,68,0.4)", "rgba(239,68,68,0.15)", True)]:
            with st.container(border=True):
                st.markdown(f"<div style='background:{clr_bg}; padding:12px; border-radius:8px; border:1px solid {clr_border}; margin-bottom:12px; display:flex; align-items:center; gap:8px;'><b style='color:white; font-size:15px;'>{title} ({len(df_data)})</b></div>", unsafe_allow_html=True)
                if not df_data.empty: st.dataframe(df_data[['Nama Operator', 'Status']] if show_sts else df_data[['Nama Operator']], hide_index=True, use_container_width=True)
                else: st.write("Tidak ada data pada kategori ini.")


def ui_manager_panel(df_i, df_j):
    st.markdown("<h3 class='section-title'><span class='material-symbols-rounded' style='color:#38bdf8;'>admin_panel_settings</span> Panel Manajer</h3>", unsafe_allow_html=True)
    approver_name = st.session_state.user_name

    tab_izin, tab_edit, tab_todo = st.tabs(["📋 Panel Persetujuan Izin", "⚙️ Panel Edit & AI", "📝 To-Do List Harian"])
    
    with tab_izin:
        col_status = find_col(df_i, ['status', 'approval', 'appr'])
        if not col_status and not df_i.empty:
            df_i["Status Approval"] = ""
            col_status = "Status Approval"
            
        if df_i.empty: 
            st.info("Tugas selesai. Tidak ada antrean izin saat ini.")
        else:
            pending_df = df_i[df_i[col_status].astype(str).str.lower().isin(["", "nan", "none", "null"])]

            col_hdr1, col_hdr2 = st.columns([2, 1])
            with col_hdr1: st.markdown("<br><h4 style='color:white; font-size:16px; margin-top:0; display:flex; align-items:center; gap:6px;'><span class='material-symbols-rounded' style='font-size:20px; color:#facc15;'>pending_actions</span> Antrean Persetujuan</h4>", unsafe_allow_html=True)
            with col_hdr2:
                if not pending_df.empty:
                    if st.button("🗑️ Hapus Semua Antrean"): clear_pending_requests(df_i)

            if pending_df.empty: st.info("Tugas selesai. Tidak ada antrean izin saat ini.")
            else:
                rendered_count = 0
                for idx, row in pending_df.iterrows():
                    rendered_count += 1
                    with st.container(border=True):
                        st.markdown(generate_izin_card_html(row, delay=rendered_count*0.1), unsafe_allow_html=True)
                        c1, c2 = st.columns(2)
                        if c1.button("✓ Setujui (Approve)", key=f"app_{idx}", type="primary", use_container_width=True): 
                            with st.spinner("Menyimpan..."): execute_database_action(idx, row, "APPROVE", approver_name, df_j, df_i)
                        if c2.button("✕ Tolak (Reject)", key=f"rej_{idx}", use_container_width=True): 
                            with st.spinner("Menolak..."): execute_database_action(idx, row, "REJECT", approver_name, df_j, df_i)

            st.markdown("<hr style='opacity:0.1; margin: 30px 0;'><h4 style='color:white; font-size:16px; display:flex; align-items:center; gap:6px;'><span class='material-symbols-rounded' style='font-size:20px; color:#94a3b8;'>history</span> Riwayat Terakhir</h4>", unsafe_allow_html=True)
            history_df = df_i[df_i[col_status].astype(str).str.upper().str.contains('APPROVED|REJECTED', regex=True, na=False)]
            
            if history_df.empty: st.info("Belum ada riwayat keputusan yang tercatat.")
            else:
                for _, row in history_df.tail(5).iloc[::-1].iterrows():
                    status = str(row[col_status]).upper()
                    is_appr = "APPROVED" in status
                    c_text, c_bg, icon = ("#4ade80", "rgba(34,197,94,0.15)", "check_circle") if is_appr else ("#fca5a5", "rgba(239,68,68,0.15)", "cancel")
                    nama_pengaju = get_val(row, ['nama', 'pengaju', 'operator', 'lengkap'], exclude=['pengganti'], default='Tidak Diketahui', fallback_idx=1)
                    t_mulai = get_val(row, ['mulai', 'dari'], default='-', fallback_idx=3)
                    t_selesai = get_val(row, ['selesai', 'sampai'], default='-', fallback_idx=4)
                    mark = "✅" if is_appr else "❌"
                    
                    with st.container(border=True):
                        st.markdown(f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;'><div><b style='font-size:15px; color:white;'>{mark} {nama_pengaju}</b><br><span style='font-size:12px; color:#94a3b8;'>{t_mulai} s/d {t_selesai}</span></div><div style='background:{c_bg}; color:{c_text}; padding:6px 12px; border-radius:8px; font-size:11px; font-weight:700; display:flex; align-items:center; gap:4px;'><span class='material-symbols-rounded' style='font-size:14px;'>{icon}</span> {status}</div></div>", unsafe_allow_html=True)
                        if st.button("⟲ Batalkan Keputusan", key=f"undo_{_}", use_container_width=True): 
                            with st.spinner("Membatalkan..."): execute_database_action(_, row, "UNDO", approver_name, df_j, df_i)

    with tab_edit:
        st.markdown("<br><div style='background:rgba(15,23,42,0.6); padding:16px; border-radius:12px; border-left:4px solid #38bdf8; margin-bottom:24px; display:flex; align-items:center; gap:10px;'><span class='material-symbols-rounded' style='color:#38bdf8;'>database</span> <b style='color:#f8fafc;'>Akses Database Utama</b></div>", unsafe_allow_html=True)
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1: st.link_button("Edit Jadwal Aktual", URL_JADWAL, use_container_width=True)
        with c_btn2: st.link_button("Edit Database Izin", URL_IZIN, use_container_width=True)
        
        st.markdown("<hr style='opacity:0.1; margin: 30px 0;'><h4 style='color:white; font-size:16px; display:flex; align-items:center; gap:6px;'><span class='material-symbols-rounded' style='font-size:20px; color:#38bdf8;'>smart_toy</span> Asisten Jadwal Pintar (BETA)</h4>", unsafe_allow_html=True)
        st.markdown("<div style='background: rgba(56,189,248,0.1); border: 1px solid rgba(56,189,248,0.3); border-radius: 12px 12px 12px 0; padding: 12px 16px; margin-bottom: 10px; font-size: 14px; line-height: 1.5;'><span style='background: #0ea5e9; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 800; margin-right: 6px;'>AI</span> Halo! Saya asisten jadwal. Anda bisa menyuruh saya mengubah jadwal tanpa harus repot membuka dropdown.</div>", unsafe_allow_html=True)
        
        perintah = st.text_input("Ketik perintah Anda di sini:", placeholder="Tulis instruksi...")
        if st.button("Kirim Perintah", type="primary"):
            if not perintah: st.error("Silakan ketik perintah terlebih dahulu.")
            else:
                parsed = parse_natural_language_schedule(perintah, df_j)
                if not parsed['nama']: st.error("❌ Saya tidak menemukan nama personel tersebut di database.")
                elif not parsed['status']: st.error("❌ Saya tidak menangkap status yang diinginkan (sakit/cuti/off/pagi/malam).")
                elif not parsed['tgl_mulai']: st.error("❌ Saya tidak mengerti tanggalnya. Coba gunakan angka atau rentang.")
                else: st.session_state.ai_parsed_data = parsed

        if st.session_state.get('ai_parsed_data'):
            p = st.session_state.ai_parsed_data
            tgl_str = p['tgl_mulai'].strftime('%d %b %Y') if p['tgl_mulai'] == p['tgl_selesai'] else f"{p['tgl_mulai'].strftime('%d %b')} - {p['tgl_selesai'].strftime('%d %b %Y')}"
            st.markdown(f"<div style='background:rgba(234,179,8,0.15); border:1px solid rgba(234,179,8,0.5); padding:16px; border-radius:12px; margin-top:10px;'><b style='color:#facc15;'>Konfirmasi Tindakan:</b><br>Apakah Anda yakin ingin mengubah jadwal <b>{p['nama']}</b> menjadi <b style='color:#38bdf8;'>{p['status']}</b> untuk tanggal <b>{tgl_str}</b>?</div>", unsafe_allow_html=True)
            c_y, c_n = st.columns(2)
            if c_y.button("✅ Ya, Eksekusi", use_container_width=True, type="primary"):
                execute_smart_edit(p['nama'], p['status'], p['tgl_mulai'], p['tgl_selesai'], df_j)
                st.session_state.ai_parsed_data = None
            if c_n.button("❌ Batal", use_container_width=True):
                st.session_state.ai_parsed_data = None
                st.rerun()

    with tab_todo:
        td = fetch_todo_from_sheet()
        is_msg_active = check_active_date(td.get('main_msg_date', ''))
        is_todo_active = check_active_date(td.get('todo_date', ''))
        
        st.markdown("<br><b style='color:#38bdf8;'>Status Penayangan Saat Ini</b>", unsafe_allow_html=True)
        
        if td['main_msg'].strip():
            status_lbl = "🟢 AKTIF" if is_msg_active else "🔴 EXPIRED"
            date_disp = td.get('main_msg_date','').replace('|',' s/d ')
            if is_msg_active: st.info(f"**{status_lbl} Pengumuman** ({date_disp}):\n\n{td['main_msg']}")
            else: st.warning(f"**{status_lbl} Pengumuman** ({date_disp}):\n\n{td['main_msg']}")
        
        todo_count = len([t for t in td['tasks'].values() if t.get('task', '').strip()])
        if todo_count > 0:
            status_lbl_t = "🟢 AKTIF" if is_todo_active else "🔴 EXPIRED"
            date_disp_t = td.get('todo_date','').replace('|',' s/d ')
            if is_todo_active: st.success(f"**{status_lbl_t} To-Do List** ({date_disp_t}): Ada {todo_count} tugas berjalan.")
            else: st.error(f"**{status_lbl_t} To-Do List** ({date_disp_t}): Ada {todo_count} tugas tersimpan.")
            
        if not td['main_msg'].strip() and todo_count == 0:
            st.write("Belum ada data Pengumuman atau To-Do List.")
            
        with st.expander("✏️ Edit Pengumuman & Tugas Individu", expanded=True):
            st.warning("Perubahan di bawah ini akan langsung disimpan permanen ke dalam Google Sheets.")
            
            st.markdown("<b style='color:#4ade80;'>1. Pengumuman Utama</b>", unsafe_allow_html=True)
            new_main_msg = st.text_area("Isi Pengumuman / Briefing Umum:", value=td['main_msg'])
            new_msg_dates = st.date_input("Periode Tayang Pengumuman:", value=get_date_tuple(td.get('main_msg_date', '')))
            
            st.markdown("<hr style='opacity:0.2;'><b style='color:#4ade80;'>2. Tugas Spesifik Individu (To-Do List)</b>", unsafe_allow_html=True)
            new_todo_dates = st.date_input("Periode Tayang To-Do List:", value=get_date_tuple(td.get('todo_date', '')))
            
            operator_list = []
            if not df_j.empty and 'Nama Operator' in df_j.columns:
                operator_list = sorted(df_j['Nama Operator'].dropna().astype(str).str.replace('*','', regex=False).str.strip().unique())
                operator_list = [o for o in operator_list if o.lower() not in ['nan', 'none', '']]
            
            new_tasks = {}
            for op in operator_list:
                old_task = td['tasks'].get(op, {}).get('task', "")
                old_comment = td['tasks'].get(op, {}).get('comment', "")
                
                st.markdown(f"<b style='font-size:14px; color:#e2e8f0;'>{op}</b>", unsafe_allow_html=True)
                new_tasks[op] = st.text_input(f"Tugas {op}:", value=old_task, label_visibility="collapsed", placeholder=f"Tugas untuk {op}...")
                
                if old_comment:
                    st.markdown(f"<div style='font-size:13px; color:#facc15; margin-top:-10px; margin-bottom:10px; padding:8px; background:rgba(0,0,0,0.2); border-radius:4px; max-height:100px; overflow-y:auto;'><span class='material-symbols-rounded' style='font-size:14px; vertical-align:middle;'>chat</span> <b>Balasan:</b><br>{old_comment}</div>", unsafe_allow_html=True)
                
            col_save, col_clear = st.columns(2)
            
            date_to_save_msg = format_date_output(new_msg_dates)
            date_to_save_todo = format_date_output(new_todo_dates)
            
            if col_save.button("💾 Simpan Perubahan ke Database", type="primary", use_container_width=True):
                if push_todo_to_sheet(new_main_msg, date_to_save_msg, date_to_save_todo, new_tasks):
                    st.success("✅ Berhasil diperbarui!")
                    time.sleep(1)
                    st.rerun()
            if col_clear.button("🗑️ Bersihkan Semua", use_container_width=True):
                if push_todo_to_sheet("", "", "", {}):
                    st.success("✅ To-Do List berhasil dikosongkan!")
                    time.sleep(1)
                    st.rerun()

# =====================================================================
# RUNNER UTAMA
# =====================================================================
if __name__ == "__main__":
    is_login_page = not st.session_state.get('logged_in', False)
    inject_custom_css(get_base64_image("orfmk2.jpg"), get_base64_image("logo-pertaminaregasv2.png"), is_login=is_login_page)

    df_j, df_i, df_k = load_all_data()

    if is_login_page:
        ui_login(df_j)
    else:
        col_status_global = find_col(df_i, ['status', 'approval', 'appr'])
        pending_count = 0
        if not df_i.empty and col_status_global and col_status_global in df_i.columns:
            df_v = df_i[df_i[col_status_global].astype(str).str.lower().isin(["", "nan", "none", "null"])]
            pending_count = len(df_v)

        ui_header(get_base64_image("pertamina.png"), pending_count, is_manager=(st.session_state.user_role == "Manajer"))
        ui_live_hud_widget() 
        ui_todo_widget()

        if 'menu' not in st.session_state: st.session_state.menu = "Dash"
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.session_state.user_role == "Manajer":
            c1, c2, c3 = st.columns(3)
            with c1: st.button("Dashboard Utama", type="primary" if st.session_state.menu == "Dash" else "secondary", on_click=lambda: st.session_state.update(menu="Dash"), use_container_width=True)
            with c2: st.button("Kalender Lengkap", type="primary" if st.session_state.menu == "Kal" else "secondary", on_click=lambda: st.session_state.update(menu="Kal"), use_container_width=True)
            with c3: st.button("Panel Manajer", type="primary" if st.session_state.menu == "Mgr" else "secondary", on_click=lambda: st.session_state.update(menu="Mgr"), use_container_width=True)
        else:
            c1, c2 = st.columns(2)
            with c1: st.button("Dashboard Utama", type="primary" if st.session_state.menu == "Dash" else "secondary", on_click=lambda: st.session_state.update(menu="Dash"), use_container_width=True)
            with c2: st.button("Kalender Lengkap", type="primary" if st.session_state.menu == "Kal" else "secondary", on_click=lambda: st.session_state.update(menu="Kal"), use_container_width=True)
            
        st.markdown("<br>", unsafe_allow_html=True)

        ui_timeline(df_j, df_i)

        if st.session_state.menu == "Dash":
            col_m, col_s = st.columns([2.5, 1.5])
            with col_m: st.info("Pilih tab menu di atas untuk melakukan fungsi lebih lanjut.")
            with col_s: ui_off_tracker(df_j, df_k)
        elif st.session_state.menu == "Kal": ui_kalender_lengkap(df_j)
        elif st.session_state.menu == "Mgr" and st.session_state.user_role == "Manajer": ui_manager_panel(df_i, df_j)
