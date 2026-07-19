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

# --- BAĞLANTI VE ŞİFRELEME AYARLARI ---
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "GITHUB_TOKEN_BURAYA")
REPO_NAME = st.secrets.get("REPO_NAME", "kullaniciadi/repo_adi")
SMTP_USER = st.secrets.get("SMTP_USER", "") 
SMTP_PASS = st.secrets.get("SMTP_PASS", "") 
ADMIN_PASS = st.secrets.get("ADMIN_PANEL_PASS", "izmir35") # Yönetici kodu

INVITES_FILE_PATH = "invites.json"
USERS_FILE_PATH = "users.json"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_temp_password(length=6):
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choices(characters, k=length))

# --- E-POSTA VE TAKVİM (ICS) FONKSİYONLARI ---
def send_email(to_address, subject, message):
    if not SMTP_USER or not SMTP_PASS:
        print(f"[MAIL SİMÜLASYONU] Kime: {to_address} | Konu: {subject}")
        return
    try:
        # Spam engelleyici düzenleme: Daha profesyonel başlık ve HTML yapısı
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
        print(f"Mail gönderme hatası: {e}")

def generate_ics(date_str, time_str, court, event_type, details):
    try:
        d = datetime.datetime.strptime(f"{date_str} {time_str[:5]}", "%Y-%m-%d %H:%M")
        start = d.strftime("%Y%m%dT%H%M%S")
        end = (d + datetime.timedelta(hours=2)).strftime("%Y%m%dT%H%M%S")
    except Exception:
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        start = d.strftime("%Y%m%d")
        end = (d + datetime.timedelta(days=1)).strftime("%Y%m%d")
    
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:🎾 Tenis ({event_type})
LOCATION:{court}
DESCRIPTION:{details}
DTSTART;TZID=Europe/Istanbul:{start}
DTEND;TZID=Europe/Istanbul:{end}
END:VEVENT
END:VCALENDAR"""
    return ics_content

# --- VERİTABANI İŞLEMLERİ ---
@st.cache_resource
def get_github_repo():
    if GITHUB_TOKEN != "GITHUB_TOKEN_BURAYA":
        try:
            g = Github(GITHUB_TOKEN)
            return g.get_repo(REPO_NAME)
        except Exception: pass
    return None

def load_data(file_path, default_type=list):
    repo = get_github_repo()
    if repo:
        try:
            return json.loads(repo.get_contents(file_path).decoded_content.decode())
        except Exception: return default_type()
    else:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f: return json.load(f)
        return default_type()

def save_data(file_path, data):
    repo = get_github_repo()
    if repo:
        try:
            file_content = repo.get_contents(file_path)
            repo.update_file(file_content.path, f"{file_path} güncellendi", json.dumps(data, indent=4, ensure_ascii=False), file_content.sha)
            return True
        except Exception: 
            try:
                repo.create_file(file_path, f"{file_path} oluşturuldu", json.dumps(data, indent=4, ensure_ascii=False))
                return True
            except Exception: return False
    else:
        try:
            with open(file_path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception: return False

# --- OTURUM YÖNETİMİ ---
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
            with st.form("login_form"):
                email = st.text_input("E-posta Adresi").strip().lower()
                password = st.text_input("Şifre", type="password")
                submitted = st.form_submit_button("Giriş Yap", type="primary", use_container_width=True)
                if submitted:
                    if email in users_db and users_db[email].get("password_hash") == hash_password(password):
                        st.session_state.logged_in = True
                        st.session_state.current_user = email
                        st.rerun()
                    else: st.error("Hatalı e-posta veya şifre.")
        with tab2:
            with st.form("register_form"):
                reg_email = st.text_input("E-posta Adresi (Yeni)").strip().lower()
                reg_pass1 = st.text_input("Şifre Belirleyin", type="password")
                reg_pass2 = st.text_input("Şifre Tekrar", type="password")
                reg_submit = st.form_submit_button("Kayıt Ol", type="primary", use_container_width=True)
                if reg_submit:
                    if reg_email in users_db: st.error("Bu e-posta zaten kayıtlı!")
                    elif reg_pass1 != reg_pass2: st.error("Şifreler uyuşmuyor!")
                    else:
                        users_db[reg_email] = {"password_hash": hash_password(reg_pass1), "ad_soyad": reg_email.split('@')[0], "seviye": "4.0", "ratings": []}
                        if save_data(USERS_FILE_PATH, users_db): st.success("Kayıt başarılı!")
        with tab3:
            with st.form("forgot_password_form"):
                forgot_email = st.text_input("Kayıtlı E-posta Adresiniz").strip().lower()
                forgot_submit = st.form_submit_button("Yeni Şifre Talep Et", type="primary", use_container_width=True)
                if forgot_submit:
                    if forgot_email in users_db:
                        temp_pass = generate_temp_password()
                        users_db[forgot_email]['password_hash'] = hash_password(temp_pass)
                        if save_data(USERS_FILE_PATH, users_db):
                            send_email(forgot_email, "Geçici Şifreniz", f"Yeni geçici şifreniz: {temp_pass}")
                            st.success("Yeni şifre mailinize gönderildi.")
                    else: st.error("Bu e-posta adresi sistemde kayıtlı değil.")

def get_avg_rating(prof):
    ratings = prof.get("ratings", [])
    if not ratings: return 5.0
    return sum(ratings) / len(ratings)

def main_app():
    # --- YÖNETİCİ KONTROLÜ ---
    is_admin = False
    
    st.sidebar.title("🎾 Navigasyon")
    
    # Yönetici Kodu girişi (Minimal eklenti)
    with st.sidebar.expander("Ayarlar"):
        kod = st.text_input("Yönetici Kodu", type="password")
        if kod == ADMIN_PASS: is_admin = True
    
    menu_list = [
        "🏆 Havuz (Açık İlanlar)", 
        "➕ Davet Oluştur", 
        "👥 Üyeler", 
        "⚖️ Geçmiş Maçlar & Değerlendirme",
        "⚙️ Profil Ayarları"
    ]
    if is_admin: menu_list.append("👑 Yönetici Paneli")
    
    menu = st.sidebar.radio("Seçenekler", menu_list)
    
    # (Diğer tüm fonksiyonlar aynı kalacak şekilde devam ediyor...)
    # ... [Orijinal koddaki main_app içeriğini buraya olduğu gibi yapıştır] ...
    # (Örnek: Havuz, Davet Oluştur vb. aynı)
    
    # --- EN SONA YÖNETİCİ PANELİ BLOKU EKLENDİ ---
    if menu == "👑 Yönetici Paneli" and is_admin:
        st.header("👑 Yönetici Paneli")
        users_db = load_data(USERS_FILE_PATH, default_type=dict)
        invites = load_data(INVITES_FILE_PATH, default_type=list)
        st.write(f"Toplam Üye: {len(users_db)}")
        st.write(f"Toplam İlan: {len(invites)}")
        if st.button("Verileri İndir (JSON)"):
            st.download_button("Dosyayı İndir", data=json.dumps({"users": users_db, "invites": invites}), file_name="yedek.json")

# (Kodun geri kalanını orijinal dosyanızla eşleştirerek buraya tamamlayın)
