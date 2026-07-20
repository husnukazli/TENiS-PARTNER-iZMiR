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
COURT_STATUS = ["Kort Rezervasyonu Bende", "Birlikte Ayarlarız", "Davetlinin Kortu Olması Tercihimdir"]
TURKEY_TZ = datetime.timezone(datetime.timedelta(hours=3))

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
    if not SMTP_USER or not SMTP_PASS: return
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
    except: pass

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
for key in ['logged_in', 'is_admin', 'current_user', 'offer_to']:
    if key not in st.session_state: st.session_state[key] = False if key in ['logged_in', 'is_admin'] else None

# --- YÖNETİCİ KONTROL MERKEZİ ---
def admin_dashboard():
    st.markdown("<h1 style='color: #D32F2F;'>👑 Sistem Kontrol Merkezi</h1>", unsafe_allow_html=True)
    if st.button("🚪 Yönetici Panelinden Çık"):
        st.session_state.logged_in = False
        st.session_state.is_admin = False
        st.rerun()
    
    users_db = load_data(USERS_FILE_PATH, default_type=dict)
    invites = load_data(INVITES_FILE_PATH, default_type=list)
    messages = load_data(MESSAGES_FILE_PATH, default_type=list)

    t1, t2, t3 = st.tabs(["👥 Üye Yönetimi", "📅 İlan Yönetimi", "🤖 Test Simülasyonu"])
    
    with t1:
        st.subheader("Kayıtlı Üyeler")
        for u_email, u_data in users_db.items():
            if u_data.get("is_bot"): continue
            with st.container(border=True):
                c1, c2, c3 = st.columns([4, 2, 2])
                status = "🔴 (Askıda)" if u_data.get("suspended") else "🟢 (Aktif)"
                c1.write(f"**{u_data.get('ad_soyad')}** | {u_email} | {status}")
                
                if c2.button("Kaldır / Askıya Al", key=f"susp_{u_email}"):
                    users_db[u_email]["suspended"] = not u_data.get("suspended", False)
                    save_data(USERS_FILE_PATH, users_db)
                    st.rerun()
                
                if c3.button("🗑️ Komple Sil", key=f"del_{u_email}"):
                    del users_db[u_email]
                    save_data(USERS_FILE_PATH, users_db)
                    st.rerun()

    with t2:
        st.subheader("Havuzdaki İlanlar")
        if st.button("🧹 Zamanı Geçmiş İlanları Temizle"):
            today = datetime.date.today()
            active_inv = []
            for inv in invites:
                try:
                    inv_d = datetime.datetime.strptime(inv['date'], "%Y-%m-%d").date()
                    if inv_d >= today: active_inv.append(inv)
                except: active_inv.append(inv)
            save_data(INVITES_FILE_PATH, active_inv)
            st.success("Geçmiş ilanlar temizlendi!")
            st.rerun()
        
        for inv in reversed(invites):
            st.write(f"📍 {inv.get('court')} | 🗓️ {inv.get('date')} | 👤 {users_db.get(inv.get('creator'), {}).get('ad_soyad', 'Bilinmeyen')}")

    with t3:
        st.subheader("Test Ortamı (Botlar)")
        c1, c2 = st.columns(2)
        if c1.button("🤖 Test Botları Ekle"):
            bots = [
                {"e": "bot1@test.com", "n": "Ali (Bot)", "lvl": "4.0"},
                {"e": "bot2@test.com", "n": "Ayşe (Bot)", "lvl": "3.5"},
                {"e": "bot3@test.com", "n": "Cem (Bot)", "lvl": "5.0"}
            ]
            for b in bots:
                users_db[b["e"]] = {
                    "password_hash": "123", "ad_soyad": b["n"], "is_bot": True, "suspended": False,
                    "privacy": {"ghost": False, "show_age": True, "show_style": True},
                    "notif_prefs": {"active": False}, "ratings": {}, "hand": "Sağ", "age": "30", "style": "All-Rounder"
                }
                invites.append({
                    "id": str(uuid.uuid4()), "creator": b["e"], "date": str(datetime.date.today() + datetime.timedelta(days=2)),
                    "time_details": "18:00 - 19:30", "court": random.choice(IZMIR_KORTLARI),
                    "court_custom": "", "court_status": "Birlikte Ayarlarız", "type": "Maç", "levels": [b["lvl"]],
                    "status": "active", "is_bot": True
                })
            save_data(USERS_FILE_PATH, users_db)
            save_data(INVITES_FILE_PATH, invites)
            st.success("3 Test Botu ve İlanları eklendi!")
            st.rerun()
            
        if c2.button("🧹 Botları ve Verilerini Temizle"):
            users_db = {k: v for k, v in users_db.items() if not v.get("is_bot")}
            invites = [i for i in invites if not i.get("is_bot")]
            messages = [m for m in messages if "bot" not in m.get("sender") and "bot" not in m.get("receiver")]
            save_data(USERS_FILE_PATH, users_db)
            save_data(INVITES_FILE_PATH, invites)
            save_data(MESSAGES_FILE_PATH, messages)
            st.success("Test verileri tamamen silindi!")
            st.rerun()

