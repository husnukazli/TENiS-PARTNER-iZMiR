import streamlit as st
import json
import datetime
from github import Github
import os

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Tenis Partner Ağı", page_icon="🎾", layout="wide")

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
        except Exception as e:
            st.error("GitHub bağlantı hatası. Token ve Repo adını kontrol edin.")
    return None

def load_data(file_path):
    repo = get_github_repo()
    if repo:
        try:
            file_content = repo.get_contents(file_path)
            return json.loads(file_content.decoded_content.decode())
        except Exception:
            return []
    else:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

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
                    st.session_state.current_user = email
                    st.rerun()

def main_app():
    st.sidebar.title("🎾 Navigasyon")
    menu = st.sidebar.radio("Seçenekler", ["🏆 Havuz (Açık İlanlar)", "➕ Davet Oluştur", "⚙️ Profil Ayarları"])
    
    st.sidebar.markdown("---")
    st.sidebar.write(f"👤 Aktif Kullanıcı: **{st.session_state.current_user.split('@')[0]}**")
    if st.sidebar.button("Çıkış Yap"):
        st.session_state.logged_in = False
        st.rerun()

    if menu == "🏆 Havuz (Açık İlanlar)":
        st.header("Güncel Eşleşme Havuzu")
        st.markdown("Filtrelenmiş saat ve seviyenize uygun ilanlara buradan teklif gönderebilirsiniz.")
        
        invites = load_data(INVITES_FILE_PATH)
        
        if not invites:
            st.info("Şu an havuzda bekleyen bir davet yok. İlk daveti oluşturarak kortu sen rezerve et!")
        else:
            # --- FİLTRELEME BÖLÜMÜ ---
            with st.expander("🔍 İlanları Filtrele", expanded=True):
                f_col1, f_col2, f_col3 = st.columns(3)
                with f_col1:
                    filter_type = st.selectbox("Davet Tipi", ["Tümü", "Sabit (Kesin Kort)", "Esnek (Zaman/Bölge)"])
                with f_col2:
                    filter_level = st.selectbox("Seviye", ["Tümü", "Başlangıç", "Orta (ITN 7-8)", "İleri (ITN 5-6)", "Performans (ITN 1-4)"])
                with f_col3:
                    st.markdown("<br>", unsafe_allow_html=True) # Checkbox'ı hizalamak için
                    hide_matched = st.checkbox("Sadece Bekleyenleri Göster", value=True)
            
            # Filtreleri Uygulama
            filtered_invites = []
            for inv in invites:
                inv_type = inv.get('type', 'Sabit')
                
                # Davet Tipi Kontrolü
                if filter_type == "Sabit (Kesin Kort)" and inv_type != "Sabit":
                    continue
                elif filter_type == "Esnek (Zaman/Bölge)" and inv_type != "Esnek":
                    continue
                
                # Seviye Kontrolü
                if filter_level != "Tümü" and inv.get('level') != filter_level:
                    continue
                    
                # Eşleşme Durumu Kontrolü
                if hide_matched and inv.get('matched'):
                    continue
                    
                filtered_invites.append(inv)

            # Tarih ve Saate göre sırala
            filtered_invites.sort(key=lambda x: (x['date'], x['time']))
            
            st.markdown("---")
            if not filtered_invites:
                st.warning("Seçtiğiniz kriterlere uygun ilan bulunamadı.")
            else:
                for invite in filtered_invites:
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([2, 2, 1])
                        
                        invite_type = invite.get('type', 'Sabit')
                        badge = "🎯 Kesin Rezervasyon" if invite_type == "Sabit" else "🤝 Esnek Zaman/Kort"
                        
                        with col1:
                            st.markdown(f"**{badge}**")
                            st.markdown(f"🗓️ **Tarih:** {invite['date']} | ⏰ **Saat:** {invite['time']}")
                            st.markdown(f"📍 **Kort/Bölge:** {invite['court']}")
                        with col2:
                            st.markdown(f"👤 **Oyuncu:** {invite['creator'].split('@')[0]}")
                            st.markdown(f"⭐ **Seviye:** {invite['level']}")
                        with col3:
                            st.markdown("<br>", unsafe_allow_html=True) 
                            if not invite.get('matched'):
                                if st.button("🎾 Eşleş", key=invite['id'], type="primary", use_container_width=True):
                                    invite['matched'] = True
                                    invite['matched_with'] = st.session_state.current_user
                                    if save_data(INVITES_FILE_PATH, invites):
                                        st.success("Harika! Eşleşme sağlandı. İletişim bilgilerini Profil'den kontrol edebilirsiniz.")
                                        st.rerun()
                                    else:
                                        st.error("Çakışma tespit edildi! Kayıt yapılamadı, lütfen tekrar deneyin.")
                            else:
                                st.button("✅ Eşleşti", key=invite['id']+"_matched", disabled=True, use_container_width=True)

    elif menu == "➕ Davet Oluştur":
        st.header("Yeni Partner Daveti")
        st.markdown("Müsait olduğunuz zaman dilimini ve oyun standartlarınızı belirleyerek havuza düşün.")
        
        with st.container(border=True):
            davet_turu = st.radio(
                "Davet Durumunuz Nedir?", 
                ["🎯 Kortumu ayırttım (Sabit saat ve kort)", "🤝 Partnerle birlikte belirleyeceğiz (Esnek saat ve bölge)"],
                horizontal=True
            )
            
            with st.form("new_invite"):
                date = st.date_input("Tarih")
                
                col1, col2 = st.columns(2)
                
                if "ayırttım" in davet_turu:
                    with col1:
                        time_val = st.time_input("Kesin Saat")
                        time_str = time_val.strftime("%H:%M")
                    with col2:
                        court = st.selectbox("Kort Seçimi", ["Kültürpark Tenis Kulübü", "İnciraltı Kortları", "Bostanlı Kortları", "Fuar Alanı", "Diğer"])
                        if court == "Diğer":
                            court = st.text_input("Kort adını giriniz")
                    invite_tag = "Sabit"
                else:
                    with col1:
                        st.write("Müsaitlik Aralığı")
                        t1, t2 = st.columns(2)
                        with t1:
                            start_time = st.time_input("Şu saatten...", value=datetime.time(9,0))
                        with t2:
                            end_time = st.time_input("...şu saate kadar", value=datetime.time(18,0))
                        time_str = f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} Arası"
                    with col2:
                        court = st.selectbox("Bölge Tercihi", ["Farketmez (Birlikte Karar Verelim)", "Karşıyaka / Çiğli Bölgesi", "Alsancak / Bornova Bölgesi", "Balçova / Narlıdere Bölgesi"])
                    invite_tag = "Esnek"
                
                st.markdown("---")
                level = st.selectbox("Aranan Seviye", ["Başlangıç", "Orta (ITN 7-8)", "İleri (ITN 5-6)", "Performans (ITN 1-4)"])
                
                submitted = st.form_submit_button("Havuza Gönder", type="primary", use_container_width=True)
                
                if submitted:
                    invites = load_data(INVITES_FILE_PATH)
                    new_invite = {
                        "id": str(datetime.datetime.now().timestamp()),
                        "creator": st.session_state.current_user,
                        "type": invite_tag,
                        "date": str(date),
                        "time": time_str,
                        "court": court,
                        "level": level,
                        "matched": False
                    }
                    invites.append(new_invite)
                    
                    if save_data(INVITES_FILE_PATH, invites):
                        st.success("Davetiniz başarıyla havuza eklendi! Havuz sekmesinden takip edebilirsiniz.")
                    else:
                        st.error("Sunucu yoğunluğu nedeniyle veri kaydedilemedi. Lütfen tekrar deneyin.")

    elif menu == "⚙️ Profil Ayarları":
        st.header("Kişisel Bilgiler ve Tercihler")
        st.markdown("Oyun karakteristiklerinizi ve gizlilik ayarlarınızı buradan yönetin.")
        with st.container(border=True):
            with st.form("profile_form"):
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Ad Soyad")
                    st.selectbox("Kendi Seviyeniz", ["Başlangıç", "Orta", "İleri", "Performans"])
                    st.selectbox("Oyun Eliniz", ["Sağ El", "Sol El", "İki El (Ambidextrous)"])
                with col2:
                    st.text_input("Telefon Numarası")
                    st.selectbox("Bölge (İlçe)", ["Alsancak", "Karşıyaka", "Bornova", "Güzelyalı", "Balçova", "Diğer"])
                    st.selectbox("İletişim Gizliliği", [
                        "Telefon numaramı herkes görebilir", 
                        "Sadece eşleştiğim kişiler görebilir", 
                        "Sadece platform / e-posta üzerinden iletişim"
                    ])
                
                st.form_submit_button("Profili Kaydet", type="primary")

if not st.session_state.logged_in:
    login_page()
else:
    main_app()
