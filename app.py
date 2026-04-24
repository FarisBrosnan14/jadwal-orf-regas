import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
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
    favicon = Image.open("pertamina.png")
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

    # FITUR SSO (AUTO-LOGIN VIA TOKEN DI URL)
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
# 2. UTILITIES & AI PARSER
# =====================================================================
@st.cache_data
def get_base64_image(file_name):
    try:
        with open(file_name, 'rb') as f: return base64.b64encode(f.read()).decode()
    except Exception: return None

def find_col(df, keywords, default_name):
    if df.empty: return default_name
    for col in df.columns:
        if any(kw in str(col).lower() for kw in keywords): return col
    return default_name

def get_val(row, keywords, default='-'):
    """Mengambil nilai baris dengan pelindung anti-error (Tahan banting terhadap duplikasi/NaN)"""
    for col in row.index:
        if any(kw in str(col).lower() for kw in keywords):
            val = row[col]
            if isinstance(val, pd.Series): 
                val = val.iloc[0] # Ambil data pertama jika kolom duplikat
            val_str = str(val).strip()
            if val_str.lower() in ['nan', 'none', 'null', '']:
                return default
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

def generate_izin_card_html(row, delay):
    """Nama fungsi diganti agar terlepas dari konflik kode lama"""
    nama = get_val(row, ['nama', 'pengaju', 'operator', 'lengkap'], 'Tidak Diketahui')
    tgl_mulai = get_val(row, ['mulai', 'dari'], '-')
    tgl_selesai = get_val(row, ['selesai', 'sampai'], '-')
    shift = get_val(row, ['shift'], 'Pg')
    alasan = get_val(row, ['alasan', 'keterangan'], 'Tidak ada keterangan')
    bukti = get_val(row, ['bukti', 'upload', 'dokumen'], '')
    pengganti = get_val(row, ['pengganti', 'backup', 'ganti'], '-')
    jenis = get_val(row, ['jenis', 'kategori', 'izin'], 'Izin')
    
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


# =====================================================================
# 3. DATABASE (GSPREAD) - PEMBERSIHAN KETAT BARIS HANTU
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
            df_j = df_j.dropna(how='all') # Hapus baris kosong absolut
            if 'Nama Operator' in df_j.columns:
                df_j = df_j[df_j['Nama Operator'].astype(str).str.strip() != '']
    except: pass

    try:
        ws_i_data = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0).get_all_values()
        if len(ws_i_data) > 1:
            headers_i = [str(h).strip() if str(h).strip() else f"Col_{i}" for i, h in enumerate(ws_i_data[0])]
            df_i = pd.DataFrame(ws_i_data[1:], columns=headers_i)
            df_i = df_i.dropna(how='all')
            
            # PEMBUNUH BARIS HANTU: Hapus jika Timestamp kosong
            if len(df_i.columns) > 0:
                col_0 = df_i.columns[0]
                df_i = df_i[df_i[col_0].astype(str).str.strip() != '']
                df_i = df_i[~df_i[col_0].astype(str).str.lower().isin(['nan', 'none', 'null'])]
    except: pass
    
    return df_j, df_i

@st.cache_data(ttl=60)
def fetch_todo_from_sheet():
    client = get_client()
    default_data = {"main_msg": "", "tasks": {}, "last_updated": ""}
    if not client: return default_data
    try:
        sh = client.open_by_key(ID_SHEET_JADWAL)
        try:
            ws = sh.worksheet("To_Do_List")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title="To_Do_List", rows=100, cols=3)
            ws.append_row(["Target", "Task", "Comment"])
        
        records = ws.get_all_records()
        for r in records:
            target = str(r.get("Target", ""))
            task = str(r.get("Task", ""))
            comment = str(r.get("Comment", ""))
            
            if target == "PENGUMUMAN_UTAMA":
                default_data["main_msg"] = task
            elif target == "LAST_UPDATED":
                default_data["last_updated"] = task
            elif target:
                default_data["tasks"][target] = {"task": task, "comment": comment}
        return default_data
    except:
        return default_data

def push_todo_to_sheet(main_msg, tasks_dict):
    client = get_client()
    if not client: return False
    try:
        sh = client.open_by_key(ID_SHEET_JADWAL)
        try:
            ws = sh.worksheet("To_Do_List")
        except:
            ws = sh.add_worksheet(title="To_Do_List", rows=100, cols=3)
        
        existing_data = fetch_todo_from_sheet()
        ws.clear()
        time.sleep(0.5)
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [["Target", "Task", "Comment"], ["PENGUMUMAN_UTAMA", main_msg, ""], ["LAST_UPDATED", timestamp, ""]]
        
        for op, task in tasks_dict.items():
            if task.strip():
                old_comment = existing_data["tasks"].get(op, {}).get("comment", "")
                rows.append([op, task.strip(), old_comment])
        
        try: ws.update(values=rows, range_name="A1")
        except:
            try: ws.update("A1", rows)
            except: ws.append_rows(rows)
                
        fetch_todo_from_sheet.clear()
        return True
    except Exception as e:
        return False

def reply_todo_operator(nama_operator, komentar, user_name):
    client = get_client()
    if not client: return False
    try:
        sh = client.open_by_key(ID_SHEET_JADWAL)
        ws = sh.worksheet("To_Do_List")
        
        header = ws.row_values(1)
        if len(header) < 3 or header[2] != "Comment":
            ws.update_cell(1, 3, "Comment")
        
        records = ws.get_all_records()
        for i, r in enumerate(records):
            if str(r.get("Target", "")) == nama_operator:
                old_comment = str(r.get("Comment", ""))
                time_str = datetime.now().strftime("%H:%M")
                
                new_chat = f"<div style='margin-bottom:4px;'><span style='color:#94a3b8; font-size:11px;'>[{time_str}]</span> <b style='color:#38bdf8;'>{user_name}:</b> <span style='color:#e2e8f0;'>{komentar}</span></div>"
                final_comment = f"{old_comment}{new_chat}" if old_comment else new_chat
                
                ws.update_cell(i + 2, 3, final_comment)
                fetch_todo_from_sheet.clear()
                return True
        return False
    except:
        return False

