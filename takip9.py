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

# --- ANA UYGULAMA BAŞLANGICI ---
st.set_page_config(page_title="Delfiee Cloud Pro", layout="wide", page_icon="☁️")

if 'ana_veri' not in st.session_state: st.session_state.ana_veri = None
yollar = ayarlari_yukle()

# --- SIDEBAR (DOSYA KAYIT SİSTEMİ) ---
with st.sidebar:
    st.title("⚙️ Veri Yönetimi")
    page = st.radio("Menü", ["📊 Özet Panel", "📋 Detaylı Takip", "🔍 Barkod Sorgu", "📥 Eksik Listesi"])
    
    st.divider()
    st.write("📂 **Dosya Yükleme**")
    
    # Dosya 1: Ana Liste
    main_file = st.file_uploader("1. Ana Ürün Listesi", type=['xlsx'])
    if main_file:
        with open("saved_main.xlsx", "wb") as f:
            f.write(main_file.getbuffer())
        st.success("✅ Ana liste hafızaya alındı.")
    
    # Dosya 2: Medya Listesi
    media_file = st.file_uploader("2. Medya Barkod Listesi", type=['xlsx'])
    if media_file:
        with open("saved_media.xlsx", "wb") as f:
            f.write(media_file.getbuffer())
        st.success("✅ Medya listesi hafızaya alındı.")

    # Dosya 3: Nebim
    nebim_file = st.file_uploader("3. Nebim TXT", type=['txt'])
    if nebim_file:
        with open(NEBIM_CACHE_FILE, "wb") as f:
            f.write(nebim_file.getbuffer())

    st.divider()
    bas_tarih = st.date_input("Fiyat Tarihi", yollar["secili_tarih"])

    if st.button("🚀 ANALİZİ BAŞLAT", use_container_width=True, type="primary"):
        if os.path.exists("saved_main.xlsx") and os.path.exists("saved_media.xlsx"):
            with st.spinner("Analiz ediliyor..."):
                try:
                    df_prod = pd.read_excel("saved_main.xlsx", sheet_name='DmProducts1')
                    df_media = pd.read_excel("saved_media.xlsx")
                    
                    df_prod.columns = [str(c).strip().upper() for c in df_prod.columns]
                    df_media.columns = [str(c).strip().upper() for c in df_media.columns]
                    
                    get_set = lambda col: set(df_media[col].apply(clean_barcode)) if col in df_media.columns else set()
                    has_jpg, has_vid = get_set('JPG'), get_set('VIDEO')
                    has_kj, has_km = get_set('KOLAJ JPG'), get_set('KOLAJ MP4')
                    
                    h_nebim = set()
                    if os.path.exists(NEBIM_CACHE_FILE):
                        with open(NEBIM_CACHE_FILE, "r", encoding="utf-8", errors="ignore") as f:
                            h_nebim = {line.strip().lower() for line in f if line.strip()}

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
                            "JPG": "✅" if j else "❌", "VIDEO": "✅" if v else "❌",
                            "KOLAJ_JPG": "✅" if kj else "❌", "KOLAJ_MP4": "✅" if km else "❌",
                            "NEBIM": "✅" if n else "❌", "DURUM": "HAZIR" if j and v else "EKSİK"
                        })
                    
                    st.session_state.ana_veri = pd.DataFrame(processed)
                    yollar["secili_tarih"] = bas_tarih
                    ayarlari_kaydet(yollar)
                    st.rerun()
                except Exception as e:
                    st.error(f"Hata: {e}")
        else:
            st.error("Lütfen önce dosyaları yükleyin!")

