import streamlit as st
import json
import datetime
import hashlib
import smtplib
from email.mime.text import MIMEText
from github import Github
import os
import random
import string
import uuid

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Tenis Partner Ağı", page_icon="🎾", layout="wide")

# --- SABİT VERİLER ---
NTRP_LEVELS = ["1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0", "5.5", "6.0", "6.5", "7.0"]
IZMIR_KORTLARI = [
    "Kültürpark Tenis Kulübü (KTK)", "İnciraltı Büyükşehir Kortları", "Bostanlı Suat Taşer Kortları",
    "Fuar Alanı (Celal Atik) Kortları", "Buca Tenis Kulübü", "Ege Üniversitesi Tenis Kortları",
    "Gaziemir Belediyesi Kortları", "Göztepe Tenis Kulübü", "Küçük Kulüp Alliance", "Mavişehir Şemikler Kortları", "Diğer"
]
ACTIVITY_TYPES = ["Maç", "Antrenman", "Ralli", "Fark Etmez"]
TURKEY_TZ = datetime.timezone(datetime.timedelta(hours=3))

# --- AYARLAR ---
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "GITHUB_TOKEN_BURAYA")
REPO_NAME = st.secrets.get("REPO_NAME", "kullaniciadi/repo_adi")
SMTP_USER = st.secrets.get("SMTP_USER", "")
SMTP_PASS = st.secrets.get("SMTP_PASS", "")
ADMIN_PASS = st.secrets.get("ADMIN_PANEL_PASS", "izmir35")

INVITES_FILE_PATH = "invites.json"
USERS_FILE_PATH = "users.json"

# --- YARDIMCI FONKSİYONLAR ---
def hash_password(password): return hashlib.sha256(password.encode()).hexdigest()
def generate_temp_password(length=6): return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def send_email(to_address, subject, message):
    if not SMTP_USER or not SMTP_PASS: return
    try:
        full_message = f"<html><body><h3>🎾 İzmir Tenis Ağı</h3><p>{message}</p></body></html>"
        msg = MIMEText(full_message, 'html', 'utf-8')
        msg['Subject'] = f"[İzmir Tenis Ağı] {subject}"
        msg['From'] = f"İzmir Tenis Ağı <{SMTP_USER}>"
        msg['To'] = to_address
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [to_address], msg.as_string())
        server.quit()
    except: pass

@st.cache_resource
def get_github_repo():
    if GITHUB_TOKEN != "GITHUB_TOKEN_BURAYA":
        try: return Github(GITHUB_TOKEN).get_repo(REPO_NAME)
        except: pass
    return None

def load_data(file_path, default_type=list):
    repo = get_github_repo()
    if repo:
        try: return json.loads(repo.get_contents(file_path).decoded_content.decode())
        except: return default_type()
    else:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f: return json.load(f)
        return default_type()

def save_data(file_path, data):
    repo = get_github_repo()
    if repo:
        try:
            content = repo.get_contents(file_path)
            repo.update_file(content.path, "Güncelleme", json.dumps(data, indent=4, ensure_ascii=False), content.sha)
            return True
        except:
            try:
                repo.create_file(file_path, "Oluşturma", json.dumps(data, indent=4, ensure_ascii=False))
                return True
            except: return False
    else:
        with open(file_path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)
        return True

def check_expired_invites(invites):
    updated = False
    now = datetime.datetime.now(TURKEY_TZ)
    for inv in invites:
        if inv.get('status') == 'active' and inv.get('time') != "Esnek":
            d_str = inv.get('date')
            t_str = inv.get('time', '00:00')
            try:
                dt = datetime.datetime.strptime(f"{d_str} {t_str}", "%Y-%m-%d %H:%M")
                dt = dt.replace(tzinfo=TURKEY_TZ)
                if now > dt:
                    inv['status'] = 'expired'
                    updated = True
            except: pass
    return updated

# --- OTURUM YÖNETİMİ ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'is_admin' not in st.session_state: st.session_state.is_admin = False
if 'current_user' not in st.session_state: st.session_state.current_user = ""

def login_page():
    st.markdown("<h1 style='text-align: center; color: #2E7D32;'>🎾 İzmir Tenis Partner Havuzu</h1>", unsafe_allow_html=True)
    users_db = load_data(USERS_FILE_PATH, default_type=dict)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        t1, t2, t3 = st.tabs(["🔑 Giriş", "📝 Kayıt", "❓ Şifre"])
        with t1:
            with st.form("login"):
                email = st.text_input("E-posta").strip().lower()
                password = st.text_input("Şifre", type="password")
                if st.form_submit_button("Giriş"):
                    if email in users_db and users_db[email].get("password_hash") == hash_password(password):
                        st.session_state.logged_in = True
                        st.session_state.current_user = email
                        st.rerun()
                    else: st.error("Hatalı bilgiler!")
        with t2:
            with st.form("register"):
                reg_email = st.text_input("Yeni E-posta").strip().lower()
                reg_pass1 = st.text_input("Şifre", type="password")
                if st.form_submit_button("Kayıt"):
                    if reg_email not in users_db:
                        users_db[reg_email] = {"password_hash": hash_password(reg_pass1), "ad_soyad": reg_email.split('@')[0], "seviye": "4.0", "ratings": [], "notif_prefs": {}}
                        save_data(USERS_FILE_PATH, users_db)
                        st.success("Kayıt başarılı!")
                    else: st.error("Bu e-posta kayıtlı.")