def load_all_data():
    df_j, df_i = load_jadwal_izin_data()
    df_k = load_kontak_data()
    return df_j, df_i, df_k

def execute_database_action(idx, row, action_type, approver_name, df_j, df_i):
    client = get_client()
    if not client: return st.error("Gagal terhubung.")
    try:
        sh_izin = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0)
        
        col_status = find_col(df_i, ['status', 'approval', 'appr'], None)
        if col_status:
            c_idx = list(df_i.columns).index(col_status) + 1
        else:
            c_idx = len(df_i.columns) + 1
            sh_izin.update_cell(1, c_idx, "Status Approval")
            
        status_text = f"APPROVED by {approver_name}" if action_type=="APPROVE" else f"REJECTED by {approver_name}" if action_type=="REJECT" else ""
        sh_izin.update_cell(int(idx)+2, c_idx, status_text)
        
        stat = str(get_val(row, ['status', 'approval'], '')).upper()
        if action_type == "APPROVE" or (action_type == "UNDO" and "APPROVED" in stat):
            sh_aktual = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual")
            
            t_mulai = get_val(row, ['mulai', 'dari'])
            t_selesai = get_val(row, ['selesai', 'sampai'])
            
            try:
                d_start = pd.to_datetime(t_mulai, dayfirst=True).date()
                d_end = pd.to_datetime(t_selesai, dayfirst=True).date()
            except:
                st.error("Format tanggal tidak valid. Lewati integrasi jadwal.")
                return
            
            app = str(get_val(row, ['nama', 'pengaju', 'operator', 'lengkap'], '')).strip().lower()
            sub = str(get_val(row, ['pengganti', 'backup'], '')).strip().lower()
            jenis = str(get_val(row, ['jenis', 'kategori'], 'IZIN')).upper()
            shift = str(get_val(row, ['shift'], 'PG')).title()
            
            updates = []
            for d in pd.date_range(d_start, d_end):
                d_str = d.strftime('%Y-%m-%d')
                if d_str in df_j.columns:
                    c_date = list(df_j.columns).index(d_str) + 1
                    v_app = jenis if action_type == "APPROVE" else shift
                    v_sub = shift if action_type == "APPROVE" else 'OFF'
                    
                    m_p = df_j[df_j.iloc[:,0].astype(str).str.strip().str.lower() == app]
                    if not m_p.empty: updates.append(gspread.Cell(int(m_p.index[0])+2, c_date, v_app))
                    if sub and sub not in ['nan', 'tidak ada', '-', '']:
                        m_s = df_j[df_j.iloc[:,0].astype(str).str.strip().str.lower() == sub]
                        if not m_s.empty: updates.append(gspread.Cell(int(m_s.index[0])+2, c_date, v_sub))
            if updates: sh_aktual.update_cells(updates)
        load_jadwal_izin_data.clear()
        st.rerun()
    except Exception as e: st.error(f"Error API: {e}")

def execute_smart_edit(nama, status, d_start, d_end, df_j):
    client = get_client()
    try:
        sh_aktual = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual")
        updates = []
        match_p = df_j[df_j.iloc[:,0].astype(str).str.replace('*', '', regex=False).str.strip().str.lower() == nama.replace('*', '').strip().lower()]
        if not match_p.empty:
            r_idx = int(match_p.index[0]) + 2
            for d in pd.date_range(d_start, d_end):
                d_str = d.strftime('%Y-%m-%d')
                if d_str in df_j.columns: updates.append(gspread.Cell(r_idx, list(df_j.columns).index(d_str) + 1, status.upper()))
            if updates: 
                sh_aktual.update_cells(updates)
                load_jadwal_izin_data.clear()
                time.sleep(1)
                st.rerun()
    except: pass

def clear_pending_requests(df_i):
    client = get_client()
    try:
        col_status = find_col(df_i, ['status', 'approval', 'appr'], None)
        if not col_status or col_status not in df_i.columns:
            return st.info("Tidak ada antrean yang harus dihapus.")
            
        sh_izin = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0)
        col_nama = find_col(df_i, ['nama', 'operator', 'lengkap', 'pengaju'], None)
        if not col_nama: return
        
        df_valid = df_i[~df_i[col_nama].astype(str).str.lower().isin(["", "nan", "none", "null"])]
        pending_rows = df_valid[df_valid[col_status].astype(str).str.strip().str.lower().isin(["", "nan", "none", "null"])]
        
        if pending_rows.empty: return st.info("Tidak ada antrean.")
        indices = sorted([int(idx) + 2 for idx in pending_rows.index], reverse=True)
        for r in indices: sh_izin.delete_rows(r)
        load_jadwal_izin_data.clear()
        time.sleep(1)
        st.rerun()
    except Exception as e: st.error(f"Error: {e}")


