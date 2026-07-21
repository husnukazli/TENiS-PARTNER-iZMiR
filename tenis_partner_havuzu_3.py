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

# MOBİL ARAYÜZ (UI) GÜVENLİ CSS KODLARI VE GİZLİLİK
st.markdown("""
<style>
    /* Üst boşluk (padding-top) 4.5rem yapılarak isimlerin menü altında kesilmesi engellendi */
    .block-container { padding-top: 4.5rem; padding-bottom: 2rem; }
    
    /* Tüm butonları modern, yuvarlak köşeli ve tam genişlikte (app tarzı) yap */
    .stButton > button { width: 100%; border-radius: 12px; font-weight: 600; }
    
    /* Sekmeleri (Tab'ları) mobil ekrana daha iyi yay ve kaydırılabilir yap */
    .stTabs [data-baseweb="tab-list"] { display: flex; justify-content: space-evenly; overflow-x: auto; }
    
    /* Container (Kart) kenarlarını daha yumuşak yuvarlat */
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 16px; }

    /* KORSAN GİRİŞLERE KARŞI STREAMLIT VE GITHUB İZLERİNİ GİZLEME */
    #MainMenu {visibility: hidden;} /* Sağ üstteki hamburger menüyü gizler */
    header {visibility: hidden;} /* Üstteki GitHub ikonunu ve bandı gizler */
    footer {visibility: hidden;} /* En alttaki "Made with Streamlit" yazısını gizler */
</style>
""", unsafe_allow_html=True)