# --- GİRİŞ SAYFASI ---
def login_page():
    st.markdown("<h1 style='text-align: center; color: #2E7D32;'>🎾 İzmir Tenis Partner Havuzu</h1>", unsafe_allow_html=True)
    users_db = load_data(USERS_FILE_PATH, default_type=dict)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        t1, t2, t3 = st.tabs(["🔑 Giriş", "📝 Kayıt", "❓ Şifremi Unuttum"])
        with t1:
            with st.form("login"):
                email = st.text_input("E-posta").strip().lower()
                password = st.text_input("Şifre", type="password")
                if st.form_submit_button("Giriş Yap"):
                    if email in users_db and users_db[email].get("password_hash") == hash_password(password):
                        if users_db[email].get("suspended"):
                            st.error("Hesabınız geçici olarak durdurulmuştur.")
                        else:
                            st.session_state.logged_in = True
                            st.session_state.current_user = email
                            st.rerun()
                    else: st.error("Hatalı e-posta veya şifre!")
        with t2:
            with st.form("register"):
                reg_email = st.text_input("E-posta Adresi").strip().lower()
                reg_pass = st.text_input("Şifre Belirle", type="password")
                reg_name = st.text_input("Ad Soyad")
                if st.form_submit_button("Kayıt Ol"):
                    if reg_email not in users_db and reg_email and reg_pass:
                        users_db[reg_email] = {
                            "password_hash": hash_password(reg_pass), "ad_soyad": reg_name or reg_email.split('@')[0],
                            "suspended": False, "is_bot": False,
                            "privacy": {"ghost": False, "show_age": True, "show_style": True},
                            "notif_prefs": {"active": False, "levels": [], "courts": [], "types": []},
                            "ratings": {"zaman": [], "seviye": [], "davranis": []}
                        }
                        save_data(USERS_FILE_PATH, users_db)
                        st.success("Kayıt başarılı! Giriş sekmesinden devam edebilirsin.")
                    else: st.error("Bu e-posta zaten kayıtlı veya bilgiler eksik.")
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
                    else: st.error("E-posta sistemde bulunamadı.")
                    
        with st.expander("👑 Yönetici Paneli"):
            admin_code = st.text_input("Yönetici Parolası", type="password")
            if st.button("Panele Gir"):
                if admin_code == ADMIN_PASS:
                    st.session_state.logged_in = True
                    st.session_state.is_admin = True
                    st.rerun()
                else: st.error("Hatalı Parola!")

