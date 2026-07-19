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

# --- SABİT VERİLER VE ZAMAN AYARI ---
NTRP_LEVELS = ["1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0", "5.5", "6.0", "6.5", "7.0"]
IZMIR_KORTLARI = [
    "Kültürpark Tenis Kulübü (KTK)", "İnciraltı Büyükşehir Kortları", "Bostanlı Suat Taşer Kortları",
    "Fuar Alanı (Celal Atik) Kortları", "Buca Tenis Kulübü", "Ege Üniversitesi Tenis Kortları",
    "Gaziemir Belediyesi Kortları", "Göztepe Tenis Kulübü", "Küçük Kulüp Alliance", "Mavişehir Şemikler Kortları", "Diğer"
]
TURKEY_TZ = datetime.timezone(datetime.timedelta(hours=3))

# --- BAĞLANTI VE ŞİFRELEME AYARLARI ---
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
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# --- E-POSTA FONKSİYONU ---
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
    except Exception as e:
        pass # Arka planda kullanıcıyı rahatsız etmemek için hatayı yutuyoruz

# --- VERİTABANI İŞLEMLERİ ---
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

# --- TEMBEL KONTROL (SÜRESİ DOLANLARI TEMİZLEME) ---
def check_expired_invites(invites):
    updated = False
    now = datetime.datetime.now(TURKEY_TZ)
    for inv in invites:
        if inv.get('status', 'active') == 'active':
            d_str = inv.get('date')
            t_str = inv.get('time', '00:00')
            if d_str:
                try:
                    dt = datetime.datetime.strptime(f"{d_str} {t_str}", "%Y-%m-%d %H:%M")
                    dt = dt.replace(tzinfo=TURKEY_TZ)
                    if now > dt:
                        inv['status'] = 'expired'
                        updated = True
                        creator = inv.get('creator')
                        if creator:
                            send_email(creator, "İlan Süresi Doldu", f"{d_str} tarihli tenis davetinizin tarihi geçtiği için pasife alınmıştır.")
                except:
                    pass
    return updated

# --- OTURUM YÖNETİMİ ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = ""

def login_page():
    st.markdown("<h1 style='text-align: center; color: #2E7D32;'>🎾 İzmir Tenis Partner Havuzu</h1>", unsafe_allow_html=True)
    users_db = load_data(USERS_FILE_PATH, default_type=dict)
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        t1, t2, t3 = st.tabs(["🔑 Giriş", "📝 Kayıt", "❓ Şifremi Unuttum"])
        with t1:
            with st.form("login_form"):
                email = st.text_input("E-posta Adresi").strip().lower()
                password = st.text_input("Şifre", type="password")
                if st.form_submit_button("Giriş Yap", type="primary", use_container_width=True):
                    if email in users_db and users_db[email].get("password_hash") == hash_password(password):
                        st.session_state.logged_in = True
                        st.session_state.current_user = email
                        st.rerun()
                    else: st.error("Hatalı e-posta veya şifre.")
        with t2:
            with st.form("register_form"):
                reg_email = st.text_input("Yeni E-posta").strip().lower()
                reg_pass1 = st.text_input("Şifre", type="password")
                reg_pass2 = st.text_input("Şifre Tekrar", type="password")
                if st.form_submit_button("Kayıt Ol", type="primary", use_container_width=True):
                    if reg_email in users_db: st.error("Bu e-posta zaten kayıtlı!")
                    elif reg_pass1 != reg_pass2: st.error("Şifreler uyuşmuyor!")
                    else:
                        users_db[reg_email] = {"password_hash": hash_password(reg_pass1), "ad_soyad": reg_email.split('@')[0], "seviye": "4.0", "ratings": [], "notif_prefs": {}}
                        save_data(USERS_FILE_PATH, users_db)
                        st.success("Kayıt başarılı! Giriş yapabilirsiniz.")
        with t3:
            with st.form("forgot_password_form"):
                forgot_email = st.text_input("E-posta Adresiniz").strip().lower()
                if st.form_submit_button("Şifre Talep Et"):
                    if forgot_email in users_db:
                        temp_pass = generate_temp_password()
                        users_db[forgot_email]['password_hash'] = hash_password(temp_pass)
                        save_data(USERS_FILE_PATH, users_db)
                        send_email(forgot_email, "Geçici Şifreniz", f"Yeni geçici şifreniz: {temp_pass}")
                        st.success("Yeni şifre mailinize gönderildi.")

def get_avg_rating(prof):
    ratings = prof.get("ratings", [])
    return sum(ratings) / len(ratings) if ratings else 5.0

