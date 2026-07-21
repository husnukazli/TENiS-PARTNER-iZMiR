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

# MOBİL ARAYÜZ (UI) GÜVENLİ CSS KODLARI
st.markdown("""
<style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    .stButton > button { width: 100%; border-radius: 12px; font-weight: 600; }
    .stTabs [data-baseweb="tab-list"] { display: flex; justify-content: space-evenly; overflow-x: auto; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 16px; }
</style>
""", unsafe_allow_html=True)

# Çerez Yöneticisini Başlat (Hatasız Yapı)
def get_manager():
    return stx.CookieManager(key="cookie_manager_widget")

if HAS_STX:
    if "cookie_manager" not in st.session_state:
        st.session_state.cookie_manager = get_manager()
    cookie_manager = st.session_state.cookie_manager
else:
    cookie_manager = None

# --- SABİT VERİLER ---
NTRP_LEVELS = ["1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0", "5.5", "6.0", "6.5", "7.0"]
IZMIR_KORTLARI = [
    "Kültürpark Tenis Kulübü (KTK)", "İnciraltı Büyükşehir Kortları", "Bostanlı Suat Taşer Kortları",
    "Fuar Alanı (Celal Atik) Kortları", "Buca Tenis Kulübü", "Ege Üniversitesi Tenis Kortları",
    "Gaziemir Belediyesi Kortları", "Göztepe Tenis Kulübü", "Küçük Kulüp Alliance", "Mavişehir Şemikler Kortları", "Diğer"
]
IZMIR_ILCELER = [
    "Belirtilmemiş", "Balçova", "Bayraklı", "Bornova", "Buca", "Çiğli", "Gaziemir", 
    "Güzelbahçe", "Karabağlar", "Karşıyaka", "Konak", "Narlıdere", "Urla", "Diğer Merkez Dışı"
]
ACTIVITY_TYPES = ["Maç", "Antrenman", "Ralli", "Fark Etmez"]
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
                with open(file_path, "r", encoding="utf-8") as f: 
                    data = json.load(f)
            except:
                return default_type()
        else:
            return default_type()
            
    if not isinstance(data, default_type):
        return default_type()
        
    return data

def save_data(file_path, data, state_key=None):
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
            with open(file_path, "w", encoding="utf-8") as f: 
                json.dump(data, f, indent=4, ensure_ascii=False)
            success = True
        except: 
            success = False
            
    if success and state_key:
        st.session_state[state_key] = data
    return success

def calculate_rating(ratings_dict):
    if not isinstance(ratings_dict, dict): return 5.0
    all_scores = ratings_dict.get("zaman", []) + ratings_dict.get("seviye", []) + ratings_dict.get("davranis", [])
    return sum(all_scores) / len(all_scores) if all_scores else 5.0

