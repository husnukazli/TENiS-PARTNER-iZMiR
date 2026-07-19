import streamlit as st
import json
import datetime
from github import Github
import os

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Tenis Partner Ağı", page_icon="🎾", layout="wide")

# --- SABİT VERİLER ---
NTRP_LEVELS = ["1.0", "1.5", "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0", "5.5", "6.0", "6.5", "7.0"]

IZMIR_KORTLARI = [
    "Kültürpark Tenis Kulübü (KTK)",
    "İnciraltı Büyükşehir Kortları",
    "Bostanlı Suat Taşer Kortları",
    "Fuar Alanı (Celal Atik) Kortları",
    "Buca Tenis Kulübü",
    "Ege Üniversitesi Tenis Kortları",
    "Gaziemir Belediyesi Kortları",
    "Göztepe Tenis Kulübü",
    "Küçük Kulüp Alliance",
    "Mavişehir Şemikler Kortları",
    "Diğer"
]

# --- GITHUB BAĞLANTISI ---
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "GITHUB_TOKEN_BURAYA")
REPO_NAME = st.secrets.get("REPO_NAME", "kullaniciadi/repo_adi")
INVITES_FILE_PATH = "invites.json"
USERS_FILE_PATH = "users.json"

@st.cache_resource
def get_github_repo():
    if GITHUB_TOKEN != "GITHUB_TOKEN_BURAYA":
        try:
            g = Github(GITHUB_TOKEN)
            return g.get_repo(REPO_NAME)
        except Exception:
            pass
    return None

def load_data(file_path, default_type=list):
    repo = get_github_repo()
    if repo:
        try:
            file_content = repo.get_contents(file_path)
            return json.loads(file_content.decoded_content.decode())
        except Exception:
            return default_type()
    else:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
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
            except Exception:
                return False
    else:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception:
            return False

# --- OTURUM YÖNETİMİ ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = ""

def login_page():
    st.markdown("<h1 style='text-align: center; color: #2E7D32;'>🎾 İzmir Tenis Partner Havuzu</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.2rem;'>Korta çıkmak ve uygun partneri bulmak için giriş yapın.</p>", unsafe_allow_html=True)
    st.write("")
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.container(border=True):
            with st.form("login_form"):
                email = st.text_input("E-posta Adresi")
                password = st.text_input("Şifre", type="password")
                submitted = st.form_submit_button("Giriş Yap", type="primary", use_container_width=True)
                
                if submitted:
                    st.session_state.logged_in = True
                    st.session_state.current_user = email.strip().lower()
                    st.rerun()