# =====================================================================
# 4. CSS INJECTION KONDISIONAL (LOGIN VS DASHBOARD)
# =====================================================================
def inject_custom_css(bg_base64, logo_base64, is_login=False):
    bg_img = f"url('data:image/jpeg;base64,{bg_base64}')" if bg_base64 else ""
    
    css = "<style>\n"
    css += "@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&display=swap');\n"
    css += "@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0');\n"
    
    css += "html, body, .stApp { font-family: 'Plus Jakarta Sans', sans-serif !important; color: #f8fafc; }\n"
    css += "[data-testid=\"collapsedControl\"] { display: none; }\n"
    css += ".block-container { max-width: 1200px !important; padding-top: 2rem !important; }\n"
    css += "header[data-testid=\"stHeader\"] { display: none !important; }\n"
    css += ".stMarkdown a.header-anchor, svg.icon-link { display: none !important; }\n" 
    
    if is_login:
        # ---------------- HALAMAN LOGIN (ANTI OVERRIDE DARK MODE) ----------------
        bg_overlay = "rgba(15,23,42,0.4), rgba(15,23,42,0.7)" 
        css += f".stApp {{ background-image: linear-gradient({bg_overlay}), {bg_img} !important; background-size: cover; background-attachment: fixed; background-position: center; }}\n"
        
        css += """
        /* KOTAK LOGIN KACA GELAP */
        div[data-testid="stVerticalBlockBorderWrapper"],
        div[data-testid="stVerticalBlock"] > div[style*="border"] {
            background-color: rgba(15, 23, 42, 0.65) !important;
            background: rgba(15, 23, 42, 0.65) !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            border-radius: 16px !important;
            box-shadow: 0 20px 50px rgba(0,0,0,0.6) !important;
            padding: 30px !important;
        }
        
        /* TULISAN JUDUL (PUTIH TERANG MUTLAK) */
        .login-title { color: #ffffff !important; font-weight: 900 !important; text-align: center; font-size: 34px; margin-bottom: 5px; letter-spacing: 1px; text-shadow: 0 2px 5px rgba(0,0,0,0.8) !important; -webkit-text-fill-color: #ffffff !important;}
        .login-subtitle { color: #e2e8f0 !important; text-align: center; margin-bottom: 30px; font-weight: 600; font-size: 15px; text-shadow: 0 1px 3px rgba(0,0,0,0.8) !important; -webkit-text-fill-color: #e2e8f0 !important;}
        
        div[data-testid="stVerticalBlockBorderWrapper"] label p, 
        div[data-testid="stVerticalBlockBorderWrapper"] .stMarkdown p { 
            color: #ffffff !important; font-weight: 700 !important; text-shadow: 0 1px 3px rgba(0,0,0,0.8) !important; -webkit-text-fill-color: #ffffff !important;
        }
        
        /* ISIAN FORM (PUTIH ABU) */
        div[data-baseweb="input"] > div, 
        div[data-baseweb="select"] > div {
            background-color: #f1f5f9 !important; 
            border: 2px solid #cbd5e1 !important;
            border-radius: 8px !important;
            min-height: 42px !important;
        }
        
        /* TEKS INPUT (HITAM PEKAT) */
        div[data-baseweb="input"] input, 
        div[data-baseweb="select"] span,
        div[data-baseweb="select"] div,
        div[data-baseweb="select"] div[class*="singleValue"] { 
            color: #0f172a !important; 
            font-weight: 800 !important; 
            font-size: 14px !important; 
            -webkit-text-fill-color: #0f172a !important;
        }
        
        /* TOMBOL MASUK KEMBALI WARNA PUTIH/BIRU */
        div[data-testid="stVerticalBlockBorderWrapper"] button,
        .stButton>button { 
            background: linear-gradient(135deg, #0284c7, #0369a1) !important; 
            border: 1px solid rgba(56, 189, 248, 0.5) !important; 
            border-radius: 10px !important; 
            width: 100% !important; 
            padding: 12px !important; 
            margin-top: 15px !important;
            transition: all 0.2s !important; 
        }
        div[data-testid="stVerticalBlockBorderWrapper"] button p,
        .stButton>button p {
            color: #ffffff !important;
            font-weight: 800 !important; 
            text-shadow: none !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        .stButton>button:hover { transform: translateY(-2px) !important; box-shadow: 0 8px 15px rgba(2, 132, 199, 0.4) !important; }
        """
    else:
        # ---------------- HALAMAN DASHBOARD ----------------
        bg_overlay = "rgba(15,23,42,0.88), rgba(15,23,42,0.88)"
        css += f".stApp {{ background-image: linear-gradient({bg_overlay}), {bg_img} !important; background-size: cover; background-attachment: fixed; background-position: center; }}\n"
        
        css += """
        /* KOTAK DASHBOARD (KACA GELAP) */
        div[data-testid="stVerticalBlockBorderWrapper"],
        div[data-testid="stVerticalBlock"] > div[style*="border"] { 
            border-radius: 16px; 
            background: linear-gradient(145deg, rgba(30,41,59,0.7), rgba(15,23,42,0.9)) !important; 
            border: 1px solid rgba(255,255,255,0.1) !important; 
            padding: 24px; 
            transition: all 0.3s; 
        }
        
        /* INPUT FORM DASHBOARD */
        div[data-baseweb="input"] > div, div[data-baseweb="select"] > div { background-color: #f8fafc !important; border-radius: 8px !important; min-height: 38px !important; border: 2px solid transparent !important; }
        div[data-baseweb="input"] input, div[data-baseweb="select"] span { color: #0f172a !important; font-weight: 700 !important; font-size: 13px !important; }
        .stButton>button { border-radius: 12px; font-weight: 700 !important; width: 100%; transition: all 0.2s; }
        button[kind="primary"] { background: linear-gradient(135deg, #0284c7, #0369a1) !important; color: white !important; border: none !important; }
        
        @keyframes headerGlow { 0%, 100% { box-shadow: 0 0 20px rgba(0,77,149,0.6); border-color: rgba(0,77,149,0.9); } 33% { box-shadow: 0 0 20px rgba(239,68,68,0.6); border-color: rgba(239,68,68,0.9); } 66% { box-shadow: 0 0 20px rgba(130,195,65,0.6); border-color: rgba(130,195,65,0.9); } }
        .header-bar { background: #fff; border-radius: 16px; padding: 16px 32px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; animation: fadeIn 0.5s 1s both, headerGlow 6s infinite; border: 2px solid transparent; }
        @keyframes bellFlash { 0%, 100% { color: #1e293b; transform: scale(1); } 50% { color: #ef4444; transform: scale(1.1); filter: drop-shadow(0 0 8px rgba(239,68,68,0.8)); } }
        .bell-active { animation: bellFlash 1.5s infinite; }
        .home-btn { display: flex; background: rgba(30,41,59,0.1); color: #0f172a; padding: 8px 16px; border-radius: 8px; border: 1px solid rgba(0,0,0,0.1); cursor: pointer; text-decoration: none; transition: 0.2s; }
        .home-btn:hover { background: rgba(56,189,248,0.2); color: #0284c7; transform: translateY(-2px); }
        
        /* SCROLL CONTAINER TIMELINE */
        .scroll-container { display: flex; overflow-x: auto; gap: 14px; padding-bottom: 20px; padding-top: 10px; scroll-behavior: smooth; scrollbar-width: none; }
        .scroll-container::-webkit-scrollbar { display: none; }
        
        .scroll-card { flex: 0 0 220px; background: linear-gradient(145deg, rgba(30,41,59,0.9), rgba(15,23,42,0.95)); border: 1px solid rgba(255,255,255,0.1); border-radius: 14px; padding: 16px; transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275), box-shadow 0.3s ease; scroll-snap-align: start; cursor: pointer; }
        .scroll-card:hover { transform: translateY(-8px); border-color: rgba(56, 189, 248, 0.5); box-shadow: 0 15px 30px rgba(56, 189, 248, 0.2); }
        .scroll-card:active { transform: scale(0.97) translateY(0); box-shadow: 0 5px 15px rgba(56, 189, 248, 0.4); }
        .today-card { border: 2px solid #38bdf8 !important; box-shadow: 0 0 15px rgba(56,189,248,0.3) !important; background: linear-gradient(145deg, rgba(20,50,85,0.9), rgba(15,23,42,0.95)) !important; transform: translateY(-2px); }
        .today-card:hover { transform: translateY(-10px); box-shadow: 0 15px 35px rgba(56, 189, 248, 0.4) !important; }
        .scroll-header { text-align: center; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 8px; font-weight: 700; margin-bottom: 14px; font-size: 13px; color:#94a3b8; border-bottom:2px solid #38bdf8; transition: background 0.3s, color 0.3s; }
        .scroll-card:hover .scroll-header { background: rgba(56, 189, 248, 0.15); color: #ffffff; }
        .today-header { background: linear-gradient(135deg, #0284c7, #38bdf8) !important; color: #ffffff !important; border-bottom: none !important; box-shadow: 0 4px 10px rgba(2,132,199,0.5); }
        .scroll-item { margin-bottom: 12px; font-size: 14px; padding: 10px; border-radius: 8px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); transition: background 0.2s, transform 0.2s; }
        .scroll-item:hover { background: rgba(255,255,255,0.08); transform: translateX(3px); border-color: rgba(255,255,255,0.2); }
        .status-badge { display:inline-flex; align-items:center; gap:6px; font-size:11px; font-weight:700; padding:4px 8px; border-radius:6px; margin-top:6px; width: 100%; box-sizing: border-box; }
        .status-dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
        
        details.off-personnel { background: rgba(255,255,255,0.03); border-left: 3px solid #38bdf8; border-radius: 8px; margin-bottom: 10px; transition: 0.2s; }
        details.off-personnel:hover { background: rgba(56,189,248,0.08); transform: translateX(4px); }
        details.off-personnel summary { padding: 14px 16px; cursor: pointer; font-size: 14px; font-weight: 600; display: flex; align-items: center; list-style: none; }
        details.off-personnel summary::-webkit-details-marker { display: none; }
        .chevron-icon { transition: transform 0.3s; color: #94a3b8; margin-left:auto; }
        details.off-personnel[open] .chevron-icon { transform: rotate(180deg); color: #38bdf8; }
        .off-details-content { padding: 0 16px 16px 16px; font-size: 14px; color:#cbd5e1; }
        
        /* EXPANDER TO DO LIST (UTAMA) */
        div[data-testid="stExpander"] { border: 1px solid rgba(56,189,248,0.4) !important; border-radius: 12px !important; background: linear-gradient(145deg, rgba(30,41,59,0.8), rgba(15,23,42,0.9)) !important; overflow: hidden; transition: all 0.3s; }
        div[data-testid="stExpander"] summary { background: rgba(56,189,248,0.1) !important; padding: 15px 20px !important; }
        div[data-testid="stExpander"] summary p { font-weight: 800 !important; color: #38bdf8 !important; font-size: 16px !important; letter-spacing: 0.5px; transition: all 0.3s; }
        div[data-testid="stExpander"] summary svg { color: #38bdf8 !important; }
        
        /* SUB-EXPANDER (TANGGAPAN OPERATOR - NESTED) */
        div[data-testid="stExpander"] div[data-testid="stExpander"] { border: 1px solid rgba(255,255,255,0.1) !important; border-top: none !important; border-radius: 0 0 8px 8px !important; background: rgba(0,0,0,0.2) !important; margin-top: 0px !important; margin-bottom: 12px !important; box-shadow: none !important; }
        div[data-testid="stExpander"] div[data-testid="stExpander"] summary { background: rgba(255,255,255,0.03) !important; padding: 10px 15px !important; border-top: 1px solid rgba(255,255,255,0.05) !important; }
        div[data-testid="stExpander"] div[data-testid="stExpander"] summary p { font-weight: 600 !important; color: #cbd5e1 !important; font-size: 13px !important; letter-spacing: 0px !important; }
        div[data-testid="stExpander"] div[data-testid="stExpander"] summary svg { color: #cbd5e1 !important; }
        
        /* ANIMASI GLOW UPDATE TO DO LIST KUNING NEON */
        @keyframes todoGlow { 
            0%, 100% { box-shadow: 0 0 0px transparent; border-color: rgba(56,189,248,0.4); } 
            50% { box-shadow: 0 0 25px rgba(250, 204, 21, 0.85); border-color: #facc15; background-color: rgba(250, 204, 21, 0.05); } 
        }
        .todo-updated-animation { animation: todoGlow 1.5s infinite !important; }
        .todo-updated-text { color: #facc15 !important; text-shadow: 0 0 8px rgba(250, 204, 21, 0.5); }
        
        /* GAYA TAB STREAMLIT AGAR LEBIH KONTRAST */
        div[data-testid="stTabs"] button { font-family: 'Plus Jakarta Sans', sans-serif !important; font-weight: 600 !important; font-size: 16px !important; color: #94a3b8 !important; }
        div[data-testid="stTabs"] button[aria-selected="true"] { color: #38bdf8 !important; }
        
        @media (max-width: 768px) { .header-bar { flex-direction: column; gap: 16px; padding: 20px; align-items: center !important; } .header-title { font-size: 20px !important; text-align: center; } .stButton>button { padding: 16px 10px !important; font-size: 14px !important; } }
        """
        
    css += "</style>"
    st.markdown(css, unsafe_allow_html=True)

    if 'splash_shown' not in st.session_state:
        st.session_state.splash_shown = True
        logo_src_splash = f"data:image/png;base64,{get_base64_image('pertamina.png')}"
        st.markdown(f"""
        <div id="splash-overlay">
            <div class="splash-content">
                <img src="{logo_src_splash}" class="splash-logo" alt="Logo">
                <h2 class="splash-title">NR ORF COMMAND</h2>
                <div class="splash-fade-early">
                    <div class="splash-subtitle">SINKRONISASI DATABASE...</div>
                    <div class="loading-bar-container"><div class="loading-bar"></div></div>
                </div>
            </div>
        </div>
        <style>
        #splash-overlay {{ position: fixed; top: 0; left: 0; right: 0; bottom: 0; width: 100vw; height: 100vh; z-index: 999999; display: flex; flex-direction: column; justify-content: center; align-items: center; background: #ffffff !important; animation: overlayFade 2s forwards; margin: 0 !important; padding: 0 !important; pointer-events: none; overflow: hidden; }}
        .splash-content {{ text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; animation: moveToHeader 2s forwards; }}
        .splash-fade-early {{ animation: fadeOutEarly 2s forwards; display: flex; flex-direction: column; align-items: center; }}
        .splash-logo {{ max-height: 70px; margin-bottom: 20px; animation: floatLogo 1.5s infinite alternate; }}
        .splash-title {{ color: #000000 !important; font-family: 'Plus Jakarta Sans', sans-serif !important; font-weight: 900 !important; font-size: 36px !important; letter-spacing: 2px !important; margin: 0 !important; line-height: 1.2 !important; text-align: center; }}
        .splash-subtitle {{ color: #64748b; font-size: 14px; font-weight: 600; letter-spacing: 3px; margin-top: 15px; opacity: 0.8; text-align: center; }}
        .loading-bar-container {{ width: 200px; height: 4px; background: #e2e8f0; border-radius: 4px; margin-top: 20px; overflow: hidden; position: relative; }}
        .loading-bar {{ position: absolute; height: 100%; width: 40%; background: #38bdf8; animation: loadingSwipe 1s infinite; }}
        @keyframes overlayFade {{ 0%, 70% {{ opacity: 1; visibility: visible; }} 99% {{ opacity: 0; visibility: visible; }} 100% {{ opacity: 0; visibility: hidden; display: none; }} }}
        @keyframes moveToHeader {{ 0%, 70% {{ transform: translateY(0) scale(1); opacity: 1; }} 100% {{ transform: translateY(-40vh) scale(0.4); opacity: 0; }} }}
        @keyframes fadeOutEarly {{ 0%, 50% {{ opacity: 1; transform: translateY(0); }} 70%, 100% {{ opacity: 0; transform: translateY(10px); }} }}
        @keyframes floatLogo {{ 0% {{ transform: translateY(0px); filter: drop-shadow(0 5px 10px rgba(0,0,0,0.1)); }} 100% {{ transform: translateY(-10px); filter: drop-shadow(0 15px 20px rgba(0,0,0,0.15)); }} }}
        @keyframes loadingSwipe {{ 0% {{ left: -40%; }} 100% {{ left: 140%; }} }}
        </style>
        """, unsafe_allow_html=True)


