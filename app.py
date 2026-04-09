import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import base64
import os

# =====================================================================
# 1. KONFIGURASI UTAMA & KONSTANTA (Ubah di sini jika ada penyesuaian)
# =====================================================================
st.set_page_config(page_title="NR ORF Command", page_icon="⚓", layout="wide", initial_sidebar_state="collapsed")

ID_SHEET_JADWAL = "1HuIrvhzm7xzXXbX5Foy2XPms7NLzFyttgH58Ez31pj0"
ID_SHEET_IZIN = "1mdr7InOGhuVwLCpgPW-fDVOMw38XvELlXK9sxJymMYU"

URL_JADWAL = f"https://docs.google.com/spreadsheets/d/{ID_SHEET_JADWAL}/edit#gid=0"
URL_IZIN = f"https://docs.google.com/spreadsheets/d/{ID_SHEET_IZIN}/edit"
URL_GFORM = "https://forms.gle/KB9CkfEsLB4yY9MK9"

PIN_MANAGER = "regas123"
DAFTAR_MANAJER = ["-- Pilih Nama Anda --", "Yosep Zulkarnain", "Ade Imat", "Benny Sulistio", "Ibrahim"]


# =====================================================================
# 2. FUNGSI BANTUAN (UTILITIES) - Menghindari Pengulangan Kode
# =====================================================================
def get_base64_image(file_name):
    """Membaca gambar lokal menjadi string Base64."""
    try:
        with open(file_name, 'rb') as f: return base64.b64encode(f.read()).decode()
    except Exception: return None

def find_col(df, keywords, default_name):
    """Mencari nama kolom cerdas walau ada typo atau spasi."""
    if df.empty: return default_name
    for col in df.columns:
        if any(kw in str(col).lower() for kw in keywords): return col
    return default_name

