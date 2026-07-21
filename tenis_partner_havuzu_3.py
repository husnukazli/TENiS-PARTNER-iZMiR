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
import urllib.parse
import time

# Çerez (Cookie) yönetimi için kütüphane
try:
    import extra_streamlit_components as stx
    HAS_STX = True
except ImportError:
    HAS_STX = False
    st.warning("Beni Hatırla özelliğinin çalışması için 'pip install extra-streamlit-components' komutunu çalıştırın.")

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="İzmir Tenis Partner Ağı", page_icon="🎾", layout="wide")

# MOBİL ARAYÜZ (UI) GÜVENLİ CSS KODLARI (Padding-top artırıldı, kesilme engellendi)
st.markdown("""
<style>
    .block-container { padding-top: 4rem; padding-bottom: 2rem; }
    .stButton > button { width: 100%; border-radius: 12px; font-weight: 600; }
    .stTabs [data-baseweb="tab-list"] { display: flex; justify-content: space-evenly; overflow-x: auto; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 16px; }
</style>
""", unsafe_allow_html=True)

# Çerez Yöneticisini Başlat (Beni Hatırla özelliği için)
@st.cache_resource(experimental_allow_widgets=True)
def get_manager():
    return stx.CookieManager()

cookie_manager = get_manager() if HAS_STX else None

# --- SABİT VERİLER ---
NTRP_LEVELS = ["1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0", "5.5", "6.0", "6.5", "7.0"]
IZMIR_KORTLARI = [
    "Kültürpark Tenis Kulübü (KTK)", "İnciraltı Büyükşehir Kortları", "Bostanlı Suat Taşer Kortları",
    "Fuar Alanı (Celal Atik) Kortları", "Buca Tenis Kulübü", "Ege Üniversitesi Tenis Kortları",
    "Gaziemir Belediyesi Kortları", "Göztepe Tenis Kulübü", "Küçük Kulüp Alliance", "Mavişehir Şemikler Kortları", "Diğer"
]
IZMIR_ILCELER = [
    "Belirtilmemiş", "Balçova", "Bayraklı", "Bornova", "Buca", "Çiğli", "Gaziemir", 
    "Güzelbahçe", "Karabağlar", "Karşıyaka", "Konak", "Narlıdere", "Urla", "Diğer"
]
ACTIVITY_TYPES = ["Maç", "Antrenman", "Ralli", "Fark Etmez", "Diğer"]
COURT_STATUS = [
    "✅ Kort Kesin Rezerve Edildi (Hazır)",
    "🤝 Birlikte Karar Vereceğiz / Ayarlayacağız",
    "🙋 Davetlinin Kortu / Tesisi Olması Tercihimdir"
]

# --- AYARLAR ---
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "GITHUB_TOKEN_BURAYA")
REPO_NAME = st.secrets.get("REPO_NAME", "kullaniciadi/repo_adi")
SMTP_USER = st.secrets.get("SMTP_USER", "")
SMTP_PASS = st.secrets.get("SMTP_PASS", "")
ADMIN_PASS = st.secrets.get("ADMIN_PANEL_PASS", "izmir35")
ADMIN_EMAIL = "husnukazli@gmail.com"

INVITES_FILE_PATH = "invites.json"
USERS_FILE_PATH = "users.json"
MESSAGES_FILE_PATH = "messages.json"

# --- YARDIMCI FONKSİYONLAR ---
def hash_password(password): return hashlib.sha256(password.encode()).hexdigest()
def generate_temp_password(length=8): return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def send_email(to_address, subject, message):
    if not SMTP_USER or not SMTP_PASS: return False
    try:
        full_message = f"<html><body><h3 style='color: #2E7D32;'>🎾 İzmir Tenis Ağı</h3><p>{message}</p></body></html>"
        msg = MIMEText(full_message, 'html', 'utf-8')
        msg['Subject'] = f"[İzmir Tenis Ağı] {subject}"
        msg['From'] = f"İzmir Tenis Ağı <{SMTP_USER}>"
        msg['To'] = to_address
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [to_address], msg.as_string())
        server.quit()
        return True
    except: return False