# =====================================================================
# 5. SISTEM LOGIN AWAL
# =====================================================================
def ui_login(df_j):
    logo_base64 = get_base64_image("logo-pertaminaregasv2.png")
    
    st.markdown("<div style='height: 5vh;'></div>", unsafe_allow_html=True)
    
    if logo_base64:
        st.markdown(f"""
        <div style="display: flex; justify-content: center; margin-bottom: 25px;">
            <img src="data:image/png;base64,{logo_base64}" style="max-height: 80px; filter: drop-shadow(0 4px 6px rgba(0,0,0,0.3));">
        </div>
        """, unsafe_allow_html=True)
        
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.container(border=True):
            st.markdown("<h2 class='login-title'>SISTEM LOGIN</h2>", unsafe_allow_html=True)
            st.markdown("<p class='login-subtitle'>Akses Terintegrasi NR ORF Command</p>", unsafe_allow_html=True)
            
            role = st.selectbox("Masuk Sebagai:", ["Operator", "Manajer"])
            
            if role == "Manajer":
                nama = st.selectbox("Nama Manajer:", DAFTAR_MANAJER)
                pin = st.text_input("PIN Keamanan:", type="password")
            else:
                op_list = []
                if not df_j.empty and 'Nama Operator' in df_j.columns:
                    op_list = sorted(df_j['Nama Operator'].dropna().astype(str).str.replace('*','', regex=False).str.strip().unique())
                    op_list = [o for o in op_list if o.lower() not in ['nan', 'none', '']]
                nama = st.selectbox("Nama Operator:", ["-- Pilih Nama Anda --"] + op_list)
                pin = ""

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Masuk Aplikasi", type="primary", use_container_width=True):
                if role == "Manajer" and pin != PIN_MANAGER:
                    st.error("❌ PIN Keamanan Salah!")
                elif not nama or nama == "-- Pilih Nama Anda --":
                    st.error("❌ Silakan pilih nama Anda terlebih dahulu!")
                else:
                    token_str = f"{role}::{nama}"
                    token_b64 = base64.b64encode(token_str.encode("utf-8")).decode("utf-8")
                    st.query_params["auth"] = token_b64
                    
                    st.session_state.logged_in = True
                    st.session_state.user_role = role
                    st.session_state.user_name = nama
                    st.rerun()