def generate_html_card(row, col_reason, col_proof, delay):
    """Membuat template HTML untuk kartu antrean persetujuan."""
    alasan = str(row.get(col_reason, '-')).strip()
    if alasan.lower() in ['nan', '']: alasan = 'Tidak ada keterangan'
    
    bukti = str(row.get(col_proof, '')).strip()
    bukti_html = f"<a href='{bukti}' target='_blank' style='color:#38bdf8; text-decoration:none;'>📎 Buka Lampiran Dokumen</a>" if bukti.startswith('http') else "<span style='color:#64748b; font-style:italic;'>Tidak ada lampiran</span>"

    return f"""
    <div style='animation: slideInRight 0.4s {delay}s ease-out backwards;'>
        <b style='font-size:16px; color:#ffffff;'>{row['Nama Lengkap Operator']}</b> <span style='color:#cbd5e1; font-weight:500;'>({row.get('Jenis Izin yang Diajukan', 'Izin')})</span>
        <div style='font-size:14px; margin-top:8px; color:#e2e8f0;'>📅 {row['Tanggal Mulai Izin']} s/d {row['Tanggal Selesai Izin']} | Shift: {row.get('Shift Izin', 'Pg')}</div>
        <div style='margin-top:10px; background: rgba(255,255,255,0.05); border-left: 3px solid #94a3b8; padding: 10px; border-radius: 4px;'>
            <div style='font-size:13px; color:#cbd5e1; margin-bottom:5px;'><b>📝 Alasan:</b><br>{alasan}</div><div style='font-size:13px;'>{bukti_html}</div>
        </div>
        <div style='font-size:14px; color:#fca5a5; font-weight:700; margin-top:12px; margin-bottom:12px; background: rgba(239,68,68,0.2); padding: 4px 8px; border-radius: 4px; display:inline-block;'>🔄 Pengganti: {row.get('Nama Lengkap Operator Pengganti', '-')}</div>
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
    """Mengambil 3 sheet sekaligus dalam satu fungsi."""
    client = get_client()
    df_j, df_i, df_k = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    if not client: return df_j, df_i, df_k

    try:
        # 1. Jadwal
        ws_j = client.open_by_key(ID_SHEET_JADWAL).worksheet("Jadwal_Aktual").get_all_values()
        if len(ws_j) > 1:
            df_j = pd.DataFrame(ws_j[1:], columns=ws_j[0])
            if 'Nama Operator' in df_j.columns: df_j = df_j[df_j['Nama Operator'].astype(str).str.strip() != '']

        # 2. Izin
        ws_i = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0).get_all_values()
        if len(ws_i) > 1:
            df_i = pd.DataFrame(ws_i[1:], columns=ws_i[0])
            if 'Nama Lengkap Operator' in df_i.columns:
                df_i = df_i[df_i['Nama Lengkap Operator'].astype(str).str.strip() != '']
                df_i = df_i[~df_i['Nama Lengkap Operator'].astype(str).str.lower().isin(['nan', 'none', 'null'])]

        # 3. Kontak (Auto-Scanner)
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
    """
    SUPER FUNGSI: Menggabungkan logika Approve, Reject, dan Undo.
    action_type = "APPROVE", "REJECT", atau "UNDO"
    """
    client = get_client()
    if not client: return st.error("Gagal terhubung ke database.")

    try:
        sh_izin = client.open_by_key(ID_SHEET_IZIN).get_worksheet(0)
        col_status_idx = row.index.get_loc('Status Approval') + 1
        
        # Penentuan Teks Status
        if action_type == "APPROVE": status_text = f"APPROVED by {approver_name}"
        elif action_type == "REJECT": status_text = f"REJECTED by {approver_name}"
        else: status_text = "" # UNDO
        
        sh_izin.update_cell(int(idx)+2, col_status_idx, status_text)
        
        # Update Jadwal Jika Tindakannya Approve atau Membatalkan Approve (Undo)
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
                    
                    # Logika Nilai Sel (Jika Approve maju, Jika Undo mundur)
                    val_app = str(row['Jenis Izin yang Diajukan']).upper() if action_type == "APPROVE" else str(row.get('Shift Izin', 'PG')).title()
                    val_sub = str(row.get('Shift Izin', 'PG')).title() if action_type == "APPROVE" else 'OFF'
                    
                    match_p = df_j[df_j.iloc[:,0].astype(str).str.strip().str.lower() == applicant]
                    if not match_p.empty: batch_updates.append(gspread.Cell(int(match_p.index[0])+2, col_date_idx, val_app))
                        
                    if has_sub:
                        match_sub = df_j[df_j.iloc[:,0].astype(str).str.strip().str.lower() == substitute]
                        if not match_sub.empty: batch_updates.append(gspread.Cell(int(match_sub.index[0])+2, col_date_idx, val_sub))
            
            # Tembak API sekaligus untuk menghemat kuota Google
            if batch_updates: sh_aktual.update_cells(batch_updates)

        load_all_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Terjadi kesalahan saat memproses data: {e}")


# =====================================================================
# 4. PENGATURAN TAMPILAN (CSS)
# =====================================================================
def inject_custom_css(bg_base64):
    st.markdown("""<style>[data-testid="collapsedControl"] { display: none; } .block-container { padding-top: 2rem !important; }</style>""", unsafe_allow_html=True)
    bg_color = "rgba(15, 23, 42, 0.85)"
    bg_img = f"url('data:image/jpeg;base64,{bg_base64}')" if bg_base64 else "url('https://images.unsplash.com/photo-1583508108422-0a13d712ce19')"
    
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"], .stApp {{ font-family: 'Plus Jakarta Sans', sans-serif !important; color: #f8fafc; }}
    .stApp {{ background-image: linear-gradient({bg_color}, {bg_color}), {bg_img}; background-size: cover; background-attachment: fixed; }}
    .block-container {{ max-width: 1200px !important; margin: 0 auto; }}
    header[data-testid="stHeader"] {{ display: none !important; }}
    h2, h3, h4, h5 {{ color: #ffffff !important; text-shadow: 0px 2px 4px rgba(0,0,0,0.8); }}
    
    /* Komponen Umum */
    .header-bar {{ background-color: #ffffff; border-radius: 16px; padding: 15px 30px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 30px; box-shadow: 0 8px 25px rgba(0,0,0,0.3); }}
    .header-title {{ color: #004D95 !important; font-weight: 800; font-size: clamp(20px, 3vw, 32px) !important; text-align: center; flex-grow: 1; letter-spacing: -0.5px; text-shadow: none !important; }}
    div[data-testid="stVerticalBlock"] > div[style*="border"] {{ border-radius: 16px; background: linear-gradient(145deg, rgba(30,41,59,0.8), rgba(15,23,42,0.9)) !important; backdrop-filter: blur(16px); border: 1px solid rgba(255,255,255,0.15); box-shadow: 0 10px 30px rgba(0,0,0,0.5); padding: 20px; }}
    .stButton>button {{ border-radius: 12px; font-weight: 800 !important; padding: 20px 10px !important; font-size: 16px !important; height: auto !important; width: 100%; }}
    button[kind="primary"] {{ background: linear-gradient(135deg, #0284c7, #0369a1) !important; color: white !important; border: 1px solid rgba(56,189,248,0.5) !important; box-shadow: 0 6px 15px rgba(2,132,199,0.5) !important; }}
    
    /* Notifikasi */
    .notif-badge {{ position: absolute; top: -5px; right: -8px; background-color: #ef4444; color: white; border-radius: 50%; padding: 2px 7px; font-size: 11px; font-weight: 800; animation: pulseRed 2s infinite; }}
    @keyframes pulseRed {{ 0% {{ box-shadow: 0 0 0 0 rgba(239,68,68,0.7); }} 70% {{ box-shadow: 0 0 0 8px rgba(239,68,68,0); }} 100% {{ box-shadow: 0 0 0 0 rgba(239,68,68,0); }} }}
    
    /* Tabel & Accordion */
    details.off-personnel {{ background: rgba(56,189,248,0.05); border-left: 3px solid #38bdf8; border-radius: 8px; margin-bottom: 8px; }}
    details.off-personnel summary {{ padding: 12px 15px; cursor: pointer; font-size: 14px; font-weight: 600; display: flex; align-items: center; list-style: none; }}
    details.off-personnel summary::-webkit-details-marker {{ display: none; }}
    .off-details-content {{ padding: 10px 15px 15px 15px; border-top: 1px dashed rgba(255,255,255,0.1); font-size: 14px; }}
    .scroll-container {{ display: flex; overflow-x: auto; gap: 12px; padding-bottom: 15px; padding-top: 10px; }}
    .scroll-card {{ flex: 0 0 200px; background: linear-gradient(145deg, rgba(30,41,59,0.9), rgba(15,23,42,0.95)); border: 1px solid rgba(255,255,255,0.15); border-radius: 14px; padding: 16px; }}
    .scroll-item {{ margin-bottom: 10px; font-size: 13px; line-height: 1.5; padding: 8px; border-radius: 8px; background-color: rgba(255,255,255,0.05); }}
    
    /* Status Colors */
    .item-absen {{ border-left: 4px solid #ef4444; background-color: rgba(239,68,68,0.15); }}
    .item-dinas {{ border-left: 4px solid #f97316; background-color: rgba(249,115,22,0.15); }}
    .item-hadir {{ border-left: 4px solid #22c55e; background-color: rgba(34,197,94,0.1); }}
    .item-pengganti {{ border-left: 4px solid #38bdf8; background-color: rgba(56,189,248,0.15); }}
    
    .section-title {{ font-weight: 800; margin-bottom: 15px; position: relative; padding-bottom: 8px; font-size: 20px; }}
    .section-title::after {{ content: ''; position: absolute; left: 0; bottom: 0; width: 40px; height: 4px; background: linear-gradient(90deg, #38bdf8, transparent); border-radius: 2px; }}
    
    @media (max-width: 768px) {{ .header-bar {{ flex-direction: column; gap: 12px; padding: 20px 15px; }} .stButton>button {{ padding: 15px 10px !important; font-size: 14px !important; }} }}
    </style>
    """, unsafe_allow_html=True)


