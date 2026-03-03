import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, date
import io

# --- AYARLAR VE SABİTLER ---
SETTINGS_FILE = "ayarlar_cloud.json"
NEBIM_CACHE_FILE = "nebim_listesi.txt"
SAVED_MAIN = "kayitli_ana_liste.xlsx"
SAVED_MEDIA = "kayitli_media_liste.xlsx"

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
    try: return str(int(float(b)))
    except: return str(b).strip()

# --- PDF MOTORU ---
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
    def safe_text(text): return str(text).replace('İ','I').replace('ı','i').replace('Ş','S').replace('ş','s').replace('Ğ','G').replace('ğ','g').replace('Ü','U').replace('ü','u').replace('Ö','O').replace('ö','o').replace('Ç','C').replace('ç','c')
    elements.append(Paragraph(safe_text(baslik), styles['Heading1']))
    elements.append(Spacer(1, 15))
    data = [baslik_satiri]
    for row in veri_matrisi: data.append([safe_text(cell) for cell in row])
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.grey), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('FONTSIZE', (0,0), (-1,-1), 9)]))
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer

st.set_page_config(page_title="Delfiee Cloud Pro", layout="wide", page_icon="☁️")

# Oturum Durumu Kontrolü
if 'ana_veri' not in st.session_state: st.session_state.ana_veri = None
yollar = ayarlari_yukle()

# --- SIDEBAR (DOSYA SAKLAMA SİSTEMİ) ---
with st.sidebar:
    st.title("⚙️ Veri Yönetimi")
    page = st.radio("Menü", ["📊 Özet Panel", "📋 Detaylı Takip", "🔍 Barkod Sorgu", "📥 Eksik Listesi"])
    
    st.divider()
    st.write("📂 **Kalıcı Dosya Yükleme**")
    
    # Dosya 1
    m_file = st.file_uploader("1. Ana Ürün Listesi", type=['xlsx'], key="main_up")
    if m_file:
        with open(SAVED_MAIN, "wb") as f: f.write(m_file.getbuffer())
        st.success("✅ Ana liste kaydedildi.")
    elif os.path.exists(SAVED_MAIN):
        st.info("📦 Önceki Ana Liste hazır.")

    # Dosya 2
    med_file = st.file_uploader("2. Medya Barkod Listesi", type=['xlsx'], key="media_up")
    if med_file:
        with open(SAVED_MEDIA, "wb") as f: f.write(med_file.getbuffer())
        st.success("✅ Medya listesi kaydedildi.")
    elif os.path.exists(SAVED_MEDIA):
        st.info("📦 Önceki Medya Listesi hazır.")

    st.divider()
    bas_tarih = st.date_input("Fiyat Başlangıç Tarihi", yollar["secili_tarih"])

    if st.button("🚀 ANALİZİ BAŞLAT / GÜNCELLE", use_container_width=True, type="primary"):
        if os.path.exists(SAVED_MAIN) and os.path.exists(SAVED_MEDIA):
            with st.spinner("Dosyalar okunuyor..."):
                try:
                    df_p = pd.read_excel(SAVED_MAIN, sheet_name='DmProducts1')
                    df_m = pd.read_excel(SAVED_MEDIA)
                    df_p.columns = [str(c).strip().upper() for c in df_p.columns]
                    df_m.columns = [str(c).strip().upper() for c in df_m.columns]
                    
                    # Medya Setleri
                    get_s = lambda c: set(df_m[c].apply(clean_barcode)) if c in df_m.columns else set()
                    h_jpg, h_vid = get_s('JPG'), get_s('VIDEO')
                    h_kj, h_km = get_s('KOLAJ JPG'), get_s('KOLAJ MP4')

                    processed = []
                    for _, row in df_p.iterrows():
                        b = clean_barcode(row.get('BARCODE'))
                        if not b: continue
                        
                        # Tarih Filtresi
                        if 'FIYATBELIRLEMETARIHI' in df_p.columns:
                            ft = pd.to_datetime(row['FIYATBELIRLEMETARIHI'], errors='coerce').date()
                            if pd.notna(ft) and ft < bas_tarih: continue

                        j, v = b in h_jpg, b in h_vid
                        kj, km = b in h_kj, b in h_km
                        
                        processed.append({
                            "BARKOD": b, "URUN_KODU": str(row.get('PRODUCTCODE', 'N/A')),
                            "MARKA": str(row.get('PRODUCTATT07DESC', 'Belirsiz')),
                            "RENK": str(row.get('COLORDESCRIPTION', '-')),
                            "STOK": int(row.get('INVENTORY', 0)) if pd.notna(row.get('INVENTORY', 0)) else 0,
                            "JPG": "✅" if j else "❌", "VIDEO": "✅" if v else "❌",
                            "KOLAJ_JPG": "✅" if kj else "❌", "KOLAJ_MP4": "✅" if km else "❌",
                            "DURUM": "HAZIR" if j and v else "EKSİK"
                        })
                    st.session_state.ana_veri = pd.DataFrame(processed)
                    yollar["secili_tarih"] = bas_tarih
                    ayarlari_kaydet(yollar)
                    st.rerun()
                except Exception as e: st.error(f"Hata: {e}")
        else: st.error("⚠️ Kayıtlı dosya bulunamadı! Lütfen yükleme yapın.")