# =====================================================================
# 6. HEADER, HUD, DAN TO-DO WIDGET
# =====================================================================
def ui_header(logo_base64, pending_count):
    logo = f'<img src="data:image/png;base64,{logo_base64}" style="max-height: 50px;">' if logo_base64 else ''
    notif = f'<div style="position:relative;" title="Ada {pending_count} antrean!"><span class="material-symbols-rounded bell-active" style="font-size:28px;">notifications_active</span><span style="position:absolute; top:-6px; right:-8px; background:#ef4444; color:white; border-radius:50%; padding:2px 6px; font-size:11px; font-weight:800;">{pending_count}</span></div>' if pending_count > 0 else '<div style="opacity:0.4;"><span class="material-symbols-rounded" style="font-size:28px; color:#1e293b;">notifications</span></div>'
    
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
            <h1 style="color:#004D95; font-weight:800; font-size:clamp(16px, 3vw, 24px); margin:0;">NR ORF Integrated Command</h1>
            <span style="font-size:12px; color:#64748b; font-weight:600;">Halo, {st.session_state.user_name} ({st.session_state.user_role})</span>
        </div>
        <div>{notif}</div>
    </div>
    """, unsafe_allow_html=True)

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

            fetch('https://api.open-meteo.com/v1/forecast?latitude=' + lat + '&longitude=' + lon + '&current_weather=true')
            .then(r => r.json())
            .then(json => {{
                var cw = json.current_weather;
                document.getElementById('w-temp').innerText = cw.temperature + '°C'; 
                document.getElementById('w-wind').innerText = cw.windspeed + ' km/h'; 
                var i = 'partly_cloudy_day'; var desc = 'Berawan'; 
                if(cw.weathercode === 0) {{ i = 'clear_day'; desc = 'Cerah'; }} 
                else if(cw.weathercode > 50) {{ i = 'rainy'; desc = 'Hujan'; }}
                document.getElementById('w-icon').innerText = i; document.getElementById('w-desc').innerText = desc;
            }}).catch(e => console.log(e));
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
        
        function handleOrientation(e) {{
            let heading = null;
            if(e.webkitCompassHeading !== undefined && e.webkitCompassHeading !== null) {{ heading = e.webkitCompassHeading; }} 
            else if(e.alpha !== null) {{ heading = 360 - e.alpha; }}
            if(heading !== null) {{
                document.getElementById('deg').innerText = Math.round(heading) + '°'; 
                document.getElementById('compass').style.transform = 'rotate(-' + heading + 'deg)'; 
            }}
        }}

        window.addEventListener('deviceorientationabsolute', handleOrientation, true);
        window.addEventListener('deviceorientation', handleOrientation, true);

        document.getElementById('compass-box').addEventListener('click', async function() {{
            if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {{
                try {{
                    const perm = await DeviceOrientationEvent.requestPermission();
                    if (perm === 'granted') window.addEventListener('deviceorientation', handleOrientation, true);
                }} catch (err) {{}}
            }}
        }});
    </script>
    """, height=90)

