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
            repo.update_file(content.path, "Update", json.dumps(data, indent=4, ensure_ascii=False), content.sha)
        except:
            try: repo.create_file(file_path, "Create", json.dumps(data, indent=4, ensure_ascii=False))
            except: return False
    else:
        with open(file_path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)
    return True

def calculate_rating(ratings_dict):
    if not ratings_dict: return 5.0
    all_scores = ratings_dict.get("zaman", []) + ratings_dict.get("seviye", []) + ratings_dict.get("davranis", [])
    return sum(all_scores) / len(all_scores) if all_scores else 5.0

# --- OTURUM YÖNETİMİ ---
for key in ['logged_in', 'is_admin', 'current_user', 'offer_to', 'reg_step', 'reg_data', 'reg_code']:
    if key not in st.session_state: st.session_state[key] = False if key in ['logged_in', 'is_admin'] else None
if 'reg_step' not in st.session_state or st.session_state.reg_step is None: st.session_state.reg_step = "form"

# --- YÖNETİCİ KONTROL MERKEZİ ---
def admin_dashboard():
    st.markdown("<h1 style='color: #D32F2F;'>👑 Sistem Kontrol Merkezi</h1>", unsafe_allow_html=True)
    if st.button("🚪 Yönetici Panelinden Çık"):
        st.session_state.logged_in = False; st.session_state.is_admin = False; st.rerun()
    
    users_db = load_data(USERS_FILE_PATH, default_type=dict)
    invites = load_data(INVITES_FILE_PATH, default_type=list)
    messages = load_data(MESSAGES_FILE_PATH, default_type=list)

    t1, t2, t3, t4 = st.tabs(["👥 Üye Yönetimi", "📅 İlan Yönetimi", "💾 Yedekleme & Kurtarma", "🤖 Test Simülasyonu"])
    
    with t1:
        st.subheader("Kayıtlı Üyeler")
        for u_email, u_data in users_db.items():
            if u_data.get("is_bot"): continue
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 2, 2])
                status = "🔴 Askıda" if u_data.get("suspended") else "🟢 Aktif"
                c1.write(f"**{u_data.get('ad_soyad')}** | {u_email} | {status}")
                if c2.button("Kaldır / Askıya Al", key=f"susp_{u_email}"):
                    users_db[u_email]["suspended"] = not u_data.get("suspended", False)
                    save_data(USERS_FILE_PATH, users_db); st.rerun()
                if c3.button("🗑️ Sil", key=f"del_{u_email}"):
                    del users_db[u_email]; save_data(USERS_FILE_PATH, users_db); st.rerun()

    with t2:
        st.subheader("Havuzdaki İlanlar")
        for inv in reversed(invites):
            st.write(f"📍 {inv.get('court')} | 🗓️ {inv.get('date')} | Durum: {inv.get('status')} | 👤 {users_db.get(inv.get('creator'), {}).get('ad_soyad', 'Bilinmeyen')}")

    with t3:
        st.subheader("Sistem Yedekleme ve Geri Yükleme")
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("### 📥 Mevcut Veriyi İndir")
            st.download_button("Üyeler Yedeğini İndir (users.json)", data=json.dumps(users_db, indent=4, ensure_ascii=False), file_name="users_backup.json", mime="application/json")
            st.download_button("İlanlar Yedeğini İndir (invites.json)", data=json.dumps(invites, indent=4, ensure_ascii=False), file_name="invites_backup.json", mime="application/json")
            st.download_button("Mesajlar Yedeğini İndir (messages.json)", data=json.dumps(messages, indent=4, ensure_ascii=False), file_name="messages_backup.json", mime="application/json")

        with c2:
            st.markdown("### 📤 Yedekten Geri Yükle")
            uploaded_users = st.file_uploader("Üye Yedeği Yükle (users.json)", type=["json"])
            if st.button("Uygula (Üyeler)") and uploaded_users:
                save_data(USERS_FILE_PATH, json.loads(uploaded_users.getvalue().decode("utf-8")))
                st.success("Üyeler geri yüklendi!"); st.rerun()
                
            uploaded_invites = st.file_uploader("İlan Yedeği Yükle (invites.json)", type=["json"])
            if st.button("Uygula (İlanlar)") and uploaded_invites:
                save_data(INVITES_FILE_PATH, json.loads(uploaded_invites.getvalue().decode("utf-8")))
                st.success("İlanlar geri yüklendi!"); st.rerun()

    with t4:
        st.subheader("Test Ortamı")
        if st.button("🤖 Test Botları Ekle"):
            # Bot ekleme işlemleri (Önceki kod ile aynı)
            bots = [{"e": "bot1@test.com", "n": "Ali (Bot)", "lvl": "4.0"}]
            for b in bots:
                users_db[b["e"]] = {"password_hash": "123", "ad_soyad": b["n"], "is_bot": True, "suspended": False, "privacy": {"ghost": False}, "ratings": {}, "contact_visibility": "eslesince"}
            save_data(USERS_FILE_PATH, users_db); st.success("Bot eklendi!"); st.rerun()

