import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, date
import io

# --- AYARLAR VE SABİTLER ---
SETTINGS_FILE = "ayarlar_cloud.json"
NEBIM_CACHE_FILE = "nebim_listesi.txt"

@st.cache_data
def ayarlari_yukle():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                if "secili_tarih" in data:
                    data["secili_tarih"] = datetime.strptime(data["secili_tarih"], "%Y-%m-%d").date()
                return data
        except: pass
    return {"secili_tarih": date(2026, 1, 1), "gizli_markalar": []}

def ayarlari_kaydet(ayarlar):
    kayit_verisi = ayarlar.copy()
    if isinstance(kayit_verisi.get("secili_tarih"), (date, datetime)):
        kayit_verisi["secili_tarih"] = kayit_verisi["secili_tarih"].strftime("%Y-%m-%d")
    with open(SETTINGS_FILE, "w") as f:
        json.dump(kayit_verisi, f)

def clean_barcode(b):
    """Barkodları temiz metin formatına çevirir."""
    if pd.isna(b) or str(b).strip() == "": return None
    try:
        return str(int(float(b)))
    except:
        return str(b).strip()

# --- PDF OLUŞTURUCU ---
def pdf_olustur(baslik, baslik_satiri, veri_matrisi, col_widths):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
    except ImportError: return None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    def safe_text(text):
        return str(text).replace('İ','I').replace('ı','i').replace('Ş','S').replace('ş','s')\
                        .replace('Ğ','G').replace('ğ','g').replace('Ü','U').replace('ü','u')\
                        .replace('Ö','O').replace('ö','o').replace('Ç','C').replace('ç','c')

    elements.append(Paragraph(safe_text(baslik), styles['Heading1']))
    elements.append(Spacer(1, 15))
    
    data = [baslik_satiri]
    for row in veri_matrisi:
        data.append([safe_text(cell) for cell in row])
    
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTSIZE', (0,0), (-1,-1), 9)
    ]))
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer

st.set_page_config(page_title="Delfiee Cloud Pro", layout="wide", page_icon="☁️")

if 'ana_veri' not in st.session_state: st.session_state.ana_veri = None
yollar = ayarlari_yukle()

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Veri Yönetimi")
    page = st.radio("Menü", ["📊 Özet Panel", "📋 Detaylı Takip", "🔍 Barkod Sorgu", "📥 Eksik Listesi"])
    
    st.divider()
    main_file = st.file_uploader("1. Ana Ürün Listesi (Excel)", type=['xlsx'])
    media_file = st.file_uploader("2. Medya Barkod Listesi (Excel)", type=['xlsx'])
    nebim_file = st.file_uploader("3. Nebim TXT (Opsiyonel)", type=['txt'])
    
    st.divider()
    bas_tarih = st.date_input("Fiyat Başlangıç Tarihi", yollar["secili_tarih"])

    if st.button("🚀 ANALİZİ BAŞLAT", use_container_width=True, type="primary"):
        if main_file and media_file:
            with st.spinner("Veriler birleştiriliyor..."):
                df_prod = pd.read_excel(main_file, sheet_name='DmProducts1')
                df_media = pd.read_excel(media_file)
                df_prod.columns = [str(c).strip().upper() for c in df_prod.columns]
                df_media.columns = [str(c).strip().upper() for c in df_media.columns]
                
                get_set = lambda col: set(df_media[col].apply(clean_barcode)) if col in df_media.columns else set()
                has_jpg, has_vid = get_set('JPG'), get_set('VIDEO')
                has_kj, has_km = get_set('KOLAJ JPG'), get_set('KOLAJ MP4')
                
                h_nebim = set()
                if nebim_file:
                    content = nebim_file.getvalue().decode("utf-8", errors="ignore")
                    h_nebim = {line.strip().lower() for line in content.splitlines() if line.strip()}

                processed = []
                for _, row in df_prod.iterrows():
                    b_code = clean_barcode(row.get('BARCODE'))
                    if not b_code: continue
                    
                    if 'FIYATBELIRLEMETARIHI' in df_prod.columns:
                        f_tarih = pd.to_datetime(row['FIYATBELIRLEMETARIHI'], errors='coerce').date()
                        if pd.notna(f_tarih) and f_tarih < bas_tarih: continue

                    j, v = b_code in has_jpg, b_code in has_vid
                    kj, km = b_code in has_kj, b_code in has_km
                    n = b_code.lower() in h_nebim

                    processed.append({
                        "BARKOD": b_code,
                        "URUN_KODU": str(row.get('PRODUCTCODE', 'N/A')),
                        "MARKA": str(row.get('PRODUCTATT07DESC', 'Belirsiz')),
                        "RENK": str(row.get('COLORDESCRIPTION', '-')),
                        "STOK": int(row.get('INVENTORY', 0)) if pd.notna(row.get('INVENTORY', 0)) else 0,
                        "JPG": "✅" if j else "❌",
                        "VIDEO": "✅" if v else "❌",
                        "KOLAJ_JPG": "✅" if kj else "❌",
                        "KOLAJ_MP4": "✅" if km else "❌",
                        "NEBIM": "✅" if n else "❌",
                        "DURUM": "HAZIR" if j and v else "EKSİK"
                    })
                
                st.session_state.ana_veri = pd.DataFrame(processed)
                yollar["secili_tarih"] = bas_tarih
                ayarlari_kaydet(yollar)
                st.rerun()
        else:
            st.warning("Lütfen iki Excel dosyasını da yükleyin!")

