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
SMTP_USER = st.secrets.get("SMTP_USER", "") # İleride gerçek mail atmak için eklenecek
SMTP_PASS = st.secrets.get("SMTP_PASS", "") 

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
        # Mail ayarları girilmediyse hata vermesin, konsola/sisteme simüle etsin
        print(f"[MAIL SİMÜLASYONU] Kime: {to_address} | Konu: {subject}\nMesaj: {message}")
        return
    try:
        msg = MIMEText(message, 'html', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = SMTP_USER
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

# --- VERİTABANI İŞLEMLERİ (GITHUB & LOKAL) ---
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
    st.write("")
    
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
                    else:
                        st.error("Hatalı e-posta veya şifre.")
                        
        with tab2:
            with st.form("register_form"):
                reg_email = st.text_input("E-posta Adresi (Yeni)").strip().lower()
                reg_pass1 = st.text_input("Şifre Belirleyin", type="password")
                reg_pass2 = st.text_input("Şifre Tekrar", type="password")
                reg_submit = st.form_submit_button("Kayıt Ol", type="primary", use_container_width=True)
                
                if reg_submit:
                    if reg_email in users_db:
                        st.error("Bu e-posta zaten kayıtlı!")
                    elif reg_pass1 != reg_pass2:
                        st.error("Şifreler uyuşmuyor!")
                    elif len(reg_pass1) < 4:
                        st.warning("Şifre çok kısa!")
                    else:
                        users_db[reg_email] = {
                            "password_hash": hash_password(reg_pass1),
                            "ad_soyad": reg_email.split('@')[0],
                            "seviye": "4.0",
                            "ratings": [] 
                        }
                        if save_data(USERS_FILE_PATH, users_db):
                            st.success("Kayıt başarılı! Lütfen 'Giriş Yap' sekmesinden giriş yapın.")
                        else:
                            st.error("Kayıt oluşturulamadı (Sunucu hatası).")
        
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
                            st.success(f"Geçici şifreniz oluşturuldu! (Test aşaması için ekranda gösteriliyor): **{temp_pass}**")
                            st.info("Lütfen giriş yaptıktan sonra Profil Ayarları'ndan şifrenizi değiştirin.")
                        else:
                            st.error("Sistem hatası oluştu.")
                    else:
                        st.error("Bu e-posta adresi sistemde kayıtlı değil.")

def get_avg_rating(prof):
    ratings = prof.get("ratings", [])
    if not ratings: return 5.0 
    return sum(ratings) / len(ratings)

def main_app():
    st.sidebar.title("🎾 Navigasyon")
    menu = st.sidebar.radio("Seçenekler", [
        "🏆 Havuz (Açık İlanlar)", 
        "➕ Davet Oluştur", 
        "👥 Üyeler", 
        "⚖️ Geçmiş Maçlar & Değerlendirme",
        "⚙️ Profil Ayarları"
    ])
    
    users_db = load_data(USERS_FILE_PATH, default_type=dict)
    invites = load_data(INVITES_FILE_PATH, default_type=list)
    current_user_profile = users_db.get(st.session_state.current_user, {})
    
    st.sidebar.markdown("---")
    isim_gosterim = current_user_profile.get("ad_soyad", st.session_state.current_user.split('@')[0])
    puan = get_avg_rating(current_user_profile)
    st.sidebar.write(f"👤 **{isim_gosterim}** (⭐ {puan:.1f})")
    
    if st.sidebar.button("Çıkış Yap"):
        st.session_state.logged_in = False
        st.rerun()

    if menu == "🏆 Havuz (Açık İlanlar)":
        st.header("Güncel Eşleşme Havuzu")
        
        if not invites:
            st.info("Şu an havuzda bekleyen bir davet yok.")
        else:
            with st.expander("🔍 İlanları Filtrele"):
                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1: filter_type = st.selectbox("Davet Tipi", ["Tümü", "Sabit (Kesin Kort)", "Esnek (Zaman/Bölge)"])
                with f_col2: filter_level = st.selectbox("Seviye (NTRP)", ["Tümü"] + NTRP_LEVELS)
                with f_col3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    hide_matched = st.checkbox("Sadece Bekleyenleri Göster", value=True)
            
            filtered_invites = []
            for inv in invites:
                if filter_type != "Tümü" and filter_type.split()[0] != inv.get('type'): continue
                if filter_level != "Tümü" and inv.get('level') != filter_level: continue
                if hide_matched and inv.get('matched'): continue
                filtered_invites.append(inv)

            filtered_invites.sort(key=lambda x: (x['date'], x['time']))
            st.markdown("---")
            
            for invite in filtered_invites:
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2, 2, 2])
                    
                    creator_prof = users_db.get(invite['creator'], {})
                    creator_name = creator_prof.get("ad_soyad", invite['creator'].split('@')[0])
                    
                    with col1:
                        badge = "🎯 Sabit" if invite.get('type') == "Sabit" else "🤝 Esnek"
                        st.markdown(f"**{badge}** | {invite.get('event_type', 'Maç veya Antrenman')}")
                        st.markdown(f"🗓️ **{invite['date']}** | ⏰ **{invite['time']}**")
                        st.markdown(f"📍 **{invite['court']}**")
                    with col2:
                        st.markdown(f"👤 **Oyuncu:** {creator_name} (⭐ {get_avg_rating(creator_prof):.1f})")
                        st.markdown(f"⭐ **Aranan Seviye:** {invite['level']} NTRP")
                        if invite.get('notes'):
                            st.caption(f"📝 Not: {invite['notes']}")
                    
                    with col3:
                        offers = invite.get('offers', [])
                        
                        if invite.get('matched'):
                            matched_email = invite.get('matched_with')
                            matched_prof = users_db.get(matched_email, {})
                            matched_name = matched_prof.get("ad_soyad", matched_email.split('@')[0])
                            st.success(f"✅ {matched_name} ile eşleşti")
                            
                            if st.session_state.current_user in [invite['creator'], matched_email]:
                                ics_data = generate_ics(invite['date'], invite['time'], invite['court'], invite.get('event_type','Tenis'), invite.get('notes',''))
                                st.download_button(label="📅 Takvime Ekle", data=ics_data, file_name=f"tenis_maci_{invite['date']}.ics", mime="text/calendar")
                        
                        elif invite['creator'] == st.session_state.current_user:
                            st.info(f"📩 Gelen Teklifler ({len(offers)})")
                            for offer_email in offers:
                                offer_prof = users_db.get(offer_email, {})
                                offer_name = offer_prof.get("ad_soyad", offer_email.split('@')[0])
                                if st.button(f"✅ {offer_name} - Kabul Et", key=f"accept_{invite['id']}_{offer_email}"):
                                    invite['matched'] = True
                                    invite['matched_with'] = offer_email
                                    if save_data(INVITES_FILE_PATH, invites):
                                        send_email(offer_email, "Teklifiniz Kabul Edildi!", f"Merhaba, {invite['date']} tarihli tenis teklifiniz {creator_name} tarafından kabul edildi!")
                                        st.success("Eşleşme tamamlandı!")
                                        st.rerun()
                        else:
                            st.markdown("<br>", unsafe_allow_html=True)
                            if st.session_state.current_user in offers:
                                st.button("⏳ Teklif Gönderildi", disabled=True, use_container_width=True, key=f"wait_{invite['id']}")
                            else:
                                if st.button("🙋‍♂️ Teklif Gönder", key=f"offer_{invite['id']}", type="primary", use_container_width=True):
                                    if 'offers' not in invite: invite['offers'] = []
                                    invite['offers'].append(st.session_state.current_user)
                                    if save_data(INVITES_FILE_PATH, invites):
                                        curr_name = current_user_profile.get("ad_soyad", "Bir oyuncu")
                                        send_email(invite['creator'], "İlanınıza Yeni Teklif Var!", f"{curr_name} isimli oyuncu {invite['date']} tarihli ilanınıza teklif gönderdi.")
                                        st.success("Teklifiniz iletildi!")
                                        st.rerun()

    elif menu == "➕ Davet Oluştur":
        st.header("Yeni Partner Daveti")
        with st.container(border=True):
            davet_turu = st.radio("Davet Durumunuz Nedir?", ["🎯 Kortumu ayırttım (Sabit)", "🤝 Birlikte belirleyeceğiz (Esnek)"], horizontal=True)
            with st.form("new_invite"):
                
                event_type = st.radio("Etkinlik Türü", ["🏆 Maç (Puanlı/Setli)", "🎾 Antrenman / Ralli", "🤷‍♂️ Maç veya Antrenman Fark Etmez"], horizontal=True)
                
                date = st.date_input("Tarih")
                col1, col2 = st.columns(2)
                
                if "ayırttım" in davet_turu:
                    with col1: time_str = st.time_input("Kesin Saat").strftime("%H:%M")
                    with col2:
                        court = st.selectbox("Kort Seçimi", IZMIR_KORTLARI)
                        if court == "Diğer": court = st.text_input("Kort adını giriniz")
                    invite_tag = "Sabit"
                else:
                    with col1:
                        st.write("Müsaitlik Aralığı")
                        t1, t2 = st.columns(2)
                        with t1: start_time = st.time_input("Şu saatten...", value=datetime.time(9,0))
                        with t2: end_time = st.time_input("...şu saate kadar", value=datetime.time(18,0))
                        time_str = f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} Arası"
                    with col2:
                        court = st.selectbox("Bölge Tercihi", ["Farketmez", "Karşıyaka / Çiğli", "Alsancak / Bornova", "Balçova / Narlıdere"])
                    invite_tag = "Esnek"
                
                st.markdown("---")
                col3, col4 = st.columns(2)
                with col3: level = st.selectbox("Aranan Seviye (NTRP)", NTRP_LEVELS, index=6)
                with col4: notes = st.text_area("Ekstra Notlar (Örn: 3 kişiyiz, 4. aranıyor)", max_chars=150)
                
                submitted = st.form_submit_button("Havuza Gönder", type="primary", use_container_width=True)
                
                if submitted:
                    new_invite = {
                        "id": str(datetime.datetime.now().timestamp()),
                        "creator": st.session_state.current_user,
                        "type": invite_tag,
                        "event_type": event_type.split()[1], 
                        "date": str(date),
                        "time": time_str,
                        "court": court,
                        "level": level,
                        "notes": notes,
                        "matched": False,
                        "offers": [],
                        "rated_by": [] 
                    }
                    invites.append(new_invite)
                    if save_data(INVITES_FILE_PATH, invites):
                        st.success("Davetiniz eklendi!")
                        
                        for email, prof in users_db.items():
                            if email != st.session_state.current_user and prof.get('seviye') == level:
                                send_email(email, f"Seviyenize Uygun Yeni İlan ({level} NTRP)", f"Merhaba, havuzda {level} NTRP seviyesinde {court} bölgesi için yeni bir ilan açıldı!")
                    else:
                        st.error("Kayıt hatası.")

    elif menu == "⚖️ Geçmiş Maçlar & Değerlendirme":
        st.header("Maç Değerlendirmeleri")
        st.markdown("Oynadığınız maçları değerlendirerek topluluğun güvenilirlik puanına katkıda bulunun. **Puanlar tamamen gizli tutulur.**")
        
        past_matches = []
        for inv in invites:
            if inv.get('matched') == True:
                if inv['creator'] == st.session_state.current_user or inv.get('matched_with') == st.session_state.current_user:
                    inv_date = datetime.datetime.strptime(inv['date'], "%Y-%m-%d").date()
                    if inv_date <= datetime.date.today():
                        past_matches.append(inv)
        
        if not past_matches:
            st.info("Değerlendirilecek geçmiş bir eşleşmeniz bulunmuyor.")
        else:
            for match in past_matches:
                opponent_email = match.get('matched_with') if match['creator'] == st.session_state.current_user else match['creator']
                opp_name = users_db.get(opponent_email, {}).get("ad_soyad", opponent_email.split('@')[0])
                
                with st.container(border=True):
                    st.write(f"🗓️ **{match['date']} | 📍 {match['court']} | 👤 Rakip/Partner: {opp_name}**")
                    
                    rated_by = match.get('rated_by', [])
                    if st.session_state.current_user in rated_by:
                        st.success("Bu maçı zaten değerlendirdiniz. Teşekkürler!")
                    else:
                        with st.form(f"rate_form_{match['id']}"):
                            c1 = st.slider("Katılım ve Zamanlama (Söz verilen saatte geldi mi?)", 1.0, 5.0, 5.0, 0.5)
                            c2 = st.slider("Seviye Doğruluğu (Belirttiği NTRP seviyesinde oynuyor mu?)", 1.0, 5.0, 5.0, 0.5)
                            c3 = st.slider("Kort İçi Tutum ve Fair-Play", 1.0, 5.0, 5.0, 0.5)
                            submit_rate = st.form_submit_button("Değerlendirmeyi Kaydet")
                            
                            if submit_rate:
                                ortalama_puan = (c1 + c2 + c3) / 3.0
                                if opponent_email in users_db:
                                    users_db[opponent_email]['ratings'].append(ortalama_puan)
                                    if 'rated_by' not in match: match['rated_by'] = []
                                    match['rated_by'].append(st.session_state.current_user)
                                    
                                    save_data(USERS_FILE_PATH, users_db)
                                    save_data(INVITES_FILE_PATH, invites)
                                    st.success("Değerlendirmeniz gizli olarak sisteme işlendi!")
                                    st.rerun()

    elif menu == "👥 Üyeler":
        st.header("Topluluk Üyeleri")
        st.markdown("Üyeler, geçmiş maçlarından aldıkları gizli sistem puanına göre (en dürüst/uyumlu oyuncular en üstte olacak şekilde) sıralanmaktadır.")
        
        sorted_users = sorted(users_db.items(), key=lambda item: get_avg_rating(item[1]), reverse=True)
        
        if not sorted_users:
            st.info("Kayıtlı üye bulunmuyor.")
        else:
            for email, prof in sorted_users:
                with st.container(border=True):
                    cinsiyet_ek = f" ({prof.get('cinsiyet')})" if prof.get('cinsiyet') and prof.get('cinsiyet') != "Belirtmek İstemiyorum" else ""
                    st.write(f"**{prof.get('ad_soyad', email.split('@')[0])}**{cinsiyet_ek}")
                    st.write(f"⭐ NTRP: {prof.get('seviye', '-')} | 📍 {prof.get('bolge', '-')}")

    elif menu == "⚙️ Profil Ayarları":
        
        tab_profil, tab_sifre = st.tabs(["Kişisel Bilgiler", "🔒 Şifre Değiştir"])
        
        with tab_profil:
            c_name = current_user_profile.get("ad_soyad", "")
            c_gender = current_user_profile.get("cinsiyet", "Belirtmek İstemiyorum")
            c_level = current_user_profile.get("seviye", "4.0")
            c_hand = current_user_profile.get("el", "Sağ El")
            c_phone = current_user_profile.get("telefon", "")
            c_region = current_user_profile.get("bolge", "Alsancak")

            gender_options = ["Kadın", "Erkek", "Belirtmek İstemiyorum"]
            hand_options = ["Sağ El", "Sol El", "İki El (Ambidextrous)"]
            region_options = ["Alsancak", "Karşıyaka", "Bornova", "Güzelyalı", "Balçova", "Çiğli", "Güzelbahçe", "Buca", "Gaziemir", "Diğer"]

            with st.container(border=True):
                with st.form("profile_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        ad_soyad = st.text_input("Ad Soyad", value=c_name)
                        cinsiyet = st.selectbox("Cinsiyet", gender_options, index=gender_options.index(c_gender) if c_gender in gender_options else 2)
                        seviye = st.selectbox("Kendi Seviyeniz (NTRP)", NTRP_LEVELS, index=NTRP_LEVELS.index(c_level) if c_level in NTRP_LEVELS else 6)
                        oyun_eli = st.selectbox("Oyun Eliniz", hand_options, index=hand_options.index(c_hand) if c_hand in hand_options else 0)
                    with col2:
                        telefon = st.text_input("Telefon Numarası", value=c_phone)
                        bolge = st.selectbox("Yaşadığınız Bölge (İlçe)", region_options, index=region_options.index(c_region) if c_region in region_options else 0)
                    
                    submitted = st.form_submit_button("Profili Kaydet", type="primary")
                    
                    if submitted:
                        users_db[st.session_state.current_user].update({
                            "ad_soyad": ad_soyad,
                            "cinsiyet": cinsiyet,
                            "seviye": seviye,
                            "el": oyun_eli,
                            "telefon": telefon,
                            "bolge": bolge
                        })
                        if save_data(USERS_FILE_PATH, users_db):
                            st.success("Profil başarıyla güncellendi!")
                            st.rerun()

        with tab_sifre:
            with st.container(border=True):
                st.markdown("Geçici veya mevcut şifrenizi buradan güncelleyebilirsiniz.")
                with st.form("change_password_form"):
                    old_pass = st.text_input("Mevcut Şifreniz", type="password")
                    new_pass1 = st.text_input("Yeni Şifre", type="password")
                    new_pass2 = st.text_input("Yeni Şifre Tekrar", type="password")
                    pass_submit = st.form_submit_button("Şifreyi Güncelle", type="primary")
                    
                    if pass_submit:
                        if hash_password(old_pass) != users_db[st.session_state.current_user]["password_hash"]:
                            st.error("Mevcut şifrenizi yanlış girdiniz.")
                        elif new_pass1 != new_pass2:
                            st.error("Yeni şifreler uyuşmuyor.")
                        elif len(new_pass1) < 4:
                            st.warning("Yeni şifreniz çok kısa.")
                        else:
                            users_db[st.session_state.current_user]["password_hash"] = hash_password(new_pass1)
                            if save_data(USERS_FILE_PATH, users_db):
                                st.success("Şifreniz başarıyla güncellendi!")
                            else:
                                st.error("Şifre güncellenirken bir sorun oluştu.")

if not st.session_state.logged_in:
    login_page()
else:
    main_app()