# --- GİRİŞ VE VİTRİN SAYFASI ---
def login_page():
    st.markdown("<h1 style='text-align: center; color: #2E7D32;'>🎾 İzmir Tenis Partner Ağı</h1>", unsafe_allow_html=True)
    users_db = load_data(USERS_FILE_PATH, default_type=dict)
    invites = load_data(INVITES_FILE_PATH, default_type=list)
    
    col_showcase, spacer, col_login = st.columns([5, 1, 4])
    
    with col_showcase:
        st.markdown("### 🌟 Güncel İlanlar (Vitrin)")
        st.write("Aşağıdaki ilanlara teklif göndermek veya kendi ilanını açmak için sağ taraftan giriş yapmalısın.")
        active_inv = [i for i in invites if i.get('status') == 'active']
        active_inv.sort(key=lambda x: x.get('date', '9999-12-31'))
        
        if not active_inv: st.info("Şu an havuzda aktif ilan bulunmuyor.")
        
        for inv in active_inv[:8]:
            with st.container(border=True):
                k_isim = f"{inv.get('court')} ({inv.get('court_custom')})" if inv.get('court') == 'Diğer' else inv.get('court')
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**📍 {k_isim}** | 🗓️ {inv.get('date')} | ⏰ {inv.get('time_details')}")
                c1.markdown(f"🎾 Tür: {inv.get('type')} | ⭐ Seviye: {', '.join(inv.get('levels', []))}")
                if c2.button("Teklif Gönder", key=f"pub_{inv.get('id')}"):
                    st.toast("Teklif göndermek için sağ taraftan sisteme giriş yapmalısın! 🎾", icon="⚠️")

    with col_login:
        t1, t2, t3 = st.tabs(["🔑 Giriş", "📝 Kayıt", "❓ Şifre"])
        with t1:
            with st.form("login"):
                email = st.text_input("E-posta").strip().lower()
                password = st.text_input("Şifre", type="password")
                if st.form_submit_button("Giriş Yap"):
                    if email in users_db and users_db[email].get("password_hash") == hash_password(password):
                        if users_db[email].get("suspended"): st.error("Hesabınız geçici olarak durdurulmuştur.")
                        else:
                            st.session_state.logged_in = True
                            st.session_state.current_user = email
                            st.rerun()
                    else: st.error("Hatalı e-posta veya şifre!")
        with t2:
            if st.session_state.reg_step == "form":
                with st.form("register"):
                    reg_email = st.text_input("E-posta Adresi").strip().lower()
                    reg_pass = st.text_input("Şifre Belirle", type="password")
                    reg_name = st.text_input("Ad Soyad")
                    if st.form_submit_button("İleri (E-Posta Doğrulama)"):
                        if reg_email in users_db: st.error("Bu e-posta zaten kayıtlı.")
                        elif not reg_email or not reg_pass or not reg_name: st.error("Lütfen tüm alanları doldurun.")
                        else:
                            code = str(random.randint(100000, 999999))
                            st.session_state.reg_code = code
                            st.session_state.reg_data = {"email": reg_email, "pass": hash_password(reg_pass), "name": reg_name}
                            
                            # E-posta gönderme (Eğer SMTP yoksa test için ekranda gösterilir - Prod'da silinmelidir)
                            mail_sent = send_email(reg_email, "Hesap Doğrulama Kodu", f"Sisteme kayıt için doğrulama kodunuz: <b>{code}</b>")
                            if not mail_sent: st.warning(f"SMTP ayarları eksik. Geliştirici Test Kodu: {code}")
                            
                            st.session_state.reg_step = "verify"
                            st.rerun()
            elif st.session_state.reg_step == "verify":
                st.info(f"**{st.session_state.reg_data['email']}** adresine 6 haneli bir kod gönderdik.")
                with st.form("verify"):
                    user_code = st.text_input("Doğrulama Kodu")
                    if st.form_submit_button("Kayıt İşlemini Tamamla"):
                        if user_code.strip() == st.session_state.reg_code:
                            d = st.session_state.reg_data
                            users_db[d["email"]] = {
                                "password_hash": d["pass"], "ad_soyad": d["name"], "suspended": False, "is_bot": False,
                                "phone": "", "contact_visibility": "eslesince", 
                                "privacy": {"ghost": False, "show_age": True, "show_style": True},
                                "notif_prefs": {"active": False, "levels": [], "courts": [], "types": []},
                                "ratings": {"zaman": [], "seviye": [], "davranis": []}
                            }
                            save_data(USERS_FILE_PATH, users_db)
                            st.session_state.reg_step = "form"
                            st.success("Kayıt başarılı! Giriş sekmesinden hesabına girebilirsin.")
                        else: st.error("Hatalı kod!")
                if st.button("Geri Dön / İptal"):
                    st.session_state.reg_step = "form"; st.rerun()

        with t3:
            with st.form("forgot_pass"):
                reset_email = st.text_input("E-posta Adresi").strip().lower()
                if st.form_submit_button("Şifremi Sıfırla"):
                    if reset_email in users_db:
                        new_pass = generate_temp_password()
                        users_db[reset_email]["password_hash"] = hash_password(new_pass)
                        save_data(USERS_FILE_PATH, users_db)
                        send_email(reset_email, "Şifre Sıfırlama Talebi", f"Geçici şifreniz: <b>{new_pass}</b>")
                        st.success("Yeni şifreniz gönderildi!")
                    else: st.error("E-posta bulunamadı.")
                    
        with st.expander("👑 Yönetici Paneli"):
            admin_code = st.text_input("Yönetici Parolası", type="password")
            if st.button("Panele Gir"):
                if admin_code == ADMIN_PASS:
                    st.session_state.logged_in = True; st.session_state.is_admin = True; st.rerun()
                else: st.error("Hatalı Parola!")