def ui_todo_widget():
    td = fetch_todo_from_sheet()
    
    is_new = False
    if td['last_updated'] and td['last_updated'] != st.session_state.last_seen_todo:
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
            
        if td['main_msg'].strip():
            st.markdown(f"<div style='background:rgba(56,189,248,0.15); border-left:4px solid #38bdf8; padding:12px 16px; border-radius:8px; margin-bottom:15px;'><b style='color:#38bdf8; font-size:15px;'><span class='material-symbols-rounded' style='font-size:18px; vertical-align:text-bottom;'>campaign</span> Pesan Utama:</b><br><span style='color:#f8fafc; line-height:1.5;'>{td['main_msg']}</span></div>", unsafe_allow_html=True)
        
        has_task = False
        
        for op, data in td['tasks'].items():
            task_text = data.get('task', '')
            comment_text = data.get('comment', '')
            
            if task_text.strip():
                has_task = True
                
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
        
        if not has_task and not td['main_msg'].strip():
            st.info("Belum ada instruksi atau tugas spesifik dari Manajer untuk hari ini.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        components.html("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@700&display=swap');
            body { margin: 0; padding: 0; background: transparent; overflow: hidden; }
            button {
                width: 100%; background: transparent; border: 1px solid rgba(56, 189, 248, 0.4); 
                color: #38bdf8; border-radius: 8px; padding: 8px 0; 
                font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 700; font-size: 14px; 
                cursor: pointer; transition: all 0.2s ease;
            }
            button:hover { background: rgba(56, 189, 248, 0.1); border-color: #38bdf8; color: #ffffff; }
            button:active { transform: scale(0.95); background: rgba(56, 189, 248, 0.2); }
        </style>
        <button onclick="
            const pDoc = window.parent.document;
            const mainExp = pDoc.querySelector('div[data-testid=\\'stExpander\\'] details');
            if(mainExp && mainExp.hasAttribute('open')) { mainExp.querySelector('summary').click(); }
        ">⬆️ Tutup Daftar Tugas</button>
        """, height=40)


# =====================================================================
# 7. HALAMAN UTAMA (TIMELINE SCROLL) 
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
        col_status = find_col(df_i, ['status', 'approval', 'appr'], None)
        if col_status and col_status in df_i.columns:
            appr_df = df_i[df_i[col_status].astype(str).str.upper().str.contains('APPROVED', na=False)]
            for _, row in appr_df.iterrows():
                try:
                    sub = str(get_val(row, ['pengganti', 'backup'], '')).strip().lower()
                    if sub and sub not in ['nan', '']:
                        for d in pd.date_range(pd.to_datetime(get_val(row, ['mulai'], today), dayfirst=True).date(), pd.to_datetime(get_val(row, ['selesai'], today), dayfirst=True).date()):
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


# =====================================================================
# 8. HALAMAN MANAJER (HANYA TERLIHAT OLEH MANAJER)
# =====================================================================
def ui_manager_panel(df_i, df_j):
    st.markdown("<h3 class='section-title'><span class='material-symbols-rounded' style='color:#38bdf8;'>admin_panel_settings</span> Panel Manajer</h3>", unsafe_allow_html=True)
    
    approver_name = st.session_state.user_name

    tab_izin, tab_edit, tab_todo = st.tabs(["📋 Panel Persetujuan Izin", "⚙️ Panel Edit & AI", "📝 To-Do List Harian"])
    
    with tab_izin:
        col_nama = find_col(df_i, ['nama', 'pengaju', 'operator', 'lengkap'], None)
        if not col_nama and not df_i.empty and len(df_i.columns) > 1:
            col_nama = df_i.columns[1] 
            
        if df_i.empty or not col_nama: 
            st.warning("Data form izin kosong atau belum ada pengajuan terbaru.")
        else:
            col_status = find_col(df_i, ['status', 'approval', 'appr'], None)
            if not col_status or col_status not in df_i.columns:
                df_i["Status Approval"] = ""
                col_status = "Status Approval"
                
            # FILTER SUPER KETAT: Membuang baris kosong yang menjadi "nan"
            df_valid = df_i[~df_i[col_nama].astype(str).str.lower().isin(["", "nan", "none", "null"])]
            pending_df = df_valid[df_valid[col_status].astype(str).str.lower().isin(["", "nan", "none", "null"])]

            col_hdr1, col_hdr2 = st.columns([2, 1])
            with col_hdr1: st.markdown("<br><h4 style='color:white; font-size:16px; margin-top:0; display:flex; align-items:center; gap:6px;'><span class='material-symbols-rounded' style='font-size:20px; color:#facc15;'>pending_actions</span> Antrean Persetujuan</h4>", unsafe_allow_html=True)
            with col_hdr2:
                if not pending_df.empty:
                    if st.button("🗑️ Hapus Semua Antrean"): clear_pending_requests(df_i)

            if pending_df.empty: st.info("Tugas selesai. Tidak ada antrean izin saat ini.")
            else:
                for i, (idx, row) in enumerate(pending_df.head(5).iterrows()):
                    with st.container(border=True):
                        st.markdown(generate_izin_card_html(row, delay=i*0.1), unsafe_allow_html=True)
                        c1, c2 = st.columns(2)
                        if c1.button("✓ Setujui (Approve)", key=f"app_{idx}", type="primary", use_container_width=True): execute_database_action(idx, row, "APPROVE", approver_name, df_j, df_i)
                        if c2.button("✕ Tolak (Reject)", key=f"rej_{idx}", use_container_width=True): execute_database_action(idx, row, "REJECT", approver_name, df_j, df_i)

            st.markdown("<hr style='opacity:0.1; margin: 30px 0;'><h4 style='color:white; font-size:16px; display:flex; align-items:center; gap:6px;'><span class='material-symbols-rounded' style='font-size:20px; color:#94a3b8;'>history</span> Riwayat Terakhir</h4>", unsafe_allow_html=True)
            history_df = df_valid[df_valid[col_status].astype(str).str.upper().str.contains('APPROVED|REJECTED', regex=True, na=False)]
            
            if history_df.empty: st.info("Belum ada riwayat keputusan yang tercatat.")
            else:
                for _, row in history_df.tail(5).iloc[::-1].iterrows():
                    status = str(row[col_status]).upper()
                    is_appr = "APPROVED" in status
                    c_text, c_bg, icon = ("#4ade80", "rgba(34,197,94,0.15)", "check_circle") if is_appr else ("#fca5a5", "rgba(239,68,68,0.15)", "cancel")
                    
                    nama_pengaju = get_val(row, ['nama', 'pengaju', 'operator'], 'Tidak Diketahui')
                    t_mulai = get_val(row, ['mulai', 'dari'], '-')
                    t_selesai = get_val(row, ['selesai', 'sampai'], '-')
                    
                    with st.container(border=True):
                        st.markdown(f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;'><div><b style='font-size:14px; color:white;'>{nama_pengaju}</b><br><span style='font-size:12px; color:#94a3b8;'>{t_mulai} s/d {t_selesai}</span></div><div style='background:{c_bg}; color:{c_text}; padding:6px 12px; border-radius:8px; font-size:11px; font-weight:700; display:flex; align-items:center; gap:4px;'><span class='material-symbols-rounded' style='font-size:14px;'>{icon}</span> {status}</div></div>", unsafe_allow_html=True)
                        if st.button("⟲ Batalkan Keputusan", key=f"undo_{_}", use_container_width=True): execute_database_action(_, row, "UNDO", approver_name, df_j, df_i)

    with tab_edit:
        st.markdown("<br><div style='background:rgba(15,23,42,0.6); padding:16px; border-radius:12px; border-left:4px solid #38bdf8; margin-bottom:24px; display:flex; align-items:center; gap:10px;'><span class='material-symbols-rounded' style='color:#38bdf8;'>database</span> <b style='color:#f8fafc;'>Akses Database Utama</b></div>", unsafe_allow_html=True)
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1: st.link_button("Edit Jadwal Aktual", URL_JADWAL, use_container_width=True)
        with c_btn2: st.link_button("Edit Database Izin", URL_IZIN, use_container_width=True)
        
        st.markdown("<hr style='opacity:0.1; margin: 30px 0;'><h4 style='color:white; font-size:16px; display:flex; align-items:center; gap:6px;'><span class='material-symbols-rounded' style='font-size:20px; color:#38bdf8;'>smart_toy</span> Asisten Jadwal Pintar (BETA)</h4>", unsafe_allow_html=True)
        st.markdown("<div style='background: rgba(56,189,248,0.1); border: 1px solid rgba(56,189,248,0.3); border-radius: 12px 12px 12px 0; padding: 12px 16px; margin-bottom: 10px; font-size: 14px; line-height: 1.5;'><span style='background: #0ea5e9; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 800; margin-right: 6px;'>AI</span> Halo! Saya asisten jadwal. Anda bisa menyuruh saya mengubah jadwal tanpa harus repot membuka dropdown.<br><br><b>Contoh:</b> <i>'Ubah jadwal Hanif jadi cuti tanggal 18 sampai 20'</i> atau <i>'Besok Haerul off'</i></div>", unsafe_allow_html=True)
        
        if 'ai_parsed_data' not in st.session_state: st.session_state.ai_parsed_data = None
        perintah = st.text_input("Ketik perintah Anda di sini:", placeholder="Tulis instruksi...")
        if st.button("Kirim Perintah", type="primary"):
            if not perintah: st.error("Silakan ketik perintah terlebih dahulu.")
            else:
                parsed = parse_natural_language_schedule(perintah, df_j)
                if not parsed['nama']: st.error("❌ Saya tidak menemukan nama personel tersebut di database.")
                elif not parsed['status']: st.error("❌ Saya tidak menangkap status yang diinginkan (sakit/cuti/off/pagi/malam).")
                elif not parsed['tgl_mulai']: st.error("❌ Saya tidak mengerti tanggalnya. Coba gunakan angka atau rentang.")
                else: st.session_state.ai_parsed_data = parsed

        if st.session_state.ai_parsed_data:
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
        st.markdown("<br><b style='color:#38bdf8;'>Pengumuman Saat Ini</b>", unsafe_allow_html=True)
        td = fetch_todo_from_sheet()
        if td['main_msg'].strip():
            st.info(td['main_msg'])
        else:
            st.write("Belum ada pengumuman umum.")
            
        with st.expander("✏️ Edit Pengumuman & Tugas Individu", expanded=True):
            st.warning("Perubahan di bawah ini akan langsung disimpan permanen ke dalam Google Sheets.")
            new_main_msg = st.text_area("Pesan Utama / Briefing Umum:", value=td['main_msg'], placeholder="Tulis pengumuman umum di sini...")
            
            st.markdown("<hr style='opacity:0.2;'><b style='color:#4ade80;'>Tugas Spesifik Individu</b>", unsafe_allow_html=True)
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
            
            if col_save.button("💾 Simpan Perubahan ke Database", type="primary", use_container_width=True):
                if push_todo_to_sheet(new_main_msg, new_tasks):
                    st.success("✅ Berhasil diperbarui!")
                    time.sleep(1)
                    st.rerun()
            if col_clear.button("🗑️ Bersihkan Semua", use_container_width=True):
                if push_todo_to_sheet("", {}):
                    st.success("✅ To-Do List berhasil dikosongkan!")
                    time.sleep(1)
                    st.rerun()


# =====================================================================
# MAIN RUNNER
# =====================================================================
if __name__ == "__main__":
    is_login_page = not st.session_state.get('logged_in', False)
    inject_custom_css(get_base64_image("fsru.jpg"), get_base64_image("logo-pertaminaregasv2.png"), is_login=is_login_page)

    df_j, df_i, df_k = load_all_data()

    if is_login_page:
        ui_login(df_j)
    else:
        # PENGHITUNGAN ANTREAN IZIN (ANTI-DUMMY ROW)
        col_status_global = find_col(df_i, ['status', 'approval', 'appr'], None)
        col_nama_global = find_col(df_i, ['nama', 'operator', 'lengkap', 'pengaju'], None)
        
        pending_count = 0
        if not df_i.empty and col_nama_global and col_status_global and col_status_global in df_i.columns:
            df_v = df_i[~df_i[col_nama_global].astype(str).str.lower().isin(["", "nan", "none", "null"])]
            pending_count = len(df_v[df_v[col_status_global].astype(str).str.lower().isin(["", "nan", "none", "null"])])

        ui_header(get_base64_image("pertamina.png"), pending_count)
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
            with col_m: 
                st.info("Pilih tab menu di atas untuk melakukan fungsi lebih lanjut.")
            with col_s: 
                ui_off_tracker(df_j, df_k)
        elif st.session_state.menu == "Kal":
            ui_kalender_lengkap(df_j)
        elif st.session_state.menu == "Mgr" and st.session_state.user_role == "Manajer":
            ui_manager_panel(df_i, df_j)
