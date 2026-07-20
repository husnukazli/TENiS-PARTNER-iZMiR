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
    # Takvim linki oluşturucu
    try:
        dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        end_dt = dt + datetime.timedelta(hours=1, minutes=30) # Varsayılan 1.5 saat
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

# --- OTURUM YÖNETİMİ ---
for key in ['logged_in', 'is_admin', 'current_user', 'offer_to']:
    if key not in st.session_state: st.session_state[key] = False if key in ['logged_in', 'is_admin'] else None

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
                            "privacy": {"ghost": False, "show_age": True, "show_style": True},
                            "notif_prefs": {"active": False, "levels": [], "courts": [], "types": []},
                            "ratings": {"zaman": [], "seviye": [], "davranis": []}
                        }
                        save_data(USERS_FILE_PATH, users_db)
                        st.success("Kayıt başarılı! Giriş sekmesinden devam edebilirsin.")
                    else: st.error("Bu e-posta zaten kayıtlı veya bilgiler eksik.")
        with t3:
            with st.form("forgot_pass"):
                st.info("Sisteme kayıtlı e-posta adresinizi girin. Yeni şifreniz mailinize gönderilecektir.")
                reset_email = st.text_input("E-posta Adresi").strip().lower()
                if st.form_submit_button("Şifremi Sıfırla"):
                    if reset_email in users_db:
                        new_pass = generate_temp_password()
                        users_db[reset_email]["password_hash"] = hash_password(new_pass)
                        save_data(USERS_FILE_PATH, users_db)
                        send_email(reset_email, "Şifre Sıfırlama Talebi", f"Yeni geçici şifreniz: <b>{new_pass}</b><br>Giriş yaptıktan sonra profilinizden değiştirebilirsiniz.")
                        st.success("Yeni şifreniz e-posta adresinize gönderildi!")
                    else: st.error("Bu e-posta adresi sistemde bulunamadı.")

def calculate_rating(ratings_dict):
    if not ratings_dict: return 5.0
    all_scores = ratings_dict.get("zaman", []) + ratings_dict.get("seviye", []) + ratings_dict.get("davranis", [])
    return sum(all_scores) / len(all_scores) if all_scores else 5.0