# --- ANA UYGULAMA ---
def main_app():
    users_db = load_data(USERS_FILE_PATH, default_type=dict)
    invites = load_data(INVITES_FILE_PATH, default_type=list)
    messages = load_data(MESSAGES_FILE_PATH, default_type=list)
    me = users_db.get(st.session_state.current_user, {})
    
    # Üst Bilgi Barı
    c_head1, c_head2 = st.columns([4, 1])
    c_head1.write("### 🎾 İzmir Tenis Partner Havuzu")
    c_head2.write(f"👤 **{me.get('ad_soyad')}** | ⭐ {calculate_rating(me.get('ratings')):.1f}")
    if c_head2.button("🚪 Çıkış"): st.session_state.logged_in = False; st.rerun()

    tabs = st.tabs(["🏆 İlan Havuzu", "➕ İlan Oluştur", "👥 Üyeler & Meydan Oku", "📩 Kutum & Takvim", "⚖️ Değerlendirme", "⚙️ Profil & Radar"])

    with tabs[0]: # HAVUZ
        for inv in reversed([i for i in invites if i.get('status') == 'active']):
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 3, 2])
                c1.markdown(f"**📍 Kort:** {inv.get('court')} {'('+inv.get('court_custom')+')' if inv.get('court_custom') else ''}")
                c1.markdown(f"**🗓️ Tarih:** {inv.get('date')} | ⏰ **Zaman Aralığı:** {inv.get('time_details')}")
                c2.markdown(f"**🎾 Tür:** {inv.get('type')} | **⭐ Seviye:** {', '.join(inv.get('levels', []))}")
                c2.markdown(f"**🔑 Durum:** {inv.get('court_status')}")
                
                creator = users_db.get(inv.get('creator'), {})
                c3.markdown(f"👤 **Açan:** {creator.get('ad_soyad')}")
                if inv.get('creator') != st.session_state.current_user:
                    if st.button("Teklif Gönder", key=f"inv_{inv.get('id')}"):
                        messages.append({
                            "id": str(uuid.uuid4()), "type": "invite_request", "invite_id": inv.get('id'),
                            "sender": st.session_state.current_user, "receiver": inv.get('creator'),
                            "status": "pending", "timestamp": str(datetime.datetime.now())
                        })
                        save_data(MESSAGES_FILE_PATH, messages)
                        st.success("Teklifiniz ilan sahibine iletildi!")

    with tabs[1]: # İLAN OLUŞTUR (BAŞLANGIÇ VE BİTİŞ SAATİ AYRI)
        with st.form("create_invite"):
            c1, c2 = st.columns(2)
            d = c1.date_input("Tarih")
            
            c_t1, c_t2 = c1.columns(2)
            t_start = c_t1.time_input("Başlangıç Saati", datetime.time(18, 0))
            t_end = c_t2.time_input("Bitiş Saati", datetime.time(19, 30))
            t_det = f"{t_start.strftime('%H:%M')} - {t_end.strftime('%H:%M')}"

            court = c2.selectbox("Kort", IZMIR_KORTLARI)
            court_custom = c2.text_input("Diğer ise belirtin:") if court == "Diğer" else ""
            court_status = c2.selectbox("Kort Rezervasyon Durumu", COURT_STATUS)
            
            act_type = st.selectbox("Etkinlik Tipi", ACTIVITY_TYPES)
            levels = st.multiselect("Aranan Seviyeler", NTRP_LEVELS, default=["4.0"])
            
            if st.form_submit_button("İlanı Yayınla"):
                if not levels: st.error("Lütfen en az bir seviye seçin.")
                else:
                    new_inv = {
                        "id": str(uuid.uuid4()), "creator": st.session_state.current_user,
                        "date": str(d), "time_details": t_det,
                        "court": court, "court_custom": court_custom, "court_status": court_status,
                        "type": act_type, "levels": levels, "status": "active"
                    }
                    invites.append(new_inv)
                    save_data(INVITES_FILE_PATH, invites)
                    st.success("İlan yayınlandı!")
                    st.rerun()

    with tabs[2]: # ÜYELER & DOĞRUDAN TEKLİF (BAŞLANGIÇ VE BİTİŞ SAATİ AYRI)
        if st.session_state.offer_to:
            target = st.session_state.offer_to
            st.info(f"👉 **{users_db[target].get('ad_soyad')}** kişisine teklif gönderiyorsunuz.")
            with st.form("direct_offer"):
                o_date = st.date_input("Tarih Önerisi")
                
                c_ot1, c_ot2 = st.columns(2)
                o_start = c_ot1.time_input("Başlangıç Saati", datetime.time(18, 0))
                o_end = c_ot2.time_input("Bitiş Saati", datetime.time(19, 30))
                o_time = f"{o_start.strftime('%H:%M')} - {o_end.strftime('%H:%M')}"
                
                o_court = st.selectbox("Kort", IZMIR_KORTLARI)
                o_note = st.text_area("Özel Not")
                c_sub, c_can = st.columns(2)
                if c_sub.form_submit_button("Gönder"):
                    messages.append({
                        "id": str(uuid.uuid4()), "type": "direct_challenge",
                        "sender": st.session_state.current_user, "receiver": target,
                        "date": str(o_date), "time": o_time, "court": o_court, "note": o_note,
                        "status": "pending"
                    })
                    save_data(MESSAGES_FILE_PATH, messages)
                    st.session_state.offer_to = None
                    st.success("Teklif iletildi!"); st.rerun()
                if c_can.form_submit_button("İptal"):
                    st.session_state.offer_to = None; st.rerun()

        for u_email, u_data in users_db.items():
            if u_email == st.session_state.current_user or u_data.get("privacy", {}).get("ghost"): continue
            with st.container(border=True):
                colA, colB, colC = st.columns([2,3,1])
                colA.markdown(f"**👤 {u_data.get('ad_soyad')}** | ⭐ {calculate_rating(u_data.get('ratings')):.1f}")
                
                det = []
                if u_data.get("privacy", {}).get("show_age") and u_data.get("age"): det.append(f"Yaş: {u_data.get('age')}")
                if u_data.get("privacy", {}).get("show_style") and u_data.get("style"): det.append(f"Tarz: {u_data.get('style')}")
                if u_data.get("hand"): det.append(f"El: {u_data.get('hand')}")
                colB.write(" | ".join(det) if det else "")
                
                if colC.button("🎾 Teklif Gönder", key=f"chall_{u_email}"):
                    st.session_state.offer_to = u_email; st.rerun()

    with tabs[3]: # KUTUM VE TAKVİM
        st.subheader("Gelen Teklifler")
        my_inbox = [m for m in messages if m.get('receiver') == st.session_state.current_user and m.get('status') == 'pending']
        if not my_inbox: st.write("Bekleyen bir teklifiniz yok.")
        
        for msg in my_inbox:
            with st.container(border=True):
                sender_name = users_db.get(msg['sender'], {}).get('ad_soyad')
                if msg['type'] == 'invite_request': st.write(f"🔔 **{sender_name}** ilanınıza katılmak istiyor!")
                else: st.write(f"⚔️ **{sender_name}** sana teklif gönderdi! (🗓️ {msg.get('date')} | ⏰ {msg.get('time')} | 📍 {msg.get('court')} | 📝 {msg.get('note')})")
                
                c_acc, c_rej = st.columns(2)
                if c_acc.button("✅ Kabul Et", key=f"acc_{msg['id']}"):
                    msg['status'] = 'accepted'
                    t_str = msg.get('time', '18:00 - 19:30')
                    msg['calendar_link'] = generate_gcal_link("Tenis Maçı", msg.get('date', str(datetime.date.today())), t_str, msg.get('court', 'Kort'))
                    save_data(MESSAGES_FILE_PATH, messages)
                    st.success("Kabul edildi!"); st.rerun()
                if c_rej.button("❌ Reddet", key=f"rej_{msg['id']}"):
                    msg['status'] = 'rejected'
                    save_data(MESSAGES_FILE_PATH, messages); st.rerun()

        st.subheader("Kabul Edilmiş Maçlarım (Takvim)")
        my_acc = [m for m in messages if (m.get('receiver') == st.session_state.current_user or m.get('sender') == st.session_state.current_user) and m.get('status') == 'accepted']
        for acc in reversed(my_acc):
            partner = acc['sender'] if acc['receiver'] == st.session_state.current_user else acc['receiver']
            st.info(f"🤝 **{users_db.get(partner, {}).get('ad_soyad')}** ile maç onaylı. [📅 Google Takvimine Ekle]({acc.get('calendar_link', '#')})")

    with tabs[4]: # ETKİNLİK BAZLI DEĞERLENDİRME
        st.subheader("Etkinlik Bazlı Oyuncu Değerlendirme")
        
        accepted_events = [m for m in messages if (m.get('receiver') == st.session_state.current_user or m.get('sender') == st.session_state.current_user) and m.get('status') == 'accepted']
        unrated_events = [m for m in accepted_events if st.session_state.current_user not in m.get('rated_by', [])]
        
        if not unrated_events:
            st.info("Değerlendirebileceğiniz tamamlanmış / onaylanmış yeni bir etkinlik bulunmuyor.")
        else:
            with st.form("rating_form"):
                def format_event(m):
                    partner_email = m['sender'] if m['receiver'] == st.session_state.current_user else m['receiver']
                    p_name = users_db.get(partner_email, {}).get('ad_soyad', 'Kullanıcı')
                    return f"Tarih: {m.get('date', 'Belirtilmemiş')} | Kort: {m.get('court', 'Kort')} | Rakip: {p_name}"
                
                selected_event_id = st.selectbox("Değerlendirilecek Etkinlik / Maç", options=[m['id'] for m in unrated_events], format_func=lambda eid: format_event(next(m for m in unrated_events if m['id'] == eid)))
                
                st.markdown("**(1: Çok Kötü - 5: Çok İyi)**")
                sz = st.slider("⏱️ Zaman Planlaması (Söz verilen saatte geldi mi?)", 1, 5, 5)
                ss = st.slider("🎾 Seviye Tutarlılığı (Belirttiği NTRP seviyesine uygun mu?)", 1, 5, 5)
                sd = st.slider("🤝 Kort İçi Davranış & Sportmenlik", 1, 5, 5)
                
                if st.form_submit_button("Değerlendirmeyi Kaydet"):
                    target_event = next(m for m in unrated_events if m['id'] == selected_event_id)
                    partner_email = target_event['sender'] if target_event['receiver'] == st.session_state.current_user else target_event['receiver']
                    
                    if partner_email in users_db:
                        r_db = users_db[partner_email].setdefault("ratings", {"zaman": [], "seviye": [], "davranis": []})
                        r_db.setdefault("zaman", []).append(sz)
                        r_db.setdefault("seviye", []).append(ss)
                        r_db.setdefault("davranis", []).append(sd)
                        save_data(USERS_FILE_PATH, users_db)
                        
                        target_event.setdefault('rated_by', []).append(st.session_state.current_user)
                        save_data(MESSAGES_FILE_PATH, messages)
                        st.success("Değerlendirmeniz başarıyla kaydedildi!")
                        st.rerun()

    with tabs[5]: # PROFİL & RADAR
        colL, colR = st.columns(2)
        with colL:
            st.subheader("Profil")
            with st.form("profile_form"):
                ad = st.text_input("Ad Soyad", value=me.get("ad_soyad", ""))
                age = st.text_input("Yaş", value=me.get("age", ""))
                hand = st.selectbox("El", ["Sağ", "Sol", "İki El"], index=["Sağ", "Sol", "İki El"].index(me.get("hand", "Sağ")) if me.get("hand") else 0)
                style = st.selectbox("Oyun Tarzı", ["Agresif Baseline", "Servis & Vole", "Defansif / Karşılayıcı", "All-Rounder"], index=0)
                bio = st.text_area("Biyografi / Not", value=me.get("bio", ""))
                if st.form_submit_button("Güncelle"):
                    me.update({"ad_soyad": ad, "age": age, "hand": hand, "style": style, "bio": bio})
                    users_db[st.session_state.current_user] = me
                    save_data(USERS_FILE_PATH, users_db)
                    st.success("Güncellendi!")

            st.subheader("Gizlilik")
            with st.form("privacy_form"):
                priv = me.setdefault("privacy", {"ghost": False, "show_age": True, "show_style": True})
                ghost = st.toggle("👻 Hayalet Modu (Gizle)", value=priv.get("ghost", False))
                s_age = st.checkbox("Yaşı göster", value=priv.get("show_age", True))
                s_style = st.checkbox("Tarzı göster", value=priv.get("show_style", True))
                if st.form_submit_button("Kaydet"):
                    me["privacy"] = {"ghost": ghost, "show_age": s_age, "show_style": s_style}
                    users_db[st.session_state.current_user] = me
                    save_data(USERS_FILE_PATH, users_db); st.success("Kaydedildi!")

        with colR:
            st.subheader("Radar Bildirimleri")
            with st.form("radar_form"):
                notif = me.setdefault("notif_prefs", {"active": False, "levels": [], "courts": [], "types": []})
                active = st.toggle("🔔 Radarı Aktif Et", value=notif.get("active", False))
                r_levels = st.multiselect("Seviyeler", NTRP_LEVELS, default=notif.get("levels", []))
                r_courts = st.multiselect("Kortlar", IZMIR_KORTLARI, default=notif.get("courts", []))
                r_types = st.multiselect("Türler", ACTIVITY_TYPES, default=notif.get("types", []))
                if st.form_submit_button("Radarı Kur"):
                    me["notif_prefs"] = {"active": active, "levels": r_levels, "courts": r_courts, "types": r_types}
                    users_db[st.session_state.current_user] = me
                    save_data(USERS_FILE_PATH, users_db); st.success("Radar ayarlandı!")

# Ana tetikleyici
if not st.session_state.logged_in: login_page()
elif st.session_state.is_admin: admin_dashboard()
else: main_app()