# =====================================================================
# 5. KOMPONEN UI UTAMA
# =====================================================================
def ui_header(logo_base64, pending_count):
    logo = f'<img src="data:image/png;base64,{logo_base64}" style="max-height: 55px;">' if logo_base64 else '<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Pertamina_Logo.svg/512px-Pertamina_Logo.svg.png" style="max-height: 55px;">'
    notif = f'<div style="position:relative; margin-right:15px; cursor:help;" title="Ada {pending_count} ajuan"><span style="font-size:24px;">🔔</span><span class="notif-badge">{pending_count}</span></div>' if pending_count > 0 else '<div style="position:relative; margin-right:15px; opacity:0.3;"><span style="font-size:24px;">🔔</span></div>'
    st.markdown(f'<div class="header-bar"><div>{logo}</div><h1 class="header-title">NR ORF Integrated Command</h1><div style="display:flex; align-items:center;">{notif}<div style="background:#f8fafc; color:#0f172a; padding:10px 18px; border-radius:12px; font-weight:700; border:1px solid #e2e8f0; font-size:14px;">📅 {datetime.now().strftime("%d %b %Y")}</div></div></div>', unsafe_allow_html=True)

def ui_manager_panel(df_i, df_j):
    st.markdown("<h3 class='section-title'>🔔 Panel Manajer</h3>", unsafe_allow_html=True)
    if st.text_input("🔑 PIN Verifikasi Manajer", type="password") != PIN_MANAGER:
        return st.markdown("<div style='border:1px solid rgba(255,255,255,0.15); border-radius:16px; background:rgba(30,41,59,0.8); padding:20px; text-align:center;'>🔒<br><span style='color:#cbd5e1; font-size:14px;'>Masukkan PIN untuk akses Panel.</span></div>", unsafe_allow_html=True)

    approver_name = st.selectbox("👨‍💼 Nama Approver:", DAFTAR_MANAJER)
    is_locked = approver_name == DAFTAR_MANAJER[0]
    if is_locked: st.info("⚠️ Silakan pilih Nama Anda terlebih dahulu.")
    
    st.markdown("<div style='background:rgba(15,23,42,0.85); padding:16px; border-radius:12px; border-left:4px solid #38bdf8; margin-bottom:20px; color:white;'>🛠️ <b style='color:#38bdf8;'>Akses Database</b></div>", unsafe_allow_html=True)
    st.link_button("📝 Edit Jadwal Aktual", URL_JADWAL, use_container_width=True)
    st.link_button("📋 Edit Database Izin", URL_IZIN, use_container_width=True)

    if df_i.empty or 'Status Approval' not in df_i.columns: return st.warning("Menunggu data izin...")

    df_valid = df_i.dropna(subset=['Nama Lengkap Operator'])
    col_reason = find_col(df_i, ['alasan', 'keterangan'], 'Alasan Izin')
    col_proof = find_col(df_i, ['upload', 'bukti', 'dokumen'], 'Bukti Izin')

    # Bagian 1: Antrean Pending
    st.markdown("<h4 style='color:white; font-size:16px; margin-top:10px;'>Antrean Persetujuan:</h4>", unsafe_allow_html=True)
    pending_df = df_valid[df_valid['Status Approval'].isna() | (df_valid['Status Approval'] == "")]
    
    if pending_df.empty: st.info("✨ Tidak ada antrean.")
    else:
        for idx, row in pending_df.head(5).iterrows():
            with st.container(border=True):
                st.markdown(generate_html_card(row, col_reason, col_proof, idx*0.1), unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                if c1.button("✅ Approve", key=f"app_{idx}", type="primary", use_container_width=True, disabled=is_locked): execute_database_action(idx, row, "APPROVE", approver_name, df_j)
                if c2.button("❌ Reject", key=f"rej_{idx}", use_container_width=True, disabled=is_locked): execute_database_action(idx, row, "REJECT", approver_name, df_j)

    # Bagian 2: Riwayat Keputusan
    st.markdown("<hr style='opacity:0.2;'><h4 style='color:white; font-size:16px;'>Riwayat Terakhir:</h4>", unsafe_allow_html=True)
    history_df = df_valid[df_valid['Status Approval'].astype(str).str.upper().str.contains('APPROVED|REJECTED', regex=True, na=False)]
    
    if history_df.empty: st.info("Belum ada riwayat.")
    else:
        for idx, row in history_df.tail(5).iloc[::-1].iterrows():
            status = str(row['Status Approval']).upper()
            c_text, c_bg = ("#4ade80", "rgba(34,197,94,0.2)") if "APPROVED" in status else ("#fca5a5", "rgba(239,68,68,0.2)")
            with st.container(border=True):
                st.markdown(f"<div style='display:flex; justify-content:space-between; align-items:center;'><div><b style='font-size:14px; color:white;'>{row['Nama Lengkap Operator']}</b><br><span style='font-size:12px; color:#cbd5e1;'>{row['Tanggal Mulai Izin']} s/d {row['Tanggal Selesai Izin']}</span></div><div style='background:{c_bg}; color:{c_text}; padding:4px 10px; border-radius:6px; font-size:11px; font-weight:bold;'>{status}</div></div>", unsafe_allow_html=True)
                if st.button("↩️ Batalkan", key=f"undo_{idx}", use_container_width=True, disabled=is_locked): execute_database_action(idx, row, "UNDO", approver_name, df_j)

def ui_off_tracker(df_j, df_k):
    st.markdown("<h3 class='section-title'>👥 Cari Personel OFF</h3>", unsafe_allow_html=True)
    tgl_cek = st.date_input("Pilih Tanggal:", value=datetime.now().date())
    tgl_str = tgl_cek.strftime('%Y-%m-%d')
    
    if df_j.empty or tgl_str not in df_j.columns:
        st.warning("Data jadwal belum tersedia.")
        return st.link_button("📝 Ajukan Form Izin", URL_GFORM, use_container_width=True, type="primary")

    valid_df = df_j.dropna(subset=['Nama Operator'])
    off_list = valid_df[valid_df[tgl_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])]["Nama Operator"].astype(str).tolist()
    
    with st.container(border=True):
        if not off_list: st.write("Tidak ada personel OFF hari ini.")
        else:
            col_n = find_col(df_k, ['nama', 'operator'], None)
            col_hp = find_col(df_k, ['contact', 'kontak', 'hp'], None)

            for i, name in enumerate(off_list):
                hp = "(Belum diinput)"
                if col_n and col_hp and not df_k.empty:
                    clean_db = df_k[col_n].astype(str).str.replace('*','', regex=False).str.strip().str.lower()
                    target = str(name).replace('*','').strip().lower()
                    match = df_k[clean_db == target]
                    if match.empty: match = df_k[clean_db.str.contains(target, na=False)]
                    if not match.empty: hp = str(match.iloc[0][col_hp]).strip()

                st.markdown(f'<details class="off-personnel" style="animation: slideInRight 0.3s {i*0.05}s ease-out backwards;"><summary><b style="color:#38bdf8; font-size:12px; margin-right:8px;">OFF</b><span>{name}</span><span style="margin-left:auto; font-size:10px; color:#94a3b8; border:1px solid rgba(255,255,255,0.2); padding:2px 6px; border-radius:4px;">▼ Kontak</span></summary><div class="off-details-content">📞 No. HP: <b style="color:#38bdf8; font-size:15px;">{hp}</b></div></details>', unsafe_allow_html=True)
                
    st.markdown("<br>", unsafe_allow_html=True)
    st.link_button("📝 Form Izin / Tukar Shift", URL_GFORM, use_container_width=True, type="primary")