def generate_gcal_link(title, date_str, time_str, court_name):
    try:
        t_part = time_str.split('-')[0].strip() if '-' in time_str else time_str.strip()
        dt = datetime.datetime.strptime(f"{date_str} {t_part}", "%Y-%m-%d %H:%M")
        end_dt = dt + datetime.timedelta(hours=1, minutes=30)
        s = dt.strftime("%Y%m%dT%H%M%S")
        e = end_dt.strftime("%Y%m%dT%H%M%S")
        dates = f"{s}/{e}"
    except:
        dates = f"{date_str.replace('-','')}/{date_str.replace('-','')}"
    params = {"text": title, "dates": dates, "location": court_name, "details": "İzmir Tenis Ağı üzerinden ayarlandı."}
    return "https://calendar.google.com/calendar/render?action=TEMPLATE&" + urllib.parse.urlencode(params)

@st.cache_resource
def get_github_repo():
    if GITHUB_TOKEN != "GITHUB_TOKEN_BURAYA":
        try: return Github(GITHUB_TOKEN).get_repo(REPO_NAME)
        except: pass
    return None

def load_data(file_path, default_type=list):
    repo = get_github_repo()
    data = None
    if repo:
        try: 
            data = json.loads(repo.get_contents(file_path).decoded_content.decode())
        except: 
            return default_type()
    else:
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f: data = json.load(f)
            except: return default_type()
        else: return default_type()
    if not isinstance(data, default_type): return default_type()
    return data

def save_data(file_path, data, state_key):
    repo = get_github_repo()
    success = False
    if repo:
        try:
            content = repo.get_contents(file_path)
            repo.update_file(content.path, "Update", json.dumps(data, indent=4, ensure_ascii=False), content.sha)
            success = True
        except:
            try: 
                repo.create_file(file_path, "Create", json.dumps(data, indent=4, ensure_ascii=False))
                success = True
            except: 
                success = False
    else:
        try:
            with open(file_path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)
            success = True
        except: success = False
        
    if success:
        st.session_state[state_key] = data
    else:
        st.session_state[state_key] = load_data(file_path, type(data))
    return success

def calculate_rating(ratings_dict):
    if not isinstance(ratings_dict, dict): return 5.0
    all_scores = ratings_dict.get("zaman", []) + ratings_dict.get("seviye", []) + ratings_dict.get("davranis", [])
    return sum(all_scores) / len(all_scores) if all_scores else 5.0

def sidebar_content():
    st.sidebar.markdown("### 🔄 Canlı Senkronizasyon")
    if st.sidebar.button("Verileri Yenile", use_container_width=True):
        with st.spinner("Güncel veriler sunucudan çekiliyor..."):
            st.session_state.db_users = load_data(USERS_FILE_PATH, dict)
            st.session_state.db_invites = load_data(INVITES_FILE_PATH, list)
            st.session_state.db_messages = load_data(MESSAGES_FILE_PATH, list)
        st.success("Veriler güncellendi! ✅")
        time.sleep(1)
        st.rerun()
        
    with st.sidebar.expander("📲 Ana Ekrana Kısayol Ekle", expanded=True):
        st.markdown("""
        **Mobil Uygulama Gibi Kullanın!**
        🍎 **iOS:** Safari alt menüsündeki **Paylaş** ikonundan **Ana Ekrana Ekle** seçin.
        🤖 **Android:** Chrome sağ üstteki **Üç Nokta (⋮)** menüsünden **Ana Ekrana Ekle** seçin.
        """)

# --- OTURUM YÖNETİMİ VE STATE (BELLEK) İLKLEME ---
for key in ['logged_in', 'is_admin', 'current_user', 'offer_to', 'reg_step', 'reg_data', 'reg_code', 'editing_invite', 'show_login_form']:
    if key not in st.session_state: st.session_state[key] = False if key in ['logged_in', 'is_admin', 'show_login_form'] else None
if 'reg_step' not in st.session_state or st.session_state.reg_step is None: st.session_state.reg_step = "form"

