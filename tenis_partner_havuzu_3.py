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

# --- DOSYA YOLLARI (Lokal Kayıt İçin) ---
USERS_FILE = "users.json"
INVITES_FILE = "invites.json"

# --- YARDIMCI FONKSİYONLAR ---
def load_data(filepath, default_type):
    if not os.path.exists(filepath):
        return default_type()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default_type()

def save_data(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Kayıt Hatası: {e}")
        return False

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def send_email(to_address, subject, message):
    smtp_user = st.secrets.get("SMTP_USER", "")
    smtp_pass = st.secrets.get("SMTP_PASS", "")
    
    if not smtp_user or not smtp_pass:
        print(f"\n--- SİMÜLASYON MAIL --- \nKime: {to_address}\nKonu: {subject}\nMesaj: {message}\n-----------------------\n")
        return False
        
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_address
        msg['Subject'] = subject
        msg.attach(MIMEText(message, 'html'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Mail gönderme hatası: {e}")
        return False

def generate_ics(invite_id, invite_data):
    # Basit bir .ics dosyası üreteci
    start_time = datetime.datetime.strptime(f"{invite_data['tarih']} {invite_data['saat']}", "%Y-%m-%d %H:%M")
    end_time = start_time + datetime.timedelta(hours=1, minutes=30) # Ortalama 1.5 saat
    
    dtstart = start_time.strftime("%Y%m%dT%H%M%S")
    dtend = end_time.strftime("%Y%m%dT%H%M%S")
    
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Tenis Maçı - {invite_data['kort']}
DTSTART:{dtstart}
DTEND:{dtend}
LOCATION:{invite_data['kort']}
DESCRIPTION:İzmir Tenis Ağı üzerinden ayarlandı.
END:VEVENT
END:VCALENDAR"""
    return ics_content

def get_avg_rating(user_profile):
    ratings = user_profile.get("ratings", [])
    if not ratings:
        return 5.0
    return sum(ratings) / len(ratings)

# --- SESSİON STATE BAŞLANGIÇ ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = ""

# --- GİRİŞ / KAYIT / ŞİFRE SIFIRLAMA EKRANI ---
def login_screen():
    st.title("🎾 İzmir Tenis Partner Ağı")
    st.write("Hoş Geldiniz! Lütfen giriş yapın veya kayıt olun.")
    
    tab1, tab2, tab3 = st.tabs(["Giriş Yap", "Kayıt Ol", "Şifremi Unuttum"])
    users_db = load_data(USERS_FILE, dict)
    
    with tab1:
        email_login = st.text_input("E-posta Adresi", key="login_email").strip().lower()
        pass_login = st.text_input("Şifre", type="password", key="login_pass")
        if st.button("Giriş", type="primary"):
            if email_login in users_db and users_db[email_login]["password"] == hash_password(pass_login):
                st.session_state.logged_in = True
                st.session_state.current_user = email_login
                st.rerun()
            else:
                st.error("E-posta veya şifre hatalı!")
                
    with tab2:
        email_reg = st.text_input("Yeni E-posta Adresi", key="reg_email").strip().lower()
        ad_soyad = st.text_input("Ad Soyad", key="reg_name")
        pass_reg = st.text_input("Yeni Şifre", type="password", key="reg_pass")
        ntrp = st.selectbox("NTRP Seviyeniz", ["1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0+"])
        bolge = st.selectbox("Oynadığınız Bölge", ["Karşıyaka", "Bornova", "Buca", "Konak", "Balçova", "Güzelyalı"])
        el = st.radio("Oynadığınız El", ["Sağ", "Sol"])
        
        if st.button("Kayıt Ol", type="primary"):
            if email_reg in users_db:
                st.warning("Bu e-posta zaten kayıtlı!")
            elif email_reg and pass_reg and ad_soyad:
                users_db[email_reg] = {
                    "password": hash_password(pass_reg),
                    "ad_soyad": ad_soyad,
                    "ntrp": ntrp,
                    "bolge": bolge,
                    "el": el,
                    "ratings": [],
                    "matches_played": 0
                }
                save_data(USERS_FILE, users_db)
                st.success("Kayıt başarılı! Şimdi giriş yapabilirsiniz.")
            else:
                st.warning("Lütfen tüm alanları doldurun.")
                
    with tab3:
        email_forgot = st.text_input("Kayıtlı E-posta Adresiniz", key="forgot_email").strip().lower()
        if st.button("Geçici Şifre Gönder"):
            if email_forgot in users_db:
                new_temp_pass = str(uuid.uuid4())[:8] # 8 haneli rastgele şifre
                users_db[email_forgot]["password"] = hash_password(new_temp_pass)
                save_data(USERS_FILE, users_db)
                
                mesaj = f"<h3>Şifre Sıfırlama</h3><p>Yeni geçici şifreniz: <b>{new_temp_pass}</b></p><p>Lütfen sisteme giriş yaptıktan sonra profil ayarlarından şifrenizi değiştirin.</p>"
                mail_gitti = send_email(email_forgot, "Geçici Şifreniz - Tenis Ağı", mesaj)
                
                if mail_gitti:
                    st.success("Geçici şifreniz e-posta adresinize gönderildi. (Gereksiz/Spam kutusunu kontrol etmeyi unutmayın)")
                else:
                    st.info(f"Mail servisi şu an simülasyon modunda. (Şifreniz sıfırlandı, yeni şifre: {new_temp_pass} - Lütfen not alınız)")
            else:
                st.error("Bu e-posta sistemde bulunamadı.")

# --- ANA UYGULAMA EKRANI ---
def main_app():
    users_db = load_data(USERS_FILE, dict)
    invites_db = load_data(INVITES_FILE, list)
    current_user_profile = users_db.get(st.session_state.current_user, {})
    
    # --- YÖNETİCİ KONTROLÜ ---
    ADMIN_SECRET = st.secrets.get("ADMIN_PANEL_PASS", "izmir35") 
    is_admin = False
    
    st.sidebar.title("🎾 Navigasyon")
    
    with st.sidebar.expander("🔒 Yönetici Girişi"):
        admin_kod = st.text_input("Yönetici Kodu", type="password")
        if admin_kod == ADMIN_SECRET:
            is_admin = True
            st.success("Yönetici yetkisi doğrulandı!")

    menu_options = [
        "🏆 Havuz (Açık İlanlar)", 
        "➕ Davet Oluştur", 
        "👥 Üyeler", 
        "⚙️ Profil Ayarları"
    ]
    if is_admin:
        menu_options.append("👑 Yönetici Paneli")

    menu = st.sidebar.radio("Seçenekler", menu_options)
    
    st.sidebar.markdown("---")
    isim_gosterim = current_user_profile.get("ad_soyad", st.session_state.current_user.split('@')[0])
    puan = get_avg_rating(current_user_profile)
    st.sidebar.write(f"👤 **{isim_gosterim}** (⭐ {puan:.1f})")
    
    if st.sidebar.button("Çıkış Yap"):
        st.session_state.logged_in = False
        st.rerun()

    # --- 1. HAVUZ (AÇIK İLANLAR) ---
    if menu == "🏆 Havuz (Açık İlanlar)":
        st.header("🏆 Açık Maç İlanları")
        aktif_ilanlar = [inv for inv in invites_db if inv["durum"] == "Açık"]
        
        if not aktif_ilanlar:
            st.info("Şu an açık ilan bulunmuyor. Yeni bir davet oluşturabilirsiniz!")
            
        for idx, inv in enumerate(aktif_ilanlar):
            with st.container():
                st.markdown(f"### {inv['tip']} Davet - {inv['bolge']}")
                st.write(f"**Tarih:** {inv['tarih']} | **Saat:** {inv['saat']} | **Kort:** {inv['kort']}")
                st.write(f"**Oluşturan:** {inv['olusturan_isim']} (NTRP: {inv['istenen_ntrp']})")
                st.write(f"**Not:** {inv['notlar']}")
                
                if inv['olusturan_email'] != st.session_state.current_user:
                    if st.button("Bu Maça Talip Ol", key=f"talip_{idx}"):
                        inv["durum"] = "Eşleşildi"
                        inv["rakip_email"] = st.session_state.current_user
                        inv["rakip_isim"] = isim_gosterim
                        save_data(INVITES_FILE, invites_db)
                        
                        # .ics Takvim Dosyası İndirme Butonu
                        ics_data = generate_ics(idx, inv)
                        st.download_button(
                            label="📅 Takvime Ekle (.ics)",
                            data=ics_data,
                            file_name="tenis_maci.ics",
                            mime="text/calendar"
                        )
                        st.success("Eşleşme başarılı! İyi oyunlar.")
                        st.rerun()
                st.markdown("---")

    # --- 2. DAVET OLUŞTUR ---
    elif menu == "➕ Davet Oluştur":
        st.header("➕ Yeni Maç Daveti")
        tip = st.radio("Davet Tipi", ["Sabit (Kort ve Saat Kesin)", "Esnek (Zaman ve Bölge Aralığı)"])
        
        tarih = st.date_input("Tarih", min_value=datetime.date.today())
        
        if tip == "Sabit (Kort ve Saat Kesin)":
            saat = st.time_input("Saat")
            kort = st.text_input("Kort Adı / Yeri")
            bolge = "Belirtilmedi"
        else:
            saat = st.text_input("Uygun Saat Aralığı (Örn: 18:00 - 21:00)")
            bolge = st.selectbox("Tercih Edilen Bölge", ["Karşıyaka", "Bornova", "Buca", "Konak", "Balçova", "Fark Etmez"])
            kort = "Henüz net değil"
            
        istenen_ntrp = st.selectbox("Aranan NTRP Seviyesi", ["Fark Etmez", "2.0 - 3.0", "3.0 - 4.0", "4.0+"])
        notlar = st.text_area("Ekstra Notlar (Örn: Toplar benden, kort ücreti yarı yarıya)")
        
        if st.button("İlanı Yayınla", type="primary"):
            yeni_ilan = {
                "tip": tip,
                "tarih": str(tarih),
                "saat": str(saat),
                "kort": kort,
                "bolge": bolge,
                "istenen_ntrp": istenen_ntrp,
                "notlar": notlar,
                "olusturan_email": st.session_state.current_user,
                "olusturan_isim": isim_gosterim,
                "durum": "Açık",
                "rakip_email": None,
                "rakip_isim": None
            }
            invites_db.append(yeni_ilan)
            save_data(INVITES_FILE, invites_db)
            st.success("İlan başarıyla oluşturuldu! Havuz sekmesinden takip edebilirsiniz.")

    # --- 3. ÜYELER ---
    elif menu == "👥 Üyeler":
        st.header("👥 Topluluk Üyeleri")
        st.write("Ağımızdaki tenisçileri buradan inceleyebilirsiniz.")
        
        for email, details in users_db.items():
            user_puan = get_avg_rating(details)
            st.markdown(f"**{details['ad_soyad']}** - NTRP: {details['ntrp']} - Bölge: {details['bolge']} - ⭐ {user_puan:.1f}")

    # --- 4. PROFİL AYARLARI ---
    elif menu == "⚙️ Profil Ayarları":
        st.header("⚙️ Profil Ayarları")
        
        yeni_ad = st.text_input("Ad Soyad", value=current_user_profile.get("ad_soyad", ""))
        yeni_ntrp = st.selectbox("NTRP Seviyesi", ["1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0+"], index=["1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0+"].index(current_user_profile.get("ntrp", "1.0")))
        
        # Şifre Değiştirme
        st.subheader("Şifre Değiştir")
        yeni_sifre = st.text_input("Yeni Şifreniz", type="password")
        
        if st.button("Değişiklikleri Kaydet"):
            users_db[st.session_state.current_user]["ad_soyad"] = yeni_ad
            users_db[st.session_state.current_user]["ntrp"] = yeni_ntrp
            if yeni_sifre:
                users_db[st.session_state.current_user]["password"] = hash_password(yeni_sifre)
            
            save_data(USERS_FILE, users_db)
            st.success("Profiliniz başarıyla güncellendi!")

    # --- 5. YÖNETİCİ PANELİ (GİZLİ) ---
    elif menu == "👑 Yönetici Paneli" and is_admin:
        st.header("👑 Sistem Yönetim Merkezi")
        st.write("Sistem verilerini yedekleyebilir, geri yükleyebilir veya e-posta altyapısını test edebilirsiniz.")
        
        tab_yedek, tab_gmail = st.tabs(["💾 Yedekleme & Geri Yükleme", "📧 Gmail Testi"])
        
        with tab_yedek:
            st.subheader("Verileri İndir (Yedek Al)")
            master_backup = {
                "users": users_db,
                "invites": invites_db,
                "backup_date": str(datetime.date.today())
            }
            backup_string = json.dumps(master_backup, indent=4, ensure_ascii=False)
            
            st.download_button(
                label="📥 Tüm Sistem Verisini İndir (.json)",
                data=backup_string,
                file_name=f"tenis_agi_yedek_{datetime.date.today()}.json",
                mime="application/json",
                use_container_width=True
            )
            
            st.markdown("---")
            st.subheader("Sistemi Geri Yükle")
            uploaded_file = st.file_uploader("Yedek JSON dosyasını seçin", type=["json"])
            
            if uploaded_file is not None:
                try:
                    loaded_backup = json.load(uploaded_file)
                    if "users" in loaded_backup and "invites" in loaded_backup:
                        if st.button("🚨 Geri Yüklemeyi Onayla", type="primary"):
                            save_data(USERS_FILE, loaded_backup["users"])
                            save_data(INVITES_FILE, loaded_backup["invites"])
                            st.success("Sistem eski haline döndürüldü! Lütfen sayfayı yenileyin.")
                    else:
                        st.error("Geçersiz yedek dosyası.")
                except:
                    st.error("Dosya okuma hatası.")
                    
        with tab_gmail:
            st.subheader("E-posta Gönderim Testi")
            test_mail_adresi = st.text_input("Test Mesajı Alacak E-posta", placeholder="ornek@gmail.com")
            
            if st.button("🚀 Test E-postası Gönder"):
                if test_mail_adresi:
                    with st.spinner("Gönderiliyor..."):
                        basari = send_email(test_mail_adresi, "Sistem Testi", "Bu mail Streamlit üzerinden başarıyla gönderildi!")
                    if basari:
                        st.success("İşlem tamam! Eğer ayarlar doğruysa mail kutuna düştü.")
                    else:
                        st.warning("Gönderim başarısız. Secrets ayarlarını veya Uygulama Şifresini (App Password) kontrol et.")

# --- ANA KONTROL ---
if st.session_state.logged_in:
    main_app()
else:
    login_screen()