def ui_timeline(df_j, df_i):
    st.markdown("<br><hr style='opacity:0.2;'><h3 class='section-title'>📅 Tinjauan 14 Hari Kedepan</h3>", unsafe_allow_html=True)
    if df_j.empty: return st.warning("Sedang menyinkronisasi jadwal...")

    subs_map = {}
    if not df_i.empty and 'Status Approval' in df_i.columns:
        for _, row in df_i[df_i['Status Approval'].astype(str).str.upper().str.contains('APPROVED', na=False)].iterrows():
            try:
                sub = str(row.get('Nama Lengkap Operator Pengganti', '')).strip().lower()
                if sub and sub not in ['nan', '']:
                    for d in pd.date_range(pd.to_datetime(row['Tanggal Mulai Izin'], dayfirst=True).date(), pd.to_datetime(row['Tanggal Selesai Izin'], dayfirst=True).date()):
                        subs_map.setdefault(d.strftime('%Y-%m-%d'), []).append(sub)
            except Exception: pass

    today = datetime.now().date()
    html = '<div class="scroll-container">'
    
    for i in range(14):
        d_obj = today + timedelta(days=i)
        d_str = d_obj.strftime('%Y-%m-%d')
        html += f'<div class="scroll-card"><div class="scroll-header">{d_obj.strftime("%d %b %Y")}</div>'
        
        if d_str in df_j.columns:
            day_df = df_j[['Nama Operator', d_str]].dropna()
            day_df = day_df[~day_df[d_str].astype(str).str.strip().str.lower().isin(['off', 'nan', '', 'none'])]
            
            if not day_df.empty:
                for _, row in day_df.iterrows():
                    name = str(row['Nama Operator']).replace('*', '').strip()
                    status = str(row[d_str]).upper()
                    
                    if any(k in status for k in ["DINAS", "PD"]): html += f'<div class="scroll-item item-dinas">🟠 <b>{name}</b><br><span style="color:#fdba74; font-size:10px; background:rgba(249,115,22,0.3); padding:2px; border-radius:4px;">{status}</span></div>'
                    elif any(k in status for k in ["IZIN", "SAKIT", "CUTI"]): html += f'<div class="scroll-item item-absen">🔴 <b>{name}</b><br><span style="color:#fca5a5; font-size:10px; background:rgba(239,68,68,0.3); padding:2px; border-radius:4px;">{status}</span></div>'
                    elif name.lower() in subs_map.get(d_str, []): html += f'<div class="scroll-item item-pengganti">🔵 <b>{name}</b><br><span style="color:#7dd3fc; font-size:10px; background:rgba(56,189,248,0.2); padding:2px; border-radius:4px;">PENGGANTI SHIFT</span></div>'
                    else: html += f'<div class="scroll-item item-hadir">🟢 <b>{name}</b><br><span style="color:#4ade80; font-size:10px; background:rgba(34,197,94,0.3); padding:2px; border-radius:4px;">SHIFT {status}</span></div>'
            else: html += '<div class="scroll-item" style="text-align:center; background:none;">Semua OFF</div>'
        else: html += '<div class="scroll-item" style="text-align:center; background:none;">Belum dirilis</div>'
        html += '</div>'
    st.markdown(html + '</div>', unsafe_allow_html=True)


