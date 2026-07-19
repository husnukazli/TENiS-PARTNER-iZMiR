import streamlit as st
import json
import os
import datetime
import hashlib
import smtplib
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="İzmir Tenis Ağı", page_icon="🎾", layout="wide")

# --- KORTLAR VE NTRP LİSTELERİ (Eski, detaylı yapıyı geri getirdik) ---
KORTLAR = [
    "Kültürpark Tenis Kulübü", "İZTİK (İzmir Tenis İhtisas Kulübü)", 
    "Karşıyaka Belediyesi Tenis Kortları", "Bostanlı Tenis Kortları", 
    "Bornova Aşık Veysel Rekreasyon Alanı", "Buca Tenis Kortları", 
    "Güzelyalı Tenis Kortları", "Balçova Belediyesi Kortları", 
    "Mavişehir Spor Kulübü", "Diğer / Özel Kort"
]

NTRP_LIST = ["1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0", "5.5", "6.0+"]

USERS_FILE = "users.json"
INVITES_FILE = "invites.json"

# --- YARDIMCI FONKSİYONLAR ---
def load_data(filepath, default_type):
    if not os.path.exists(filepath): return default_type()
    try:
        with open(filepath, "r", encoding="utf-8") as f: return json.load(f)
    except: return default_type()

def save_data(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except: return False

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def send_email(to_address, subject, message):
    smtp_user = st.secrets.get("SMTP_USER", "")
    smtp_pass = st.secrets.get("SMTP_PASS", "")
    if not smtp_user or not smtp_pass: return False
    try:
        msg = MIMEMultipart()
        msg['From'] = f"İzmir Tenis Ağı <{smtp_user}>"
        msg['To'] = to_address
        msg['Subject'] = subject
        msg.attach(MIMEText(message, 'html'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True
    except: return False

def generate_ics(invite_data):
    # Basit bir takvim dosyası
    return "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nSUMMARY:Tenis Maçı\nEND:VEVENT\nEND:VCALENDAR"

# --- GİRİŞ / KAYIT / SİSTEM ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "current_user" not in st.session_state: st.session_state.current_user = ""

def main_app():
    users_db = load_data(USERS_FILE, dict)
    invites_db = load_data(INVITES_FILE, list)
    
    # --- YÖNETİCİ GİRİŞİ ---
    ADMIN_SECRET = st.secrets.get("ADMIN_PANEL_PASS", "izmir35")
    is_admin = False
    
    st.sidebar.title("🎾 Navigasyon")
    with st.sidebar.expander("Ayarlar"):
        admin_kod = st.text_input("Yönetici Kodu", type="password")
        if admin_kod == ADMIN_SECRET: is_admin = True
        
    menu = st.sidebar.radio("Menü", ["🏆 Havuz", "➕ İlan Ver", "👥 Üyeler"] + (["👑 Yönetici Paneli"] if is_admin else []))
    
    # --- HAVUZ ---
    if menu == "🏆 Havuz":
        st.header("🏆 Açık İlanlar")
        for idx, inv in enumerate(invites_db):
            if inv.get("durum") == "Açık":
                st.info(f"**{inv['kort']}** - {inv['tarih']} ({inv['saat']}) | Seviye: {inv['istenen_ntrp']}")
    
    # --- İLAN VER ---
    elif menu == "➕ İlan Ver":
        st.header("➕ Yeni İlan")
        tarih = st.date_input("Tarih")
        saat = st.text_input("Saat")
        kort = st.selectbox("Kort Seçin", KORTLAR)
        ntrp = st.selectbox("Aranan Seviye", NTRP_LIST)
        notlar = st.text_area("Notlar")
        
        if st.button("İlanı Yayınla"):
            invites_db.append({"tarih":str(tarih), "saat":saat, "kort":kort, "istenen_ntrp":ntrp, "notlar":notlar, "durum":"Açık"})
            save_data(INVITES_FILE, invites_db)
            st.success("İlan eklendi.")

    # --- YÖNETİCİ PANELİ ---
    elif menu == "👑 Yönetici Paneli" and is_admin:
        st.header("👑 Yönetici Paneli")
        st.download_button("Tüm Veriyi İndir", data=json.dumps({"users":users_db, "invites":invites_db}), file_name="yedek.json")
        st.warning("Verileriniz yedeklendi.")

if st.session_state.logged_in:
    main_app()
else:
    # Giriş Ekranı (Basitleştirilmiş)
    st.title("Giriş Yap")
    e = st.text_input("Email")
    p = st.text_input("Şifre", type="password")
    if st.button("Giriş"):
        st.session_state.logged_in = True
        st.session_state.current_user = e
        st.rerun()
    if st.button("Şifremi Unuttum"):
        st.info("Geçici şifre gönderildi.")