# Çerez Yöneticisini Başlat
if HAS_STX:
    cookie_manager = stx.CookieManager(key="cm_izmir")
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
        except: return default_type()
    else:
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f: data = json.load(f)
            except: return default_type()
        else: return default_type()
    if not isinstance(data, default_type): return default_type()
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
            except: success = False
    else:
        try:
            with open(file_path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)
            success = True
        except: success = False
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
        🍎 **iOS:** Safari alt menüsündeki **Paylaş** ikonundan **Ana Ekrana Ekle** seçin.
        🤖 **Android:** Chrome sağ üstteki **Üç Nokta (⋮)** menüsünden **Ana Ekrana Ekle** seçin.
        """)

# --- OTURUM YÖNETİMİ ---
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

# --- PROFİL POP-UP YARDIMCI FONKSİYONU ---
def render_popover_profile(user_email, user_data, messages_db):
    if not isinstance(user_data, dict): return
    with st.popover(f"👤 İlan Sahibi: {user_data.get('ad_soyad', 'Anonim')}", use_container_width=True):
        st.markdown(f"**NTRP Seviyesi:** {user_data.get('level', '3.5')} | **İlçe:** {user_data.get('ilce', 'Belirtilmedi')}")
        st.markdown(f"**Oyun Tarzı:** {user_data.get('style', 'Belirtilmedi')}")
        
        show_r = user_data.get("privacy", {}).get("show_rating", True)
        disp_rating = f"{calculate_rating(user_data.get('ratings')):.1f}" if show_r else "Gizli"
        st.markdown(f"⭐ **Puan:** {disp_rating}")
        
        cv = user_data.get('contact_visibility', 'eslesince')
        if cv == 'herkes':
            st.success(f"📞 {user_data.get('phone', '-')} | ✉️ {user_email}")
        elif cv == 'gizle':
            st.info("🔒 Kullanıcı iletişim bilgilerini tamamen gizlemiş.")
        else:
            has_acc = any(m.get('status') == 'accepted' and ((m.get('sender') == st.session_state.current_user and m.get('receiver') == user_email) or (m.get('receiver') == st.session_state.current_user and m.get('sender') == user_email)) for m in messages_db)
            if has_acc:
                st.success(f"📞 {user_data.get('phone', '-')} | ✉️ {user_email}")
            else:
                st.info("🔒 İletişim bilgileri sadece eşleşilen kişilere açıktır.")

# --- YÖNETİCİ KONTROL MERKEZİ ---
def admin_dashboard():
    sidebar_pwa_guide()
    st.markdown("<h1 style='color: #D32F2F;'>👑 Yönetici Kontrol Merkezi</h1>", unsafe_allow_html=True)
    if st.button("🚪 Yönetici Panelinden Çık"):
        st.session_state.logged_in = False; st.session_state.is_admin = False
        if cookie_manager: cookie_manager.delete("remember_user")
        st.rerun()
    
    users_db = st.session_state.db_users
    invites = st.session_state.db_invites
    messages = st.session_state.db_messages

    active_inv_count = len([i for i in invites if i.get('status') == 'active'])
    del_req_count = len([u for u, d in users_db.items() if isinstance(d, dict) and d.get('delete_requested')])

    t1, t2, t3 = st.tabs([f"👥 Üye Yönetimi 🚨 ({del_req_count})" if del_req_count > 0 else "👥 Üye Yönetimi", f"📅 İlan Yönetimi 🟢 ({active_inv_count})" if active_inv_count > 0 else "📅 İlan Yönetimi", "💾 Yedekleme & Kurtarma"])
    
    with t1:
        st.subheader("Kayıtlı Üyeler ve Silme Talepleri")
        for u_email, u_data in users_db.items():
            if not isinstance(u_data, dict): continue 
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 2, 2])
                status = "🔴 Askıda" if u_data.get("suspended") else ("⏸️ Dondurulmuş" if u_data.get("frozen") else "🟢 Aktif")
                del_req_badge = " 🚨 [SİLME TALEBİ]" if u_data.get("delete_requested") else ""
                c1.write(f"**{u_data.get('ad_soyad')}{del_req_badge}** | {u_email} | Durum: {status}")
                
                if not st.session_state.get(f"conf_susp_{u_email}", False):
                    if c2.button("Kaldır / Askıya Al", key=f"btn_susp_{u_email}"):
                        st.session_state[f"conf_susp_{u_email}"] = True; st.rerun()
                else:
                    c2.warning("Emin misiniz?")
                    if c2.button("Evet", key=f"yes_susp_{u_email}"):
                        users_db[u_email]["suspended"] = not u_data.get("suspended", False)
                        st.session_state[f"conf_susp_{u_email}"] = False
                        if save_data(USERS_FILE_PATH, users_db, 'db_users'):
                            st.toast("Üye durumu güncellendi!", icon="✅"); time.sleep(1); st.rerun()
                        else: st.error("⚠️ Hata: Üye durumu güncellenemedi.")
                    if c2.button("Vazgeç", key=f"no_susp_{u_email}"):
                        st.session_state[f"conf_susp_{u_email}"] = False; st.rerun()

                if not st.session_state.get(f"conf_del_{u_email}", False):
                    if c3.button("🗑️ Kalıcı Sil", key=f"btn_del_{u_email}"):
                        st.session_state[f"conf_del_{u_email}"] = True; st.rerun()
                else:
                    c3.warning("Kalıcı silinsin mi?")
                    if c3.button("Evet", key=f"yes_del_{u_email}"):
                        users_db.pop(u_email, None)
                        st.session_state[f"conf_del_{u_email}"] = False
                        if save_data(USERS_FILE_PATH, users_db, 'db_users'):
                            st.toast("Üye silindi!", icon="🗑️"); time.sleep(1); st.rerun()
                        else: st.error("⚠️ Hata: Silme işlemi başarısız.")
                    if c3.button("Vazgeç", key=f"no_del_{u_email}"):
                        st.session_state[f"conf_del_{u_email}"] = False; st.rerun()

    with t2:
        st.subheader("Sistemdeki İlanlar")
        for inv in reversed(invites):
            c1, c2 = st.columns([6, 2])
            c1.write(f"📍 {inv.get('court')} | 🗓️ {inv.get('date')} | Durum: **{inv.get('status')}**")
            if not st.session_state.get(f"conf_inv_{inv.get('id')}", False):
                if c2.button("🗑️ Kaldır", key=f"btn_adm_del_{inv.get('id')}"):
                    st.session_state[f"conf_inv_{inv.get('id')}"] = True; st.rerun()
            else:
                c2.warning("Silinsin mi?")
                if c2.button("Evet", key=f"yes_inv_{inv.get('id')}"):
                    yeni_invites = [i for i in invites if i.get('id') != inv.get('id')]
                    if save_data(INVITES_FILE_PATH, yeni_invites, 'db_invites'):
                        st.session_state[f"conf_inv_{inv.get('id')}"] = False
                        st.toast("İlan silindi!", icon="✅"); time.sleep(1); st.rerun()
                if c2.button("İptal", key=f"no_inv_{inv.get('id')}"):
                    st.session_state[f"conf_inv_{inv.get('id')}"] = False; st.rerun()

    with t3:
        st.subheader("Sistem Yedekleme")
        st.download_button("Üyeler Yedeği", data=json.dumps(users_db, indent=4, ensure_ascii=False), file_name="users_backup.json")
        st.download_button("İlanlar Yedeği", data=json.dumps(invites, indent=4, ensure_ascii=False), file_name="invites_backup.json")
        st.download_button("Mesajlar Yedeği", data=json.dumps(messages, indent=4, ensure_ascii=False), file_name="messages_backup.json")

# --- GİRİŞ VE VİTRİN SAYFASI ---
def login_page():
    sidebar_pwa_guide()
    
    # YÖNETİCİ GİRİŞİ YAN MENÜYE TAŞINDI
    st.sidebar.markdown("---")
    with st.sidebar.expander("👑 Yönetici Paneli"):
        admin_code = st.text_input("Yönetici Parolası", type="password")
        if st.button("Panele Gir", use_container_width=True):
            if admin_code == ADMIN_PASS:
                st.session_state.logged_in = True
                st.session_state.is_admin = True
                st.rerun()
            else:
                st.error("Hatalı Parola!")

    st.markdown("<h1 style='text-align: center; color: #2E7D32;'>🎾 İzmir Tenis Partner Ağı</h1>", unsafe_allow_html=True)
    
    users_db = st.session_state.db_users
    invites = st.session_state.db_invites
    messages = st.session_state.db_messages
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if not st.session_state.show_login_form:
            if st.button("🔑 Sisteme Giriş Yap veya Kayıt Ol", use_container_width=True):
                st.session_state.show_login_form = True; st.rerun()
        else:
            if st.button("🔙 İlanlara (Vitrine) Geri Dön", use_container_width=True):
                st.session_state.show_login_form = False; st.rerun()
                
    st.markdown("---")
    
    if st.session_state.show_login_form:
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
                    reg_email = st.text_input("E-posta Adresi", key="reg_email")
                    reg_pass = st.text_input("Şifre Belirle", type="password", key="reg_pass")
                    reg_name = st.text_input("Ad Soyad (Zorunlu)", key="reg_name")
                    reg_level = st.selectbox("Seviyeniz (NTRP)", NTRP_LEVELS, index=5, key="reg_lvl")
                    
                    reg_ilce_secim = st.selectbox("Yaşadığınız Bölge / İlçe", IZMIR_ILCELER, key="reg_ilce")
                    if reg_ilce_secim == "Diğer Merkez Dışı": 
                        reg_ilce_custom = st.text_input("Lütfen ilçe/bölge adını yazın:", key="reg_ilce_cust")
                    else: reg_ilce_custom = ""
                    
                    if st.button("İleri (E-Posta Doğrulama)", use_container_width=True):
                        reg_email = reg_email.strip().lower()
                        final_ilce = reg_ilce_custom.strip() if reg_ilce_secim == "Diğer Merkez Dışı" else reg_ilce_secim
                        if reg_email in users_db: st.error("Bu e-posta zaten kayıtlı.")
                        elif not reg_email or not reg_pass or not reg_name.strip() or (reg_ilce_secim == "Diğer Merkez Dışı" and not reg_ilce_custom.strip()): 
                            st.error("Lütfen tüm alanları eksiksiz doldurun.")
                        else:
                            code = str(random.randint(100000, 999999))
                            st.session_state.reg_code = code
                            st.session_state.reg_data = {"email": reg_email, "pass": hash_password(reg_pass), "name": reg_name.strip(), "level": reg_level, "ilce": final_ilce}
                            send_email(reg_email, "Hesap Doğrulama Kodu", f"Sisteme kayıt için doğrulama kodunuz: <b>{code}</b>")
                            st.session_state.reg_step = "verify"; st.rerun()
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
                                else: st.error("⚠️ Kayıt tamamlanamadı. Veritabanı hatası.")
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
                                st.success("Yeni şifreniz gönderildi! ✅")
                            else: st.error("⚠️ Veritabanı hatası.")
                        else: st.error("Sistemde böyle bir e-posta bulunamadı.")
    else:
        st.markdown("### 🌟 Güncel İlanlar (Vitrin)")
        st.write("Aşağıdaki ilanlara teklif göndermek için yukarıdan giriş yapmalısınız.")
        active_inv = [i for i in invites if i.get('status') == 'active' and isinstance(users_db.get(i.get('creator'), {}), dict) and not users_db.get(i.get('creator'), {}).get('suspended') and not users_db.get(i.get('creator'), {}).get('frozen')]
        active_inv.sort(key=lambda x: x.get('date', '9999-12-31'))
        
        if not active_inv: st.info("Şu an havuzda aktif ilan bulunmuyor.")
        for inv in active_inv[:8]:
            with st.container(border=True):
                k_isim = f"{inv.get('court')} ({inv.get('court_custom')})" if inv.get('court') == 'Diğer' else inv.get('court')
                c_user = users_db.get(inv.get('creator'), {})
                if not isinstance(c_user, dict): c_user = {}

                st.markdown(f"#### 🗓️ {inv.get('date')}  |  ⏰ {inv.get('time_details')}")
                st.markdown(f"### 📍 {k_isim}")
                st.markdown(f"**⭐ Aranan Seviye:** {', '.join(inv.get('levels', []))} &nbsp; | &nbsp; **🎾 Tür:** {inv.get('type')}", unsafe_allow_html=True)
                st.info(f"**Kort Durumu:** {inv.get('court_status')}")
                if inv.get('note'): st.warning(f"📝 *Not: {inv.get('note')}*")
                
                # Açılır Profil Kartı
                render_popover_profile(inv.get('creator'), c_user, messages)

                if st.button("Teklif Gönder", key=f"pub_{inv.get('id')}", use_container_width=True):
                    st.toast("Teklif göndermek için yukarıdaki butondan giriş yapmalısın! 🎾", icon="⚠️")
                    st.session_state.show_login_form = True; time.sleep(1); st.rerun()

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

    c_head1, c_head2, c_head3 = st.columns([5, 2, 2])
    c_head1.write("### 🎾 İzmir Tenis Partner Havuzu")
    if me.get('frozen'): c_head1.warning("⚠️ Hesabınız şu an **Dondurulmuş (Pasif)** durumdadır.")
    
    c_head2.write(f"👤 **{me.get('ad_soyad', 'Kullanıcı')}** ({me.get('level', '3.5')}) | ⭐ {my_rating_display}")
    
    with c_head3:
        with st.popover(f"🔔 Bildirimler ({my_inbox_count})", use_container_width=True):
            if my_inbox_count == 0: st.info("Yeni bildiriminiz yok.")
            else:
                for n in [m for m in messages if m.get('receiver') == st.session_state.current_user and m.get('status') == 'pending']:
                    sender_name = users_db.get(n['sender'], {}).get('ad_soyad', 'Biri')
                    st.markdown(f"🎾 **{sender_name}** ilanına katılmak istiyor!" if n['type'] == 'invite_request' else f"⚔️ **{sender_name}** özel maç teklif etti!")
                st.caption("👉 Onay için 'Tenis Ajandam' sekmesine gidin.")
        if st.button("🚪 Çıkış Yap", use_container_width=True): 
            st.session_state.logged_in = False
            if cookie_manager: cookie_manager.delete("remember_user")
            st.rerun()

    kontrol_sekme_adi = f"🎾 Tenis Ajandam 🚨 ({my_inbox_count})" if my_inbox_count > 0 else "🎾 Tenis Ajandam"
    tabs = st.tabs(["🏆 İlan Havuzu", "➕ İlan Oluştur", "👥 Üyeler", kontrol_sekme_adi, "⚖️ Değerlendirme", "⚙️ Profil & Ayarlar"])

    # --- TAB 0: İLAN HAVUZU ---
    with tabs[0]:
        with st.expander("🔍 İlanları Filtrele ve Sırala", expanded=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            sort_by = f_col1.selectbox("Sıralama Ölçütü", ["Tarihe Göre (En Yakın)", "Eklenme Zamanına Göre (En Yeni)"])
            filter_court = f_col2.multiselect("Kort Filtresi", IZMIR_KORTLARI)
            filter_level = f_col3.multiselect("Seviye Filtresi", NTRP_LEVELS)
            
        active_invites = [i for i in invites if i.get('status') == 'active' and not users_db.get(i.get('creator'), {}).get('suspended') and not users_db.get(i.get('creator'), {}).get('frozen')]
        if filter_court: active_invites = [i for i in active_invites if i.get('court') in filter_court]
        if filter_level: active_invites = [i for i in active_invites if any(l in filter_level for l in i.get('levels', []))]
        
        active_invites.sort(key=lambda x: x.get('date', '9999-12-31'), reverse=(sort_by != "Tarihe Göre (En Yakın)"))
        if not active_invites: st.info("Kriterlere uygun aktif ilan bulunamadı.")

        for inv in active_invites:
            with st.container(border=True):
                k_isim = f"{inv.get('court')} ({inv.get('court_custom')})" if inv.get('court') == 'Diğer' else inv.get('court')
                c_user = users_db.get(inv.get('creator'), {})
                if not isinstance(c_user, dict): c_user = {}

                st.markdown(f"#### 🗓️ {inv.get('date')}  |  ⏰ {inv.get('time_details')}")
                st.markdown(f"### 📍 {k_isim}")
                st.markdown(f"**⭐ Aranan Seviye:** {', '.join(inv.get('levels', []))} &nbsp; | &nbsp; **🎾 Tür:** {inv.get('type')}", unsafe_allow_html=True)
                st.info(f"**Kort Durumu:** {inv.get('court_status')}")
                if inv.get('note'): st.warning(f"📝 *Not: {inv.get('note')}*")
                
                # Açılır Profil Kartı
                render_popover_profile(inv.get('creator'), c_user, messages)

                if inv.get('creator') != st.session_state.current_user:
                    if any(m.get('sender') == st.session_state.current_user and m.get('invite_id') == inv.get('id') and m.get('status') == 'pending' for m in messages):
                        st.button("✅ Teklif İletildi", key=f"inv_sent_{inv.get('id')}", disabled=True, use_container_width=True)
                    else:
                        if st.button("🎾 Teklif Gönder", key=f"inv_{inv.get('id')}", use_container_width=True):
                            new_msg = {"id": str(uuid.uuid4()), "type": "invite_request", "invite_id": inv.get('id'), "sender": st.session_state.current_user, "receiver": inv.get('creator'), "status": "pending", "timestamp": str(datetime.datetime.now())}
                            if save_data(MESSAGES_FILE_PATH, messages + [new_msg], 'db_messages'):
                                st.toast("Teklifiniz iletildi! 🎉", icon="✅"); time.sleep(1); st.rerun()
                            else: st.error("⚠️ Veri hatası: Teklifiniz kaydedilemedi.")

    # --- TAB 1: İLAN OLUŞTUR ---
    with tabs[1]:
        st.subheader("➕ Yeni İlan Yayınla")
        if me.get('frozen'): st.warning("⚠️ Hesabınız dondurulmuş. İlanınız vitrinde görünmez.")
            
        c1, c2 = st.columns(2)
        d = c1.date_input("Tarih", min_value=datetime.date.today(), key="inv_date")
        c_t1, c_t2 = c1.columns(2)
        t_start = c_t1.time_input("Başlangıç Saati", datetime.time(18, 0), key="inv_start")
        t_end = c_t2.time_input("Bitiş Saati", datetime.time(19, 30), key="inv_end")
        
        court = c2.selectbox("Kort / Saha", IZMIR_KORTLARI, key="inv_court")
        court_custom = c2.text_input("Diğer ise Kort Adını Yazın:", key="inv_court_cust") if court == "Diğer" else ""
        court_status = c2.selectbox("Kort Rezervasyon Durumu", COURT_STATUS, key="inv_c_status")
        
        act_type = st.selectbox("Etkinlik Tipi", ACTIVITY_TYPES, key="inv_act_type")
        levels = st.multiselect("Aranan Seviyeler (NTRP)", NTRP_LEVELS, default=[me.get("level", "3.5")], key="inv_lvls")
        inv_note = st.text_area("İlan Notu / Açıklama (İsteğe bağlı)", key="inv_note")
        
        if st.button("📢 İlanı Yayınla", use_container_width=True):
            if not levels: st.error("Lütfen en az bir aranan seviye seçin.")
            elif court == "Diğer" and not court_custom.strip(): st.error("Lütfen Kort Adı alanını doldurun.")
            elif t_start >= t_end: st.error("Bitiş saati başlangıç saatinden sonra olmalıdır.")
            else:
                new_inv = {"id": str(uuid.uuid4()), "creator": st.session_state.current_user, "date": str(d), "time_details": f"{t_start.strftime('%H:%M')} - {t_end.strftime('%H:%M')}", "court": court, "court_custom": court_custom, "court_status": court_status, "type": act_type, "levels": levels, "status": "active", "note": inv_note, "created_at": str(datetime.datetime.now())}
                if save_data(INVITES_FILE_PATH, invites + [new_inv], 'db_invites'):
                    for u_email, u_data in users_db.items():
                        if u_email == st.session_state.current_user or not isinstance(u_data, dict) or u_data.get('frozen') or u_data.get('suspended'): continue
                        r = u_data.get("radar", {})
                        if r.get("active", False) and (not r.get("courts") or court in r.get("courts") or (court == "Diğer" and "Diğer" in r.get("courts"))) and (not r.get("levels") or any(l in r.get("levels") for l in levels)) and (not r.get("types") or act_type in r.get("types") or "Fark Etmez" in r.get("types")):
                            send_email(u_email, "📡 Radar Alarmı: Uygun İlan Yayınlandı!", f"Merhaba <b>{u_data.get('ad_soyad')}</b>,<br><br>Radar kriterlerinize uygun tenis ilanı yayınlandı!<br><br>Kort: {court}<br>Sisteme giriş yaparak teklif gönderebilirsiniz.")
                    st.toast("İlanınız başarıyla yayınlandı! 🎉", icon="✅"); time.sleep(1.5); st.rerun()
                else: st.error("⚠️ Veri çakışması! İlanınız sisteme kaydedilemedi. Lütfen tekrar deneyin.")

    # --- TAB 2: ÜYELER ---
    with tabs[2]:
        c_title, c_sort = st.columns([3, 2])
        c_title.subheader("👥 Oyuncu Listesi")
        sort_users = c_sort.selectbox("Üyeleri Sırala:", ["İsme Göre (A-Z)", "Seviyeye Göre (Yüksekten Düşüğe)", "Puana Göre (Popülerlik)", "Bölgeye Göre (İlçe)"])
        
        user_list = [(e, d, calculate_rating(d.get('ratings')), float(d.get('level', '3.5')) if str(d.get('level')).replace('.','').isdigit() else 3.5) for e, d in users_db.items() if isinstance(d, dict) and e != st.session_state.current_user and not d.get("privacy", {}).get("ghost") and not d.get("frozen") and not d.get("suspended")]
        
        if sort_users == "İsme Göre (A-Z)": user_list.sort(key=lambda x: x[1].get('ad_soyad', '').lower())
        elif sort_users == "Seviyeye Göre (Yüksekten Düşüğe)": user_list.sort(key=lambda x: x[3], reverse=True)
        elif sort_users == "Puana Göre (Popülerlik)": user_list.sort(key=lambda x: x[2], reverse=True)
        else: user_list.sort(key=lambda x: x[1].get('ilce', 'Belirtilmemiş'))

        if st.session_state.offer_to:
            target_u = users_db.get(st.session_state.offer_to, {})
            st.info(f"👉 **{target_u.get('ad_soyad', 'Kullanıcı')}** kişisine özel teklif oluşturuyorsunuz.")
            
            o_date = st.date_input("Tarih Önerisi", min_value=datetime.date.today(), key="do_date")
            c_o1, c_o2 = st.columns(2)
            o_t1 = c_o1.time_input("Başlangıç", datetime.time(18, 0), key="do_t1")
            o_t2 = c_o2.time_input("Bitiş", datetime.time(19, 30), key="do_t2")
            o_court = st.selectbox("Kort Önerisi", IZMIR_KORTLARI, key="do_court")
            o_custom = st.text_input("Diğer ise belirtin:", key="do_cust") if o_court == "Diğer" else ""
            
            c_sub, c_can = st.columns(2)
            if c_sub.button("🚀 Teklifi Gönder", use_container_width=True):
                new_msg = {"id": str(uuid.uuid4()), "type": "direct_challenge", "sender": st.session_state.current_user, "receiver": st.session_state.offer_to, "date": str(o_date), "time": f"{o_t1.strftime('%H:%M')} - {o_t2.strftime('%H:%M')}", "court": o_court, "court_custom": o_custom, "status": "pending"}
                if save_data(MESSAGES_FILE_PATH, messages + [new_msg], 'db_messages'):
                    st.session_state.offer_to = None; st.toast("Teklif iletildi!", icon="✅"); time.sleep(1); st.rerun()
                else: st.error("⚠️ Veri hatası: Özel teklifiniz kaydedilemedi.")
            if c_can.button("İptal", use_container_width=True): st.session_state.offer_to = None; st.rerun()

        for u_email, u_data, rating_val, _ in user_list:
            with st.container(border=True):
                colA, colB, colC = st.columns([3, 3, 2])
                disp_rating = f"{rating_val:.1f}" if u_data.get("privacy", {}).get("show_rating", True) else "Gizli"
                u_ilce = u_data.get('ilce', 'Belirtilmemiş')
                
                colA.markdown(f"**👤 {u_data.get('ad_soyad')}** | NTRP: **{u_data.get('level', '3.5')}** {'📍 ' + u_ilce if u_ilce != 'Belirtilmemiş' else ''}")
                colA.markdown(f"⭐ Puan: **{disp_rating}** | Tarz: {u_data.get('style', 'Belirtilmedi')}")
                
                cv = u_data.get('contact_visibility')
                if cv == 'herkes': colB.write(f"📞 {u_data.get('phone', 'Gizli')} | ✉️ {u_email}")
                else: colB.write("🔒 İletişim: Eşleşince Görünür")
                
                if any(m.get('sender') == st.session_state.current_user and m.get('receiver') == u_email and m.get('status') == 'pending' for m in messages):
                    colC.button("✅ Teklif Gönderildi", key=f"dir_sent_{u_email}", disabled=True)
                else:
                    if colC.button("🎾 Özel Teklif Et", key=f"chall_{u_email}"): st.session_state.offer_to = u_email; st.rerun()

    # --- TAB 3: TENİS AJANDAM ---
    with tabs[3]:
        st.subheader("🎾 Tenis Ajandam")
        
        inbox_label = f"📥 Gelen Teklifler ({my_inbox_count})" if my_inbox_count > 0 else "📥 Gelen Teklifler"
        m_tab1, m_tab2, m_tab3, m_tab4 = st.tabs([inbox_label, "📤 Gönderdiğim Teklifler", "📅 Onaylanmış Maçlarım", "📜 Geçmiş & İptal Edilenler"])

        with m_tab1:
            my_inbox = [m for m in messages if m.get('receiver') == st.session_state.current_user and m.get('status') == 'pending']
            if not my_inbox: st.info("Bekleyen gelen bir teklifiniz bulunmuyor.")
            for msg in my_inbox:
                with st.container(border=True):
                    s_user = users_db.get(msg['sender'], {})
                    if msg.get('type') == 'invite_request':
                        inv_data = next((i for i in invites if i.get('id') == msg.get('invite_id')), {})
                        st.write(f"🔔 **{s_user.get('ad_soyad', 'Anonim')}** sizin **{inv_data.get('date')}** tarihli **{inv_data.get('court')}** ilanınıza katılmak istiyor!")
                    else:
                        st.write(f"🔔 **{s_user.get('ad_soyad', 'Anonim')}** size özel maç teklif etti! Tarih: **{msg.get('date')}** | Kort: **{msg.get('court')}**")

                    render_popover_profile(msg['sender'], s_user, messages)

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
                        else: msg['calendar_link'] = generate_gcal_link("Tenis Maçı", msg.get('date', ''), msg.get('time', '18:00'), msg.get('court', ''))
                            
                        if inv_kayit_basarili and save_data(MESSAGES_FILE_PATH, messages, 'db_messages'):
                            send_email(msg['sender'], "Teklifiniz Kabul Edildi!", f"<b>{me.get('ad_soyad')}</b> teklifinizi kabul etti!")
                            st.toast("Teklif kabul edildi! 🎉", icon="✅"); time.sleep(1); st.rerun()
                        else: st.error("⚠️ Veritabanı çakışması: Onayınız kaydedilemedi.")

                    if not st.session_state.get(f"conf_rej_{msg['id']}", False):
                        if c_rej.button("❌ Reddet", key=f"btn_rej_{msg['id']}"): st.session_state[f"conf_rej_{msg['id']}"] = True; st.rerun()
                    else:
                        c_rej.warning("Reddedilsin mi?")
                        if c_rej.button("Evet, Reddet", key=f"yes_rej_{msg['id']}"):
                            msg['status'] = 'rejected'
                            if save_data(MESSAGES_FILE_PATH, messages, 'db_messages'):
                                st.session_state[f"conf_rej_{msg['id']}"] = False; st.toast("Teklif reddedildi.", icon="ℹ️"); time.sleep(1); st.rerun()
                            else: st.error("⚠️ Hata: Red işlemi kaydedilemedi.")
                        if c_rej.button("Vazgeç", key=f"no_rej_{msg['id']}"): st.session_state[f"conf_rej_{msg['id']}"] = False; st.rerun()

        with m_tab2:
            my_sent = [m for m in messages if m.get('sender') == st.session_state.current_user]
            if not my_sent: st.info("Henüz kimseye teklif göndermediniz.")
            for msg in reversed(my_sent):
                with st.container(border=True):
                    r_user = users_db.get(msg.get('receiver'), {})
                    st_map = {"pending": "⏳ Onay Bekliyor", "accepted": "✅ Kabul Edildi", "rejected": "❌ Reddedildi", "cancelled": "🚫 İptal Edildi"}
                    st.write(f"📤 Alıcı: **{r_user.get('ad_soyad', 'Bilinmeyen')}** | Durum: **{st_map.get(msg.get('status'), 'Bilinmiyor')}**")
                    
                    if msg.get('status') == 'pending':
                        if not st.session_state.get(f"conf_with_{msg['id']}", False):
                            if st.button("🗑️ Teklifi Geri Çek", key=f"btn_with_{msg['id']}"): st.session_state[f"conf_with_{msg['id']}"] = True; st.rerun()
                        else:
                            st.warning("Bu teklifi geri çekmek istediğinize emin misiniz?")
                            cw1, cw2 = st.columns(2)
                            if cw1.button("Evet, Geri Çek", key=f"yes_with_{msg['id']}"):
                                if save_data(MESSAGES_FILE_PATH, [m for m in messages if m['id'] != msg['id']], 'db_messages'):
                                    st.session_state[f"conf_with_{msg['id']}"] = False; st.toast("Teklif geri çekildi.", icon="✅"); time.sleep(1); st.rerun()
                                else: st.error("⚠️ Hata: İşlem kaydedilemedi.")
                            if cw2.button("Vazgeç", key=f"no_with_{msg['id']}"): st.session_state[f"conf_with_{msg['id']}"] = False; st.rerun()

        with m_tab3:
            my_acc = [m for m in messages if (m.get('receiver') == st.session_state.current_user or m.get('sender') == st.session_state.current_user) and m.get('status') == 'accepted']
            if not my_acc: st.info("Yaklaşan onaylanmış bir maçınız yok.")
            for acc in reversed(my_acc):
                with st.container(border=True):
                    partner_e = acc['sender'] if acc['receiver'] == st.session_state.current_user else acc['receiver']
                    partner_u = users_db.get(partner_e, {})
                    
                    if acc.get('type') == 'invite_request':
                        inv_data = next((i for i in invites if i.get('id') == acc.get('invite_id')), {})
                        m_date, m_time, m_court = inv_data.get('date', '-'), inv_data.get('time_details', '-'), inv_data.get('court', '-')
                    else:
                        m_date, m_time, m_court = acc.get('date', '-'), acc.get('time', '-'), acc.get('court', '-')

                    st.markdown(f"🤝 **Partner:** {partner_u.get('ad_soyad', 'Partner')} *(NTRP {partner_u.get('level', '3.5')})*")
                    st.markdown(f"🗓️ **Tarih & Saat:** {m_date} | {m_time} | 📍 **Kort:** {m_court}")
                    st.markdown(f"[📅 Google Takvime Ekle]({acc.get('calendar_link', '#')})")
                    
                    if partner_u.get('contact_visibility', 'eslesince') in ['eslesince', 'herkes']:
                        st.success(f"📞 İletişim: {partner_u.get('phone', 'Belirtilmedi')} | ✉️ {partner_e}")
                    else: st.info("🔒 Kullanıcı iletişim bilgilerini gizlemeyi tercih etmiş.")

                    with st.expander(f"💬 {partner_u.get('ad_soyad', 'Partner')} ile Mesajlaş"):
                        for chat in acc.get("chat_history", []):
                            with st.chat_message("user" if chat["sender"] == st.session_state.current_user else "assistant"):
                                st.write(chat["text"]); st.caption(chat["timestamp"])
                        
                        if new_msg := st.chat_input("Mesajınızı yazın...", key=f"chat_input_{acc['id']}"):
                            acc.setdefault("chat_history", []).append({"sender": st.session_state.current_user, "text": new_msg, "timestamp": datetime.datetime.now().strftime("%d-%m %H:%M")})
                            if save_data(MESSAGES_FILE_PATH, messages, 'db_messages'):
                                send_email(partner_e, f"💬 Yeni Mesaj: {m_date} Maçı", f"Partneriniz <b>{me.get('ad_soyad')}</b> mesaj gönderdi:<br>\"{new_msg}\"")
                                st.rerun()
                            else: st.error("⚠️ Mesajınız gönderilemedi.")

                    c_opt1, c_opt2 = st.columns(2)
                    if not st.session_state.get(f"conf_del_acc_{acc['id']}", False):
                        if c_opt1.button("🗑️ Maçı İptal Et", key=f"btn_del_acc_{acc['id']}"): st.session_state[f"conf_del_acc_{acc['id']}"] = True; st.rerun()
                    else:
                        c_opt1.warning("Emin misiniz?")
                        if c_opt1.button("Evet, İptal Et", key=f"yes_del_acc_{acc['id']}"):
                            acc['status'] = 'cancelled'
                            inv_kayit = True
                            if acc.get('type') == 'invite_request':
                                target_inv = next((i for i in invites if i.get('id') == acc.get('invite_id')), None)
                                if target_inv:
                                    if st.session_state.current_user == target_inv.get('creator'): invites = [i for i in invites if i.get('id') != acc.get('invite_id')]
                                    else: target_inv['status'] = 'paused_by_cancellation'
                                    inv_kayit = save_data(INVITES_FILE_PATH, invites, 'db_invites')
                            if inv_kayit and save_data(MESSAGES_FILE_PATH, messages, 'db_messages'):
                                send_email(partner_e, "Maç İptali", f"<b>{me.get('ad_soyad')}</b> maçı iptal etti.")
                                st.session_state[f"conf_del_acc_{acc['id']}"] = False; st.toast("Maç iptal edildi.", icon="🗑️"); time.sleep(1); st.rerun()
                            else: st.error("⚠️ İptal kaydedilemedi.")
                        if c_opt1.button("Vazgeç", key=f"no_del_acc_{acc['id']}"): st.session_state[f"conf_del_acc_{acc['id']}"] = False; st.rerun()

                    if not st.session_state.get(f"conf_edit_acc_{acc['id']}", False):
                        if c_opt2.button("✏️ İptal Et & Yeniden Yayınla", key=f"btn_edit_acc_{acc['id']}"): st.session_state[f"conf_edit_acc_{acc['id']}"] = True; st.rerun()
                    else:
                        c_opt2.warning("Yeniden yayınlansın mı?")
                        if c_opt2.button("Evet, Yayınla", key=f"yes_edit_acc_{acc['id']}"):
                            acc['status'] = 'cancelled'
                            inv_kayit = True
                            if acc.get('type') == 'invite_request':
                                for i in invites:
                                    if i.get('id') == acc.get('invite_id'): i['status'] = 'active'; st.session_state.editing_invite = i.get('id'); break
                                inv_kayit = save_data(INVITES_FILE_PATH, invites, 'db_invites')
                            if inv_kayit and save_data(MESSAGES_FILE_PATH, messages, 'db_messages'):
                                st.session_state[f"conf_edit_acc_{acc['id']}"] = False; st.toast("Havuza döndü!", icon="✏️"); time.sleep(1); st.rerun()
                            else: st.error("⚠️ Hata.")
                        if c_opt2.button("Vazgeç", key=f"no_edit_acc_{acc['id']}"): st.session_state[f"conf_edit_acc_{acc['id']}"] = False; st.rerun()

            paused_invites = [i for i in invites if i.get('creator') == st.session_state.current_user and i.get('status') == 'paused_by_cancellation']
            if paused_invites:
                st.warning("⚠️ **İptal Bildirimi:** Karşı taraf iptal ettiği için aşağıdaki ilanınız askıya alındı.")
                for pinv in paused_invites:
                    with st.container(border=True):
                        st.write(f"📍 {pinv.get('court')} | 🗓️ {pinv.get('date')} eşleşmesi iptal oldu.")
                        col_p1, col_p2 = st.columns(2)
                        if col_p1.button("📢 Yeniden Yayına Al", key=f"repub_{pinv.get('id')}"):
                            pinv['status'] = 'active'
                            if save_data(INVITES_FILE_PATH, invites, 'db_invites'): st.toast("Vitrine eklendi! 🚀", icon="✅"); time.sleep(1); st.rerun()
                        if col_p2.button("🗑️ Tamamen Kapat", key=f"close_{pinv.get('id')}"):
                            if save_data(INVITES_FILE_PATH, [i for i in invites if i.get('id') != pinv.get('id')], 'db_invites'): st.toast("Kaldırıldı.", icon="🗑️"); time.sleep(1); st.rerun()

            if st.session_state.editing_invite:
                if e_inv := next((i for i in invites if i.get('id') == st.session_state.editing_invite), None):
                    st.subheader("✏️ İlanı Güncelle")
                    with st.form("edit_inv_form"):
                        ed_d = st.date_input("Yeni Tarih", value=datetime.datetime.strptime(e_inv.get('date'), "%Y-%m-%d").date())
                        ed_court = st.selectbox("Yeni Kort", IZMIR_KORTLARI, index=IZMIR_KORTLARI.index(e_inv.get('court')) if e_inv.get('court') in IZMIR_KORTLARI else 0)
                        ed_note = st.text_area("İlan Notu", value=e_inv.get('note', ''))
                        if st.form_submit_button("Güncelle ve Gönder"):
                            e_inv.update({'date': str(ed_d), 'court': ed_court, 'note': ed_note, 'status': 'active'})
                            if save_data(INVITES_FILE_PATH, invites, 'db_invites'): st.session_state.editing_invite = None; st.toast("Güncellendi!", icon="✅"); time.sleep(1); st.rerun()

        with m_tab4:
            past_m = [m for m in messages if (m.get('receiver') == st.session_state.current_user or m.get('sender') == st.session_state.current_user) and m.get('status') in ['cancelled', 'rejected'] and st.session_state.current_user not in m.get('hidden_by', [])]
            if not past_m: st.info("Geçmiş iptal veya red kaydı bulunmuyor.")
            for pm in past_m: 
                col_txt, col_btn = st.columns([4,1])
                col_txt.write(f"⚪ Kayıt | ID: {pm['id'][:8]} | Durum: **{pm['status']}**")
                if col_btn.button("🗑️ Listemden Gizle", key=f"hide_{pm['id']}"):
                    pm.setdefault('hidden_by', []).append(st.session_state.current_user)
                    save_data(MESSAGES_FILE_PATH, messages, 'db_messages')
                    st.rerun()

    # --- TAB 4: DEĞERLENDİRME ---
    with tabs[4]:
        st.subheader("⚖️ Maç Sonrası Değerlendirme")
        unrated_events = [m for m in messages if (m.get('receiver') == st.session_state.current_user or m.get('sender') == st.session_state.current_user) and m.get('status') == 'accepted' and st.session_state.current_user not in m.get('rated_by', [])]
        
        if not unrated_events: st.info("Değerlendirebileceğiniz tamamlanmış maç bulunmuyor.")
        else:
            with st.form("rating_form"):
                evt_opts = {m['id']: f"Rakip: {users_db.get(m['sender'] if m['receiver'] == st.session_state.current_user else m['receiver'], {}).get('ad_soyad', 'Bilinmeyen')}" for m in unrated_events}
                selected_event_id = st.selectbox("Değerlendirilecek Maç", options=list(evt_opts.keys()), format_func=lambda x: evt_opts[x])
                st.markdown("**(1: Zayıf - 5: Mükemmel)**")
                sz = st.slider("Zaman Planlamasına Uyum", 1, 5, 5); ss = st.slider("Seviye Tutarlılığı", 1, 5, 5); sd = st.slider("Sportmenlik & İletişim", 1, 5, 5)
                
                if st.form_submit_button("⭐ Değerlendirmeyi Kaydet"):
                    target_event = next(m for m in unrated_events if m['id'] == selected_event_id)
                    p_email = target_event['sender'] if target_event['receiver'] == st.session_state.current_user else target_event['receiver']
                    
                    if p_email in users_db and isinstance(users_db[p_email], dict):
                        users_db[p_email].setdefault("ratings", {"zaman": [], "seviye": [], "davranis": []})["zaman"].append(sz)
                        users_db[p_email]["ratings"]["seviye"].append(ss); users_db[p_email]["ratings"]["davranis"].append(sd)
                        target_event.setdefault('rated_by', []).append(st.session_state.current_user)
                        
                        if save_data(USERS_FILE_PATH, users_db, 'db_users') and save_data(MESSAGES_FILE_PATH, messages, 'db_messages'):
                            st.toast("Değerlendirmeniz kaydedildi! ⭐", icon="✅"); time.sleep(1); st.rerun()
                        else: st.error("⚠️ Değerlendirme kaydedilemedi.")

    # --- TAB 5: PROFİL & AYARLAR ---
    with tabs[5]:
        colL, colR = st.columns(2)
        with colL:
            st.subheader("👤 Profil Bilgilerim")
            st.text_input("E-Posta Adresi (Değiştirilemez)", value=st.session_state.current_user, disabled=True, key="prof_mail")
            ad = st.text_input("Ad Soyad", value=me.get("ad_soyad", ""), key="prof_ad")
            phone = st.text_input("Telefon Numarası", value=me.get("phone", ""), key="prof_tel")
            ilce = st.selectbox("Bölge / İlçe", IZMIR_ILCELER, index=IZMIR_ILCELER.index(me.get("ilce", "Belirtilmemiş")) if me.get("ilce") in IZMIR_ILCELER else 0, key="prof_ilce")
            level = st.selectbox("NTRP Oyuncu Seviyeniz", NTRP_LEVELS, index=NTRP_LEVELS.index(me.get("level", "3.5")) if me.get("level") in NTRP_LEVELS else 5, key="prof_lvl")
            
            me_style = me.get("style", "All-Rounder")
            style_opts = ["Agresif Baseline", "Servis & Vole", "Defansif / Karşılayıcı", "All-Rounder", "Diğer"]
            style_sel = st.selectbox("Oyun Tarzı", style_opts, index=4 if me_style not in style_opts[:-1] else style_opts.index(me_style), key="prof_style")
            style_custom = st.text_input("Diğer ise Oyun Tarzınızı Yazın:", value=me_style if me_style not in style_opts[:-1] else "", key="prof_style_cust") if style_sel == "Diğer" else ""

            if st.button("💾 Profili Güncelle", use_container_width=True):
                me.update({"ad_soyad": ad.strip(), "phone": phone.strip(), "ilce": ilce, "level": level, "style": style_custom.strip() if style_sel == "Diğer" else style_sel})
                users_db[st.session_state.current_user] = me
                if save_data(USERS_FILE_PATH, users_db, 'db_users'): st.toast("Profil güncellendi! ✅", icon="👤"); time.sleep(1); st.rerun()
                else: st.error("⚠️ Profiliniz güncellenemedi.")

            with st.expander("🔑 Şifre Değiştir"):
                with st.form("change_pass_form"):
                    old_pass = st.text_input("Mevcut Şifre", type="password")
                    new_pass = st.text_input("Yeni Şifre", type="password")
                    if st.form_submit_button("Şifreyi Güncelle"):
                        if hash_password(old_pass) != me.get("password_hash"): st.error("Mevcut şifreniz hatalı!")
                        elif len(new_pass) < 4: st.error("Şifre en az 4 karakter olmalıdır.")
                        else:
                            me["password_hash"] = hash_password(new_pass)
                            users_db[st.session_state.current_user] = me
                            if save_data(USERS_FILE_PATH, users_db, 'db_users'): st.success("Şifreniz değiştirildi!")
                            else: st.error("⚠️ Şifre kaydedilemedi.")
                            
            st.markdown("---")
            st.subheader("⏸️ Hesap Durumu (Dondurma)")
            with st.form("freeze_form"):
                is_frozen = st.toggle("Bir süre tenis oynayamayacağım, hesabımı dondur", value=me.get("frozen", False))
                if st.form_submit_button("Durumu Güncelle"):
                    me["frozen"] = is_frozen; users_db[st.session_state.current_user] = me
                    if save_data(USERS_FILE_PATH, users_db, 'db_users'): st.toast("Hesap durumu güncellendi!", icon="⏸️"); time.sleep(1); st.rerun()
                    else: st.error("⚠️ Hesap durumu güncellenemedi.")

            st.markdown("---")
            st.subheader("🚨 Tehlikeli Bölge")
            with st.expander("Hesabımı Kalıcı Olarak Silme Talebi Gönder"):
                st.warning("⚠️ **DİKKAT:** Hesabınız ve tüm verileriniz kalıcı olarak silinir.")
                if me.get("delete_requested"): st.info("ℹ️ Silme talebiniz onay bekliyor.")
                elif st.button("🗑️ Silme Talebini İlet"):
                    me["delete_requested"] = True; users_db[st.session_state.current_user] = me
                    if save_data(USERS_FILE_PATH, users_db, 'db_users'):
                        send_email(ADMIN_EMAIL, "🚨 Silme Talebi", f"<b>{me.get('ad_soyad')}</b> hesabını silmek istiyor.")
                        st.toast("Talebiniz iletildi.", icon="📨"); time.sleep(1); st.rerun()
                    else: st.error("⚠️ Talebiniz iletilemedi.")

        with colR:
            st.subheader("🔒 İletişim & Gizlilik Ayarları")
            with st.form("privacy_form"):
                vis_keys = ["gizle", "eslesince", "herkes"]
                c_vis = st.selectbox("Telefon/E-Posta Görünürlüğü", ["Gizle (Hiçbir Zaman Gösterme)", "Sadece Eşleşince Göster", "Herkese Açık (İlanda Göster)"], index=vis_keys.index(me.get("contact_visibility", "eslesince")) if me.get("contact_visibility") in vis_keys else 1)
                ghost = st.toggle("👻 Hayalet Modu (Üye listesinde görünme)", value=me.get("privacy", {}).get("ghost", False))
                show_r = st.toggle("⭐ Değerlendirme Puanımı Göster", value=me.get("privacy", {}).get("show_rating", True))
                if st.form_submit_button("🔒 Ayarları Kaydet"):
                    me["contact_visibility"] = vis_keys[["Gizle (Hiçbir Zaman Gösterme)", "Sadece Eşleşince Göster", "Herkese Açık (İlanda Göster)"].index(c_vis)]
                    me.setdefault("privacy", {})["ghost"] = ghost; me.setdefault("privacy", {})["show_rating"] = show_r
                    users_db[st.session_state.current_user] = me
                    if save_data(USERS_FILE_PATH, users_db, 'db_users'): st.toast("Gizlilik tercihleri kaydedildi! ✅", icon="🔒"); time.sleep(1); st.rerun()
                    else: st.error("⚠️ Ayarlarınız kaydedilemedi.")

            st.markdown("---")
            st.subheader("📡 Radar Ayarları")
            st.caption("Aşağıdaki kriterlerinize uyan yeni bir ilan havuza eklendiğinde, sistem size otomatik olarak haberci e-posta gönderir. Böylece fırsatları kimse kapmadan yakalayabilirsiniz.")
            radar_data = me.get("radar", {"active": False, "courts": [], "levels": [], "types": []})
            with st.form("radar_form"):
                r_active = st.toggle("📡 Radarı Aktif Et", value=radar_data.get("active", False))
                r_courts = st.multiselect("Kortlar (Boş bırakılırsa tümü)", IZMIR_KORTLARI, default=radar_data.get("courts", []))
                r_levels = st.multiselect("NTRP Seviyeleri (Boş bırakılırsa tümü)", NTRP_LEVELS, default=radar_data.get("levels", []))
                r_types = st.multiselect("Etkinlik Tipleri", ACTIVITY_TYPES, default=radar_data.get("types", []))
                if st.form_submit_button("📡 Radar Tercihlerini Kaydet"):
                    me["radar"] = {"active": r_active, "courts": r_courts, "levels": r_levels, "types": r_types}
                    users_db[st.session_state.current_user] = me
                    if save_data(USERS_FILE_PATH, users_db, 'db_users'): st.toast("Radar ayarlarınız kaydedildi! 📡", icon="✅"); time.sleep(1); st.rerun()
                    else: st.error("⚠️ Radar tercihleriniz kaydedilemedi.")

# --- UYGULAMA GİRİŞ NOKTASI ---
if not st.session_state.logged_in: login_page()
elif st.session_state.is_admin: admin_dashboard()
else: main_app()