# =====================================================================
# 6. ROUTER & MAIN EXECUTION
# =====================================================================
if __name__ == "__main__":
    inject_custom_css(get_base64_image("fsru.jpg"))
    df_j, df_i, df_k = load_all_data()

    # Hitung Antrean Valid
    pending_count = len(df_i.dropna(subset=['Nama Lengkap Operator'])[df_i['Status Approval'].isna() | (df_i['Status Approval'] == "")]) if not df_i.empty and 'Status Approval' in df_i.columns else 0

    ui_header(get_base64_image("pertamina.png"), pending_count)

    # Navigasi Tab
    if 'active_menu' not in st.session_state: st.session_state.active_menu = "Dashboard"
    c1, c2 = st.columns(2)
    with c1: st.button("🏠 Dashboard", type="primary" if st.session_state.active_menu == "Dashboard" else "secondary", on_click=lambda: st.session_state.update(active_menu="Dashboard"), use_container_width=True)
    with c2: st.button("📅 Kalender Lengkap", type="primary" if st.session_state.active_menu == "Kalender" else "secondary", on_click=lambda: st.session_state.update(active_menu="Kalender"), use_container_width=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if st.session_state.active_menu == "Dashboard":
        col_m, col_s = st.columns([2.5, 1.5])
        with col_m: ui_manager_panel(df_i, df_j)
        with col_s: ui_off_tracker(df_j, df_k)
        ui_timeline(df_j, df_i)
        
    elif st.session_state.active_menu == "Kalender":
        st.markdown("<h3 class='section-title'>Pencarian Jadwal Spesifik</h3>", unsafe_allow_html=True)
        with st.container(border=True): tgl = st.date_input("Pilih Tanggal:").strftime('%Y-%m-%d')
        
        if df_j.empty or tgl not in df_j.columns:
            st.warning("⚠️ Data jadwal untuk tanggal ini belum tersedia.")
        else:
            st.markdown(f"<br><h4 style='color:white; font-size:18px;'>Status pada: <b style='color:#38bdf8;'>{tgl}</b></h4>", unsafe_allow_html=True)
            df_day = df_j[['Nama Operator', tgl]].dropna().copy()
            df_day['Status'] = df_day[tgl].fillna('').astype(str).str.strip().str.upper()

            df_off = df_day[df_day['Status'].isin(['OFF', 'NAN', '', 'NONE'])]
            df_abs = df_day[df_day['Status'].str.contains('IZIN|SAKIT|CUTI|DINAS|PD', na=False)]
            df_hdr = df_day[~df_day['Nama Operator'].isin(df_off['Nama Operator']) & ~df_day['Nama Operator'].isin(df_abs['Nama Operator'])]

            for title, df_data, clr_border, clr_bg, show_sts in [("🟢 Hadir / Shift", df_hdr, "rgba(34,197,94,0.4)", "rgba(34,197,94,0.2)", True), ("⚪ Sedang OFF", df_off, "rgba(56,189,248,0.4)", "rgba(56,189,248,0.2)", False), ("🔴 Absen / Dinas", df_abs, "rgba(239,68,68,0.4)", "rgba(239,68,68,0.2)", True)]:
                with st.container(border=True):
                    st.markdown(f"<div style='background:{clr_bg}; padding:10px; border-radius:8px; border:1px solid {clr_border}; margin-bottom:10px;'><b style='color:white;'>{title} ({len(df_data)})</b></div>", unsafe_allow_html=True)
                    if not df_data.empty: st.dataframe(df_data[['Nama Operator', 'Status']] if show_sts else df_data[['Nama Operator']], hide_index=True, use_container_width=True)
                    else: st.write("Tidak ada data.")