def main_app():
    st.sidebar.title("🎾 Navigasyon")
    menu = st.sidebar.radio("Seçenekler", [
        "🏆 Havuz (Açık İlanlar)", 
        "➕ Davet Oluştur", 
        "👥 Üyeler", 
        "⚙️ Profil Ayarları"
    ])
    
    # Kullanıcı verilerini yükle (dict formatında)
    users_db = load_data(USERS_FILE_PATH, default_type=dict)
    current_user_profile = users_db.get(st.session_state.current_user, {})
    
    st.sidebar.markdown("---")
    isim_gosterim = current_user_profile.get("ad_soyad", st.session_state.current_user.split('@')[0])
    st.sidebar.write(f"👤 Aktif Kullanıcı: **{isim_gosterim}**")
    
    if st.sidebar.button("Çıkış Yap"):
        st.session_state.logged_in = False
        st.rerun()

    if menu == "🏆 Havuz (Açık İlanlar)":
        st.header("Güncel Eşleşme Havuzu")
        st.markdown("Uygun ilanlara teklif gönderin veya kendi ilanlarınıza gelen teklifleri onaylayın.")
        
        invites = load_data(INVITES_FILE_PATH, default_type=list)
        
        if not invites:
            st.info("Şu an havuzda bekleyen bir davet yok. İlk daveti sen oluştur!")
        else:
            with st.expander("🔍 İlanları Filtrele"):
                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1:
                    filter_type = st.selectbox("Davet Tipi", ["Tümü", "Sabit (Kesin Kort)", "Esnek (Zaman/Bölge)"])
                with f_col2:
                    filter_level = st.selectbox("Seviye (NTRP)", ["Tümü"] + NTRP_LEVELS)
                with f_col3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    hide_matched = st.checkbox("Sadece Bekleyenleri Göster", value=True)
            
            filtered_invites = []
            for inv in invites:
                inv_type = inv.get('type', 'Sabit')
                if filter_type == "Sabit (Kesin Kort)" and inv_type != "Sabit": continue
                if filter_type == "Esnek (Zaman/Bölge)" and inv_type != "Esnek": continue
                if filter_level != "Tümü" and inv.get('level') != filter_level: continue
                if hide_matched and inv.get('matched'): continue
                filtered_invites.append(inv)

            filtered_invites.sort(key=lambda x: (x['date'], x['time']))
            
            st.markdown("---")
            if not filtered_invites:
                st.warning("Seçtiğiniz kriterlere uygun ilan bulunamadı.")
            else:
                for invite in filtered_invites:
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([2, 2, 2])
                        
                        invite_type = invite.get('type', 'Sabit')
                        badge = "🎯 Kesin Rezervasyon" if invite_type == "Sabit" else "🤝 Esnek Zaman/Kort"
                        
                        # İlan sahibinin bilgilerini veritabanından çek
                        creator_email = invite['creator']
                        creator_prof = users_db.get(creator_email, {})
                        creator_name = creator_prof.get("ad_soyad", creator_email.split('@')[0])
                        
                        with col1:
                            st.markdown(f"**{badge}**")
                            st.markdown(f"🗓️ **Tarih:** {invite['date']} | ⏰ **Saat:** {invite['time']}")
                            st.markdown(f"📍 **Kort/Bölge:** {invite['court']}")
                        with col2:
                            st.markdown(f"👤 **Oyuncu:** {creator_name}")
                            st.markdown(f"⭐ **Aranan Seviye:** {invite['level']} NTRP")
                        
                        with col3:
                            offers = invite.get('offers', [])
                            if invite.get('matched'):
                                matched_prof = users_db.get(invite.get('matched_with'), {})
                                matched_name = matched_prof.get("ad_soyad", invite.get('matched_with').split('@')[0])
                                st.success(f"✅ {matched_name} ile eşleşti")
                            
                            elif invite['creator'] == st.session_state.current_user:
                                st.info(f"📩 Gelen Teklifler ({len(offers)})")
                                if offers:
                                    for offer_email in offers:
                                        offer_prof = users_db.get(offer_email, {})
                                        offer_name = offer_prof.get("ad_soyad", offer_email.split('@')[0])
                                        if st.button(f"✅ {offer_name} - Kabul Et", key=f"accept_{invite['id']}_{offer_email}"):
                                            invite['matched'] = True
                                            invite['matched_with'] = offer_email
                                            if save_data(INVITES_FILE_PATH, invites):
                                                st.success("Eşleşme tamamlandı!")
                                                st.rerun()
                                            else:
                                                st.error("Hata oluştu.")
                                else:
                                    st.caption("Henüz teklif yok.")
                            
                            else:
                                st.markdown("<br>", unsafe_allow_html=True)
                                if st.session_state.current_user in offers:
                                    st.button("⏳ Teklif Gönderildi (Cevap Bekleniyor)", disabled=True, use_container_width=True, key=f"wait_{invite['id']}")
                                else:
                                    if st.button("🙋‍♂️ Teklif Gönder", key=f"offer_{invite['id']}", type="primary", use_container_width=True):
                                        if 'offers' not in invite:
                                            invite['offers'] = []
                                        invite['offers'].append(st.session_state.current_user)
                                        if save_data(INVITES_FILE_PATH, invites):
                                            st.success("Teklifiniz iletildi!")
                                            st.rerun()
                                        else:
                                            st.error("Hata oluştu, tekrar deneyin.")

    elif menu == "➕ Davet Oluştur":
        st.header("Yeni Partner Daveti")
        with st.container(border=True):
            davet_turu = st.radio("Davet Durumunuz Nedir?", ["🎯 Kortumu ayırttım (Sabit saat ve kort)", "🤝 Partnerle birlikte belirleyeceğiz (Esnek saat ve bölge)"], horizontal=True)
            with st.form("new_invite"):
                date = st.date_input("Tarih")
                col1, col2 = st.columns(2)
                
                if "ayırttım" in davet_turu:
                    with col1:
                        time_val = st.time_input("Kesin Saat")
                        time_str = time_val.strftime("%H:%M")
                    with col2:
                        court = st.selectbox("Kort Seçimi", IZMIR_KORTLARI)
                        if court == "Diğer": 
                            court = st.text_input("Lütfen kort adını giriniz")
                    invite_tag = "Sabit"
                else:
                    with col1:
                        st.write("Müsaitlik Aralığı")
                        t1, t2 = st.columns(2)
                        with t1: start_time = st.time_input("Şu saatten...", value=datetime.time(9,0))
                        with t2: end_time = st.time_input("...şu saate kadar", value=datetime.time(18,0))
                        time_str = f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} Arası"
                    with col2:
                        court = st.selectbox("Bölge Tercihi", ["Farketmez (Birlikte Karar Verelim)", "Karşıyaka / Çiğli Bölgesi", "Alsancak / Bornova Bölgesi", "Balçova / Narlıdere / Güzelbahçe Bölgesi"])
                    invite_tag = "Esnek"
                
                st.markdown("---")
                level = st.selectbox("Aranan Seviye (NTRP)", NTRP_LEVELS, index=6) # Default 4.0 gelsin
                submitted = st.form_submit_button("Havuza Gönder", type="primary", use_container_width=True)
                
                if submitted:
                    invites = load_data(INVITES_FILE_PATH, default_type=list)
                    new_invite = {
                        "id": str(datetime.datetime.now().timestamp()),
                        "creator": st.session_state.current_user,
                        "type": invite_tag,
                        "date": str(date),
                        "time": time_str,
                        "court": court,
                        "level": level,
                        "matched": False,
                        "offers": []
                    }
                    invites.append(new_invite)
                    save_data(INVITES_FILE_PATH, invites)
                    st.success("Davetiniz havuza eklendi!")

    elif menu == "👥 Üyeler":
        st.header("Topluluk Üyeleri")
        st.markdown("Kayıtlı oyuncuları ve seviyelerini buradan görebilirsiniz.")
        
        if not users_db:
            st.info("Henüz profilini doldurmuş bir üye bulunmuyor.")
        else:
            for email, prof in users_db.items():
                with st.container(border=True):
                    col1, col2 = st.columns([3,1])
                    with col1:
                        cinsiyet_ek = f" ({prof.get('cinsiyet')})" if prof.get('cinsiyet') and prof.get('cinsiyet') != "Belirtmek İstemiyorum" else ""
                        st.write(f"**{prof.get('ad_soyad', email.split('@')[0])}**{cinsiyet_ek}")
                        st.write(f"⭐ NTRP: {prof.get('seviye', '-')} | 📍 {prof.get('bolge', '-')}")
                    with col2:
                        # WhatsApp butonu şimdilik kapalı, ileride eklenebilir.
                        pass

    elif menu == "⚙️ Profil Ayarları":
        st.header("Kişisel Bilgiler ve Tercihler")
        
        # Mevcut profil verilerini formda varsayılan olarak göstermek için hazırlık
        c_name = current_user_profile.get("ad_soyad", "")
        c_gender = current_user_profile.get("cinsiyet", "Belirtmek İstemiyorum")
        c_level = current_user_profile.get("seviye", "4.0")
        c_hand = current_user_profile.get("el", "Sağ El")
        c_phone = current_user_profile.get("telefon", "")
        c_region = current_user_profile.get("bolge", "Alsancak")
        c_privacy = current_user_profile.get("gizlilik", "Sadece eşleştiğim kişiler görebilir")

        gender_options = ["Kadın", "Erkek", "Belirtmek İstemiyorum"]
        hand_options = ["Sağ El", "Sol El", "İki El (Ambidextrous)"]
        region_options = ["Alsancak", "Karşıyaka", "Bornova", "Güzelyalı", "Balçova", "Çiğli", "Güzelbahçe", "Buca", "Gaziemir", "Diğer"]
        privacy_options = ["Telefon numaramı herkes görebilir", "Sadece eşleştiğim kişiler görebilir", "Sadece e-posta üzerinden iletişim"]

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
                    gizlilik = st.selectbox("İletişim Gizliliği", privacy_options, index=privacy_options.index(c_privacy) if c_privacy in privacy_options else 1)
                
                submitted = st.form_submit_button("Profili Kaydet", type="primary")
                
                if submitted:
                    # Kullanıcı verisini sözlüğe yaz ve kaydet
                    users_db[st.session_state.current_user] = {
                        "ad_soyad": ad_soyad,
                        "cinsiyet": cinsiyet,
                        "seviye": seviye,
                        "el": oyun_eli,
                        "telefon": telefon,
                        "bolge": bolge,
                        "gizlilik": gizlilik
                    }
                    if save_data(USERS_FILE_PATH, users_db):
                        st.success("Profil bilgileriniz başarıyla güncellendi!")
                        st.rerun()
                    else:
                        st.error("Kaydedilirken bir sorun oluştu.")

if not st.session_state.logged_in:
    login_page()
else:
    main_app()