def sidebar_pwa_guide():
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
        
        🍎 **iOS (iPhone/iPad):**
        1. Safari alt menüsündeki **Paylaş** (kare ve yukarı ok) ikonuna dokunun.
        2. **Ana Ekrana Ekle** seçeneğini seçin.
        
        🤖 **Android:**
        1. Chrome sağ üstteki **Üç Nokta (⋮)** menüsüne dokunun.
        2. **Ana Ekrana Ekle** seçeneğini seçin.
        """)

# --- OTURUM YÖNETİMİ VE STATE İLKLEME ---
for key in ['logged_in', 'is_admin', 'current_user', 'offer_to', 'reg_step', 'reg_data', 'reg_code', 'editing_invite', 'show_login_form']:
    if key not in st.session_state: st.session_state[key] = False if key in ['logged_in', 'is_admin', 'show_login_form'] else None
if 'reg_step' not in st.session_state or st.session_state.reg_step is None: st.session_state.reg_step = "form"

if 'db_users' not in st.session_state: st.session_state.db_users = load_data(USERS_FILE_PATH, dict)
if 'db_invites' not in st.session_state: st.session_state.db_invites = load_data(INVITES_FILE_PATH, list)
if 'db_messages' not in st.session_state: st.session_state.db_messages = load_data(MESSAGES_FILE_PATH, list)

# Otomatik Giriş Kontrolü
if cookie_manager and not st.session_state.logged_in:
    saved_user = cookie_manager.get(cookie="remember_user")
    if saved_user and saved_user in st.session_state.db_users:
        st.session_state.logged_in = True
        st.session_state.current_user = saved_user
        st.rerun()

# --- YÖNETİCİ KONTROL MERKEZİ ---
def admin_dashboard():
    sidebar_pwa_guide()
    st.markdown("<h1 style='color: #D32F2F;'>👑 Yönetici Kontrol Merkezi</h1>", unsafe_allow_html=True)
    if st.button("🚪 Yönetici Panelinden Çık"):
        st.session_state.logged_in = False; st.session_state.is_admin = False
        if cookie_manager:
            cookie_manager.delete("remember_user")
        st.rerun()
    
    users_db = st.session_state.db_users
    invites = st.session_state.db_invites
    messages = st.session_state.db_messages

    active_inv_count = len([i for i in invites if i.get('status') == 'active'])
    inv_tab_label = f"📅 İlan Yönetimi 🟢 ({active_inv_count})" if active_inv_count > 0 else "📅 İlan Yönetimi"
    
    del_requests_count = len([u for u, d in users_db.items() if isinstance(d, dict) and d.get('delete_requested')])
    users_tab_label = f"👥 Üye Yönetimi 🚨 ({del_requests_count})" if del_requests_count > 0 else "👥 Üye Yönetimi"

    t1, t2, t3 = st.tabs([users_tab_label, inv_tab_label, "💾 Yedekleme & Kurtarma"])
    
    with t1:
        st.subheader("Kayıtlı Üyeler ve Silme Talepleri")
        for u_email, u_data in users_db.items():
            if not isinstance(u_data, dict): continue 
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 2, 2])
                status = "🔴 Askıda" if u_data.get("suspended") else ("⏸️ Dondurulmuş" if u_data.get("frozen") else "🟢 Aktif")
                del_req_badge = " 🚨 [SİLME TALEBİ]" if u_data.get("delete_requested") else ""
                test_tag = " 🧪 (Test)" if u_data.get("is_bot") else ""
                
                c1.write(f"**{u_data.get('ad_soyad')}{test_tag}{del_req_badge}** | {u_email} | Durum: {status}")
                
                confirm_susp_key = f"conf_susp_{u_email}"
                confirm_del_key = f"conf_del_{u_email}"
                
                if not st.session_state.get(confirm_susp_key, False):
                    if c2.button("Kaldır / Askıya Al", key=f"btn_susp_{u_email}"):
                        st.session_state[confirm_susp_key] = True
                        st.rerun()
                else:
                    c2.warning("Emin misiniz?")
                    if c2.button("Evet, Değiştir", key=f"yes_susp_{u_email}"):
                        users_db[u_email]["suspended"] = not u_data.get("suspended", False)
                        if save_data(USERS_FILE_PATH, users_db, 'db_users'):
                            st.session_state[confirm_susp_key] = False
                            st.toast("Üye durumu güncellendi!", icon="✅")
                            time.sleep(1); st.rerun()
                        else:
                            st.error("⚠️ Hata: Üye durumu güncellenemedi, lütfen tekrar deneyin.")
                    if c2.button("Vazgeç", key=f"no_susp_{u_email}"):
                        st.session_state[confirm_susp_key] = False
                        st.rerun()

                if not st.session_state.get(confirm_del_key, False):
                    if c3.button("🗑️ Kalıcı Sil", key=f"btn_del_{u_email}"):
                        st.session_state[confirm_del_key] = True
                        st.rerun()
                else:
                    c3.warning("Kalıcı silinsin mi?")
                    if c3.button("Evet, Kalıcı Sil", key=f"yes_del_{u_email}"):
                        users_db.pop(u_email, None)
                        if save_data(USERS_FILE_PATH, users_db, 'db_users'):
                            st.session_state[confirm_del_key] = False
                            st.toast("Üye verileri tamamen silindi!", icon="🗑️")
                            time.sleep(1); st.rerun()
                        else:
                            st.error("⚠️ Hata: Üye silinirken bir çakışma yaşandı. Lütfen tekrar deneyin.")
                    if c3.button("Vazgeç", key=f"no_del_{u_email}"):
                        st.session_state[confirm_del_key] = False
                        st.rerun()

    with t2:
        st.subheader("Sistemdeki İlanlar")
        for inv in reversed(invites):
            c1, c2 = st.columns([6, 2])
            c1.write(f"📍 {inv.get('court')} | 🗓️ {inv.get('date')} | Durum: **{inv.get('status')}**")
            
            conf_inv_key = f"conf_inv_del_{inv.get('id')}"
            if not st.session_state.get(conf_inv_key, False):
                if c2.button("🗑️ İlanı Kaldır", key=f"btn_adm_del_{inv.get('id')}"):
                    st.session_state[conf_inv_key] = True
                    st.rerun()
            else:
                c2.warning("Silinsin mi?")
                if c2.button("Evet", key=f"yes_inv_{inv.get('id')}"):
                    yeni_invites = [i for i in invites if i.get('id') != inv.get('id')]
                    if save_data(INVITES_FILE_PATH, yeni_invites, 'db_invites'):
                        st.session_state[conf_inv_key] = False
                        st.toast("İlan silindi!", icon="✅")
                        time.sleep(1); st.rerun()
                    else:
                        st.error("⚠️ Hata: İlan silinirken sorun oluştu. Lütfen tekrar deneyin.")
                if c2.button("İptal", key=f"no_inv_{inv.get('id')}"):
                    st.session_state[conf_inv_key] = False
                    st.rerun()

    with t3:
        st.subheader("Sistem Yedekleme ve Kurtarma")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 📥 Yedeği İndir")
            st.download_button("Üyeler Yedeği (users.json)", data=json.dumps(users_db, indent=4, ensure_ascii=False), file_name="users_backup.json", mime="application/json")
            st.download_button("İlanlar Yedeği (invites.json)", data=json.dumps(invites, indent=4, ensure_ascii=False), file_name="invites_backup.json", mime="application/json")
            st.download_button("Mesajlar Yedeği (messages.json)", data=json.dumps(messages, indent=4, ensure_ascii=False), file_name="messages_backup.json", mime="application/json")
        with c2:
            st.markdown("### 📤 Yedekten Yükle")
            up_u = st.file_uploader("Üye Yedeği Yükle", type=["json"])
            if st.button("Uygula (Üyeler)") and up_u:
                if save_data(USERS_FILE_PATH, json.loads(up_u.getvalue().decode("utf-8")), 'db_users'):
                    st.success("Üyeler başarıyla güncellendi!")
                    time.sleep(1); st.rerun()
                else:
                    st.error("⚠️ Hata: Yedek yüklenemedi.")

# --- GİRİŞ VE VİTRİN SAYFASI ---
def login_page():
    sidebar_pwa_guide()
    st.markdown("<h1 style='text-align: center; color: #2E7D32;'>🎾 İzmir Tenis Partner Ağı</h1>", unsafe_allow_html=True)
    
    users_db = st.session_state.db_users
    invites = st.session_state.db_invites
    
    # Giriş / Vitrin Dinamik Geçişi
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
        # SADECE GİRİŞ FORMU GÖSTERİLİR (Ortalanmış)
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
                        if reg_ilce_secim == "Diğer Merkez Dışı": reg_ilce_custom = st.text_input("Lütfen ilçe/bölge adını yazın:")
                        else: reg_ilce_custom = ""
                        
                        if st.form_submit_button("İleri (E-Posta Doğrulama)"):
                            reg_email = reg_email.strip().lower()
                            final_ilce = reg_ilce_custom.strip() if reg_ilce_secim == "Diğer Merkez Dışı" else reg_ilce_secim
                            
                            if reg_email in users_db: st.error("Bu e-posta zaten kayıtlı.")
                            elif not reg_email or not reg_pass or not reg_name.strip() or (reg_ilce_secim == "Diğer Merkez Dışı" and not reg_ilce_custom.strip()): 
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
                                    admin_msg = f"Sisteme yeni bir üye katıldı!<br><br><b>Ad Soyad:</b> {d['name']}<br><b>E-posta:</b> {d['email']}<br><b>NTRP Seviyesi:</b> {d['level']}<br><b>İlçe:</b> {d.get('ilce', 'Belirtilmedi')}"
                                    send_email(ADMIN_EMAIL, "🎉 Yeni Üye Kaydı", admin_msg)
                                    st.session_state.reg_step = "form"
                                    st.success("Kayıt başarılı! 🎉 Giriş yapabilirsiniz.")
                                    time.sleep(2); st.rerun()
                                else:
                                    st.error("⚠️ Kayıt tamamlanamadı. Veritabanı ile bağlantı kurulamadı. Lütfen tekrar deneyin.")
                            else: st.error("Hatalı kod!")
                    if st.button("Geri Dön / İptal"):
                        st.session_state.reg_step = "form"; st.rerun()

            with t3:
                with st.form("forgot_pass"):
                    st.info("Kayıtlı e-posta adresinizi girin. Size geçici bir şifre göndereceğiz.")
                    reset_email = st.text_input("E-posta Adresi")
                    if st.form_submit_button("Şifremi Sıfırla"):
                        reset_email = reset_email.strip().lower()
                        if reset_email in users_db:
                            new_pass = generate_temp_password()
                            users_db[reset_email]["password_hash"] = hash_password(new_pass)
                            if save_data(USERS_FILE_PATH, users_db, 'db_users'):
                                send_email(reset_email, "Şifre Sıfırlama Talebi", f"Geçici şifreniz: <b>{new_pass}</b><br><br>Giriş yaptıktan sonra profilinizden şifrenizi değiştirmeyi unutmayın.")
                                st.success("Yeni şifreniz e-posta adresinize gönderildi! ✅")
                            else:
                                st.error("⚠️ Veritabanı hatası: Şifre sıfırlama işlemi kaydedilemedi.")
                        else: st.error("Sistemde böyle bir e-posta bulunamadı.")
                        
            with st.expander("👑 Yönetici Paneli"):
                admin_code = st.text_input("Yönetici Parolası", type="password")
                if st.button("Panele Gir"):
                    if admin_code == ADMIN_PASS:
                        st.session_state.logged_in = True; st.session_state.is_admin = True; st.rerun()
                    else: st.error("Hatalı Parola!")

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
    sidebar_pwa_guide()
    
    users_db = st.session_state.db_users
    invites = st.session_state.db_invites
    messages = st.session_state.db_messages
    me = users_db.get(st.session_state.current_user, {})
    if not isinstance(me, dict): me = {}
    
    my_rating = calculate_rating(me.get('ratings'))
    my_rating_display = f"{my_rating:.1f}" if me.get("privacy", {}).get("show_rating", True) else "Gizli"

    my_inbox_count = len([m for m in messages if m.get('receiver') == st.session_state.current_user and m.get('status') == 'pending'])

    # DİNAMİK BAŞLIK VE BİLDİRİM ÇANI
    c_head1, c_head2, c_head3 = st.columns([5, 2, 2])
    c_head1.write("### 🎾 İzmir Tenis Partner Havuzu")
    if me.get('frozen'):
        c_head1.warning("⚠️ Hesabınız şu an **Dondurulmuş (Pasif)** durumdadır. Diğer üyeler size teklif gönderemez ve ilanlarınız görünmez.")
    
    c_head2.write(f"👤 **{me.get('ad_soyad', 'Kullanıcı')}** ({me.get('level', '3.5')}) | ⭐ {my_rating_display}")
    
    with c_head3:
        # BİLDİRİM ÇANI (Popover)
        with st.popover(f"🔔 Bildirimler ({my_inbox_count})", use_container_width=True):
            if my_inbox_count == 0:
                st.info("Yeni bildiriminiz yok.")
            else:
                my_inbox_msgs = [m for m in messages if m.get('receiver') == st.session_state.current_user and m.get('status') == 'pending']
                for n in my_inbox_msgs:
                    sender_name = users_db.get(n['sender'], {}).get('ad_soyad', 'Biri')
                    if n['type'] == 'invite_request':
                        st.markdown(f"🎾 **{sender_name}** ilanına katılmak istiyor!")
                    else:
                        st.markdown(f"⚔️ **{sender_name}** özel maç teklif etti!")
                st.caption("👉 Detaylar ve onay için 'Maç Kontrol Merkezi' sekmesine gidin.")
                
        if st.button("🚪 Çıkış Yap", use_container_width=True): 
            st.session_state.logged_in = False
            if cookie_manager:
                cookie_manager.delete("remember_user")
            st.rerun()

    kontrol_sekme_adi = f"🎾 Maç Kontrol Merkezi 🚨 ({my_inbox_count})" if my_inbox_count > 0 else "🎾 Maç Kontrol Merkezi"

    tabs = st.tabs(["🏆 İlan Havuzu", "➕ İlan Oluştur", "👥 Üyeler", kontrol_sekme_adi, "⚖️ Değerlendirme", "⚙️ Profil & Ayarlar"])

    # --- TAB 0: İLAN HAVUZU ---
    with tabs[0]:
        with st.expander("🔍 İlanları Filtrele ve Sırala", expanded=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            sort_by = f_col1.selectbox("Sıralama Ölçütü", ["Tarihe Göre (En Yakın)", "Eklenme Zamanına Göre (En Yeni)"])
            filter_court = f_col2.multiselect("Kort Filtresi", IZMIR_KORTLARI)
            filter_level = f_col3.multiselect("Seviye Filtresi", NTRP_LEVELS)
            
        active_invites = []
        for i in invites:
            if i.get('status') == 'active':
                u_creator = users_db.get(i.get('creator'), {})
                if isinstance(u_creator, dict) and not u_creator.get('suspended') and not u_creator.get('frozen'):
                    active_invites.append(i)
        
        if filter_court: active_invites = [i for i in active_invites if i.get('court') in filter_court]
        if filter_level: active_invites = [i for i in active_invites if any(l in filter_level for l in i.get('levels', []))]
        
        if sort_by == "Tarihe Göre (En Yakın)":
            active_invites.sort(key=lambda x: x.get('date', '9999-12-31'))
        else:
            active_invites.reverse()

        if not active_invites:
            st.info("Kriterlere uygun aktif ilan bulunamadı.")

        for inv in active_invites:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 3, 2])
                k_isim = f"{inv.get('court')} ({inv.get('court_custom')})" if inv.get('court') == 'Diğer' else inv.get('court')
                
                creator_user = users_db.get(inv.get('creator'), {})
                if not isinstance(creator_user, dict): creator_user = {}

                c1.markdown(f"**📍 Kort:** {k_isim}")
                c1.markdown(f"**🗓️ Tarih:** {inv.get('date')} | ⏰ **Saat:** {inv.get('time_details')}")
                if inv.get('note'): c1.markdown(f"**📝 Not:** {inv.get('note')}")
                
                c2.markdown(f"**🎾 Tür:** {inv.get('type')} | **⭐ Aranan:** {', '.join(inv.get('levels', []))}")
                c2.markdown(f"**🔑 Durum:** {inv.get('court_status')}")
                
                c3.markdown(f"👤 **Açan:** {creator_user.get('ad_soyad', 'Anonim')} *(NTRP {creator_user.get('level', '3.5')})*")
                
                if creator_user.get('contact_visibility') == 'herkes':
                    c3.markdown(f"📞 {creator_user.get('phone', '-')} | ✉️ {inv.get('creator')}")

                if inv.get('creator') != st.session_state.current_user:
                    has_sent = any(
                        m.get('sender') == st.session_state.current_user and 
                        m.get('invite_id') == inv.get('id') and 
                        m.get('status') == 'pending' 
                        for m in messages
                    )
                    
                    if has_sent:
                        c3.button("✅ Teklif İletildi", key=f"inv_sent_{inv.get('id')}", disabled=True)
                    else:
                        if c3.button("🎾 Teklif Gönder", key=f"inv_{inv.get('id')}"):
                            new_msg = {
                                "id": str(uuid.uuid4()), "type": "invite_request", "invite_id": inv.get('id'),
                                "sender": st.session_state.current_user, "receiver": inv.get('creator'),
                                "status": "pending", "timestamp": str(datetime.datetime.now())
                            }
                            mesaj_yeni = messages + [new_msg]
                            if save_data(MESSAGES_FILE_PATH, mesaj_yeni, 'db_messages'):
                                st.toast("Teklifiniz başarıyla ilan sahibine iletildi! 🎉", icon="✅")
                                time.sleep(1); st.rerun()
                            else:
                                st.error("⚠️ Veri hatası: Teklifiniz kaydedilemedi. Lütfen sayfayı yenileyip tekrar deneyin.")

    # --- TAB 1: İLAN OLUŞTUR ---
    with tabs[1]:
        st.subheader("➕ Yeni İlan Yayınla")
        if me.get('frozen'):
            st.warning("⚠️ Hesabınız dondurulmuş durumda. İlan oluşturabilirsiniz ancak hesabınızı aktifleştirene kadar ilanınız vitrinde görünmez.")
            
        with st.form("create_invite"):
            c1, c2 = st.columns(2)
            d = c1.date_input("Tarih", min_value=datetime.date.today())
            
            c_t1, c_t2 = c1.columns(2)
            t_start = c_t1.time_input("Başlangıç Saati", datetime.time(18, 0))
            t_end = c_t2.time_input("Bitiş Saati", datetime.time(19, 30))
            
            court = c2.selectbox("Kort / Saha", IZMIR_KORTLARI)
            court_custom = c2.text_input("Diğer ise Kort Adını Yazın:") if court == "Diğer" else ""
            court_status = c2.selectbox("Kort Rezervasyon Durumu", COURT_STATUS)
            
            act_type = st.selectbox("Etkinlik Tipi", ACTIVITY_TYPES)
            levels = st.multiselect("Aranan Seviyeler (NTRP)", NTRP_LEVELS, default=[me.get("level", "3.5")])
            inv_note = st.text_area("İlan Notu / Açıklama (İsteğe bağlı)")
            
            if st.form_submit_button("📢 İlanı Yayınla"):
                if not levels:
                    st.error("Lütfen en az bir aranan seviye seçin.")
                elif court == "Diğer" and not court_custom.strip():
                    st.error("Lütfen Kort Adı alanını doldurun.")
                elif t_start >= t_end:
                    st.error("Bitiş saati başlangıç saatinden sonra olmalıdır.")
                else:
                    new_inv = {
                        "id": str(uuid.uuid4()), "creator": st.session_state.current_user,
                        "date": str(d), "time_details": f"{t_start.strftime('%H:%M')} - {t_end.strftime('%H:%M')}",
                        "court": court, "court_custom": court_custom, "court_status": court_status,
                        "type": act_type, "levels": levels, "status": "active", "note": inv_note,
                        "created_at": str(datetime.datetime.now())
                    }
                    ilanlar_yeni = invites + [new_inv]
                    
                    if save_data(INVITES_FILE_PATH, ilanlar_yeni, 'db_invites'):
                        radar_count = 0
                        for u_email, u_data in users_db.items():
                            if u_email == st.session_state.current_user or not isinstance(u_data, dict): continue
                            if u_data.get('frozen') or u_data.get('suspended'): continue
                            r = u_data.get("radar", {})
                            if r.get("active", False):
                                match_court = not r.get("courts") or court in r.get("courts") or (court == "Diğer" and "Diğer" in r.get("courts"))
                                match_level = not r.get("levels") or any(l in r.get("levels") for l in levels)
                                match_type = not r.get("types") or act_type in r.get("types") or "Fark Etmez" in r.get("types")
                                
                                if match_court and match_level and match_type:
                                    send_email(
                                        u_email, "📡 Radar Alarmı: Uygun İlan Yayınlandı!",
                                        f"Merhaba <b>{u_data.get('ad_soyad')}</b>,<br><br>Radar kriterlerinize uygun yeni bir tenis partner ilanı yayınlandı!<br><br><b>Kort:</b> {court}<br><b>Tarih/Saat:</b> {str(d)} | {t_start.strftime('%H:%M')}-{t_end.strftime('%H:%M')}<br><b>İlan Sahibi:</b> {me.get('ad_soyad')} ({me.get('level', '3.5')})<br><br>Sisteme giriş yaparak ilana teklif gönderebilirsiniz."
                                    )
                                    radar_count += 1

                        st.toast("İlanınız başarıyla yayınlandı! 🎉", icon="✅")
                        if radar_count > 0: st.info(f"📡 Radar kriterleri eşleşen {radar_count} kişiye e-posta bildirimi gönderildi.")
                        time.sleep(1.5); st.rerun()
                    else:
                        st.error("⚠️ Veri çakışması! İlanınız sisteme kaydedilemedi. Lütfen tekrar deneyin.")

    # --- TAB 2: ÜYELER ---
    with tabs[2]:
        c_title, c_sort = st.columns([3, 2])
        c_title.subheader("👥 Oyuncu Listesi")
        sort_users = c_sort.selectbox("Üyeleri Sırala:", ["İsme Göre (A-Z)", "Seviyeye Göre (Yüksekten Düşüğe)", "Puana Göre (Popülerlik)", "Bölgeye Göre (İlçe)"])
        
        user_list = []
        for u_email, u_data in users_db.items():
            if not isinstance(u_data, dict) or u_email == st.session_state.current_user: continue
            if u_data.get("privacy", {}).get("ghost") or u_data.get("frozen") or u_data.get("suspended"): continue
            
            u_rating = calculate_rating(u_data.get('ratings'))
            try: u_level = float(u_data.get('level', '3.5'))
            except: u_level = 3.5
            
            user_list.append((u_email, u_data, u_rating, u_level))

        if sort_users == "İsme Göre (A-Z)":
            user_list.sort(key=lambda x: x[1].get('ad_soyad', '').lower())
        elif sort_users == "Seviyeye Göre (Yüksekten Düşüğe)":
            user_list.sort(key=lambda x: x[3], reverse=True)
        elif sort_users == "Puana Göre (Popülerlik)":
            user_list.sort(key=lambda x: x[2], reverse=True)
        elif sort_users == "Bölgeye Göre (İlçe)":
            user_list.sort(key=lambda x: x[1].get('ilce', 'Belirtilmemiş'))

        if st.session_state.offer_to:
            target_u = users_db.get(st.session_state.offer_to, {})
            if not isinstance(target_u, dict): target_u = {}
            st.info(f"👉 **{target_u.get('ad_soyad', 'Kullanıcı')}** kişisine özel teklif oluşturuyorsunuz.")
            
            with st.form("direct_offer"):
                o_date = st.date_input("Tarih Önerisi", min_value=datetime.date.today())
                c_o1, c_o2 = st.columns(2)
                o_t1 = c_o1.time_input("Başlangıç", datetime.time(18, 0))
                o_t2 = c_o2.time_input("Bitiş", datetime.time(19, 30))
                o_court = st.selectbox("Kort Önerisi", IZMIR_KORTLARI)
                o_custom = st.text_input("Diğer ise belirtin:") if o_court == "Diğer" else ""
                
                c_sub, c_can = st.columns(2)
                if c_sub.form_submit_button("🚀 Teklifi Gönder"):
                    new_msg = {
                        "id": str(uuid.uuid4()), "type": "direct_challenge", "sender": st.session_state.current_user,
                        "receiver": st.session_state.offer_to, "date": str(o_date),
                        "time": f"{o_t1.strftime('%H:%M')} - {o_t2.strftime('%H:%M')}",
                        "court": o_court, "court_custom": o_custom, "status": "pending"
                    }
                    mesaj_yeni = messages + [new_msg]
                    if save_data(MESSAGES_FILE_PATH, mesaj_yeni, 'db_messages'):
                        st.session_state.offer_to = None
                        st.toast("Özel teklifiniz başarıyla iletildi!", icon="✅")
                        time.sleep(1); st.rerun()
                    else:
                        st.error("⚠️ Veri hatası: Özel teklifiniz kaydedilemedi. Lütfen tekrar deneyin.")
                if c_can.form_submit_button("İptal"):
                    st.session_state.offer_to = None; st.rerun()

        for u_email, u_data, rating_val, _ in user_list:
            with st.container(border=True):
                colA, colB, colC = st.columns([3, 3, 2])
                
                show_r = u_data.get("privacy", {}).get("show_rating", True)
                disp_rating = f"{rating_val:.1f}" if show_r else "Gizli"
                
                u_ilce = u_data.get('ilce', 'Belirtilmemiş')
                ilce_txt = f"📍 {u_ilce}" if u_ilce != "Belirtilmemiş" else ""

                colA.markdown(f"**👤 {u_data.get('ad_soyad')}** | NTRP: **{u_data.get('level', '3.5')}** {ilce_txt}")
                colA.markdown(f"⭐ Puan: **{disp_rating}** | Tarz: {u_data.get('style', 'Belirtilmedi')}")
                
                cv = u_data.get('contact_visibility')
                if cv == 'herkes':
                    colB.write(f"📞 {u_data.get('phone', 'Gizli')} | ✉️ {u_email}")
                else:
                    colB.write("🔒 İletişim: Eşleşince Görünür")
                
                has_direct = any(m.get('sender') == st.session_state.current_user and m.get('receiver') == u_email and m.get('status') == 'pending' for m in messages)
                
                if has_direct:
                    colC.button("✅ Teklif Gönderildi", key=f"dir_sent_{u_email}", disabled=True)
                else:
                    if colC.button("🎾 Özel Teklif Et", key=f"chall_{u_email}"):
                        st.session_state.offer_to = u_email; st.rerun()

    # --- TAB 3: MAÇ KONTROL MERKEZİ ---
    with tabs[3]:
        st.subheader("🎾 Maç Kontrol Merkezi")
        
        inbox_label = f"📥 Gelen Teklifler ({my_inbox_count})" if my_inbox_count > 0 else "📥 Gelen Teklifler"
        m_tab1, m_tab2, m_tab3, m_tab4 = st.tabs([
            inbox_label, "📤 Gönderdiğim Teklifler", "📅 Onaylanmış Maçlarım", "📜 Geçmiş & İptal Edilenler"
        ])

        with m_tab1:
            my_inbox = [m for m in messages if m.get('receiver') == st.session_state.current_user and m.get('status') == 'pending']
            if not my_inbox: st.info("Bekleyen gelen bir teklifiniz bulunmuyor.")
            for msg in my_inbox:
                with st.container(border=True):
                    s_user = users_db.get(msg['sender'], {})
                    if not isinstance(s_user, dict): s_user = {}
                    if msg.get('type') == 'invite_request':
                        inv_data = next((i for i in invites if i.get('id') == msg.get('invite_id')), {})
                        st.write(f"🔔 **{s_user.get('ad_soyad', 'Anonim')}** (NTRP {s_user.get('level', '3.5')}) sizin **{inv_data.get('date')}** tarihli **{inv_data.get('court')}** ilanınıza katılmak istiyor!")
                    else:
                        st.write(f"🔔 **{s_user.get('ad_soyad', 'Anonim')}** size özel maç teklif etti! Tarih: **{msg.get('date')}** | Kort: **{msg.get('court')}**")

                    c_acc, c_rej = st.columns(2)
                    if c_acc.button("✅ Kabul Et", key=f"acc_{msg['id']}"):
                        msg['status'] = 'accepted'
                        inv_kayit_basarili = True
                        if msg.get('type') == 'invite_request':
                            for i in invites:
                                if i.get('id') == msg.get('invite_id'):
                                    i['status'] = 'matched'
                                    msg['calendar_link'] = generate_gcal_link("Tenis Maçı", i.get('date'), i.get('time_details', '18:00'), i.get('court'))
                                    break
                            inv_kayit_basarili = save_data(INVITES_FILE_PATH, invites, 'db_invites')
                        else:
                            msg['calendar_link'] = generate_gcal_link("Tenis Maçı", msg.get('date', ''), msg.get('time', '18:00'), msg.get('court', ''))
                            
                        msg_kayit_basarili = save_data(MESSAGES_FILE_PATH, messages, 'db_messages')
                        
                        if inv_kayit_basarili and msg_kayit_basarili:
                            send_email(msg['sender'], "Teklifiniz Kabul Edildi!", f"<b>{me.get('ad_soyad')}</b> tenis teklifinizi kabul etti!")
                            st.toast("Teklif kabul edildi ve maç takvime eklendi! 🎉", icon="✅")
                            time.sleep(1); st.rerun()
                        else:
                            st.error("⚠️ Veritabanı çakışması: Onayınız kaydedilemedi. Lütfen sayfayı yenileyip tekrar deneyin.")

                    conf_rej_key = f"conf_rej_{msg['id']}"
                    if not st.session_state.get(conf_rej_key, False):
                        if c_rej.button("❌ Reddet", key=f"btn_rej_{msg['id']}"):
                            st.session_state[conf_rej_key] = True
                            st.rerun()
                    else:
                        c_rej.warning("Reddedilsin mi?")
                        if c_rej.button("Evet, Reddet", key=f"yes_rej_{msg['id']}"):
                            msg['status'] = 'rejected'
                            if save_data(MESSAGES_FILE_PATH, messages, 'db_messages'):
                                st.session_state[conf_rej_key] = False
                                st.toast("Teklif reddedildi.", icon="ℹ️")
                                time.sleep(1); st.rerun()
                            else:
                                st.error("⚠️ Hata: Red işlemi kaydedilemedi. Lütfen tekrar deneyin.")
                        if c_rej.button("Vazgeç", key=f"no_rej_{msg['id']}"):
                            st.session_state[conf_rej_key] = False
                            st.rerun()

        with m_tab2:
            my_sent = [m for m in messages if m.get('sender') == st.session_state.current_user]
            if not my_sent: st.info("Henüz kimseye teklif göndermediniz.")
            for msg in reversed(my_sent):
                with st.container(border=True):
                    r_user = users_db.get(msg.get('receiver'), {})
                    st_map = {"pending": "⏳ Onay Bekliyor", "accepted": "✅ Kabul Edildi", "rejected": "❌ Reddedildi", "cancelled": "🚫 İptal Edildi"}
                    st.write(f"📤 Alıcı: **{r_user.get('ad_soyad', 'Bilinmeyen')}** | Durum: **{st_map.get(msg.get('status'), 'Bilinmiyor')}**")
                    
                    if msg.get('status') == 'pending':
                        conf_with_key = f"conf_with_{msg['id']}"
                        if not st.session_state.get(conf_with_key, False):
                            if st.button("🗑️ Teklifi Geri Çek", key=f"btn_with_{msg['id']}"):
                                st.session_state[conf_with_key] = True
                                st.rerun()
                        else:
                            st.warning("Bu teklifi geri çekmek istediğinize emin misiniz?")
                            cw1, cw2 = st.columns(2)
                            if cw1.button("Evet, Geri Çek", key=f"yes_with_{msg['id']}"):
                                yeni_messages = [m for m in messages if m['id'] != msg['id']]
                                if save_data(MESSAGES_FILE_PATH, yeni_messages, 'db_messages'):
                                    st.session_state[conf_with_key] = False
                                    st.toast("Teklifiniz başarıyla geri çekildi.", icon="✅")
                                    time.sleep(1); st.rerun()
                                else:
                                    st.error("⚠️ Hata: Geri çekme işlemi kaydedilemedi.")
                            if cw2.button("Vazgeç", key=f"no_with_{msg['id']}"):
                                st.session_state[conf_with_key] = False
                                st.rerun()

        with m_tab3:
            my_acc = [m for m in messages if (m.get('receiver') == st.session_state.current_user or m.get('sender') == st.session_state.current_user) and m.get('status') == 'accepted']
            if not my_acc: st.info("Yaklaşan onaylanmış bir maçınız yok.")
            
            for acc in reversed(my_acc):
                with st.container(border=True):
                    partner_e = acc['sender'] if acc['receiver'] == st.session_state.current_user else acc['receiver']
                    partner_u = users_db.get(partner_e, {})
                    
                    if acc.get('type') == 'invite_request':
                        inv_data = next((i for i in invites if i.get('id') == acc.get('invite_id')), {})
                        m_date = inv_data.get('date', 'Belirtilmedi')
                        m_time = inv_data.get('time_details', 'Belirtilmedi')
                        m_court = inv_data.get('court', 'Belirtilmedi')
                    else:
                        m_date = acc.get('date', 'Belirtilmedi')
                        m_time = acc.get('time', 'Belirtilmedi')
                        m_court = acc.get('court', 'Belirtilmedi')

                    st.markdown(f"🤝 **Partner:** {partner_u.get('ad_soyad', 'Partner')} *(NTRP {partner_u.get('level', '3.5')})*")
                    st.markdown(f"🗓️ **Tarih & Saat:** {m_date} | {m_time}")
                    st.markdown(f"📍 **Kort:** {m_court}")
                    
                    st.markdown(f"[📅 Google Takvime Ekle]({acc.get('calendar_link', '#')})")
                    
                    p_vis = partner_u.get('contact_visibility', 'eslesince')
                    if p_vis in ['eslesince', 'herkes']:
                        st.success(f"📞 İletişim: {partner_u.get('phone', 'Belirtilmedi')} | ✉️ {partner_e}")
                    else: st.info("🔒 Kullanıcı iletişim bilgilerini gizlemeyi tercih etmiş.")

                    st.markdown("---")
                    
                    # 💬 CHAT (SOHBET) BÖLÜMÜ
                    with st.expander(f"💬 {partner_u.get('ad_soyad', 'Partner')} ile Mesajlaş"):
                        chat_history = acc.get("chat_history", [])
                        
                        for chat in chat_history:
                            is_me = chat["sender"] == st.session_state.current_user
                            with st.chat_message("user" if is_me else "assistant"):
                                st.write(chat["text"])
                                st.caption(chat["timestamp"])
                        
                        new_msg = st.chat_input("Mesajınızı yazın...", key=f"chat_input_{acc['id']}")
                        if new_msg:
                            chat_history.append({
                                "sender": st.session_state.current_user,
                                "text": new_msg,
                                "timestamp": datetime.datetime.now().strftime("%d-%m %H:%M")
                            })
                            acc["chat_history"] = chat_history
                            if save_data(MESSAGES_FILE_PATH, messages, 'db_messages'):
                                benim_adim = me.get('ad_soyad', st.session_state.current_user)
                                mail_konu = f"💬 Yeni Mesaj: {m_date} / {m_court} Maçı"
                                mail_icerik = f"""
                                Merhaba,<br><br>
                                <b>{m_date}</b> tarihli ve <b>{m_time}</b> saatli <b>{m_court}</b> maçınız için partneriniz <b>{benim_adim}</b> size bir mesaj gönderdi:<br><br>
                                <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid #2E7D32; font-style: italic; font-size: 14px;">
                                "{new_msg}"
                                </div>
                                <br>
                                Mesaja cevap vermek için uygulamaya giriş yapabilirsiniz.🎾
                                """
                                send_email(partner_e, mail_konu, mail_icerik)
                                st.rerun()
                            else:
                                st.error("⚠️ Sunucu hatası: Mesajınız gönderilemedi.")

                    st.markdown("---")
                    c_opt1, c_opt2 = st.columns(2)
                    
                    conf_del_acc = f"conf_del_acc_{acc['id']}"
                    if not st.session_state.get(conf_del_acc, False):
                        if c_opt1.button("🗑️ Maçı İptal Et", key=f"btn_del_acc_{acc['id']}"):
                            st.session_state[conf_del_acc] = True
                            st.rerun()
                    else:
                        c_opt1.warning("Maçı iptal etmek istediğinize emin misiniz?")
                        if c_opt1.button("Evet, İptal Et", key=f"yes_del_acc_{acc['id']}"):
                            acc['status'] = 'cancelled'
                            inv_kayit_basarili = True
                            
                            if acc.get('type') == 'invite_request':
                                target_inv = next((i for i in invites if i.get('id') == acc.get('invite_id')), None)
                                if target_inv:
                                    if st.session_state.current_user == target_inv.get('creator'):
                                        invites = [i for i in invites if i.get('id') != acc.get('invite_id')]
                                    else:
                                        target_inv['status'] = 'paused_by_cancellation'
                                    inv_kayit_basarili = save_data(INVITES_FILE_PATH, invites, 'db_invites')

                            msg_kayit_basarili = save_data(MESSAGES_FILE_PATH, messages, 'db_messages')
                            
                            if inv_kayit_basarili and msg_kayit_basarili:
                                send_email(partner_e, "Maç İptali", f"<b>{me.get('ad_soyad', st.session_state.current_user)}</b> maçı iptal etti.")
                                st.session_state[conf_del_acc] = False
                                st.toast("Maç iptal edildi.", icon="🗑️")
                                time.sleep(1); st.rerun()
                            else:
                                st.error("⚠️ İptal işlemi kaydedilemedi. Bir veri çakışması oluştu.")
                        if c_opt1.button("Vazgeç", key=f"no_del_acc_{acc['id']}"):
                            st.session_state[conf_del_acc] = False
                            st.rerun()

                    conf_edit_acc = f"conf_edit_acc_{acc['id']}"
                    if not st.session_state.get(conf_edit_acc, False):
                        if c_opt2.button("✏️ İptal Et & Yeniden Yayınla", key=f"btn_edit_acc_{acc['id']}"):
                            st.session_state[conf_edit_acc] = True
                            st.rerun()
                    else:
                        c_opt2.warning("İptal edilip ilanı yeniden yayına almak istiyor musunuz?")
                        if c_opt2.button("Evet, Yeniden Yayınla", key=f"yes_edit_acc_{acc['id']}"):
                            acc['status'] = 'cancelled'
                            inv_kayit_basarili = True
                            if acc.get('type') == 'invite_request':
                                for i in invites:
                                    if i.get('id') == acc.get('invite_id'):
                                        i['status'] = 'active'
                                        st.session_state.editing_invite = i.get('id')
                                        break
                                inv_kayit_basarili = save_data(INVITES_FILE_PATH, invites, 'db_invites')
                            
                            msg_kayit_basarili = save_data(MESSAGES_FILE_PATH, messages, 'db_messages')
                            
                            if inv_kayit_basarili and msg_kayit_basarili:
                                send_email(partner_e, "Maç İptal Edildi", f"<b>{me.get('ad_soyad', st.session_state.current_user)}</b> maçı iptal etti.")
                                st.session_state[conf_edit_acc] = False
                                st.toast("İlan yeniden düzenleme moduna alındı ve havuza döndü!", icon="✏️")
                                time.sleep(1); st.rerun()
                            else:
                                st.error("⚠️ Hata: Yeniden yayınlama işlemi başarısız oldu.")
                        if c_opt2.button("Vazgeç", key=f"no_edit_acc_{acc['id']}"):
                            st.session_state[conf_edit_acc] = False
                            st.rerun()

            paused_invites = [i for i in invites if i.get('creator') == st.session_state.current_user and i.get('status') == 'paused_by_cancellation']
            
            if paused_invites:
                st.markdown("---")
                st.warning("⚠️ **Partner İptali Bildirimi:** Kabul edilen bir maçınız karşı tarafça iptal edildiği için aşağıdaki ilanınız askıya alındı. Ne yapmak istersiniz?")
                for pinv in paused_invites:
                    with st.container(border=True):
                        st.write(f"📍 {pinv.get('court')} | 🗓️ {pinv.get('date')} tarihli ilanınızın eşleşmesi iptal oldu.")
                        col_p1, col_p2 = st.columns(2)
                        if col_p1.button("📢 İlanı Yeniden Yayına Al", key=f"repub_{pinv.get('id')}"):
                            pinv['status'] = 'active'
                            if save_data(INVITES_FILE_PATH, invites, 'db_invites'):
                                st.toast("İlanınız tekrar başarıyla vitrine eklendi! 🚀", icon="✅")
                                time.sleep(1); st.rerun()
                            else:
                                st.error("⚠️ Hata: İlanınız yayına alınamadı.")
                        if col_p2.button("🗑️ İlanı Tamamen Kapat", key=f"close_{pinv.get('id')}"):
                            yeni_invites_2 = [i for i in invites if i.get('id') != pinv.get('id')]
                            if save_data(INVITES_FILE_PATH, yeni_invites_2, 'db_invites'):
                                st.toast("İlan tamamen kaldırıldı.", icon="🗑️")
                                time.sleep(1); st.rerun()
                            else:
                                st.error("⚠️ Hata: İlan silinirken sorun oluştu.")

            if st.session_state.editing_invite:
                e_inv = next((i for i in invites if i.get('id') == st.session_state.editing_invite), None)
                if e_inv:
                    st.markdown("---")
                    st.subheader("✏️ İlanı Güncelle ve Yeniden Yayınla")
                    with st.form("edit_inv_form"):
                        ed_d = st.date_input("Yeni Tarih", value=datetime.datetime.strptime(e_inv.get('date'), "%Y-%m-%d").date())
                        ed_court = st.selectbox("Yeni Kort", IZMIR_KORTLARI, index=IZMIR_KORTLARI.index(e_inv.get('court')) if e_inv.get('court') in IZMIR_KORTLARI else 0)
                        ed_note = st.text_area("İlan Notu", value=e_inv.get('note', ''))
                        if st.form_submit_button("Güncelle ve Havuza Gönder"):
                            e_inv['date'] = str(ed_d)
                            e_inv['court'] = ed_court
                            e_inv['note'] = ed_note
                            e_inv['status'] = 'active'
                            if save_data(INVITES_FILE_PATH, invites, 'db_invites'):
                                st.session_state.editing_invite = None
                                st.toast("İlan güncellendi ve havuza gönderildi! 🚀", icon="✅")
                                time.sleep(1); st.rerun()
                            else:
                                st.error("⚠️ Hata: İlan güncellenirken veri çakışması yaşandı.")

        with m_tab4:
            past_m = [m for m in messages if (m.get('receiver') == st.session_state.current_user or m.get('sender') == st.session_state.current_user) and m.get('status') in ['cancelled', 'rejected']]
            if not past_m: st.info("Geçmiş iptal kaydı bulunmuyor.")
            for pm in past_m: st.write(f"⚪ İptal/Reddedilen Kayıt | ID: {pm['id'][:8]} | Durum: **{pm['status']}**")

    # --- TAB 4: DEĞERLENDİRME ---
    with tabs[4]:
        st.subheader("⚖️ Maç Sonrası Değerlendirme")
        accepted_events = [m for m in messages if (m.get('receiver') == st.session_state.current_user or m.get('sender') == st.session_state.current_user) and m.get('status') == 'accepted']
        unrated_events = [m for m in accepted_events if st.session_state.current_user not in m.get('rated_by', [])]
        
        if not unrated_events:
            st.info("Değerlendirebileceğiniz tamamlanmış maç bulunmuyor.")
        else:
            with st.form("rating_form"):
                evt_opts = {m['id']: f"Rakip: {users_db.get(m['sender'] if m['receiver'] == st.session_state.current_user else m['receiver'], {}).get('ad_soyad', 'Bilinmeyen')}" for m in unrated_events}
                selected_event_id = st.selectbox("Değerlendirilecek Maç", options=list(evt_opts.keys()), format_func=lambda x: evt_opts[x])
                st.markdown("**(1: Zayıf - 5: Mükemmel)**")
                sz = st.slider("Zaman Planlamasına Uyum", 1, 5, 5)
                ss = st.slider("Seviye Tutarlılığı", 1, 5, 5)
                sd = st.slider("Sportmenlik & İletişim", 1, 5, 5)
                
                if st.form_submit_button("⭐ Değerlendirmeyi Kaydet"):
                    target_event = next(m for m in unrated_events if m['id'] == selected_event_id)
                    p_email = target_event['sender'] if target_event['receiver'] == st.session_state.current_user else target_event['receiver']
                    
                    if p_email in users_db and isinstance(users_db[p_email], dict):
                        r_db = users_db[p_email].setdefault("ratings", {"zaman": [], "seviye": [], "davranis": []})
                        r_db["zaman"].append(sz); r_db["seviye"].append(ss); r_db["davranis"].append(sd)
                        
                        target_event.setdefault('rated_by', []).append(st.session_state.current_user)
                        
                        u_basarili = save_data(USERS_FILE_PATH, users_db, 'db_users')
                        m_basarili = save_data(MESSAGES_FILE_PATH, messages, 'db_messages')
                        
                        if u_basarili and m_basarili:
                            st.toast("Değerlendirmeniz başarıyla kaydedildi! ⭐", icon="✅")
                            time.sleep(1); st.rerun()
                        else:
                            st.error("⚠️ Değerlendirme kaydedilemedi. Veritabanında bir çakışma oluştu.")

    # --- TAB 5: PROFİL & AYARLAR ---
    with tabs[5]:
        colL, colR = st.columns(2)
        
        with colL:
            st.subheader("👤 Profil Bilgilerim")
            with st.form("profile_form"):
                st.text_input("E-Posta Adresi (Değiştirilemez)", value=st.session_state.current_user, disabled=True)
                ad = st.text_input("Ad Soyad", value=me.get("ad_soyad", ""))
                phone = st.text_input("Telefon Numarası", value=me.get("phone", ""))
                ilce = st.selectbox("Bölge / İlçe (Sıralamalar İçin)", IZMIR_ILCELER, index=IZMIR_ILCELER.index(me.get("ilce", "Belirtilmemiş")) if me.get("ilce") in IZMIR_ILCELER else 0)
                level = st.selectbox("NTRP Oyuncu Seviyeniz", NTRP_LEVELS, index=NTRP_LEVELS.index(me.get("level", "3.5")) if me.get("level") in NTRP_LEVELS else 5)
                
                me_style = me.get("style", "All-Rounder")
                is_custom = me_style not in ["Agresif Baseline", "Servis & Vole", "Defansif / Karşılayıcı", "All-Rounder", ""]
                style_sel = st.selectbox("Oyun Tarzı", ["Agresif Baseline", "Servis & Vole", "Defansif / Karşılayıcı", "All-Rounder", "Diğer"], index=4 if is_custom else ["Agresif Baseline", "Servis & Vole", "Defansif / Karşılayıcı", "All-Rounder", ""].index(me_style) if me_style in ["Agresif Baseline", "Servis & Vole", "Defansif / Karşılayıcı", "All-Rounder"] else 3)
                style_custom = st.text_input("Diğer ise Oyun Tarzınızı Yazın:", value=me_style if is_custom else "") if style_sel == "Diğer" else ""

                if st.form_submit_button("💾 Profili Güncelle"):
                    me.update({"ad_soyad": ad.strip(), "phone": phone.strip(), "ilce": ilce, "level": level, "style": style_custom.strip() if style_sel == "Diğer" else style_sel})
                    users_db[st.session_state.current_user] = me
                    if save_data(USERS_FILE_PATH, users_db, 'db_users'):
                        st.toast("Profil bilgileriniz güncellendi! ✅", icon="👤")
                        time.sleep(1); st.rerun()
                    else:
                        st.error("⚠️ Profiliniz güncellenemedi. Lütfen işlemi tekrarlayın.")

            with st.expander("🔑 Şifre Değiştir"):
                with st.form("change_pass_form"):
                    old_pass = st.text_input("Mevcut Şifre", type="password")
                    new_pass = st.text_input("Yeni Şifre", type="password")
                    new_pass_confirm = st.text_input("Yeni Şifre (Tekrar)", type="password")
                    
                    if st.form_submit_button("Şifreyi Güncelle"):
                        if hash_password(old_pass) != me.get("password_hash"):
                            st.error("Mevcut şifreniz hatalı!")
                        elif new_pass != new_pass_confirm:
                            st.error("Yeni şifreler eşleşmiyor!")
                        elif len(new_pass) < 4:
                            st.error("Şifre en az 4 karakter olmalıdır.")
                        else:
                            me["password_hash"] = hash_password(new_pass)
                            users_db[st.session_state.current_user] = me
                            if save_data(USERS_FILE_PATH, users_db, 'db_users'):
                                st.success("Şifreniz başarıyla değiştirildi!")
                            else:
                                st.error("⚠️ Şifre değişimi veritabanına yazılamadı.")
                            
            st.markdown("---")
            st.subheader("⏸️ Hesap Durumu (Dondurma)")
            with st.form("freeze_form"):
                is_frozen = st.toggle("Bir süre tenis oynayamayacağım, hesabımı dondur (Pasife al)", value=me.get("frozen", False))
                st.caption("Aktif ettiğinizde üyeler listesinde görünmezsiniz, ilanlarınız vitrinden kalkar ve size teklif gelemez.")
                if st.form_submit_button("Durumu Güncelle"):
                    me["frozen"] = is_frozen
                    users_db[st.session_state.current_user] = me
                    if save_data(USERS_FILE_PATH, users_db, 'db_users'):
                        st.toast("Hesap dondurma tercihiniz güncellendi!", icon="⏸️")
                        time.sleep(1); st.rerun()
                    else:
                        st.error("⚠️ Hesap durumu güncellenemedi.")

            st.markdown("---")
            st.subheader("🚨 Tehlikeli Bölge")
            with st.expander("Hesabımı Kalıcı Olarak Silme Talebi Gönder"):
                st.warning("⚠️ **DİKKAT:** Bu işlem hesabınızın ve tüm verilerinizin kalıcı olarak silinmesi için yöneticiye talep bildirir.")
                
                if me.get("delete_requested"):
                    st.info("ℹ️ Zaten bir silme talebiniz yöneticiye iletilmiştir. Onay bekleniyor.")
                else:
                    if st.button("🗑️ Silme Talebini Yöneticiye İlet"):
                        me["delete_requested"] = True
                        users_db[st.session_state.current_user] = me
                        if save_data(USERS_FILE_PATH, users_db, 'db_users'):
                            admin_del_mail = f"<b>{me.get('ad_soyad')}</b> ({st.session_state.current_user}) isimli üye hesabını ve verilerini kalıcı olarak silmek istiyor.<br><br>Yönetici Panelinden onaylayabilirsiniz."
                            send_email(ADMIN_EMAIL, "🚨 Kalıcı Silme Talebi Var", admin_del_mail)
                            st.toast("Silme talebiniz yöneticiye iletildi.", icon="📨")
                            time.sleep(1); st.rerun()
                        else:
                            st.error("⚠️ Talebiniz iletilemedi. İnternet veya veritabanı bağlantısında bir sorun var.")

        with colR:
            st.subheader("🔒 İletişim & Gizlilik Ayarları")
            with st.form("privacy_form"):
                vis_options = ["Gizle (Hiçbir Zaman Gösterme)", "Sadece Eşleşince Göster", "Herkese Açık (İlanda Göster)"]
                vis_keys = ["gizle", "eslesince", "herkes"]
                curr_idx = vis_keys.index(me.get("contact_visibility", "eslesince")) if me.get("contact_visibility") in vis_keys else 1
                
                c_vis = st.selectbox("Telefon/E-Posta Görünürlüğü", vis_options, index=curr_idx)
                ghost = st.toggle("👻 Hayalet Modu (Üye listesinde görünme)", value=me.get("privacy", {}).get("ghost", False))
                show_r = st.toggle("⭐ Değerlendirme Puanımı Göster", value=me.get("privacy", {}).get("show_rating", True))
                
                if st.form_submit_button("🔒 Gizlilik Ayarlarını Kaydet"):
                    me["contact_visibility"] = vis_keys[vis_options.index(c_vis)]
                    me.setdefault("privacy", {})["ghost"] = ghost
                    me.setdefault("privacy", {})["show_rating"] = show_r
                    users_db[st.session_state.current_user] = me
                    if save_data(USERS_FILE_PATH, users_db, 'db_users'):
                        st.toast("Gizlilik tercihleri kaydedildi! ✅", icon="🔒")
                        time.sleep(1); st.rerun()
                    else:
                        st.error("⚠️ Gizlilik ayarlarınız kaydedilemedi.")

            st.markdown("---")
            st.subheader("📡 Radar (E-posta Alarmı) Ayarları")
            radar_data = me.get("radar", {"active": False, "courts": [], "levels": [], "types": []})
            with st.form("radar_form"):
                r_active = st.toggle("📡 Radar Alarmlarını Aktif Et", value=radar_data.get("active", False))
                r_courts = st.multiselect("Kortlar (Boş bırakılırsa tümü)", IZMIR_KORTLARI, default=radar_data.get("courts", []))
                r_levels = st.multiselect("NTRP Seviyeleri (Boş bırakılırsa tümü)", NTRP_LEVELS, default=radar_data.get("levels", []))
                r_types = st.multiselect("Etkinlik Tipleri", ACTIVITY_TYPES, default=radar_data.get("types", []))
                if st.form_submit_button("📡 Radar Tercihlerini Kaydet"):
                    me["radar"] = {"active": r_active, "courts": r_courts, "levels": r_levels, "types": r_types}
                    users_db[st.session_state.current_user] = me
                    if save_data(USERS_FILE_PATH, users_db, 'db_users'):
                        st.toast("Radar ayarlarınız kaydedildi! 📡", icon="✅")
                        time.sleep(1); st.rerun()
                    else:
                        st.error("⚠️ Radar tercihleriniz kaydedilirken bir hata oluştu.")

# --- UYGULAMA GİRİŞ NOKTASI ---
if not st.session_state.logged_in: login_page()
elif st.session_state.is_admin: admin_dashboard()
else: main_app()
