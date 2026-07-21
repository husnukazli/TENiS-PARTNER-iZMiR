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
    .block-container { padding-top: 4.5rem; padding-bottom: 2rem; }
    .stButton > button { width: 100%; border-radius: 12px; font-weight: 600; }
    .stTabs [data-baseweb="tab-list"] { display: flex; justify-content: space-evenly; overflow-x: auto; }
    div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 16px; }
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;} 
</style>
""", unsafe_allow_html=True)

if HAS_STX:
    cookie_manager = stx.CookieManager(key="cm_izmir")
else:
    cookie_manager = None

# --- SABİT VERİLER ---
NTRP_LEVELS = ["1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0", "5.5", "6.0", "6.5", "7.0"]
IZMIR_KORTLARI = [
    "Kültürpark Tenis Kulübü (KTK)", "İnciraltı Büyükşehir Kortları", "Bostanlı Suat Taşer Kortları",
    "Fuar Alanı (Celal Atik) Kortları", "Buca Tenis Kulübü", "Ege Üniversitesi Tenis Kortları",
    "Gaziemir Belediyesi Kortları", "Göztepe Tenis Kulübü", "Küçük Kulüp Alliance", "Mavişehir Şemikler Kortları",
    "Aşık Veysel Rekreasyon Alanı Kortları", "Hasanağa Bahçesi Kortları", "Diğer"
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
FEE_STATUS_OPTIONS = [
    "Ücretsiz Kort / Abonelik", 
    "Ücreti Bölüşeceğiz (Yarı Yarıya)", 
    "Ücreti Ben Karşılayacağım", 
    "Davetlinin Karşılaması Beklenir"
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

def format_date_tr(date_str):
    if not date_str or date_str == '-': return "-"
    if "." in date_str: return date_str
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    except:
        return date_str

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

def get_invite_status(inv_date, inv_time_details):
    try:
        t_str = inv_time_details.split('-')[0].strip()
        inv_dt = datetime.datetime.strptime(f"{inv_date} {t_str}", "%Y-%m-%d %H:%M")
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
        if now > inv_dt + datetime.timedelta(hours=12):
            return "removed"
        elif now > inv_dt:
            return "expired"
        else:
            return "active"
    except:
        return "active"

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

# --- YENİ EKLENEN DİALOG PENCERELERİ (MADDE 9 ve MADDE 7) ---
@st.dialog("⚠️ Maç İptal Onayı")
def dialog_cancel_match(acc_id, republish=False):
    st.warning("Bu maçı iptal etmek istediğinize emin misiniz? Bu işlem geri alınamaz.")
    c1, c2 = st.columns(2)
    if c1.button("Evet, İptal Et", type="primary"):
        acc = next((m for m in st.session_state.db_messages if m['id'] == acc_id), None)
        if acc:
            try:
                if acc.get('type') == 'invite_request':
                    target_inv = next((i for i in st.session_state.db_invites if i.get('id') == acc.get('invite_id')), {})
                    m_dt = datetime.datetime.strptime(f"{target_inv.get('date')} {target_inv.get('time_details', '18:00').split('-')[0].strip()}", "%Y-%m-%d %H:%M")
                else:
                    m_dt = datetime.datetime.strptime(f"{acc.get('date')} {acc.get('time', '18:00').split('-')[0].strip()}", "%Y-%m-%d %H:%M")
                now_dt = datetime.datetime.now()
                hours_left = (m_dt - now_dt).total_seconds() / 3600
                is_late = (0 < hours_left <= 3) # MADDE 7: Son dakika iptali
            except:
                is_late = False

            acc['status'] = 'cancelled_late' if is_late else 'cancelled'
            acc['cancelled_by'] = st.session_state.current_user

            inv_kayit = True
            if acc.get('type') == 'invite_request':
                target_inv = next((i for i in st.session_state.db_invites if i.get('id') == acc.get('invite_id')), None)
                if target_inv:
                    if republish and st.session_state.current_user == target_inv.get('creator'):
                        target_inv['status'] = 'active'
                    else:
                        if st.session_state.current_user == target_inv.get('creator'):
                            st.session_state.db_invites = [i for i in st.session_state.db_invites if i.get('id') != target_inv.get('id')]
                        else:
                            target_inv['status'] = 'paused_by_cancellation'
                    inv_kayit = save_data(INVITES_FILE_PATH, st.session_state.db_invites, 'db_invites')
            
            if inv_kayit and save_data(MESSAGES_FILE_PATH, st.session_state.db_messages, 'db_messages'):
                partner_e = acc['sender'] if acc['receiver'] == st.session_state.current_user else acc['receiver']
                send_email(partner_e, "Maç İptali", f"<b>{st.session_state.db_users.get(st.session_state.current_user, {}).get('ad_soyad')}</b> maçı iptal etti.")
                st.session_state.show_toast = "Maç iptal edildi. (Son dakika iptali cezası uygulanacaktır.)" if is_late else "Maç başarıyla iptal edildi."
                st.rerun()
            else:
                st.error("⚠️ İptal işlemi kaydedilemedi.")
    if c2.button("Hayır, Vazgeç"):
        st.rerun()

@st.dialog("⚠️ İlan Kaldırma Onayı")
def dialog_delete_invite(inv_id):
    st.warning("Bu ilanı panodan kaldırmak istediğinize emin misiniz?")
    c1, c2 = st.columns(2)
    if c1.button("Evet, Kaldır", type="primary"):
        st.session_state.db_invites = [i for i in st.session_state.db_invites if i.get('id') != inv_id]
        if save_data(INVITES_FILE_PATH, st.session_state.db_invites, 'db_invites'):
            st.session_state.show_toast = "İlan başarıyla kaldırıldı."
            st.rerun()
    if c2.button("Vazgeç"):
        st.rerun()


# --- OTURUM YÖNETİMİ ---
for key in ['logged_in', 'is_admin', 'current_user', 'offer_to', 'reg_step', 'reg_data', 'reg_code', 'editing_invite', 'show_login_form', 'edit_my_active', 'show_toast']:
    if key not in st.session_state: st.session_state[key] = False if key in ['logged_in', 'is_admin', 'show_login_form'] else None
if 'reg_step' not in st.session_state or st.session_state.reg_step is None: st.session_state.reg_step = "form"

if 'db_users' not in st.session_state: st.session_state.db_users = load_data(USERS_FILE_PATH, dict)
if 'db_invites' not in st.session_state: st.session_state.db_invites = load_data(INVITES_FILE_PATH, list)
if 'db_messages' not in st.session_state: st.session_state.db_messages = load_data(MESSAGES_FILE_PATH, list)

# Toast Bildirim Yöneticisi
if st.session_state.show_toast:
    st.toast(st.session_state.show_toast, icon="ℹ️")
    st.session_state.show_toast = None

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
    st.markdown("<h1 style='color: #D32F2F;'>Yönetici Kontrol Merkezi</h1>", unsafe_allow_html=True)
    if st.button("🚪 Yönetici Panelinden Çık"):
        st.session_state.logged_in = False; st.session_state.is_admin = False
        if cookie_manager and cookie_manager.get("remember_user"):
            cookie_manager.delete("remember_user")
            time.sleep(0.5)
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
            c1.write(f"📍 {inv.get('court')} | 🗓️ {format_date_tr(inv.get('date'))} | Durum: **{inv.get('status')}**")
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
        st.subheader("Sistem Yedekleme ve Kurtarma")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 📥 Yedeği İndir")
            st.download_button("Üyeler Yedeği (users.json)", data=json.dumps(users_db, indent=4, ensure_ascii=False), file_name="users_backup.json", mime="application/json")
            st.download_button("İlanlar Yedeği (invites.json)", data=json.dumps(invites, indent=4, ensure_ascii=False), file_name="invites_backup.json", mime="application/json")
            st.download_button("Mesajlar Yedeği (messages.json)", data=json.dumps(messages, indent=4, ensure_ascii=False), file_name="messages_backup.json", mime="application/json")
        with c2:
            st.markdown("### 📤 Yedekten Yükle")
            
            up_u = st.file_uploader("Üye Yedeği Yükle (users.json)", type=["json"])
            if st.button("Uygula (Üyeler)") and up_u:
                if save_data(USERS_FILE_PATH, json.loads(up_u.getvalue().decode("utf-8")), 'db_users'):
                    st.success("Üyeler başarıyla güncellendi!")
                    time.sleep(1); st.rerun()
                else:
                    st.error("⚠️ Hata: Üye yedeği yüklenemedi.")
                    
            up_i = st.file_uploader("İlanlar Yedeği Yükle (invites.json)", type=["json"])
            if st.button("Uygula (İlanlar)") and up_i:
                if save_data(INVITES_FILE_PATH, json.loads(up_i.getvalue().decode("utf-8")), 'db_invites'):
                    st.success("İlanlar başarıyla güncellendi!")
                    time.sleep(1); st.rerun()
                else:
                    st.error("⚠️ Hata: İlan yedeği yüklenemedi.")
                    
            up_m = st.file_uploader("Mesajlar Yedeği Yükle (messages.json)", type=["json"])
            if st.button("Uygula (Mesajlar)") and up_m:
                if save_data(MESSAGES_FILE_PATH, json.loads(up_m.getvalue().decode("utf-8")), 'db_messages'):
                    st.success("Mesajlar başarıyla güncellendi!")
                    time.sleep(1); st.rerun()
                else:
                    st.error("⚠️ Hata: Mesaj yedeği yüklenemedi.")

# --- GİRİŞ VE GÜNCEL İLANLAR SAYFASI ---
def login_page():
    sidebar_pwa_guide()
    
    st.markdown("<h1 style='text-align: center; color: #2E7D32;'>🎾 İzmir Tenis Partner Ağı</h1>", unsafe_allow_html=True)
    
    users_db = st.session_state.db_users
    invites = st.session_state.db_invites
    messages = st.session_state.db_messages
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if not st.session_state.show_login_form:
            # MADDE 2: VİTRİN EKLENTİSİ
            st.info("""
            **Nasıl Çalışır?**
            1. **Profilinizi Oluşturun:** Seviyenizi ve bölgelerinizi belirleyerek sisteme katılın.
            2. **İlanları İnceleyin:** Açık maçlara istek gönderin veya kendi maçınızı oluşturun.
            3. **Korta Çıkın:** Eşleştiğiniz oyuncuyla iletişime geçip maçınızı yapın.
            """)
            
            # MADDE 8: SOSYAL KANIT
            matched_invs = [i for i in invites if i.get('status') == 'matched']
            if matched_invs:
                st.markdown("#### 🤝 Son Eşleşen Maçlar")
                for m_inv in sorted(matched_invs, key=lambda x: x.get('date', ''), reverse=True)[:3]:
                    st.markdown(f"<div style='color:gray; font-size:0.9em; padding: 6px; border: 1px dashed #ccc; border-radius: 6px; margin-bottom: 5px;'>✅ {format_date_tr(m_inv.get('date'))} | {m_inv.get('court')} | Seviye: {', '.join(m_inv.get('levels', []))} <i>(Eşleşti)</i></div>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)

            if st.button("🔑 Sisteme Giriş Yap veya Kayıt Ol", use_container_width=True):
                st.session_state.show_login_form = True; st.rerun()
        else:
            if st.button("🔙 İlanlara Geri Dön", use_container_width=True):
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
                                    send_email(ADMIN_EMAIL, "🔔 Yeni Üye Kaydı", f"Sisteme yeni bir üye katıldı!<br><br><b>Ad Soyad:</b> {d['name']}<br><b>E-posta:</b> {d['email']}<br><b>Seviye:</b> {d['level']}<br><b>İlçe:</b> {d.get('ilce', 'Belirtilmemiş')}")
                                    st.session_state.reg_step = "form"
                                    st.session_state.show_toast = "Kayıt başarılı! 🎉 Giriş yapabilirsiniz."
                                    st.rerun()
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
        st.markdown("### ☀️ Güncel İlanlar")
        st.write("Aşağıdaki ilanlara teklif göndermek için yukarıdan giriş yapmalısınız.")
        
        active_inv = [i for i in invites if i.get('status') == 'active' and isinstance(users_db.get(i.get('creator'), {}), dict) and not users_db.get(i.get('creator'), {}).get('suspended') and not users_db.get(i.get('creator'), {}).get('frozen')]
        
        filtered_active = []
        for inv in active_inv:
            s = get_invite_status(inv.get('date'), inv.get('time_details', ''))
            if s != "removed":
                filtered_active.append((inv, s))
                
        active_only = [x for x in filtered_active if x[1] == 'active']
        expired_only = [x for x in filtered_active if x[1] == 'expired']
        
        active_only.sort(key=lambda x: (x[0].get('date', '9999-12-31'), x[0].get('time_details', '23:59')))
        expired_only.sort(key=lambda x: (x[0].get('date', '9999-12-31'), x[0].get('time_details', '23:59')), reverse=True)
        
        filtered_active = active_only + expired_only
        
        if not filtered_active: st.info("Şu an havuzda aktif ilan bulunmuyor.")
        for inv, s in filtered_active[:8]:
            with st.container(border=True):
                k_isim = f"{inv.get('court')} ({inv.get('court_custom')})" if inv.get('court') == 'Diğer' else inv.get('court')
                c_user = users_db.get(inv.get('creator'), {})
                if not isinstance(c_user, dict): c_user = {}

                if s == "expired":
                    st.markdown(f"#### <span style='color:gray'>🗓️ {format_date_tr(inv.get('date'))} | ⏰ {inv.get('time_details')}</span>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='color:gray'>📍 {k_isim}</h3>", unsafe_allow_html=True)
                    st.error("⏳ Bu ilanın maç saati geçtiği için süresi dolmuştur.")
                else:
                    st.markdown(f"#### 🗓️ {format_date_tr(inv.get('date'))}  |  ⏰ {inv.get('time_details')}")
                    st.markdown(f"### 📍 {k_isim}")
                    st.info(f"**Kort Durumu:** {inv.get('court_status')}")
                    fee_str = inv.get('fee_status', 'Belirtilmedi')
                    if fee_str != 'Belirtilmedi':
                        if fee_str == "Ücretsiz Kort / Abonelik":
                            st.success("💰 **Ücret:** Ücretsiz Kort / Abonelik")
                        else:
                            amt_str = f" ({inv.get('fee_amount')})" if inv.get('fee_amount') else ""
                            st.warning(f"💰 **Ücret:** {fee_str}{amt_str}")
                    
                st.markdown(f"**⭐ Aranan Seviye:** {', '.join(inv.get('levels', []))} &nbsp; | &nbsp; **🎾 Tür:** {inv.get('type')}", unsafe_allow_html=True)
                if inv.get('note'): st.warning(f"📝 *Not: {inv.get('note')}*")
                
                render_popover_profile(inv.get('creator'), c_user, messages)

                if s == "expired":
                    st.button("Teklif Gönder", key=f"pub_exp_{inv.get('id')}", disabled=True, use_container_width=True)
                else:
                    if st.button("Teklif Gönder", key=f"pub_{inv.get('id')}", use_container_width=True):
                        st.session_state.show_toast = "Teklif göndermek için yukarıdan giriş yapmalısın! 🎾"
                        st.session_state.show_login_form = True; st.rerun()

    st.markdown("---")
    with st.expander("Yönetici Paneli"):
        admin_code = st.text_input("Yönetici Parolası", type="password")
        if st.button("Panele Gir", use_container_width=True):
            if admin_code == ADMIN_PASS:
                st.session_state.logged_in = True
                st.session_state.is_admin = True
                st.rerun()
            else:
                st.error("Hatalı Parola!")

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
            if cookie_manager and cookie_manager.get("remember_user"):
                cookie_manager.delete("remember_user")
                time.sleep(0.5)
            st.rerun()

    kontrol_sekme_adi = f"🎾 Tenis Ajandam 🚨 ({my_inbox_count})" if my_inbox_count > 0 else "🎾 Tenis Ajandam"
    tabs = st.tabs(["☀️ Güncel İlanlar", "➕ İlan Oluştur", "👥 Üyeler", kontrol_sekme_adi, "⚖️ Değerlendirme", "⚙️ Profil & Ayarlar", "📍 Kort Rehberi", "📊 Seviye Rehberi"])

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
        
        filtered_active_invites = []
        for inv in active_invites:
            s = get_invite_status(inv.get('date'), inv.get('time_details', ''))
            if s != "removed":
                filtered_active_invites.append((inv, s))
                
        active_only = [x for x in filtered_active_invites if x[1] == 'active']
        expired_only = [x for x in filtered_active_invites if x[1] == 'expired']
        
        if sort_by == "Tarihe Göre (En Yakın)":
            active_only.sort(key=lambda x: (x[0].get('date', '9999-12-31'), x[0].get('time_details', '23:59')))
            expired_only.sort(key=lambda x: (x[0].get('date', '9999-12-31'), x[0].get('time_details', '23:59')), reverse=True)
        else:
            active_only.sort(key=lambda x: x[0].get('created_at', '1900-01-01'), reverse=True)
            expired_only.sort(key=lambda x: x[0].get('created_at', '1900-01-01'), reverse=True)
            
        filtered_active_invites = active_only + expired_only
        
        # MADDE 8: SOSYAL KANIT
        matched_invs = [i for i in invites if i.get('status') == 'matched']
        if matched_invs:
            st.markdown("#### 🤝 Son Eşleşen Maçlar")
            for m_inv in sorted(matched_invs, key=lambda x: x.get('date', ''), reverse=True)[:3]:
                st.markdown(f"<div style='color:gray; font-size:0.9em; padding: 4px; border: 1px dashed #ccc; border-radius: 6px; margin-bottom: 5px;'>✅ {format_date_tr(m_inv.get('date'))} | {m_inv.get('court')} | Seviye: {', '.join(m_inv.get('levels', []))} <i>(Eşleşti)</i></div>", unsafe_allow_html=True)
            st.markdown("---")

        if not filtered_active_invites: st.info("Kriterlere uygun aktif ilan bulunamadı.")

        for inv, s in filtered_active_invites:
            with st.container(border=True):
                k_isim = f"{inv.get('court')} ({inv.get('court_custom')})" if inv.get('court') == 'Diğer' else inv.get('court')
                c_user = users_db.get(inv.get('creator'), {})
                if not isinstance(c_user, dict): c_user = {}

                if s == "expired":
                    st.markdown(f"#### <span style='color:gray'>🗓️ {format_date_tr(inv.get('date'))} | ⏰ {inv.get('time_details')}</span>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='color:gray'>📍 {k_isim}</h3>", unsafe_allow_html=True)
                    st.error("⏳ Bu ilanın maç saati geçtiği için süresi dolmuştur.")
                else:
                    st.markdown(f"#### 🗓️ {format_date_tr(inv.get('date'))}  |  ⏰ {inv.get('time_details')}")
                    st.markdown(f"### 📍 {k_isim}")
                    st.info(f"**Kort Durumu:** {inv.get('court_status')}")
                    fee_str = inv.get('fee_status', 'Belirtilmedi')
                    if fee_str != 'Belirtilmedi':
                        if fee_str == "Ücretsiz Kort / Abonelik":
                            st.success("💰 **Ücret:** Ücretsiz Kort / Abonelik")
                        else:
                            amt_str = f" ({inv.get('fee_amount')})" if inv.get('fee_amount') else ""
                            st.warning(f"💰 **Ücret:** {fee_str}{amt_str}")
                    
                st.markdown(f"**⭐ Aranan Seviye:** {', '.join(inv.get('levels', []))} &nbsp; | &nbsp; **🎾 Tür:** {inv.get('type')}", unsafe_allow_html=True)
                if inv.get('note'): st.warning(f"📝 *Not: {inv.get('note')}*")
                
                render_popover_profile(inv.get('creator'), c_user, messages)

                if inv.get('creator') != st.session_state.current_user:
                    if any(m.get('sender') == st.session_state.current_user and m.get('invite_id') == inv.get('id') and m.get('status') == 'pending' for m in messages):
                        st.button("✅ Teklif İletildi", key=f"inv_sent_{inv.get('id')}", disabled=True, use_container_width=True)
                    else:
                        if s == "expired":
                            st.button("Teklif Gönder", key=f"inv_exp_{inv.get('id')}", disabled=True, use_container_width=True)
                        else:
                            # MADDE 3: ÇİFT İSTEK (SPAM) ENGELİ
                            btn_key = f"inv_req_{inv.get('id')}"
                            if st.button("🎾 Teklif Gönder", key=btn_key, disabled=st.session_state.get(btn_key, False), use_container_width=True):
                                st.session_state[btn_key] = True
                                new_msg = {"id": str(uuid.uuid4()), "type": "invite_request", "invite_id": inv.get('id'), "sender": st.session_state.current_user, "receiver": inv.get('creator'), "status": "pending", "timestamp": str(datetime.datetime.now())}
                                if save_data(MESSAGES_FILE_PATH, messages + [new_msg], 'db_messages'):
                                    st.session_state.show_toast = "Teklifiniz iletildi! 🎉"
                                    st.rerun()
                                else: st.error("⚠️ Veri hatası: Teklifiniz kaydedilemedi.")

    # --- TAB 1: İLAN OLUŞTUR ---
    with tabs[1]:
        st.subheader("➕ Yeni İlan Yayınla")
        if me.get('frozen'): st.warning("⚠️ Hesabınız dondurulmuş. İlanınız vitrinde görünmez.")
            
        c1, c2 = st.columns(2)
        d = c1.date_input("Tarih", min_value=datetime.date.today(), key="inv_date", format="DD.MM.YYYY")
        c_t1, c_t2 = c1.columns(2)
        t_start = c_t1.time_input("Başlangıç Saati", datetime.time(18, 0), key="inv_start")
        t_end = c_t2.time_input("Bitiş Saati", datetime.time(19, 30), key="inv_end")
        
        court = c2.selectbox("Kort / Saha", IZMIR_KORTLARI, key="inv_court")
        court_custom = c2.text_input("Diğer ise Kort Adını Yazın:", key="inv_court_cust") if court == "Diğer" else ""
        court_status = c2.selectbox("Kort Rezervasyon Durumu", COURT_STATUS, key="inv_c_status")
        
        fee_status = st.selectbox("💰 Kort Ücret Durumu", FEE_STATUS_OPTIONS, key="inv_fee_stat")
        fee_amount = ""
        if fee_status != "Ücretsiz Kort / Abonelik":
            fee_amount = st.text_input("Kort Ücreti Tutarı (Örn: 500 TL, Saati 300 TL vb.)", key="inv_fee_amt")
        
        act_type = st.selectbox("Etkinlik Tipi", ACTIVITY_TYPES, key="inv_act_type")
        levels = st.multiselect("Aranan Seviyeler (NTRP)", NTRP_LEVELS, default=[me.get("level", "3.5")], key="inv_lvls")
        inv_note = st.text_area("İlan Notu / Açıklama (İsteğe bağlı)", key="inv_note")
        
        if st.button("📢 İlanı Yayınla", use_container_width=True):
            # MADDE 4: MÜKERRER İLAN ENGELİ
            zaten_var = any(
                i.get('creator') == st.session_state.current_user and 
                i.get('date') == str(d) and 
                i.get('court') == court and 
                i.get('time_details') == f"{t_start.strftime('%H:%M')} - {t_end.strftime('%H:%M')}" and 
                i.get('status') == 'active' 
                for i in invites
            )
            
            if zaten_var:
                st.error("⚠️ Hata: Bu kort ve tarih/saat için zaten açık bir ilanınız bulunuyor.")
            elif not levels: st.error("Lütfen en az bir aranan seviye seçin.")
            elif court == "Diğer" and not court_custom.strip(): st.error("Lütfen Kort Adı alanını doldurun.")
            elif t_start >= t_end: st.error("Bitiş saati başlangıç saatinden sonra olmalıdır.")
            else:
                new_inv = {"id": str(uuid.uuid4()), "creator": st.session_state.current_user, "date": str(d), "time_details": f"{t_start.strftime('%H:%M')} - {t_end.strftime('%H:%M')}", "court": court, "court_custom": court_custom, "court_status": court_status, "fee_status": fee_status, "fee_amount": fee_amount.strip(), "type": act_type, "levels": levels, "status": "active", "note": inv_note, "created_at": str(datetime.datetime.now())}
                if save_data(INVITES_FILE_PATH, invites + [new_inv], 'db_invites'):
                    for u_email, u_data in users_db.items():
                        if u_email == st.session_state.current_user or not isinstance(u_data, dict) or u_data.get('frozen') or u_data.get('suspended'): continue
                        r = u_data.get("radar", {})
                        if r.get("active", False) and (not r.get("courts") or court in r.get("courts") or (court == "Diğer" and "Diğer" in r.get("courts"))) and (not r.get("levels") or any(l in r.get("levels") for l in levels)) and (not r.get("types") or act_type in r.get("types") or "Fark Etmez" in r.get("types")):
                            send_email(u_email, "📡 Radar Alarmı: Uygun İlan Yayınlandı!", f"Merhaba <b>{u_data.get('ad_soyad')}</b>,<br><br>Radar kriterlerinize uygun tenis ilanı yayınlandı!<br><br>Kort: {court}<br>Sisteme giriş yaparak teklif gönderebilirsiniz.")
                    st.session_state.show_toast = "İlanınız başarıyla yayınlandı! 🎉"
                    st.rerun()
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
            
            o_date = st.date_input("Tarih Önerisi", min_value=datetime.date.today(), key="do_date", format="DD.MM.YYYY")
            c_o1, c_o2 = st.columns(2)
            o_t1 = c_o1.time_input("Başlangıç", datetime.time(18, 0), key="do_t1")
            o_t2 = c_o2.time_input("Bitiş", datetime.time(19, 30), key="do_t2")
            o_court = st.selectbox("Kort Önerisi", IZMIR_KORTLARI, key="do_court")
            o_custom = st.text_input("Diğer ise belirtin:", key="do_cust") if o_court == "Diğer" else ""
            
            o_fee_status = st.selectbox("💰 Kort Ücret Durumu", FEE_STATUS_OPTIONS, key="do_fee_stat")
            o_fee_amount = st.text_input("Kort Ücreti Tutarı", key="do_fee_amt") if o_fee_status != "Ücretsiz Kort / Abonelik" else ""
            
            c_sub, c_can = st.columns(2)
            if c_sub.button("🚀 Teklifi Gönder", use_container_width=True):
                new_msg = {"id": str(uuid.uuid4()), "type": "direct_challenge", "sender": st.session_state.current_user, "receiver": st.session_state.offer_to, "date": str(o_date), "time": f"{o_t1.strftime('%H:%M')} - {o_t2.strftime('%H:%M')}", "court": o_court, "court_custom": o_custom, "fee_status": o_fee_status, "fee_amount": o_fee_amount.strip(), "status": "pending"}
                if save_data(MESSAGES_FILE_PATH, messages + [new_msg], 'db_messages'):
                    st.session_state.offer_to = None; st.session_state.show_toast = "Teklif iletildi!"
                    st.rerun()
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
        m_tab1, m_tab2, m_tab3, m_tab4, m_tab5 = st.tabs([inbox_label, "📤 Gönderdiğim Teklifler", "📢 Yayındaki İlanlarım", "📅 Onaylanmış Maçlarım", "📜 Geçmiş & İptal Edilenler"])

        with m_tab1:
            my_inbox = [m for m in messages if m.get('receiver') == st.session_state.current_user and m.get('status') == 'pending']
            if not my_inbox: st.info("Bekleyen gelen bir teklifiniz bulunmuyor.")
            for msg in my_inbox:
                with st.container(border=True):
                    s_user = users_db.get(msg['sender'], {})
                    if msg.get('type') == 'invite_request':
                        inv_data = next((i for i in invites if i.get('id') == msg.get('invite_id')), {})
                        st.write(f"🔔 **{s_user.get('ad_soyad', 'Anonim')}** (NTRP: {s_user.get('level', '3.5')}) sizin **{format_date_tr(inv_data.get('date'))}** tarihli **{inv_data.get('court')}** ilanınıza katılmak istiyor!")
                    else:
                        fee_info = ""
                        if msg.get('fee_status') and msg.get('fee_status') != 'Belirtilmedi':
                            if msg.get('fee_status') == "Ücretsiz Kort / Abonelik": fee_info = " | 💰 Ücretsiz Kort"
                            else: fee_info = f" | 💰 {msg.get('fee_status')} ({msg.get('fee_amount', '')})"
                        st.write(f"🔔 **{s_user.get('ad_soyad', 'Anonim')}** size özel maç teklif etti! Tarih: **{format_date_tr(msg.get('date'))}** | Kort: **{msg.get('court')}**{fee_info}")

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
                            st.session_state.show_toast = "Teklif kabul edildi! 🎉"
                            st.rerun()
                        else: st.error("⚠️ Veritabanı çakışması: Onayınız kaydedilemedi.")

                    if not st.session_state.get(f"conf_rej_{msg['id']}", False):
                        if c_rej.button("❌ Reddet / Gizle", key=f"btn_rej_{msg['id']}"): st.session_state[f"conf_rej_{msg['id']}"] = True; st.rerun()
                    else:
                        c_rej.warning("Reddedilsin mi?")
                        if c_rej.button("Evet, Reddet", key=f"yes_rej_{msg['id']}"):
                            msg['status'] = 'rejected'
                            if save_data(MESSAGES_FILE_PATH, messages, 'db_messages'):
                                st.session_state[f"conf_rej_{msg['id']}"] = False; st.session_state.show_toast = "Teklif reddedildi."
                                st.rerun()
                        if c_rej.button("Vazgeç", key=f"no_rej_{msg['id']}"): st.session_state[f"conf_rej_{msg['id']}"] = False; st.rerun()

        with m_tab2:
            my_sent = [m for m in messages if m.get('sender') == st.session_state.current_user]
            if not my_sent: st.info("Henüz kimseye teklif göndermediniz.")
            for msg in reversed(my_sent):
                with st.container(border=True):
                    r_user = users_db.get(msg.get('receiver'), {})
                    st_map = {"pending": "⏳ Onay Bekliyor", "accepted": "✅ Kabul Edildi", "rejected": "❌ Reddedildi", "cancelled": "🚫 İptal Edildi", "cancelled_late": "🚫 İptal Edildi"}
                    st.write(f"📤 Alıcı: **{r_user.get('ad_soyad', 'Bilinmeyen')}** | Durum: **{st_map.get(msg.get('status'), 'Bilinmiyor')}**")
                    
                    if msg.get('status') == 'pending':
                        if not st.session_state.get(f"conf_with_{msg['id']}", False):
                            if st.button("🗑️ Teklifi Geri Çek", key=f"btn_with_{msg['id']}"): st.session_state[f"conf_with_{msg['id']}"] = True; st.rerun()
                        else:
                            st.warning("Bu teklifi geri çekmek istediğinize emin misiniz?")
                            cw1, cw2 = st.columns(2)
                            if cw1.button("Evet, Geri Çek", key=f"yes_with_{msg['id']}"):
                                if save_data(MESSAGES_FILE_PATH, [m for m in messages if m['id'] != msg['id']], 'db_messages'):
                                    st.session_state[f"conf_with_{msg['id']}"] = False; st.session_state.show_toast = "Teklif geri çekildi."
                                    st.rerun()
                            if cw2.button("Vazgeç", key=f"no_with_{msg['id']}"): st.session_state[f"conf_with_{msg['id']}"] = False; st.rerun()

        with m_tab3:
            my_active_invs = [i for i in invites if i.get('creator') == st.session_state.current_user and i.get('status') == 'active']
            if not my_active_invs: 
                st.info("Şu an yayında olan aktif bir ilanınız bulunmuyor.")
            
            for my_inv in my_active_invs:
                with st.container(border=True):
                    s = get_invite_status(my_inv.get('date'), my_inv.get('time_details', ''))
                    if s in ["expired", "removed"]: st.error("⏳ Bu ilanın süresi dolmuştur.")
                        
                    st.write(f"📍 **{my_inv.get('court')}** | 🗓️ {format_date_tr(my_inv.get('date'))} | ⏰ {my_inv.get('time_details')}")
                    
                    col_i1, col_i2 = st.columns(2)
                    if col_i1.button("✏️ Düzenle", key=f"edit_myinv_{my_inv.get('id')}"):
                        st.session_state.edit_my_active = my_inv.get('id')
                        st.rerun()
                        
                    # MADDE 9: SİLME ONAY DİYALOĞU
                    if col_i2.button("🗑️ İlanı Kaldır", key=f"del_myinv_{my_inv.get('id')}"):
                        dialog_delete_invite(my_inv.get('id'))
                            
            if st.session_state.get('edit_my_active') and any(i.get('id') == st.session_state.edit_my_active for i in my_active_invs):
                e_inv = next(i for i in invites if i.get('id') == st.session_state.edit_my_active)
                st.markdown("---")
                st.subheader("✏️ İlanı Güncelle")
                with st.form("edit_my_active_form"):
                    ed_d = st.date_input("Yeni Tarih", value=datetime.datetime.strptime(e_inv.get('date'), "%Y-%m-%d").date(), format="DD.MM.YYYY")
                    ed_court = st.selectbox("Yeni Kort", IZMIR_KORTLARI, index=IZMIR_KORTLARI.index(e_inv.get('court')) if e_inv.get('court') in IZMIR_KORTLARI else 0)
                    ed_fee_status = st.selectbox("💰 Kort Ücret Durumu", FEE_STATUS_OPTIONS, index=FEE_STATUS_OPTIONS.index(e_inv.get('fee_status')) if e_inv.get('fee_status') in FEE_STATUS_OPTIONS else 0)
                    ed_fee_amount = st.text_input("Kort Ücreti Tutarı", value=e_inv.get('fee_amount', '')) if ed_fee_status != "Ücretsiz Kort / Abonelik" else ""
                    ed_note = st.text_area("İlan Notu", value=e_inv.get('note', ''))
                    
                    c_btn1, c_btn2 = st.columns(2)
                    if c_btn1.form_submit_button("Güncelle ve Kaydet"):
                        e_inv.update({'date': str(ed_d), 'court': ed_court, 'fee_status': ed_fee_status, 'fee_amount': ed_fee_amount.strip(), 'note': ed_note})
                        if save_data(INVITES_FILE_PATH, invites, 'db_invites'):
                            st.session_state.edit_my_active = None
                            st.session_state.show_toast = "İlanınız güncellendi!"
                            st.rerun()
                    if c_btn2.form_submit_button("Vazgeç"):
                        st.session_state.edit_my_active = None
                        st.rerun()

        with m_tab4:
            my_acc = [m for m in messages if (m.get('receiver') == st.session_state.current_user or m.get('sender') == st.session_state.current_user) and m.get('status') == 'accepted' and st.session_state.current_user not in m.get('hidden_by', [])]
            if not my_acc: st.info("Yaklaşan veya görüntülenen onaylanmış bir maçınız yok.")
            for acc in reversed(my_acc):
                with st.container(border=True):
                    partner_e = acc['sender'] if acc['receiver'] == st.session_state.current_user else acc['receiver']
                    partner_u = users_db.get(partner_e, {})
                    
                    if acc.get('type') == 'invite_request':
                        inv_data = next((i for i in invites if i.get('id') == acc.get('invite_id')), {})
                        m_date = inv_data.get('date', '-')
                        m_time = inv_data.get('time_details', '-')
                        m_court = inv_data.get('court', '-')
                    else:
                        m_date = acc.get('date', '-')
                        m_time = acc.get('time', '-')
                        m_court = acc.get('court', '-')

                    st.markdown(f"🤝 **Partner:** {partner_u.get('ad_soyad', 'Partner')} *(NTRP {partner_u.get('level', '3.5')})*")
                    st.markdown(f"🗓️ **Tarih & Saat:** {format_date_tr(m_date)} | {m_time} | 📍 **Kort:** {m_court}")
                    
                    if partner_u.get('contact_visibility', 'eslesince') in ['eslesince', 'herkes']:
                        st.success(f"📞 İletişim: {partner_u.get('phone', 'Belirtilmedi')} | ✉️ {partner_e}")

                    with st.expander(f"💬 {partner_u.get('ad_soyad', 'Partner')} ile Mesajlaş"):
                        for chat in acc.get("chat_history", []):
                            with st.chat_message("user" if chat["sender"] == st.session_state.current_user else "assistant"):
                                st.write(chat["text"]); st.caption(chat["timestamp"])
                        
                        if new_msg := st.chat_input("Mesajınızı yazın...", key=f"chat_input_{acc['id']}"):
                            acc.setdefault("chat_history", []).append({"sender": st.session_state.current_user, "text": new_msg, "timestamp": datetime.datetime.now().strftime("%d-%m %H:%M")})
                            if save_data(MESSAGES_FILE_PATH, messages, 'db_messages'):
                                send_email(partner_e, f"💬 Yeni Mesaj: {m_date} Maçı", f"Partneriniz <b>{me.get('ad_soyad')}</b> mesaj gönderdi:<br>\"{new_msg}\"")
                                st.rerun()

                    c_opt1, c_opt2 = st.columns(2)
                    # MADDE 9: İPTAL ONAY DİYALOĞU
                    if c_opt1.button("🗑️ Maçı İptal Et", key=f"btn_del_acc_{acc['id']}"): 
                        dialog_cancel_match(acc['id'], republish=False)

                    # MADDE 5: YETKİ KONTROLÜ (Sadece İlan Sahibi veya Özel Maç Göndereni Yeniden Yayınlayabilir)
                    can_republish = False
                    if acc.get('type') == 'invite_request':
                        target_inv = next((i for i in invites if i.get('id') == acc.get('invite_id')), None)
                        if target_inv and target_inv.get('creator') == st.session_state.current_user:
                            can_republish = True
                    elif acc.get('sender') == st.session_state.current_user:
                        can_republish = True

                    if can_republish and acc.get('type') == 'invite_request':
                        if c_opt2.button("✏️ İptal Et & Yeniden Yayınla", key=f"btn_edit_acc_{acc['id']}"): 
                            dialog_cancel_match(acc['id'], republish=True)

                    acc_stat = get_invite_status(m_date, m_time)
                    if acc_stat in ["expired", "removed"]:
                        st.markdown("---")
                        if st.button("🗑️ Geçmiş Maçı Listemden Gizle", key=f"hide_past_acc_{acc['id']}", use_container_width=True):
                            acc.setdefault('hidden_by', []).append(st.session_state.current_user)
                            save_data(MESSAGES_FILE_PATH, messages, 'db_messages')
                            st.rerun()

        with m_tab5:
            past_m = [m for m in messages if (m.get('receiver') == st.session_state.current_user or m.get('sender') == st.session_state.current_user) and m.get('status') in ['cancelled', 'cancelled_late', 'rejected'] and st.session_state.current_user not in m.get('hidden_by', [])]
            if not past_m: st.info("Geçmiş iptal veya red kaydı bulunmuyor.")
            for pm in past_m: 
                col_txt, col_btn = st.columns([4,1])
                durum_goster = "Son Dakika İptali" if pm['status'] == 'cancelled_late' else pm['status']
                col_txt.write(f"⚪ Kayıt | ID: {pm['id'][:8]} | Durum: **{durum_goster}**")
                if col_btn.button("🗑️ Listemden Gizle", key=f"hide_{pm['id']}"):
                    pm.setdefault('hidden_by', []).append(st.session_state.current_user)
                    save_data(MESSAGES_FILE_PATH, messages, 'db_messages')
                    st.rerun()

    # --- TAB 5: DEĞERLENDİRME ---
    with tabs[4]:
        st.subheader("⚖️ Maç Sonrası Değerlendirme")
        
        now_dt = datetime.datetime.now()
        valid_unrated = []
        late_cancels = []

        # MADDE 6 ve MADDE 7: Zaman Analizi
        for m in messages:
            if m.get('receiver') == st.session_state.current_user or m.get('sender') == st.session_state.current_user:
                if st.session_state.current_user not in m.get('rated_by', []):
                    try:
                        if m.get('type') == 'invite_request':
                            target_inv = next((i for i in invites if i.get('id') == m.get('invite_id')), {})
                            m_dt = datetime.datetime.strptime(f"{target_inv.get('date')} {target_inv.get('time_details', '18:00').split('-')[0].strip()}", "%Y-%m-%d %H:%M")
                        else:
                            m_dt = datetime.datetime.strptime(f"{m.get('date')} {m.get('time', '18:00').split('-')[0].strip()}", "%Y-%m-%d %H:%M")
                    except:
                        m_dt = now_dt 
                    
                    if m.get('status') == 'accepted' and now_dt > m_dt:
                        valid_unrated.append(m)
                    elif m.get('status') == 'cancelled_late' and m.get('cancelled_by') != st.session_state.current_user:
                        late_cancels.append(m)

        # MADDE 7: Son Dakika İptali Değerlendirme Formu
        if late_cancels:
            st.error("🚨 Son Dakika İptalleri (Cezai Değerlendirme Bekleyen)")
            for lc in late_cancels:
                with st.form(f"late_rating_{lc['id']}"):
                    p_email = lc['cancelled_by']
                    p_name = users_db.get(p_email, {}).get('ad_soyad', 'Partner')
                    st.write(f"**{p_name}** bu maçı başlama saatine 3 saatten az kala iptal etti.")
                    sr = st.slider("Güvenilirlik Puanı (1: Çok Mağdur Oldum - 5: Benim İçin Sorun Olmadı)", 1, 5, 1)
                    if st.form_submit_button("Cezai Puanı Gönder"):
                        users_db[p_email].setdefault("ratings", {"zaman": [], "seviye": [], "davranis": []})["davranis"].append(sr)
                        lc.setdefault('rated_by', []).append(st.session_state.current_user)
                        if save_data(USERS_FILE_PATH, users_db, 'db_users') and save_data(MESSAGES_FILE_PATH, messages, 'db_messages'):
                            st.session_state.show_toast = "Değerlendirmeniz sisteme işlendi."
                            st.rerun()

        # MADDE 6: Normal Değerlendirme Formu
        if not valid_unrated and not late_cancels: 
            st.info("Değerlendirebileceğiniz tamamlanmış maç bulunmuyor. (Maç saati geçene kadar değerlendirme yapılamaz).")
        elif valid_unrated:
            st.markdown("---")
            with st.form("rating_form"):
                evt_opts = {m['id']: f"Rakip: {users_db.get(m['sender'] if m['receiver'] == st.session_state.current_user else m['receiver'], {}).get('ad_soyad', 'Bilinmeyen')}" for m in valid_unrated}
                selected_event_id = st.selectbox("Değerlendirilecek Tamamlanmış Maç", options=list(evt_opts.keys()), format_func=lambda x: evt_opts[x])
                st.markdown("**(1: Zayıf - 5: Mükemmel)**")
                sz = st.slider("Zaman Planlamasına Uyum", 1, 5, 5); ss = st.slider("Seviye Tutarlılığı", 1, 5, 5); sd = st.slider("Sportmenlik & İletişim", 1, 5, 5)
                
                if st.form_submit_button("⭐ Puanı Gönder"):
                    target_event = next(m for m in valid_unrated if m['id'] == selected_event_id)
                    p_email = target_event['sender'] if target_event['receiver'] == st.session_state.current_user else target_event['receiver']
                    
                    if p_email in users_db and isinstance(users_db[p_email], dict):
                        users_db[p_email].setdefault("ratings", {"zaman": [], "seviye": [], "davranis": []})["zaman"].append(sz)
                        users_db[p_email]["ratings"]["seviye"].append(ss); users_db[p_email]["ratings"]["davranis"].append(sd)
                        target_event.setdefault('rated_by', []).append(st.session_state.current_user)
                        
                        if save_data(USERS_FILE_PATH, users_db, 'db_users') and save_data(MESSAGES_FILE_PATH, messages, 'db_messages'):
                            st.session_state.show_toast = "Değerlendirmeniz kaydedildi! ⭐"
                            st.rerun()
                        else: st.error("⚠️ Değerlendirme kaydedilemedi.")

    # --- TAB 6: PROFİL & AYARLAR ---
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
                if save_data(USERS_FILE_PATH, users_db, 'db_users'): st.session_state.show_toast = "Profil güncellendi! ✅"; st.rerun()

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
                            
            st.markdown("---")
            st.subheader("⏸️ Hesap Durumu (Dondurma)")
            with st.form("freeze_form"):
                is_frozen = st.toggle("Bir süre tenis oynayamayacağım, hesabımı dondur", value=me.get("frozen", False))
                if st.form_submit_button("Durumu Güncelle"):
                    me["frozen"] = is_frozen; users_db[st.session_state.current_user] = me
                    if save_data(USERS_FILE_PATH, users_db, 'db_users'): st.session_state.show_toast = "Hesap durumu güncellendi!"; st.rerun()

            st.markdown("---")
            st.subheader("🚨 Tehlikeli Bölge")
            with st.expander("Hesabımı Kalıcı Olarak Silme Talebi Gönder"):
                st.warning("⚠️ **DİKKAT:** Hesabınız ve tüm verileriniz kalıcı olarak silinir.")
                if me.get("delete_requested"): st.info("ℹ️ Silme talebiniz onay bekliyor.")
                elif st.button("🗑️ Silme Talebini İlet"):
                    me["delete_requested"] = True; users_db[st.session_state.current_user] = me
                    if save_data(USERS_FILE_PATH, users_db, 'db_users'):
                        send_email(ADMIN_EMAIL, "🚨 Silme Talebi", f"<b>{me.get('ad_soyad')}</b> ({st.session_state.current_user}) hesabını kalıcı olarak silmek istiyor. Yönetici panelinden işlemi onaylayabilirsiniz.")
                        st.session_state.show_toast = "Talebiniz iletildi."; st.rerun()

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
                    if save_data(USERS_FILE_PATH, users_db, 'db_users'): st.session_state.show_toast = "Gizlilik tercihleri kaydedildi! ✅"; st.rerun()

            st.markdown("---")
            st.subheader("📡 Radar Ayarları")
            st.caption("Aşağıdaki kriterlerinize uyan yeni bir ilan havuza eklendiğinde, sistem size otomatik olarak haberci e-posta gönderir.")
            radar_data = me.get("radar", {"active": False, "courts": [], "levels": [], "types": []})
            with st.form("radar_form"):
                r_active = st.toggle("📡 Radarı Aktif Et", value=radar_data.get("active", False))
                r_courts = st.multiselect("Kortlar (Boş bırakılırsa tümü)", IZMIR_KORTLARI, default=radar_data.get("courts", []))
                r_levels = st.multiselect("NTRP Seviyeleri (Boş bırakılırsa tümü)", NTRP_LEVELS, default=radar_data.get("levels", []))
                r_types = st.multiselect("Etkinlik Tipleri", ACTIVITY_TYPES, default=radar_data.get("types", []))
                if st.form_submit_button("📡 Radar Tercihlerini Kaydet"):
                    me["radar"] = {"active": r_active, "courts": r_courts, "levels": r_levels, "types": r_types}
                    users_db[st.session_state.current_user] = me
                    if save_data(USERS_FILE_PATH, users_db, 'db_users'): st.session_state.show_toast = "Radar ayarlarınız kaydedildi! 📡"; st.rerun()

    # --- TAB 7: KORT REHBERİ ---
    with tabs[6]:
        st.subheader("📍 İzmir Kort ve Tesis Rehberi")
        st.markdown("İzmir'deki popüler tenis kortlarının ve kulüplerinin güncel iletişim, adres ve rezervasyon bilgilerine buradan ulaşabilirsiniz.")
        
        c_rehber1, c_rehber2 = st.columns(2)
        
        with c_rehber1:
            st.markdown("### 🏛️ Belediye Kortları")
            
            with st.expander("Bostanlı Suat Taşer / Rekreasyon Kortları", expanded=True):
                st.markdown("**📍 Adres:** Mavişehir / Bostanlı Sahil Şeridi, Karşıyaka")
                st.markdown("**📞 Telefon:** 0(232) 362 48 28 - 0(232) 294 21 72")
                st.markdown("**🌐 Rezervasyon:** online.izmir.bel.tr")
                st.caption("Not: İzmir Büyükşehir Belediyesi'ne bağlıdır.")

            with st.expander("İnciraltı Spor Tesisleri (İzmir BŞB)"):
                st.markdown("**📍 Adres:** İnciraltı Açıkhava Tiyatrosu Altı, Balçova")
                st.markdown("**📞 Telefon:** 0(232) 294 22 98 - 0(232) 425 04 21")
                
            with st.expander("Fuar Alanı (Celal Atik) Kortları"):
                st.markdown("**📍 Adres:** Kültürpark İçi (Fuar Alanı), Konak")
                st.markdown("**📞 Telefon:** 0(232) 425 04 21")

            with st.expander("Aşık Veysel Rekreasyon Alanı Kortları"):
                st.markdown("**📍 Adres:** Kızılay Mah., Aşık Veysel Rekreasyon Alanı İçi, Bornova")
                st.caption("Not: Halka açık kortlardır. Çoğunlukla rezervasyon sistemi yoktur (gel-sıra bekle-oyna mantığıyla çalışır).")

            with st.expander("Hasanağa Bahçesi Kortları"):
                st.markdown("**📍 Adres:** Adatepe Mah., Hasanağa Bahçesi İçi, Buca")
                st.caption("Not: Buca Belediyesi'ne bağlı halka açık kortlardır. Genellikle doğrudan gidilip müsaitlik durumuna göre kullanılır.")
                
            with st.expander("Buca Tenis Kulübü (Buca Belediyesi)"):
                st.markdown("**📍 Adres:** Şirinkapı Mah. Yavuz Sultan Selim Cad. No:78/1, Buca")
                st.markdown("**📞 Telefon:** 0(232) 442 61 61")
                st.markdown("**🌐 Web:** bucatenis.com")

            with st.expander("Gaziemir Belediyesi / Gaziemir Tenis Kulübü"):
                st.markdown("**📍 Adres:** Gazikent Mah. Gazi Atatürk Bulvarı No:14, Gaziemir")
                st.markdown("**📞 Telefon:** 0(232) 274 42 97 - 0(232) 252 48 27")
                
        with c_rehber2:
            st.markdown("### 🏆 Özel Tenis Kulüpleri")
            
            with st.expander("Kültürpark Tenis Kulübü (KTK)", expanded=True):
                st.markdown("**📍 Adres:** Mimar Sinan Mah. Fuar İçi No:103, Alsancak / Konak")
                st.markdown("**📞 Telefon:** 0(232) 483 33 52 - 0(530) 370 30 25")
                st.markdown("**🌐 Web:** kptk.org")
                st.caption("Not: Tesis içerisindeki korta giriş kuralları kulüp üyeliği veya misafir oyuncu statüsüne göre değişiklik gösterebilir.")

            with st.expander("Küçük Kulüp Alliance"):
                st.markdown("**📍 Adres:** Kültür Mah. 1383 Sokak No:18, Alsancak / Konak")
                st.markdown("**📞 Telefon:** 0(232) 463 87 47 - 0(232) 421 39 70")
                st.markdown("**🌐 Web:** kucukkulup.org")

            with st.expander("Göztepe Tenis Kulübü"):
                st.markdown("**📍 Adres:** İnciraltı Mah. Mustafa Kemal Sahil Blv. Balçova (Göztepe Spor Tesisleri)")
                st.caption("Not: Özel rezervasyon ve turnuva günleri için kulüp sekreterliği ile görüşülmesi tavsiye edilir.")
                
            with st.expander("Ege Üniversitesi Tenis Kortları"):
                st.markdown("**📍 Adres:** Ege Üniversitesi Kampüsü İçi, Bornova")
                st.markdown("**📞 Rezervasyon SKSDB:** 0(232) 311 10 10 (Santral)")
                st.caption("Not: SKS (Sağlık Kültür ve Spor Daire Başkanlığı) üzerinden öğrenci/mezun/sivil statüsüne göre saatlik kiralanabilir.")

    # --- TAB 8: NTRP SEVİYE REHBERİ ---
    with tabs[7]:
        st.subheader("📊 NTRP Seviye Rehberi")
        st.markdown("Kortlarda tartışma çıkmaması, maçların zevkli geçmesi ve kimsenin kortta can çekişmemesi için kendi seviyenizi seçerken dürüst olmanız çok önemlidir. Hakem gözüyle hazırlanmış bu ufak rehber, kendinizi bulmanıza yardımcı olacaktır:")
        
        st.info("**1.0 - 1.5 (Korta İlk Adım)**\n\nRaketi tavadan yeni ayırt etmeye başladığınız dönem. Topu korta düşürmek sizin için şampiyonluk sevinci yaratır. *\"Tenis kıyafetlerim çok güzel ama topla henüz tam anlaştığımız söylenemez.\"*")
        st.info("**2.0 - 2.5 (Hayatta Kalma Mücadelesi)**\n\nTopa vurabiliyorsunuz ama nereye gideceğine çoğunlukla top kendi karar veriyor. Ralli yapmak bir rüya, maç yapmak ise cesaret işidir. Çift hatalar kortun tuzu biberidir. *\"Vuruyorum ama bazen tellere, bazen fileye... Yine de çok eğleniyorum!\"*")
        st.info("**3.0 (İstikrar Arayışı / Geçiş Dönemi)**\n\nArtık fena ralli yapmıyorsunuz ama 4. veya 5. vuruşta top illa ki bir yere uçuyor. Gelen topun hızına ve yönüne göre pozisyon almakta bazen zorlanıyorsunuz. *\"Forehand'im efsane de backhand'ime top gelince içimden ufak bir dua ediyorum.\"*")
        st.success("**3.5 (Klasik Hafta Sonu Savaşçısı)**\n\nİzmir kortlarının en kalabalık grubu! Temel taktikleri biliyor, kortu kullanıyor ve güzel terliyorsunuz. Harika bir *winner* vuruşunun hemen ardından, en basit topu dışarı atabilme yeteneğine de sahipsiniz. *\"Ben aslında çok daha iyi oynuyorum ama bugün raket/rüzgar/güneş bana karşıydı.\"*")
        st.success("**4.0 (Taktiksel Uyanış)**\n\nArtık oyunun sadece topa sert vurmak olmadığını çözdünüz. Güvenilir bir ilk servisiniz var, rakibin zayıf yönünü analiz edip oraya oynayabiliyorsunuz. Kendi hatalarınızdan kaybettiğiniz puanlar epey azaldı. *\"Tenis bacaklarla ve beyinle oynanır, kollar sadece teferruattır.\"*")
        st.success("**4.5 (Kortların Ustası)**\n\nGüçlü silahlarınız var (spin, slice, nokta atışı servisler). Baskı altındayken bile zor durumlardan kurtulabiliyor ve kendi oyun planınızı rakibe dikte edebiliyorsunuz. İzlemesi son derece keyifli bir oyuncusunuz. *\"O topu oradan nasıl çıkardığıma ben bile şaşırmıyorum artık.\"*")
        st.warning("**5.0 - 5.5 (Turnuva Avcısı)**\n\nTurnuvaların gediklisi, kupa koleksiyonerleri. Vuruşlarınızda hem ciddi bir güç hem de kusursuz bir istikrar var. Eğer bu seviyedeki biriyle eşleştiyseniz, kortta muhtemelen nefes nefese kalacaksınız ve topu sadece yanınızdan geçerken göreceksiniz. *\"Isınırken terlemem bile, maçta görüşürüz.\"*")
        st.warning("**6.0 (Ulusal Gururumuz)**\n\nBölgesel ve ulusal düzeyde turnuva oynayan, dereceleri olan oyuncular. Bu seviyeyle maç yapmak, bir amatör için tenis dersi almak gibidir. *\"Raket benim elimde bir uzvum gibi, topun nerede sekmesi gerektiğine sadece ben karar veririm.\"*")
        st.error("**6.5 - 7.0 (Televizyonda İzlediklerimiz)**\n\nUluslararası arenada oynayan profesyoneller, Grand Slam oyuncuları ve dünya sıralamasındakiler. *\"Eğer gerçekten bu seviyedeyseniz, sistemimizde partner aramak yerine Wimbledon'a hazırlanmalısınız! Buralarda işiniz ne?\"*")

# --- UYGULAMA GİRİŞ NOKTASI ---
if not st.session_state.logged_in: login_page()
elif st.session_state.is_admin: admin_dashboard()
else: main_app()