def get_avg_rating(prof):
    ratings = prof.get("ratings", [])
    return sum(ratings) / len(ratings) if ratings else 5.0

def main_app():
    users_db = load_data(USERS_FILE_PATH, default_type=dict)
    invites = load_data(INVITES_FILE_PATH, default_type=list)
    current_user_profile = users_db.get(st.session_state.current_user, {})
    
    if check_expired_invites(invites): save_data(INVITES_FILE_PATH, invites)
    
    isim = current_user_profile.get("ad_soyad", st.session_state.current_user.split('@')[0])
    
    # Üst Bilgi Barı
    c_head1, c_head2 = st.columns([4, 1])
    c_head1.write(f"### 🎾 İzmir Tenis Partner Havuzu")
    c_head2.write(f"👤 **{isim}** | ⭐ {get_avg_rating(current_user_profile):.1f}")
    if c_head2.button("🚪 Çıkış"): st.session_state.logged_in = False; st.rerun()

    # Yönetici Yetkisi
    with st.expander("👑 Yönetici Yetkisi"):
        if not st.session_state.is_admin:
            if st.text_input("Yönetici Kodu", type="password") == ADMIN_PASS: st.session_state.is_admin = True; st.rerun()
        else:
            if st.button("Yetkiden Çık"): st.session_state.is_admin = False; st.rerun()

    # Sekmeler
    tabs = st.tabs(["🏆 Havuz", "➕ Davet Oluştur", "👥 Üyeler", "⚖️ Geçmiş & Puanlama", "⚙️ Profil"] + (["🛠️ Yönetici"] if st.session_state.is_admin else []))

    with tabs[0]: # HAVUZ
        st.subheader("Aktif İlanlar")
        for inv in [i for i in invites if i.get('status') == 'active']:
            with st.container(border=True):
                c1, c2 = st.columns(2)
                c1.markdown(f"🗓️ {inv.get('date')} | ⏰ {inv.get('time')}")
                c1.markdown(f"📍 {inv.get('court')} | 🎾 {inv.get('type')}")
                c2.markdown(f"⭐ Seviye: {inv.get('level')} | 👤 {users_db.get(inv.get('creator'), {}).get('ad_soyad')}")
                if inv.get('creator') != st.session_state.current_user:
                    if st.button("Teklif Gönder", key=inv.get('id')): st.success("Teklif iletildi.")

    with tabs[1]: # DAVET OLUŞTUR
        with st.form("create_invite"):
            d = st.date_input("Tarih")
            time_mode = st.radio("Zaman", ["Belirli Saat", "Esnek (Görüşülecek)"])
            t = st.time_input("Saat") if time_mode == "Belirli Saat" else "Esnek"
            court = st.selectbox("Kort", IZMIR_KORTLARI)
            act_type = st.selectbox("Etkinlik Tipi", ACTIVITY_TYPES)
            level = st.selectbox("Seviye", NTRP_LEVELS, index=6)
            
            if st.form_submit_button("Ekle"):
                invites.append({
                    "id": str(uuid.uuid4()), "creator": st.session_state.current_user,
                    "date": str(d), "time": str(t), "court": court,
                    "type": act_type, "level": level, "status": "active"
                })
                save_data(INVITES_FILE_PATH, invites)
                st.success("İlan oluşturuldu!")
                st.rerun()

    with tabs[2]: # ÜYELER
        for u_email, u_data in users_db.items():
            st.write(f"🎾 {u_data.get('ad_soyad')} | ⭐ {get_avg_rating(u_data):.1f} | Seviye: {u_data.get('seviye')}")

    with tabs[3]: # PUANLAMA
        st.subheader("Puan Ver")
        with st.form("rating"):
            u_list = {k: v.get("ad_soyad") for k,v in users_db.items() if k != st.session_state.current_user}
            selected = st.selectbox("Üye Seç", options=list(u_list.keys()), format_func=lambda x: u_list[x])
            score = st.slider("Puan", 1, 5, 5)
            if st.form_submit_button("Kaydet"):
                users_db[selected]["ratings"].append(score)
                save_data(USERS_FILE_PATH, users_db)
                st.success("Puan kaydedildi.")
                st.rerun()

    with tabs[4]: # PROFİL
        with st.form("prof"):
            ad = st.text_input("Ad Soyad", value=current_user_profile.get("ad_soyad", ""))
            if st.form_submit_button("Güncelle"):
                users_db[st.session_state.current_user]["ad_soyad"] = ad
                save_data(USERS_FILE_PATH, users_db)
                st.rerun()

    if st.session_state.is_admin: # YÖNETİCİ
        with tabs[5]:
            st.download_button("Veritabanını İndir", json.dumps({"users": users_db, "invites": invites}), "yedek.json")
            uploaded = st.file_uploader("Yedek Yükle (JSON)")
            if uploaded and st.button("Geri Yükle"):
                data = json.load(uploaded)
                save_data(USERS_FILE_PATH, data["users"])
                save_data(INVITES_FILE_PATH, data["invites"])
                st.success("Yüklendi!")
                st.rerun()

if not st.session_state.logged_in: login_page()
else: main_app()