# --- SAYFA İÇERİKLERİ ---
if st.session_state.ana_veri is not None:
    df = st.session_state.ana_veri
    
    if page == "📊 Özet Panel":
        st.header("🚀 Genel Üretim Özeti")
        c1, c2, c3, c4 = st.columns(4)
        total = len(df)
        ready = (df["DURUM"] == "HAZIR").sum()
        missing = total - ready
        rate = (ready/total*100) if total > 0 else 0
        
        c1.metric("📦 Toplam Ürün", total)
        c2.metric("✅ Hazır", ready)
        c3.metric("❌ Eksik", missing)
        c4.metric("🎯 Başarı Oranı", f"%{rate:.1f}")
        
        st.divider()
        st.subheader("🏢 Marka Üretim Durumları")
        ozet = df.groupby("MARKA").agg(TOPLAM=("BARKOD", "count"), HAZIR=("DURUM", lambda x: (x=="HAZIR").sum()), EKSIK=("DURUM", lambda x: (x=="EKSİK").sum())).reset_index()
        ozet["BASARI"] = (ozet["HAZIR"] / ozet["TOPLAM"] * 100).round(1)
        st.dataframe(ozet.sort_values("EKSIK", ascending=False), column_config={"BASARI": st.column_config.ProgressColumn("Tamamlanma %", min_value=0, max_value=100, format="%.1f%%")}, use_container_width=True, hide_index=True)
        
        st.divider()
        pdf_data = [[r['MARKA'], str(r['HAZIR']), str(r['EKSIK']), str(r['TOPLAM']), f"%{r['BASARI']}"] for _, r in ozet.iterrows()]
        pdf = pdf_olustur("Genel Ozet Raporu", ["MARKA", "HAZIR", "EKSIK", "TOPLAM", "BASARI"], pdf_data, [160, 80, 80, 80, 80])
        if pdf: st.download_button("📥 Özeti PDF İndir", pdf, file_name=f"ozet_{date.today()}.pdf", type="primary", use_container_width=True)

    elif page == "📋 Detaylı Takip":
        st.header("📋 Akıllı Filtreleme Paneli")
        c1, c2 = st.columns(2)
        f_marka = c1.multiselect("Markalar", options=sorted(df["MARKA"].unique()))
        f_durum = c2.selectbox("Durum Filtresi", ["Hepsi", "Sadece Hazır", "Sadece Eksik"])
        
        dff = df.copy()
        if f_marka: dff = dff[dff["MARKA"].isin(f_marka)]
        if f_durum == "Sadece Hazır": dff = dff[dff["DURUM"] == "HAZIR"]
        elif f_durum == "Sadece Eksik": dff = dff[dff["DURUM"] == "EKSİK"]
        
        st.dataframe(dff, use_container_width=True, hide_index=True)
        
        if not dff.empty:
            st.divider()
            detay_matris = [[str(r['BARKOD']), str(r['URUN_KODU']), str(r['MARKA']), str(r['RENK']), str(r['DURUM'])] for _, r in dff.iterrows()]
            detay_pdf = pdf_olustur("Detayli Urun Listesi", ["BARKOD", "KOD", "MARKA", "RENK", "DURUM"], detay_matris, [100, 110, 110, 100, 70])
            if detay_pdf: st.download_button("📥 Seçili Listeyi PDF İndir", detay_pdf, file_name=f"detayli_liste_{date.today()}.pdf", use_container_width=True)

    elif page == "🔍 Barkod Sorgu":
        st.header("📷 Anlık Barkod & Medya Kontrolü")
        st.write("El terminali ile barkodu okutabilir veya aradığınız Ürün Kodunu manuel yazabilirsiniz.")
        
        c_ara1, c_ara2 = st.columns(2)
        with c_ara1:
            okunan_barkod = st.text_input("🔍 Barkod Okutunuz:", key="barkod_okuyucu")
        with c_ara2:
            okunan_kod = st.text_input("🔍 Ürün Kodu Giriniz (Örn: AMH26...):", key="kod_okuyucu")
            
        if okunan_barkod or okunan_kod:
            sonuc = pd.DataFrame()
            if okunan_barkod:
                aranan = str(okunan_barkod).strip()
                sonuc = df[df["BARKOD"] == aranan]
            elif okunan_kod:
                aranan = str(okunan_kod).strip().upper()
                sonuc = df[df["URUN_KODU"].str.upper() == aranan]
                if sonuc.empty:
                    sonuc = df[df["URUN_KODU"].str.upper().str.contains(aranan, na=False)]
                    
            if not sonuc.empty:
                urun = sonuc.iloc[0]
                
                if urun['DURUM'] == "HAZIR":
                    st.success(f"✅ Bu Ürün TAMAMLANMIŞ! ({urun['MARKA']} - {urun['URUN_KODU']})")
                else:
                    st.warning(f"⚠️ Bu Ürünün EKSİKLERİ VAR! ({urun['MARKA']} - {urun['URUN_KODU']})")
                
                c1, c2 = st.columns([1, 1])
                with c1:
                    st.subheader("📦 Ürün Detayları")
                    st.write(f"**Marka:** {urun['MARKA']}")
                    st.write(f"**Ürün Kodu:** {urun['URUN_KODU']}")
                    st.write(f"**Renk:** {urun.get('RENK', '-')}")
                    st.write(f"**Stok:** {urun['STOK']}")
                    
                    st.divider()
                    st.subheader("🎬 Medya Durumu")
                    st.write(f"**📸 Ürün Fotoğrafı (JPG):** {urun['JPG']}")
                    st.write(f"**🎥 Ürün Videosu:** {urun['VIDEO']}")
                    st.write(f"**🖼️ Kolaj (JPG/MP4):** {urun['KOLAJ_JPG']} / {urun['KOLAJ_MP4']}")

                with c2:
                    # BUNNYCDN RESİM GÖSTERİMİ
                    if urun['JPG'] == "✅":
                        # Resim linkini oluşturuyoruz
                        resim_url = f"https://delfieestore.b-cdn.net/{urun['BARKOD']}_(1).jpg"
                        try:
                            # Resmi sayfada göster
                            st.image(resim_url, caption=f"{urun['URUN_KODU']} - {urun['RENK']}", width=350)
                        except Exception:
                            st.warning("⚠️ Resim URL'si çekilirken hata oluştu.")
                    else:
                        st.info("📷 Bu ürün için henüz görsel (JPG) çekilmemiş.")
                        
                st.divider()
                st.subheader("🎨 Bu Ürünün Diğer Renk Seçenekleri (Varyantlar)")
                varyantlar = df[df["URUN_KODU"] == urun["URUN_KODU"]].copy()
                st.dataframe(varyantlar[["BARKOD", "RENK", "STOK", "DURUM"]], hide_index=True, use_container_width=True)
            else:
                st.error("❌ Okutulan barkod veya girilen ürün kodu Excel verilerinde bulunamadı!")

    elif page == "📥 Eksik Listesi":
        st.header("📥 Çekilecekler ve Eksikler Listesi")
        eksikler = df[df["DURUM"] == "EKSİK"].copy()
        
        if not eksikler.empty:
            with st.form("eksik_filtre"):
                c1, c2, c3 = st.columns([2, 2, 1])
                f_m_eksik = c1.multiselect("Markayı Süz", options=sorted(eksikler["MARKA"].unique()))
                f_t_eksik = c2.radio("Eksik Türüne Odaklan", ["Hepsi", "Video Eksik", "Resim Eksik", "Kolaj Eksik"], horizontal=True)
                inv_min_e = int(eksikler["STOK"].min()) if not eksikler.empty else 0
                f_inv_e = c3.number_input("Min Stok", value=inv_min_e)
                st.form_submit_button("Listeyi Hazırla", use_container_width=True)

            if f_m_eksik: eksikler = eksikler[eksikler["MARKA"].isin(f_m_eksik)]
            eksikler = eksikler[eksikler["STOK"] >= f_inv_e]
            
            if f_t_eksik == "Video Eksik": eksikler = eksikler[eksikler["VIDEO"] == "❌"]
            elif f_t_eksik == "Resim Eksik": eksikler = eksikler[eksikler["JPG"] == "❌"]
            elif f_t_eksik == "Kolaj Eksik": eksikler = eksikler[(eksikler["KOLAJ_JPG"] == "❌") | (eksikler["KOLAJ_MP4"] == "❌")]

            st.warning(f"Filtrelenen Eksik Ürün Sayısı: {len(eksikler)}")
            st.dataframe(eksikler, use_container_width=True, hide_index=True)
            
            if not eksikler.empty:
                towrite = io.BytesIO()
                eksikler.to_excel(towrite, index=False, engine='xlsxwriter')
                st.download_button("📥 Seçili Eksikleri Excel İndir", towrite.getvalue(), file_name=f"delfiee_eksikler_{date.today()}.xlsx", type="primary", use_container_width=True)
        else: 
            st.success("Harika! Şimdilik hiç eksik ürününüz yok. 🎉")

else:
    st.info("👋 Hoş Geldiniz! Lütfen sol taraftaki menüden Excel dosyalarınızı yükleyerek analizi başlatın.")