def main_app():
    # Verileri Yükle
    users_db = load_data(USERS_FILE_PATH, default_type=dict)
    invites = load_data(INVITES_FILE_PATH, default_type=list)
    current_user_profile = users_db.get(st.session_state.current_user, {})
    
    # Süresi geçenleri kontrol et (Lazy Checker)
    if check_expired_invites(invites):
        save_data(INVITES_FILE_PATH, invites)
    
    # Üst Bilgi Barı
    isim = current_user_profile.get("ad_soyad", st.session_state.current_user.split('@')[0])
    puan = get_avg_rating(current_user_profile)
    
    header_col1, header_col2 = st.columns([4, 1])
    with header_col1:
        st.title("🎾 İzmir Tenis Partner Havuzu")
    with header_col2:
        st.write(f"👤 **{isim}** (⭐ {puan:.1f})")
        if st.button("🚪 Çıkış Yap"):
            st.session_state.logged_in = False
            st.rerun()

    # Yönetici Doğrulama (Gizli Expander)
    is_admin = False
    with st.expander("Yönetici Yetkisi"):
        if st.text_input("Yönetici Kodu", type="password") == ADMIN_PASS:
            is_admin = True
            st.success("Yönetici yetkisi aktif.")

    # --- SEKMELER (TABS) OLUŞTURMA ---
    tab_names = ["🏆 Havuz", "➕ Davet Oluştur", "👥 Üyeler", "⚖️ Geçmiş", "⚙️ Profil"]
    if is_admin:
        tab_names.append("👑 Yönetici Paneli")
    
    tabs = st.tabs(tab_names)

    # 1. HAVUZ SEKME (Aktif İlanlar)
    with tabs[0]:
        st.subheader("Güncel Eşleşme Havuzu")
        active_invites = [i for i in invites if i.get('status', 'active') == 'active']
        
        if not active_invites:
            st.info("Şu an havuzda aktif bir davet bulunmuyor.")
        else:
            for inv in active_invites:
                creator_mail = inv.get('creator', 'Bilinmiyor')
                creator_name = users_db.get(creator_mail, {}).get("ad_soyad", creator_mail.split('@')[0])
                
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 2, 2])
                    with c1:
                        st.markdown(f"🗓️ **{inv.get('date', 'Belirtilmemiş')}** | ⏰ **{inv.get('time', 'Belirtilmemiş')}**")
                        st.markdown(f"📍 **{inv.get('court', 'Belirtilmemiş')}**")
                    with c2:
                        st.markdown(f"⭐ **Aranan Seviye:** {inv.get('level', '4.0')} NTRP")
                        st.markdown(f"👤 **Oluşturan:** {creator_name}")
                    with c3:
                        if creator_mail == st.session_state.current_user:
                            st.info("Kendi ilanınız")
                        else:
                            if st.button("🙋‍♂️ Teklif Gönder", key=f"offer_{inv.get('id', uuid.uuid4())}"):
                                send_email(creator_mail, "İlanınıza Teklif Var!", f"{isim} adlı kullanıcı davetinize katılmak istiyor! İletişime geçin: {st.session_state.current_user}")
                                st.success("Teklif gönderildi ve kullanıcıya mail atıldı.")

    # 2. DAVET OLUŞTUR SEKME (Bildirim Tetikleyici İçerir)
    with tabs[1]:
        st.subheader("Yeni Partner Daveti")
        with st.form("create_invite"):
            date_val = st.date_input("Tarih")
            time_val = st.time_input("Saat")
            court_val = st.selectbox("Kort", IZMIR_KORTLARI)
            level_val = st.selectbox("Aranan Seviye", NTRP_LEVELS, index=6)
            
            if st.form_submit_button("İlanı Havuza Ekle", type="primary"):
                new_invite = {
                    "id": str(uuid.uuid4()),
                    "creator": st.session_state.current_user,
                    "date": str(date_val),
                    "time": time_val.strftime("%H:%M"),
                    "court": court_val,
                    "level": level_val,
                    "status": "active"
                }
                invites.append(new_invite)
                save_data(INVITES_FILE_PATH, invites)
                st.success("İlan oluşturuldu!")
                
                # UYGUN KULLANICILARA BİLDİRİM GÖNDERME
                for u_mail, u_data in users_db.items():
                    if u_mail == st.session_state.current_user: continue
                    prefs = u_data.get("notif_prefs", {})
                    pref_levels = prefs.get("levels", [])
                    pref_courts = prefs.get("courts", [])
                    
                    if pref_levels or pref_courts:
                        l_match = level_val in pref_levels if pref_levels else True
                        c_match = court_val in pref_courts if pref_courts else True
                        
                        if l_match and c_match:
                            send_email(u_mail, "Yeni Tenis İlanı (Tercihlerinize Uygun)!", 
                                       f"Aradığınız kriterlerde yeni bir tenis daveti var!<br><br><b>Kort:</b> {court_val}<br><b>Seviye:</b> {level_val}<br><b>Tarih/Saat:</b> {str(date_val)} / {time_val.strftime('%H:%M')}<br><b>Sisteme girerek teklif gönderebilirsiniz.</b>")

    # 3. ÜYELER SEKME
    with tabs[2]:
        st.subheader("Sistemdeki Üyeler")
        for u_email, u_data in users_db.items():
            u_isim = u_data.get("ad_soyad", u_email.split('@')[0])
            u_puan = get_avg_rating(u_data)
            u_sev = u_data.get("seviye", "Belirtilmemiş")
            st.markdown(f"🎾 **{u_isim}** | Seviye: {u_sev} | ⭐ Puan: {u_puan:.1f}")
            st.divider()

    # 4. GEÇMİŞ SEKME (Tarihi Geçenler ve Eşleşenler)
    with tabs[3]:
        st.subheader("Geçmiş / Pasif İlanlar")
        past_invites = [i for i in invites if i.get('status') in ['expired', 'matched']]
        if not past_invites:
            st.info("Geçmiş kayıt bulunmuyor.")
        for inv in past_invites:
            st.markdown(f"[{inv.get('status').upper()}] - {inv.get('date', '')} | {inv.get('court', '')} | {inv.get('level', '')}")

    # 5. PROFİL SEKME (Çoklu Bildirim Seçimi)
    with tabs[4]:
        st.subheader("Profil ve Bildirim Ayarları")
        with st.form("profile_form"):
            new_isim = st.text_input("Ad Soyad", value=current_user_profile.get("ad_soyad", ""))
            new_sev = st.selectbox("Kendi Seviyeniz", NTRP_LEVELS, index=NTRP_LEVELS.index(current_user_profile.get("seviye", "4.0")))
            
            st.markdown("### 🔔 E-posta Bildirim Tercihleri")
            st.write("Sadece aşağıdaki kortlarda veya seviyelerde ilan açıldığında mail almak için seçim yapabilirsiniz. Boş bırakırsanız filtre uygulanmaz.")
            
            current_prefs = current_user_profile.get("notif_prefs", {})
            pref_c = st.multiselect("İlgilendiğim Kortlar", IZMIR_KORTLARI, default=current_prefs.get("courts", []))
            pref_l = st.multiselect("İlgilendiğim Seviyeler", NTRP_LEVELS, default=current_prefs.get("levels", []))
            
            if st.form_submit_button("Ayarları Kaydet"):
                users_db[st.session_state.current_user]["ad_soyad"] = new_isim
                users_db[st.session_state.current_user]["seviye"] = new_sev
                users_db[st.session_state.current_user]["notif_prefs"] = {"courts": pref_c, "levels": pref_l}
                save_data(USERS_FILE_PATH, users_db)
                st.success("Profiliniz güncellendi!")
                st.rerun()

    # 6. YÖNETİCİ PANELİ SEKME
    if is_admin:
        with tabs[5]:
            st.subheader("Sistem Yönetimi")
            st.download_button("JSON Veritabanını İndir", json.dumps({"users": users_db, "invites": invites}), "yedek.json")
            
            st.markdown("### İlan Yönetimi (Tüm İlanlar)")
            for i, inv in enumerate(invites):
                durum = inv.get('status', 'active')
                with st.expander(f"{inv.get('date', 'Tarih Yok')} | {inv.get('court', 'Kort Yok')} ({durum})"):
                    with st.form(key=f"admin_edit_{i}"):
                        e_date = st.text_input("Tarih", value=inv.get('date', ''))
                        e_time = st.text_input("Saat", value=inv.get('time', ''))
                        e_court = st.selectbox("Kort", IZMIR_KORTLARI + ["Belirtilmemiş"], index=(IZMIR_KORTLARI+["Belirtilmemiş"]).index(inv.get('court', 'Belirtilmemiş')) if inv.get('court', 'Belirtilmemiş') in IZMIR_KORTLARI+["Belirtilmemiş"] else 0)
                        e_status = st.selectbox("Durum", ["active", "expired", "matched"], index=["active", "expired", "matched"].index(durum))
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.form_submit_button("Güncelle", type="primary"):
                                invites[i]['date'] = e_date
                                invites[i]['time'] = e_time
                                invites[i]['court'] = e_court
                                invites[i]['status'] = e_status
                                save_data(INVITES_FILE_PATH, invites)
                                st.success("İlan güncellendi.")
                                st.rerun()
                        with c2:
                            if st.form_submit_button("İlanı Tamamen Sil"):
                                invites.pop(i)
                                save_data(INVITES_FILE_PATH, invites)
                                st.warning("İlan silindi.")
                                st.rerun()

if not st.session_state.logged_in:
    login_page()
else:
    main_app()