# --- SAYFA İÇERİKLERİ ---
if st.session_state.ana_veri is not None:
    df = st.session_state.ana_veri
    
    if page == "📊 Özet Panel":
        st.header("🚀 Genel Üretim Özeti")
        c1, c2, c3, c4 = st.columns(4)
        total = len(df); ready = (df["DURUM"] == "HAZIR").sum(); missing = total - ready
        rate = (ready/total*100) if total > 0 else 0
        c1.metric("📦 Toplam Ürün", total); c2.metric("✅ Hazır", ready); c3.metric("❌ Eksik", missing); c4.metric("🎯 Başarı Oranı", f"%{rate:.1f}")
        
        st.divider()
        ozet = df.groupby("MARKA").agg(TOPLAM=("BARKOD", "count"), HAZIR=("DURUM", lambda x: (x=="HAZIR").sum()), EKSIK=("DURUM", lambda x: (x=="EKSİK").sum())).reset_index()
        ozet["BASARI"] = (ozet["HAZIR"] / ozet["TOPLAM"] * 100).round(1)
        st.dataframe(ozet.sort_values("EKSIK", ascending=False), column_config={"BASARI": st.column_config.ProgressColumn("Tamamlanma %", min_value=0, max_value=100, format="%.1f%%")}, use_container_width=True, hide_index=True)
        
        pdf_data = [[r['MARKA'], str(r['HAZIR']), str(r['EKSIK']), str(r['TOPLAM']), f"%{r['BASARI']}"] for _, r in ozet.iterrows()]
        pdf = pdf_olustur("Genel Ozet Raporu", ["MARKA", "HAZIR", "EKSIK", "TOPLAM", "BASARI"], pdf_data, [160, 80, 80, 80, 80])
        if pdf: st.download_button("📥 Özeti PDF İndir", pdf, file_name="ozet.pdf", type="primary", use_container_width=True)

    elif page == "📋 Detaylı Takip":
        st.header("📋 Akıllı Filtreleme")
        c1, c2 = st.columns(2)
        f_marka = c1.multiselect("Markalar", options=sorted(df["MARKA"].unique()))
        f_durum = c2.selectbox("Durum", ["Hepsi", "Sadece Hazır", "Sadece Eksik"])
        dff = df.copy()
        if f_marka: dff = dff[dff["MARKA"].isin(f_marka)]
        if f_durum == "Sadece Hazır": dff = dff[dff["DURUM"] == "HAZIR"]
        elif f_durum == "Sadece Eksik": dff = dff[dff["DURUM"] == "EKSİK"]
        st.dataframe(dff, use_container_width=True, hide_index=True)

    elif page == "🔍 Barkod Sorgu":
        st.header("🔍 Barkod & Medya Sorgu")
        c_a1, c_a2 = st.columns(2)
        ok_barkod = c_a1.text_input("🔍 Barkod Okut:")
        ok_kod = c_a2.text_input("🔍 Ürün Kodu Gir:")
        if ok_barkod or ok_kod:
            sonuc = df[df["BARKOD"] == ok_barkod] if ok_barkod else df[df["URUN_KODU"].str.contains(ok_kod.upper(), na=False)]
            if not sonuc.empty:
                urun = sonuc.iloc[0]
                if urun['DURUM'] == "HAZIR": st.success(f"✅ TAMAM! {urun['URUN_KODU']}")
                else: st.warning(f"⚠️ EKSİK! {urun['URUN_KODU']}")
                
                ca, cb = st.columns(2)
                with ca:
                    st.write(f"**Marka:** {urun['MARKA']}\n\n**Stok:** {urun['STOK']}")
                    st.write(f"**JPG:** {urun['JPG']} | **VIDEO:** {urun['VIDEO']}")
                with cb:
                    if urun['JPG'] == "✅":
                        st.image(f"https://delfieestore.b-cdn.net/{urun['BARKOD']}_(1).jpg", width=300)
                st.divider()
                st.subheader("🎨 Varyantlar")
                st.dataframe(df[df["URUN_KODU"] == urun["URUN_KODU"]][["BARKOD", "RENK", "STOK", "DURUM"]], hide_index=True)
            else: st.error("Bulunamadı!")

    elif page == "📥 Eksik Listesi":
        st.header("📥 Eksik Listesi")
        eksikler = df[df["DURUM"] == "EKSİK"].copy()
        if not eksikler.empty:
            st.dataframe(eksikler, use_container_width=True)
            towrite = io.BytesIO()
            eksikler.to_excel(towrite, index=False, engine='xlsxwriter')
            st.download_button("📥 Excel İndir", towrite.getvalue(), file_name="eksikler.xlsx", type="primary")
else:
    st.info("👋 Başlamak için Excel dosyalarını yükleyip 'Analizi Başlat'a basın.")