# --- ANA UYGULAMA ---
def main_app():
    users_db = load_data(USERS_FILE_PATH, default_type=dict)
    invites = load_data(INVITES_FILE_PATH, default_type=list)
    messages = load_data(MESSAGES_FILE_PATH, default_type=list)
    me = users_db.get(st.session_state.current_user, {})
    
    c_head1, c_head2 = st.columns([4, 1])
    c_head1.write("### 🎾 İzmir Tenis Partner Havuzu")
    c_head2.write(f"👤 **{me.get('ad_soyad')}** | ⭐ {calculate_rating(me.get('ratings')):.1f}")
    if c_head2.button("🚪 Çıkış"): st.session_state.logged_in = False; st.rerun()

    tabs = st.tabs(["🏆 İlan Havuzu", "➕ İlan Oluştur", "👥 Üyeler", "📩 Kutum & Takvim", "⚖️ Değerlendirme", "⚙️ Profil Ayarları"])

    with tabs[0]: # İLAN HAVUZU FİLTRELEME VE GÖSTERİM
        with st.expander("🔍 İlanları Filtrele ve Sırala", expanded=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            sort_by = f_col1.selectbox("Sıralama Ölçütü", ["Tarihe Göre (En Yakın)", "Eklenme Zamanına Göre (En Yeni)"])
            filter_court = f_col2.multiselect("Kort Filtresi", IZMIR_KORTLARI)
            filter_level = f_col3.multiselect("Seviye Filtresi", NTRP_LEVELS)
            
        active_invites = [i for i in invites if i.get('status') == 'active']
        
        # Filtreleri Uygula
        if filter_court: active_invites = [i for i in active_invites if i.get('court') in filter_court]
        if filter_level: active_invites = [i for i in active_invites if any(l in filter_level for l in i.get('levels', []))]
        
        # Sıralama Uygula
        if sort_by == "Tarihe Göre (En Yakın)":
            active_invites.sort(key=lambda x: x.get('date', '9999-12-31'))
        else: # Yeniden Eskiye (Listenin tersi varsayılır)
            active_invites.reverse()

        for inv in active_invites:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 3, 2])
                k_isim = f"{inv.get('court')} ({inv.get('court_custom')})" if inv.get('court') == 'Diğer' else inv.get('court')
                c1.markdown(f"**📍 Kort:** {k_isim}")
                c1.markdown(f"**🗓️ Tarih:** {inv.get('date')} | ⏰ **Saat:** {inv.get('time_details')}")
                if inv.get('note'): c1.markdown(f"**📝 Not:** {inv.get('note')}")
                
                c2.markdown(f"**🎾 Tür:** {inv.get('type')} | **⭐ Seviye:** {', '.join(inv.get('levels', []))}")
                c2.markdown(f"**🔑 Durum:** {inv.get('court_status')}")
                
                creator = users_db.get(inv.get('creator'), {})
                c3.markdown(f"👤 **Açan:** {creator.get('ad_soyad')}")
                
                # Herkese açık iletişim bilgisi kontrolü
                if creator.get('contact_visibility') == 'herkes':
                    c3.markdown(f"📞 {creator.get('phone', 'Belirtilmedi')} | ✉️ {inv.get('creator')}")

                if inv.get('creator') != st.session_state.current_user:
                    if c3.button("Teklif Gönder", key=f"inv_{inv.get('id')}"):
                        new_msg = {
                            "id": str(uuid.uuid4()), "type": "invite_request", "invite_id": inv.get('id'),
                            "sender": st.session_state.current_user, "receiver": inv.get('creator'),
                            "status": "pending", "timestamp": str(datetime.datetime.now())
                        }
                        messages.append(new_msg); save_data(MESSAGES_FILE_PATH, messages)
                        st.success("Teklifiniz ilan sahibine iletildi!"); st.rerun()

    with tabs[1]: # İLAN OLUŞTUR
        with st.form("create_invite"):
            c1, c2 = st.columns(2)
            d = c1.date_input("Tarih")
            c_t1, c_t2 = c1.columns(2)
            t_start = c_t1.time_input("Başlangıç Saati", datetime.time(18, 0))
            t_end = c_t2.time_input("Bitiş Saati", datetime.time(19, 30))
            
            court = c2.selectbox("Kort", IZMIR_KORTLARI)
            court_custom = c2.text_input("Diğer ise kort adını belirtin:") if court == "Diğer" else ""
            court_status = c2.selectbox("Kort Rezervasyon Durumu", COURT_STATUS)
            
            act_type = st.selectbox("Etkinlik Tipi", ACTIVITY_TYPES)
            levels = st.multiselect("Aranan Seviyeler", NTRP_LEVELS, default=["4.0"])
            inv_note = st.text_area("İlan Notu / Açıklama (İsteğe bağlı)")
            
            if st.form_submit_button("İlanı Yayınla"):
                if not levels: st.error("Lütfen en az bir seviye seçin.")
                elif court == "Diğer" and not court_custom.strip(): st.error("Lütfen diğer kort alanını doldurun.")
                else:
                    new_inv = {
                        "id": str(uuid.uuid4()), "creator": st.session_state.current_user,
                        "date": str(d), "time_details": f"{t_start.strftime('%H:%M')} - {t_end.strftime('%H:%M')}",
                        "court": court, "court_custom": court_custom, "court_status": court_status,
                        "type": act_type, "levels": levels, "status": "active", "note": inv_note, "created_at": str(datetime.datetime.now())
                    }
                    invites.append(new_inv); save_data(INVITES_FILE_PATH, invites)
                    st.success("İlan başarıyla yayınlandı!"); st.rerun()

    with tabs[2]: # ÜYELER (Aynı mantık korunuyor)
        if st.session_state.offer_to:
            target = st.session_state.offer_to
            st.info(f"👉 **{users_db[target].get('ad_soyad')}** kişisine özel teklif gönderiyorsunuz.")
            with st.form("direct_offer"):
                o_date = st.date_input("Tarih Önerisi")
                o_court = st.selectbox("Kort", IZMIR_KORTLARI)
                o_custom = st.text_input("Diğer ise belirtin:") if o_court == "Diğer" else ""
                c_sub, c_can = st.columns(2)
                if c_sub.form_submit_button("Gönder"):
                    new_msg = {
                        "id": str(uuid.uuid4()), "type": "direct_challenge", "sender": st.session_state.current_user,
                        "receiver": target, "date": str(o_date), "time": "18:00 - 19:30", "court": o_court,
                        "court_custom": o_custom, "status": "pending"
                    }
                    messages.append(new_msg); save_data(MESSAGES_FILE_PATH, messages)
                    st.session_state.offer_to = None; st.success("Teklif iletildi!"); st.rerun()
                if c_can.form_submit_button("İptal"): st.session_state.offer_to = None; st.rerun()

        for u_email, u_data in users_db.items():
            if u_email == st.session_state.current_user or u_data.get("privacy", {}).get("ghost"): continue
            with st.container(border=True):
                colA, colB, colC = st.columns([2,3,1])
                colA.markdown(f"**👤 {u_data.get('ad_soyad')}** | ⭐ {calculate_rating(u_data.get('ratings')):.1f}")
                
                # Eşleşme veya herkese açık durumunda iletişim göster
                cv = u_data.get('contact_visibility')
                if cv == 'herkes': colB.write(f"📞 {u_data.get('phone', '-')} | ✉️ {u_email}")
                
                if colC.button("🎾 Teklif Gönder", key=f"chall_{u_email}"): st.session_state.offer_to = u_email; st.rerun()

    with tabs[3]: # KUTUM & TAKVİM & İPTAL İŞLEMLERİ
        st.subheader("Gelen Teklifler")
        my_inbox = [m for m in messages if m.get('receiver') == st.session_state.current_user and m.get('status') == 'pending']
        if not my_inbox: st.write("Bekleyen bir teklifiniz yok.")
        
        for msg in my_inbox:
            with st.container(border=True):
                sender_email = msg['sender']
                sender_name = users_db.get(sender_email, {}).get('ad_soyad', 'Kullanıcı')
                st.write(f"🔔 **{sender_name}** sana bir teklif gönderdi / ilanına katılmak istiyor!")
                
                c_acc, c_rej = st.columns(2)
                if c_acc.button("✅ Kabul Et", key=f"acc_{msg['id']}"):
                    msg['status'] = 'accepted'
                    
                    # Eğer bu bir ilan başvurusu ise, ilanın durumunu "matched" (eşleşti) yap ki havuzdan düşsün.
                    if msg.get('type') == 'invite_request':
                        for i in invites:
                            if i.get('id') == msg.get('invite_id'):
                                i['status'] = 'matched'
                                t_str = i.get('time_details', '18:00 - 19:30')
                                gcal = generate_gcal_link("Tenis Maçı", i.get('date', str(datetime.date.today())), t_str, i.get('court', 'Kort'))
                                msg['calendar_link'] = gcal
                                break
                    save_data(INVITES_FILE_PATH, invites)
                    save_data(MESSAGES_FILE_PATH, messages)
                    st.success("Kabul edildi!"); st.rerun()
                if c_rej.button("❌ Reddet", key=f"rej_{msg['id']}"):
                    msg['status'] = 'rejected'; save_data(MESSAGES_FILE_PATH, messages); st.rerun()

        st.subheader("Onaylanmış Maçlarım (Takvim)")
        my_acc = [m for m in messages if (m.get('receiver') == st.session_state.current_user or m.get('sender') == st.session_state.current_user) and m.get('status') == 'accepted']
        
        for acc in reversed(my_acc):
            with st.container(border=True):
                partner_e = acc['sender'] if acc['receiver'] == st.session_state.current_user else acc['receiver']
                partner_db = users_db.get(partner_e, {})
                st.markdown(f"🤝 **{partner_db.get('ad_soyad')}** ile maç onaylı. [📅 Google Takvime Ekle]({acc.get('calendar_link', '#')})")
                
                # Gizlilik "Sadece Eşleşince" veya "Herkes" ise numarayı göster
                p_vis = partner_db.get('contact_visibility', 'eslesince')
                if p_vis in ['eslesince', 'herkes']:
                    st.info(f"📞 İletişim: {partner_db.get('phone', 'Belirtilmedi')} | ✉️ {partner_e}")
                
                if st.button("❌ Maçı İptal Et & İlanı Yeniden Havuza Aç", key=f"canc_{acc['id']}"):
                    acc['status'] = 'cancelled'
                    # Eğer bu bir ilan eşleşmesi ise ilanı tekrar aktif yap
                    if acc.get('type') == 'invite_request':
                        for i in invites:
                            if i.get('id') == acc.get('invite_id'):
                                i['status'] = 'active'
                                break
                        save_data(INVITES_FILE_PATH, invites)
                    save_data(MESSAGES_FILE_PATH, messages)
                    send_email(partner_e, "Maç İptali", f"<b>{me.get('ad_soyad')}</b> ile olan maçınız iptal edilmiştir.")
                    st.warning("Maç iptal edildi ve ilanınız tekrar havuza açıldı!"); st.rerun()

    with tabs[4]: # DEĞERLENDİRME (Aynı mantık)
        st.subheader("Tamamlanmış Maçları Değerlendir")
        accepted_events = [m for m in messages if (m.get('receiver') == st.session_state.current_user or m.get('sender') == st.session_state.current_user) and m.get('status') in ['accepted', 'cancelled']]
        unrated_events = [m for m in accepted_events if st.session_state.current_user not in m.get('rated_by', [])]
        
        if not unrated_events: st.info("Değerlendirebileceğiniz etkinlik bulunmuyor.")
        else:
            with st.form("rating_form"):
                evt_opts = {m['id']: f"Rakip: {users_db.get(m['sender'] if m['receiver'] == st.session_state.current_user else m['receiver'], {}).get('ad_soyad')}" for m in unrated_events}
                selected_event_id = st.selectbox("Değerlendirilecek Maç", options=list(evt_opts.keys()), format_func=lambda x: evt_opts[x])
                st.markdown("**(1: Çok Kötü - 5: Çok İyi)**")
                sz = st.slider("Zaman Planlaması", 1, 5, 5)
                ss = st.slider("Seviye Tutarlılığı", 1, 5, 5)
                sd = st.slider("Sportmenlik", 1, 5, 5)
                if st.form_submit_button("Kaydet"):
                    target_event = next(m for m in unrated_events if m['id'] == selected_event_id)
                    p_email = target_event['sender'] if target_event['receiver'] == st.session_state.current_user else target_event['receiver']
                    if p_email in users_db:
                        r_db = users_db[p_email].setdefault("ratings", {"zaman": [], "seviye": [], "davranis": []})
                        r_db["zaman"].append(sz); r_db["seviye"].append(ss); r_db["davranis"].append(sd)
                        save_data(USERS_FILE_PATH, users_db)
                        target_event.setdefault('rated_by', []).append(st.session_state.current_user)
                        save_data(MESSAGES_FILE_PATH, messages)
                        st.success("Değerlendirildi!"); st.rerun()

    with tabs[5]: # PROFİL & GİZLİLİK
        colL, colR = st.columns(2)
        with colL:
            st.subheader("Profil ve İletişim")
            with st.form("profile_form"):
                ad = st.text_input("Ad Soyad", value=me.get("ad_soyad", ""))
                phone = st.text_input("Telefon Numarası", value=me.get("phone", ""))
                
                # Oyun Tarzı ve "Diğer" seçeneği
                me_style = me.get("style", "All-Rounder")
                is_custom_style = me_style not in ["Agresif Baseline", "Servis & Vole", "Defansif / Karşılayıcı", "All-Rounder", ""]
                style_sel = st.selectbox("Oyun Tarzı", ["Agresif Baseline", "Servis & Vole", "Defansif / Karşılayıcı", "All-Rounder", "Diğer"], index=4 if is_custom_style else ["Agresif Baseline", "Servis & Vole", "Defansif / Karşılayıcı", "All-Rounder", ""].index(me_style))
                style_custom = st.text_input("Diğer ise belirtin", value=me_style if is_custom_style else "") if style_sel == "Diğer" else ""

                if st.form_submit_button("Güncelle"):
                    final_style = style_custom if style_sel == "Diğer" else style_sel
                    me.update({"ad_soyad": ad, "phone": phone, "style": final_style})
                    users_db[st.session_state.current_user] = me
                    save_data(USERS_FILE_PATH, users_db); st.success("Güncellendi!")

        with colR:
            st.subheader("Gizlilik Ayarları")
            with st.form("privacy_form"):
                vis_options = ["Gizle (Hiçbir Zaman Gösterme)", "Sadece Eşleşince Göster", "Herkese Açık (İlanda Göster)"]
                vis_keys = ["gizle", "eslesince", "herkes"]
                current_vis_idx = vis_keys.index(me.get("contact_visibility", "eslesince"))
                
                c_vis = st.selectbox("İletişim Bilgilerimin Görünürlüğü", vis_options, index=current_vis_idx)
                ghost = st.toggle("👻 Hayalet Modu (Üye listesinde gizlen)", value=me.get("privacy", {}).get("ghost", False))
                
                if st.form_submit_button("Kaydet"):
                    me["contact_visibility"] = vis_keys[vis_options.index(c_vis)]
                    me.setdefault("privacy", {})["ghost"] = ghost
                    users_db[st.session_state.current_user] = me
                    save_data(USERS_FILE_PATH, users_db); st.success("Kaydedildi!")

if not st.session_state.logged_in: login_page()
elif st.session_state.is_admin: admin_dashboard()
else: main_app()