# --- SAYFALAR ---
if st.session_state.ana_veri is not None:
    df = st.session_state.ana_veri
    
    if page == "📊 Özet Panel":
        st.header("🚀 Genel Üretim Özeti")
        tot = len(df); rdy = (df["DURUM"] == "HAZIR").sum(); mis = tot - rdy
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📦 Toplam Ürün", tot); c2.metric("✅ Hazır", rdy); c3.metric("❌ Eksik", mis); c4.metric("🎯 Başarı", f"%{(rdy/tot*100):.1f}")
        st.divider()
        ozet = df.groupby("MARKA").agg(TOPLAM=("BARKOD", "count"), HAZIR=("DURUM", lambda x: (x=="HAZIR").sum()), EKSIK=("DURUM", lambda x: (x=="EKSİK").sum())).reset_index()
        ozet["BASARI"] = (ozet["HAZIR"] / ozet["TOPLAM"] * 100).round(1)
        st.dataframe(ozet.sort_values("EKSIK", ascending=False), column_config={"BASARI": st.column_config.ProgressColumn("Tamamlanma %", min_value=0, max_value=100, format="%.1f%%")}, use_container_width=True, hide_index=True)

    elif page == "📋 Detaylı Takip":
        st.header("📋 Akıllı Filtreleme")
        c1, c2 = st.columns(2)
        f_m = c1.multiselect("Markalar", options=sorted(df["MARKA"].unique()))
        f_d = c2.selectbox("Durum", ["Hepsi", "Sadece Hazır", "Sadece Eksik"])
        dff = df.copy()
        if f_m: dff = dff[dff["MARKA"].isin(f_m)]
        if f_d == "Sadece Hazır": dff = dff[dff["DURUM"] == "HAZIR"]
        elif f_d == "Sadece Eksik": dff = dff[dff["DURUM"] == "EKSİK"]
        st.dataframe(dff, use_container_width=True, hide_index=True)

    elif page == "🔍 Barkod Sorgu":
        st.header("🔍 Barkod & Medya Sorgu")
        c_a1, c_a2 = st.columns(2)
        ok_b = c_a1.text_input("🔍 Barkod Okut:")
        ok_k = c_a2.text_input("🔍 Ürün Kodu Gir:")
        if ok_b or ok_k:
            res = df[df["BARKOD"] == ok_b] if ok_b else df[df["URUN_KODU"].str.contains(ok_k.upper(), na=False)]
            if not res.empty:
                u = res.iloc[0]
                st.success(f"Ürün: {u['URUN_KODU']}") if u['DURUM']=="HAZIR" else st.warning(f"Eksik: {u['URUN_KODU']}")
                ca, cb = st.columns(2)
                with ca:
                    st.write(f"**Marka:** {u['MARKA']}\n\n**Stok:** {u['STOK']}")
                    st.write(f"**JPG:** {u['JPG']} | **VIDEO:** {u['VIDEO']}")
                with cb:
                    if u['JPG'] == "✅": st.image(f"https://delfieestore.b-cdn.net/{u['BARKOD']}_(1).jpg", width=300)
                st.divider()
                st.dataframe(df[df["URUN_KODU"] == u["URUN_KODU"]][["BARKOD", "RENK", "STOK", "DURUM"]], hide_index=True, use_container_width=True)

    elif page == "📥 Eksik Listesi":
        st.header("📥 Eksik Listesi Filtreleri")
        eksikler = df[df["DURUM"] == "EKSİK"].copy()
        with st.form("eksik_filtre"):
            c1, c2, c3 = st.columns([2, 2, 1])
            f_marka = c1.multiselect("Marka", options=sorted(eksikler["MARKA"].unique()))
            f_tip = c2.radio("Eksik Odak", ["Hepsi", "Resim Yok", "Video Yok"], horizontal=True)
            f_stok = c3.number_input("Min Stok", value=0)
            st.form_submit_button("Listeyi Güncelle")
        
        if f_marka: eksikler = eksikler[eksikler["MARKA"].isin(f_marka)]
        eksikler = eksikler[eksikler["STOK"] >= f_stok]
        if f_tip == "Resim Yok": eksikler = eksikler[eksikler["JPG"] == "❌"]
        elif f_tip == "Video Yok": eksikler = eksikler[eksikler["VIDEO"] == "❌"]
        
        st.dataframe(eksikler, use_container_width=True, hide_index=True)
        towrite = io.BytesIO()
        eksikler.to_excel(towrite, index=False, engine='xlsxwriter')
        st.download_button("📥 Excel İndir", towrite.getvalue(), file_name="eksikler.xlsx", type="primary", use_container_width=True)
else:
    st.info("👋 Başlamak için dosyaları yükleyin ve Analizi Başlat'a basın.")