def trigger_notifications(new_invite, users_db):
    for u_email, u_data in users_db.items():
        if u_email == st.session_state.current_user: continue
        prefs = u_data.get("notif_prefs", {})
        if not prefs.get("active"): continue
        
        # Kriter eşleşme kontrolü (Listelerden en az biri örtüşüyorsa)
        lvl_match = set(new_invite['levels']).intersection(set(prefs.get('levels', []))) if prefs.get('levels') else True
        crt_match = (new_invite['court'] in prefs.get('courts', [])) if prefs.get('courts') else True
        typ_match = (new_invite['type'] in prefs.get('types', [])) if prefs.get('types') else True
        
        if lvl_match and crt_match and typ_match:
            msg = f"Merhaba, aradığınız kriterlere uygun yeni bir ilan açıldı!<br><br><b>Kort:</b> {new_invite['court']}<br><b>Tarih:</b> {new_invite['date']}<br><b>Seviye:</b> {', '.join(new_invite['levels'])}<br><br>Sisteme girip inceleyebilirsiniz."
            send_email(u_email, "Radar: Yeni İlan Bulundu!", msg)

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

    tabs = st.tabs(["🏆 İlan Havuzu", "➕ İlan Oluştur", "👥 Üyeler & Meydan Oku", "📩 Kutum & Takvim", "⚖️ Değerlendirme", "⚙️ Profil & Radar"] + (["🛠️ Admin"] if st.session_state.is_admin else []))

    with tabs[0]: # 1. İLAN HAVUZU
        st.subheader("Aktif İlanlar")
        for inv in reversed([i for i in invites if i.get('status') == 'active']):
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 3, 2])
                c1.markdown(f"**📍 Kort:** {inv.get('court')} {'('+inv.get('court_custom')+')' if inv.get('court_custom') else ''}")
                c1.markdown(f"**🗓️ Tarih:** {inv.get('date')} | ⏰ **Saat:** {inv.get('time_details')}")
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

    with tabs[1]: # 2. DAVET OLUŞTUR
        with st.form("create_invite"):
            c1, c2 = st.columns(2)
            d = c1.date_input("Tarih")
            time_mode = c1.radio("Zaman Durumu", ["Belirli Saat", "Esnek Aralık"])
            if time_mode == "Belirli Saat":
                t_det = str(c1.time_input("Saat"))
            else:
                ts = c1.time_input("Başlangıç Müsaitliği", datetime.time(10, 0))
                te = c1.time_input("Bitiş Müsaitliği", datetime.time(16, 0))
                t_det = f"{ts} - {te} arası"

            court = c2.selectbox("Kort", IZMIR_KORTLARI)
            court_custom = c2.text_input("Diğer ise belirtin:") if court == "Diğer" else ""
            court_status = c2.selectbox("Kort Rezervasyon Durumu", COURT_STATUS)
            
            act_type = st.selectbox("Etkinlik Tipi", ACTIVITY_TYPES)
            levels = st.multiselect("Aranan Seviyeler (Birden fazla seçilebilir)", NTRP_LEVELS, default=["4.0"])
            
            if st.form_submit_button("İlanı Yayınla"):
                if not levels: st.error("Lütfen en az bir seviye seçin.")
                else:
                    new_inv = {
                        "id": str(uuid.uuid4()), "creator": st.session_state.current_user,
                        "date": str(d), "time_mode": time_mode, "time_details": t_det,
                        "court": court, "court_custom": court_custom, "court_status": court_status,
                        "type": act_type, "levels": levels, "status": "active"
                    }
                    invites.append(new_inv)
                    save_data(INVITES_FILE_PATH, invites)
                    trigger_notifications(new_inv, users_db) # RADAR TETİKLEYİCİ
                    st.success("İlan başarıyla havuzda yayınlandı!")
                    st.rerun()

    with tabs[2]: # 3. ÜYELER VE DOĞRUDAN TEKLİF
        st.subheader("Oyuncu Listesi")
        if st.session_state.offer_to:
            target = st.session_state.offer_to
            st.info(f"👉 **{users_db[target].get('ad_soyad')}** kişisine özel meydan okuma / teklif gönderiyorsunuz.")
            with st.form("direct_offer"):
                o_date = st.date_input("Tarih Önerisi")
                o_time = st.text_input("Saat veya Aralık Önerisi (Örn: 19:00 veya Akşamları)")
                o_court = st.selectbox("Kort Planı", IZMIR_KORTLARI)
                o_note = st.text_area("Özel Notunuz", "Geçen haftaki maç çok iyiydi, tekrar oynayalım mı?")
                c_submit, c_cancel = st.columns(2)
                if c_submit.form_submit_button("Teklifi Gönder"):
                    messages.append({
                        "id": str(uuid.uuid4()), "type": "direct_challenge",
                        "sender": st.session_state.current_user, "receiver": target,
                        "date": str(o_date), "time": o_time, "court": o_court, "note": o_note,
                        "status": "pending", "timestamp": str(datetime.datetime.now())
                    })
                    save_data(MESSAGES_FILE_PATH, messages)
                    st.session_state.offer_to = None
                    st.success("Özel teklifiniz iletildi!")
                    st.rerun()
                if c_cancel.form_submit_button("İptal"):
                    st.session_state.offer_to = None; st.rerun()

        for u_email, u_data in users_db.items():
            if u_email == st.session_state.current_user: continue
            if u_data.get("privacy", {}).get("ghost"): continue # Hayalet modundaysa gizle
            
            with st.container(border=True):
                colA, colB, colC = st.columns([2,3,1])
                colA.markdown(f"**👤 {u_data.get('ad_soyad')}**")
                colA.markdown(f"⭐ Puan: {calculate_rating(u_data.get('ratings')):.1f}")
                
                det = []
                if u_data.get("privacy", {}).get("show_age") and u_data.get("age"): det.append(f"Yaş: {u_data.get('age')}")
                if u_data.get("privacy", {}).get("show_style") and u_data.get("style"): det.append(f"Tarz: {u_data.get('style')}")
                if u_data.get("hand"): det.append(f"El: {u_data.get('hand')}")
                colB.write(" | ".join(det) if det else "Ek bilgi yok.")
                
                if colC.button("🎾 Teklif Gönder", key=f"chall_{u_email}"):
                    st.session_state.offer_to = u_email; st.rerun()

    with tabs[3]: # 4. KUTUM VE TAKVİM
        st.subheader("Gelen Teklifler")
        my_inbox = [m for m in messages if m.get('receiver') == st.session_state.current_user and m.get('status') == 'pending']
        if not my_inbox: st.write("Şu an bekleyen bir teklifiniz yok.")
        
        for msg in my_inbox:
            with st.container(border=True):
                sender_name = users_db.get(msg['sender'], {}).get('ad_soyad')
                if msg['type'] == 'invite_request':
                    st.write(f"🔔 **{sender_name}** havuzdaki bir ilanınıza katılmak istiyor!")
                else:
                    st.write(f"⚔️ **{sender_name}** size özel bir teklif gönderdi!")
                    st.write(f"🗓️ {msg.get('date')} | ⏰ {msg.get('time')} | 📍 {msg.get('court')}")
                    st.write(f"📝 Not: *{msg.get('note')}*")
                
                c_acc, c_rej = st.columns(2)
                if c_acc.button("✅ Kabul Et", key=f"acc_{msg['id']}"):
                    msg['status'] = 'accepted'
                    # Takvim Linki Oluştur
                    cal_time = msg.get('time', '12:00').split('-')[0].strip()[:5] if msg.get('time') else "12:00"
                    cal_link = generate_gcal_link("Tenis Maçı", msg.get('date', str(datetime.date.today())), cal_time, msg.get('court', 'Kort'))
                    msg['calendar_link'] = cal_link
                    save_data(MESSAGES_FILE_PATH, messages)
                    send_email(msg['sender'], "Teklifin Kabul Edildi!", f"{me.get('ad_soyad')} teklifini kabul etti! Takvime ekle: {cal_link}")
                    st.success("Kabul edildi! Takvim linki oluşturuldu.")
                    st.rerun()
                if c_rej.button("❌ Reddet", key=f"rej_{msg['id']}"):
                    msg['status'] = 'rejected'
                    save_data(MESSAGES_FILE_PATH, messages)
                    st.rerun()

        st.subheader("Kabul Edilmiş Maçlarım (Takvime Ekle)")
        my_accepted = [m for m in messages if (m.get('receiver') == st.session_state.current_user or m.get('sender') == st.session_state.current_user) and m.get('status') == 'accepted']
        for acc in reversed(my_accepted):
            partner = acc['sender'] if acc['receiver'] == st.session_state.current_user else acc['receiver']
            st.info(f"🤝 **{users_db.get(partner, {}).get('ad_soyad')}** ile maçınız onaylı. [📅 Google Takvimine Ekle]({acc.get('calendar_link', '#')})")

    with tabs[4]: # 5. 3 KRİTERLİ DEĞERLENDİRME
        st.subheader("Rakibini Değerlendir")
        with st.form("rating_form"):
            u_list = {k: v.get("ad_soyad") for k,v in users_db.items() if k != st.session_state.current_user}
            selected = st.selectbox("Değerlendirilecek Üye", options=list(u_list.keys()), format_func=lambda x: u_list[x])
            
            st.markdown("**(1: Çok Kötü - 5: Çok İyi)**")
            score_zaman = st.slider("⏱️ Zaman Planlaması (Söz verilen saatte geldi mi?)", 1, 5, 5)
            score_seviye = st.slider("🎾 Seviye Tutarlılığı (Belirttiği NTRP seviyesine uygun oynuyor mu?)", 1, 5, 5)
            score_davranis = st.slider("🤝 Kort İçi Davranış & Sportmenlik", 1, 5, 5)
            
            if st.form_submit_button("Oyu Kaydet"):
                r_db = users_db[selected].setdefault("ratings", {"zaman": [], "seviye": [], "davranis": []})
                r_db.setdefault("zaman", []).append(score_zaman)
                r_db.setdefault("seviye", []).append(score_seviye)
                r_db.setdefault("davranis", []).append(score_davranis)
                save_data(USERS_FILE_PATH, users_db)
                st.success("Değerlendirme kaydedildi, teşekkürler!")

    with tabs[5]: # 6. PROFİL, GİZLİLİK VE RADAR
        colL, colR = st.columns(2)
        with colL:
            st.subheader("Profil Bilgileri")
            with st.form("profile_form"):
                ad = st.text_input("Ad Soyad", value=me.get("ad_soyad", ""))
                age = st.text_input("Yaş / Yaş Aralığı", value=me.get("age", ""))
                hand = st.selectbox("Kullandığı El", ["Sağ", "Sol", "İki El"], index=["Sağ", "Sol", "İki El"].index(me.get("hand", "Sağ")))
                style = st.selectbox("Oyun Tarzı", ["Agresif Baseline", "Servis & Vole", "Defansif / Karşılayıcı", "All-Rounder", "Belirtmek İstemiyorum"], index=0)
                bio = st.text_area("Biyografi / Kort Notu", value=me.get("bio", ""))
                if st.form_submit_button("Profili Güncelle"):
                    me.update({"ad_soyad": ad, "age": age, "hand": hand, "style": style, "bio": bio})
                    users_db[st.session_state.current_user] = me
                    save_data(USERS_FILE_PATH, users_db)
                    st.success("Profil güncellendi!")

            st.subheader("Gizlilik Ayarları")
            with st.form("privacy_form"):
                priv = me.setdefault("privacy", {"ghost": False, "show_age": True, "show_style": True})
                ghost = st.toggle("👻 Hayalet Modu (Üye listesinde beni tamamen gizle)", value=priv.get("ghost", False))
                show_age = st.checkbox("Yaşımı üye listesinde göster", value=priv.get("show_age", True))
                show_style = st.checkbox("Oyun tarzımı üye listesinde göster", value=priv.get("show_style", True))
                if st.form_submit_button("Gizliliği Kaydet"):
                    me["privacy"] = {"ghost": ghost, "show_age": show_age, "show_style": show_style}
                    users_db[st.session_state.current_user] = me
                    save_data(USERS_FILE_PATH, users_db)
                    st.success("Gizlilik ayarları kaydedildi!")

        with colR:
            st.subheader("Radar (Otomatik Bildirim Sistemi)")
            st.info("Aşağıdaki kriterlere uygun bir ilan havuza düştüğünde sistem size otomatik e-posta atar.")
            with st.form("radar_form"):
                notif = me.setdefault("notif_prefs", {"active": False, "levels": [], "courts": [], "types": []})
                active = st.toggle("🔔 Radarı Aktif Et", value=notif.get("active", False))
                r_levels = st.multiselect("Hangi seviyeleri arıyorsun?", NTRP_LEVELS, default=notif.get("levels", []))
                r_courts = st.multiselect("Hangi kortları takip ediyorsun?", IZMIR_KORTLARI, default=notif.get("courts", []))
                r_types = st.multiselect("Hangi etkinlik tipi?", ACTIVITY_TYPES, default=notif.get("types", []))
                
                if st.form_submit_button("Radarı Kur"):
                    me["notif_prefs"] = {"active": active, "levels": r_levels, "courts": r_courts, "types": r_types}
                    users_db[st.session_state.current_user] = me
                    save_data(USERS_FILE_PATH, users_db)
                    st.success("Radar ayarlandı! Aradığın ilan düştüğünde mail alacaksın.")

    if st.session_state.is_admin:
        with st.expander("🛠️ Admin Paneli (Sadece Yöneticiler)", expanded=True):
            st.download_button("Veritabanını İndir", json.dumps({"users": users_db, "invites": invites, "messages": messages}), "yedek.json")

# Ana tetikleyici
if not st.session_state.logged_in: login_page()
else: main_app()