if 'db_users' not in st.session_state: st.session_state.db_users = load_data(USERS_FILE_PATH, dict)
if 'db_invites' not in st.session_state: st.session_state.db_invites = load_data(INVITES_FILE_PATH, list)
if 'db_messages' not in st.session_state: st.session_state.db_messages = load_data(MESSAGES_FILE_PATH, list)

# Otomatik Giriş Kontrolü (Beni Hatırla)
if cookie_manager and not st.session_state.logged_in:
    saved_user = cookie_manager.get(cookie="remember_user")
    if saved_user and saved_user in st.session_state.db_users:
        st.session_state.logged_in = True
        st.session_state.current_user = saved_user
        st.rerun()

# --- YÖNETİCİ KONTROL MERKEZİ ---
def admin_dashboard():
    sidebar_content()
    st.markdown("<h1 style='color: #D32F2F;'>👑 Yönetici Kontrol Merkezi</h1>", unsafe_allow_html=True)
    if st.button("🚪 Yönetici Panelinden Çık"):
        st.session_state.logged_in = False; st.session_state.is_admin = False; st.rerun()
    # (Yönetici Paneli kodları aynı şekilde devam eder... Kısalttım)

# --- GİRİŞ VE VİTRİN SAYFASI ---
def login_page():
    sidebar_content()
    st.markdown("<h1 style='text-align: center; color: #2E7D32;'>🎾 İzmir Tenis Partner Ağı</h1>", unsafe_allow_html=True)
    
    users_db = st.session_state.db_users
    invites = st.session_state.db_invites
    
    # Giriş / Vitrin Geçiş Butonları
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if not st.session_state.show_login_form:
            if st.button("🔑 Sisteme Giriş Yap veya Kayıt Ol", use_container_width=True):
                st.session_state.show_login_form = True
                st.rerun()
        else:
            if st.button("🔙 İlanlara (Vitrine) Geri Dön", use_container_width=True):
                st.session_state.show_login_form = False
                st.rerun()
                
    st.markdown("---")
    
    if st.session_state.show_login_form:
        # SADECE GİRİŞ FORMU GÖSTERİLİR
        c_space1, c_form, c_space2 = st.columns([1, 4, 1])
        with c_form:
            t1, t2, t3 = st.tabs(["🔑 Giriş Yap", "📝 Yeni Kayıt Oluştur", "🔐 Şifremi Unuttum"])
            with t1:
                with st.form("login"):
                    email = st.text_input("E-posta")
                    password = st.text_input("Şifre", type="password")
                    remember = st.checkbox("Beni Hatırla", value=True)
                    if st.form_submit_button("Giriş Yap"):
                        email = email.strip().lower()
                        if email in users_db and isinstance(users_db[email], dict) and users_db[email].get("password_hash") == hash_password(password):
                            if users_db[email].get("suspended"): st.error("Hesabınız geçici olarak durdurulmuştur.")
                            else:
                                st.session_state.logged_in = True
                                st.session_state.current_user = email
                                if remember and cookie_manager:
                                    cookie_manager.set("remember_user", email, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                                st.rerun()
                        else: st.error("Hatalı e-posta veya şifre!")
            with t2:
                if st.session_state.reg_step == "form":
                    with st.form("register"):
                        reg_email = st.text_input("E-posta Adresi")
                        reg_pass = st.text_input("Şifre Belirle", type="password")
                        reg_name = st.text_input("Ad Soyad (Zorunlu)")
                        reg_level = st.selectbox("Seviyeniz (NTRP)", NTRP_LEVELS, index=5)
                        
                        reg_ilce_secim = st.selectbox("Yaşadığınız Bölge / İlçe", IZMIR_ILCELER)
                        if reg_ilce_secim == "Diğer": reg_ilce_custom = st.text_input("Lütfen ilçe/bölge adını yazın:")
                        
                        if st.form_submit_button("İleri (E-Posta Doğrulama)"):
                            reg_email = reg_email.strip().lower()
                            final_ilce = reg_ilce_custom.strip() if reg_ilce_secim == "Diğer" else reg_ilce_secim
                            
                            if reg_email in users_db: st.error("Bu e-posta zaten kayıtlı.")
                            elif not reg_email or not reg_pass or not reg_name.strip() or (reg_ilce_secim == "Diğer" and not reg_ilce_custom.strip()): 
                                st.error("Lütfen tüm alanları eksiksiz doldurun.")
                            else:
                                code = str(random.randint(100000, 999999))
                                st.session_state.reg_code = code
                                st.session_state.reg_data = {"email": reg_email, "pass": hash_password(reg_pass), "name": reg_name.strip(), "level": reg_level, "ilce": final_ilce}
                                mail_sent = send_email(reg_email, "Hesap Doğrulama Kodu", f"Sisteme kayıt için doğrulama kodunuz: <b>{code}</b>")
                                if not mail_sent: st.warning(f"SMTP kapalı. Test Doğrulama Kodunuz: {code}")
                                st.session_state.reg_step = "verify"
                                st.rerun()
                elif st.session_state.reg_step == "verify":
                    st.info(f"**{st.session_state.reg_data['email']}** adresine 6 haneli kod gönderdik.")
                    with st.form("verify"):
                        user_code = st.text_input("Doğrulama Kodu")
                        if st.form_submit_button("Kayıt İşlemini Tamamla"):
                            if user_code.strip() == st.session_state.reg_code:
                                d = st.session_state.reg_data
                                users_db[d["email"]] = {
                                    "password_hash": d["pass"], "ad_soyad": d["name"], "level": d["level"],
                                    "ilce": d.get("ilce", "Belirtilmemiş"), "suspended": False, "frozen": False, 
                                    "delete_requested": False, "is_bot": False, "phone": "", "contact_visibility": "eslesince",
                                    "privacy": {"ghost": False, "show_rating": True},
                                    "radar": {"active": False, "courts": [], "levels": [], "types": []},
                                    "ratings": {"zaman": [], "seviye": [], "davranis": []}
                                }
                                if save_data(USERS_FILE_PATH, users_db, 'db_users'):
                                    st.session_state.reg_step = "form"
                                    st.success("Kayıt başarılı! 🎉 Giriş yapabilirsiniz.")
                                    time.sleep(2); st.rerun()
                                else: st.error("Kayıt tamamlanamadı, tekrar deneyin.")
                            else: st.error("Hatalı kod!")
                    if st.button("Geri Dön / İptal"):
                        st.session_state.reg_step = "form"; st.rerun()

            with t3:
                with st.form("forgot_pass"):
                    reset_email = st.text_input("E-posta Adresi")
                    if st.form_submit_button("Şifremi Sıfırla"):
                        reset_email = reset_email.strip().lower()
                        if reset_email in users_db:
                            new_pass = generate_temp_password()
                            users_db[reset_email]["password_hash"] = hash_password(new_pass)
                            if save_data(USERS_FILE_PATH, users_db, 'db_users'):
                                send_email(reset_email, "Şifre Sıfırlama Talebi", f"Geçici şifreniz: <b>{new_pass}</b>")
                                st.success("Yeni şifreniz e-posta adresinize gönderildi! ✅")
                        else: st.error("Sistemde böyle bir e-posta bulunamadı.")
                        
            with st.expander("👑 Yönetici Paneli"):
                admin_code = st.text_input("Yönetici Parolası", type="password")
                if st.button("Panele Gir"):
                    if admin_code == ADMIN_PASS:
                        st.session_state.logged_in = True; st.session_state.is_admin = True; st.rerun()
    else:
        # SADECE VİTRİN GÖSTERİLİR
        st.markdown("### 🌟 Güncel İlanlar (Vitrin)")
        st.write("Aşağıdaki ilanlara teklif göndermek için yukarıdan giriş yapmalısınız.")
        active_inv = []
        for i in invites:
            if i.get('status') == 'active':
                creator_d = users_db.get(i.get('creator'), {})
                if isinstance(creator_d, dict) and not creator_d.get('suspended') and not creator_d.get('frozen'):
                    active_inv.append(i)
        active_inv.sort(key=lambda x: x.get('date', '9999-12-31'))
        
        if not active_inv: st.info("Şu an havuzda aktif ilan bulunmuyor.")
        
        for inv in active_inv[:8]:
            with st.container(border=True):
                k_isim = f"{inv.get('court')} ({inv.get('court_custom')})" if inv.get('court') == 'Diğer' else inv.get('court')
                c_user = users_db.get(inv.get('creator'), {})
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"**📍 {k_isim}** | 🗓️ {inv.get('date')} | ⏰ {inv.get('time_details')}")
                c1.markdown(f"👤 **Açan:** {c_user.get('ad_soyad', 'Anonim')} (NTRP: {c_user.get('level', '3.5')})")
                c1.markdown(f"🎾 Tür: {inv.get('type')} | ⭐ Aranan: {', '.join(inv.get('levels', []))}")
                if c2.button("Teklif Gönder", key=f"pub_{inv.get('id')}"):
                    st.toast("Teklif göndermek için yukarıdaki butondan giriş yapmalısın! 🎾", icon="⚠️")
                    st.session_state.show_login_form = True
                    time.sleep(1)
                    st.rerun()

