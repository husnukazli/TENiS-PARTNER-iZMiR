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

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Tenis Partner Ağı", page_icon="🎾", layout="wide")

# --- SABİT VERİLER ---
NTRP_LEVELS = ["1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0", "5.5", "6.0", "6.5", "7.0"]
IZMIR_KORTLARI = [
    "Kültürpark Tenis Kulübü (KTK)", "İnciraltı Büyükşehir Kortları", "Bostanlı Suat Taşer Kortları",
    "Fuar Alanı (Celal Atik) Kortları", "Buca Tenis Kulübü", "Ege Üniversitesi Tenis Kortları",
    "Gaziemir Belediyesi Kortları", "Göztepe Tenis Kulübü", "Küçük Kulüp Alliance", "Mavişehir Şemikler Kortları", "Diğer"
]

# --- BAĞLANTI VE AYARLAR ---
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "GITHUB_TOKEN_BURAYA")
REPO_NAME = st.secrets.get("REPO_NAME", "kullaniciadi/repo_adi")
SMTP_USER = st.secrets.get("SMTP_USER", "")
SMTP_PASS = st.secrets.get("SMTP_PASS", "")
ADMIN_PASS = st.secrets.get("ADMIN_PANEL_PASS", "izmir35")

INVITES_FILE_PATH = "invites.json"
USERS_FILE_PATH = "users.json"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_temp_password(length=6):
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choices(characters, k=length))

# --- E-POSTA FONKSİYONU (SPAM ÖNLEYİCİ) ---
def send_email(to_address, subject, message):
    if not SMTP_USER or not SMTP_PASS:
        return
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
    except Exception as e:
        st.error(f"Mail gönderme hatası: {e}")

# --- DİĞER YARDIMCI FONKSİYONLAR ---
def generate_ics(date_str, time_str, court, event_type, details):
    d = datetime.datetime.strptime(f"{date_str} {time_str[:5]}", "%Y-%m-%d %H:%M")
    start = d.strftime("%Y%m%dT%H%M%S")
    end = (d + datetime.timedelta(hours=2)).strftime("%Y%m%dT%H%M%S")
    return f"BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nSUMMARY:🎾 Tenis ({event_type})\nLOCATION:{court}\nDESCRIPTION:{details}\nDTSTART;TZID=Europe/Istanbul:{start}\nDTEND;TZID=Europe/Istanbul:{end}\nEND:VEVENT\nEND:VCALENDAR"

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
            repo.create_file(file_path, "Oluşturma", json.dumps(data, indent=4, ensure_ascii=False))
            return True
    else:
        with open(file_path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)
        return True

# --- OTURUM VE ARAYÜZ ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = ""

def login_page():
    st.markdown("<h1 style='text-align: center; color: #2E7D32;'>🎾 İzmir Tenis Partner Havuzu</h1>", unsafe_allow_html=True)
    users_db = load_data(USERS_FILE_PATH, default_type=dict)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        tab1, tab2, tab3 = st.tabs(["🔑 Giriş Yap", "📝 Kayıt Ol", "❓ Şifremi Unuttum"])
        with tab1:
            with st.form("login"):
                email = st.text_input("E-posta").strip().lower()
                password = st.text_input("Şifre", type="password")
                if st.form_submit_button("Giriş Yap"):
                    if email in users_db and users_db[email].get("password_hash") == hash_password(password):
                        st.session_state.logged_in = True
                        st.session_state.current_user = email
                        st.rerun()
                    else: st.error("Hatalı bilgiler.")
        with tab2:
            with st.form("register"):
                reg_email = st.text_input("Email").strip().lower()
                reg_pass = st.text_input("Şifre", type="password")
                if st.form_submit_button("Kayıt"):
                    users_db[reg_email] = {"password_hash": hash_password(reg_pass), "ad_soyad": reg_email.split('@')[0], "seviye": "4.0", "ratings": []}
                    save_data(USERS_FILE_PATH, users_db)
                    st.success("Kayıt başarılı!")
        with tab3:
            with st.form("forgot"):
                f_email = st.text_input("Email").strip().lower()
                if st.form_submit_button("Yeni Şifre"):
                    if f_email in users_db:
                        tp = generate_temp_password()
                        users_db[f_email]['password_hash'] = hash_password(tp)
                        save_data(USERS_FILE_PATH, users_db)
                        send_email(f_email, "Geçici Şifreniz", f"Yeni şifreniz: {tp}")
                        st.success("Mail gönderildi.")

def get_avg_rating(prof):
    ratings = prof.get("ratings", [])
    return sum(ratings) / len(ratings) if ratings else 5.0

def main_app():
    # YÖNETİCİ KONTROLÜ
    is_admin = False
    st.sidebar.title("🎾 Navigasyon")
    with st.sidebar.expander("Ayarlar"):
        if st.text_input("Yönetici Kodu", type="password") == ADMIN_PASS:
            is_admin = True
    
    menu_list = ["🏆 Havuz (Açık İlanlar)", "➕ Davet Oluştur", "👥 Üyeler", "⚖️ Geçmiş Maçlar & Değerlendirme", "⚙️ Profil Ayarları"]
    if is_admin: menu_list.append("👑 Yönetici Paneli")
    
    menu = st.sidebar.radio("Seçenekler", menu_list)
    users_db = load_data(USERS_FILE_PATH, default_type=dict)
    invites = load_data(INVITES_FILE_PATH, default_type=list)
    current_user_profile = users_db.get(st.session_state.current_user, {})
    
    # ... (Buraya senin orijinal main_app içeriğin gelecek) ...
    # NOT: Eğer "Yönetici Paneli" seçilirse çalışacak kod:
    if menu == "👑 Yönetici Paneli" and is_admin:
        st.header("👑 Yönetici Paneli")
        st.write("Veri Yedekleme:")
        st.download_button("JSON Olarak İndir", data=json.dumps({"users": users_db, "invites": invites}), file_name="yedek.json")
    
    # --- Orijinal kodun geri kalanını (Havuz, Davet vs.) buraya yapıştır ---
    # Bu kısmı senin verdiğin kodun içindeki "elif menu == ..." bloklarının tamamını 
    # buraya ekleyerek tamamlayabilirsin.

if not st.session_state.logged_in:
    login_page()
else:
    main_app()