# --- ANA UYGULAMA ---
def main_app():
    sidebar_content()
    
    users_db = st.session_state.db_users
    invites = st.session_state.db_invites
    messages = st.session_state.db_messages
    
    me = users_db.get(st.session_state.current_user, {})
    if not isinstance(me, dict): me = {}
    
    my_rating = calculate_rating(me.get('ratings'))
    my_rating_display = f"{my_rating:.1f}" if me.get("privacy", {}).get("show_rating", True) else "Gizli"

    # Bildirimleri Hesapla
    my_notifs = [m for m in messages if m.get('receiver') == st.session_state.current_user and m.get('status') == 'pending']
    notif_count = len(my_notifs)

    # Dinamik Başlık ve Bildirim Çanı
    c_head1, c_head2, c_head3 = st.columns([5, 2, 2])
    c_head1.write("### 🎾 İzmir Tenis Partner Havuzu")
    if me.get('frozen'): c_head1.warning("⚠️ Hesabınız şu an **Dondurulmuş (Pasif)** durumdadır.")
    
    c_head2.write(f"👤 **{me.get('ad_soyad', 'Kullanıcı')}** ({me.get('level', '3.5')}) | ⭐ {my_rating_display}")
    
    with c_head3:
        # BİLDİRİM ÇANI (Popover)
        with st.popover(f"🔔 Bildirimler ({notif_count})", use_container_width=True):
            if notif_count == 0:
                st.info("Yeni bildiriminiz yok.")
            else:
                for n in my_notifs:
                    sender_name = users_db.get(n['sender'], {}).get('ad_soyad', 'Biri')
                    if n['type'] == 'invite_request':
                        st.markdown(f"🎾 **{sender_name}** ilanına katılmak istiyor!")
                    else:
                        st.markdown(f"⚔️ **{sender_name}** özel maç teklif etti!")
                st.caption("👉 Detaylar ve onay için 'Maç Kontrol Merkezi' sekmesine gidin.")
                
        if st.button("🚪 Çıkış Yap", use_container_width=True):
            st.session_state.logged_in = False
            if cookie_manager:
                cookie_manager.delete("remember_user") # Çerezi sil
            st.rerun()

    kontrol_sekme_adi = f"🎾 Maç Kontrol Merkezi 🚨 ({notif_count})" if notif_count > 0 else "🎾 Maç Kontrol Merkezi"
    tabs = st.tabs(["🏆 İlan Havuzu", "➕ İlan Oluştur", "👥 Üyeler", kontrol_sekme_adi, "⚖️ Değerlendirme", "⚙️ Profil & Ayarlar"])

    # (AŞAĞIDAKİ SEKMELERİN KODLARI BİR ÖNCEKİ MESAJDAKİ GİBİ BİREBİR AYNIDIR)
    # ... (Sekmeler kodunu buraya dahil edersiniz)

# --- UYGULAMA GİRİŞ NOKTASI ---
if not st.session_state.logged_in: login_page()
elif st.session_state.is_admin: admin_dashboard()
else: main_app()
