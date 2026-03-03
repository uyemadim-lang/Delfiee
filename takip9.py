import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, date
import io

# --- AYARLAR VE SABİTLER ---
SETTINGS_FILE = "ayarlar.json"
NEBIM_CACHE_FILE = "son_nebim_listesi.txt"

@st.cache_data
def ayarlari_yukle():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                if "secili_tarih" in data:
                    data["secili_tarih"] = datetime.strptime(data["secili_tarih"], "%Y-%m-%d").date()
                if "gizli_markalar" not in data:
                    data["gizli_markalar"] = []
                return data
        except: pass
    return {"excel": "", "jpg": "", "video": "", "k_jpg": "", "k_mp4": "", "secili_tarih": date(2026, 1, 1), "gizli_markalar": []}

def ayarlari_kaydet(ayarlar):
    kayit_verisi = ayarlar.copy()
    if isinstance(kayit_verisi.get("secili_tarih"), (date, datetime)):
        kayit_verisi["secili_tarih"] = kayit_verisi["secili_tarih"].strftime("%Y-%m-%d")
    with open(SETTINGS_FILE, "w") as f:
        json.dump(kayit_verisi, f)

@st.cache_data(ttl=600)
def dosya_listesini_getir(yol):
    if yol and os.path.exists(yol):
        try: return set(f.lower() for f in os.listdir(yol) if not f.startswith('.'))
        except: return set()
    return set()

def nebim_listesini_islemek(content):
    temiz_set = set()
    for line in content.splitlines():
        line = line.strip().lower()
        if not line: continue
        temiz_set.add(line.split('.')[0].split('_(')[0].split('_')[0])
    return temiz_set

# --- PDF OLUŞTURMA MOTORU ---
def pdf_olustur(baslik, baslik_satiri, veri_matrisi, col_widths):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
    except ImportError:
        st.error("PDF oluşturmak için terminalden 'pip install reportlab' komutunu çalıştırmalısınız.")
        return None

    def safe_text(text):
        if pd.isna(text): return ""
        return str(text).replace('İ','I').replace('ı','i').replace('Ş','S').replace('ş','s')\
                        .replace('Ğ','G').replace('ğ','g').replace('Ü','U').replace('ü','u')\
                        .replace('Ö','O').replace('ö','o').replace('Ç','C').replace('ç','c')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    title_style.alignment = 1
    
    elements.append(Paragraph(baslik, title_style))
    elements.append(Spacer(1, 15))
    
    data = [baslik_satiri]
    for row in veri_matrisi:
        data.append([safe_text(cell) for cell in row])
    
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.Color(0.2, 0.2, 0.2)),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
    ]))
    
    for i in range(1, len(data)):
        bg_color = colors.whitesmoke if i % 2 == 0 else colors.white
        t.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), bg_color)]))
    
    elements.append(t)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- EXCEL GÜNCELLİK KONTROL FONKSİYONU ---
def excel_son_guncelleme(excel_yolu):
    if os.path.exists(excel_yolu):
        mtime = os.path.getmtime(excel_yolu)
        return datetime.fromtimestamp(mtime).strftime("%d.%m.%Y %H:%M")
    return "Bulunamadı"

st.set_page_config(page_title="Delfiee Pro v4.9.6", layout="wide", page_icon="📈")

if 'yollar' not in st.session_state: st.session_state.yollar = ayarlari_yukle()
if 'ana_veri' not in st.session_state: st.session_state.ana_veri = None
if "goto_page" in st.session_state:
    st.session_state.page_radio = st.session_state.goto_page
    del st.session_state["goto_page"]

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Kontrol Merkezi")
    page = st.radio("MENÜ", ["📊 Dashboard", "📋 Detaylı Takip", "📷 Barkod Kontrol", "📥 Eksik Listesi (İndir)"], key="page_radio")
    st.divider()
    
    for k in ["excel", "jpg", "video", "k_jpg", "k_mp4"]:
        st.session_state.yollar[k] = st.text_input(f"{k.upper()}:", st.session_state.yollar.get(k, ""))
    
    st.divider()
    st.subheader("🛰️ Nebim Kaynağı")
    nebim_file = st.file_uploader("Yeni Liste Yükle (.txt)", type=['txt'])
    if nebim_file is not None:
        with open(NEBIM_CACHE_FILE, "wb") as f: f.write(nebim_file.getbuffer())
        st.success("Yeni liste kaydedildi.")

    secilen_tarih = st.date_input("Başlangıç Tarihi:", st.session_state.yollar.get("secili_tarih", date(2026, 1, 1)))
    
    if st.button("🔄 VERİLERİ YENİLE", use_container_width=True, type="primary"):
        st.session_state.yollar["secili_tarih"] = secilen_tarih
        ayarlari_kaydet(st.session_state.yollar)
        st.cache_data.clear()
        st.session_state.ana_veri = None 
        st.rerun()

    # Excel güncellik bilgisini Sidebar'a ekliyoruz
    guncel_tarih = excel_son_guncelleme(st.session_state.yollar.get("excel", ""))
    if guncel_tarih != "Bulunamadı":
        st.caption(f"📅 **Excel Son Kayıt:** {guncel_tarih}")

    if st.session_state.ana_veri is not None:
        st.divider()
        st.subheader("👁️ Görünüm Ayarları")
        tum_markalar = sorted(st.session_state.ana_veri["MARKA"].unique())
        mevcut_gizli = [m for m in st.session_state.yollar.get("gizli_markalar", []) if m in tum_markalar]
        
        yeni_gizli = st.multiselect("Gizlenecek Markalar", options=tum_markalar, default=mevcut_gizli)
        if set(yeni_gizli) != set(mevcut_gizli):
            st.session_state.yollar["gizli_markalar"] = yeni_gizli
            ayarlari_kaydet(st.session_state.yollar)
            st.rerun()

# --- VERİ İŞLEME MOTORU ---
if st.session_state.ana_veri is None:
    if os.path.exists(st.session_state.yollar["excel"]):
        try:
            with st.status("Veriler analiz ediliyor...", expanded=True) as status_box:
                df_raw = pd.read_excel(st.session_state.yollar["excel"], sheet_name='DmProducts1')
                orijinal_sutunlar = [str(c).strip().lstrip('\ufeff').strip() for c in df_raw.columns]
                def _norm(s): return str(s).strip().upper().replace(" ", "").replace("_", "")
                
                marka_sutun_idx = next((idx for idx, c in enumerate(orijinal_sutunlar) if _norm(c) == "PRODUCTATT07DESC" or "ProductAtt07Desc" in _norm(c)), None)
                df_raw.columns = [str(c).strip().upper() for c in df_raw.columns]
                
                col_barcode, col_code, col_color, col_beden, col_inv = 'BARCODE', 'PRODUCTCODE', 'COLORDESCRIPTION', 'PRODUCTATT04DESC', 'INVENTORY'
                col_brand = df_raw.columns[marka_sutun_idx] if marka_sutun_idx is not None else 'PRODUCTATT07DESC'
                
                col_category = next((cand for cand in ('CATEGORY', 'KATEGORI', 'PRODUCTATT01DESC', 'MAINPRODUCTGROUP') if cand in df_raw.columns), None)
                if 'FIYATBELIRLEMETARIHI' in df_raw.columns:
                    df_raw['FIYATBELIRLEMETARIHI'] = pd.to_datetime(df_raw['FIYATBELIRLEMETARIHI'], errors='coerce')
                    df_raw = df_raw[df_raw['FIYATBELIRLEMETARIHI'].dt.date >= secilen_tarih]
                
                h_nebim = set()
                if os.path.exists(NEBIM_CACHE_FILE):
                    try:
                        with open(NEBIM_CACHE_FILE, "r", encoding="utf-8") as f: h_nebim = nebim_listesini_islemek(f.read())
                    except:
                        with open(NEBIM_CACHE_FILE, "r", encoding="latin-1") as f: h_nebim = nebim_listesini_islemek(f.read())

                h_jpg = dosya_listesini_getir(st.session_state.yollar["jpg"])
                h_vid = dosya_listesini_getir(st.session_state.yollar["video"])
                h_kjpg = dosya_listesini_getir(st.session_state.yollar["k_jpg"])
                h_kmp4 = dosya_listesini_getir(st.session_state.yollar["k_mp4"])
                
                processed = []
                for _, row in df_raw.iterrows():
                    raw_barcode = row.get(col_barcode, '')
                    if pd.isna(raw_barcode): continue
                    barkod = str(int(float(raw_barcode))) if isinstance(raw_barcode, (float, int)) else str(raw_barcode).strip()
                    barkod_l = barkod.lower()
                    
                    try: inv_val = int(float(row.get(col_inv, 0))) if not pd.isna(row.get(col_inv, 0)) else 0
                    except: inv_val = 0
                    
                    j_count = sum(1 for f in h_jpg if f.startswith(f"{barkod_l}_("))
                    v_ok, kj_ok, km_ok, n_ok = f"{barkod_l}.mp4" in h_vid, f"{barkod_l}.jpg" in h_kjpg, f"{barkod_l}.mp4" in h_kmp4, barkod_l in h_nebim
                    
                    marka = str(row.get(col_brand, 'Belirsiz')).strip()
                    if marka.lower() in ('nan', 'none', ''): marka = "Belirsiz"

                    processed.append({
                        "BARKOD": barkod, "URUN_KODU": str(row.get(col_code, 'N/A')), "RENK": str(row.get(col_color, 'N/A')),
                        "BEDEN": str(row.get(col_beden, '')), "KATEGORI": str(row.get(col_category, '')), "MARKA": marka, 
                        "INVENTORY": inv_val, "JPG_ADET": int(j_count), "VIDEO_VAR": bool(v_ok), "VIDEO": "✅" if v_ok else "❌",
                        "KOLAJ_JPG_VAR": bool(kj_ok), "KOLAJ_JPG": "✅" if kj_ok else "❌",
                        "KOLAJ_MP4_VAR": bool(km_ok), "KOLAJ_MP4": "✅" if km_ok else "❌",
                        "NEBIM": "✅" if n_ok else "❌", "HAZIR": "HAZIR" if j_count >= 1 and v_ok else "EKSİK"
                    })
                st.session_state.ana_veri = pd.DataFrame(processed).sort_values("INVENTORY", ascending=False)
                status_box.update(label="Analiz Tamamlandı!", state="complete")
                st.rerun()
        except Exception as e: st.error(f"Excel Okuma Hatası: {e}")

aktif_veri = None
if st.session_state.ana_veri is not None:
    gizli_liste = st.session_state.yollar.get("gizli_markalar", [])
    aktif_veri = st.session_state.ana_veri[~st.session_state.ana_veri["MARKA"].isin(gizli_liste)].copy()

# Sayfa üstü güncellik bildirimi için yardımcı değişken
ust_guncellik_metni = f"*(Veri Kaynağı Son Güncelleme: {guncel_tarih})*" if guncel_tarih != "Bulunamadı" else ""

# --- SAYFA 1: DASHBOARD ---
if page == "📊 Dashboard":
    st.header("🚀 Üretim Özet Paneli")
    st.caption(ust_guncellik_metni)
    
    if aktif_veri is not None and not aktif_veri.empty:
        st.caption("👉 Bir markaya tıklayarak detaylı takip sayfasına hızlıca geçiş yapabilirsiniz.")

        brand_stats = aktif_veri.groupby("MARKA").apply(lambda x: pd.Series({
            "HAZIR": (x["HAZIR"] == "HAZIR").sum(),
            "EKSİK": (x["HAZIR"] == "EKSİK").sum(),
            "TOPLAM": len(x)
        })).reset_index()

        brand_stats["DURUM"] = (brand_stats["HAZIR"] / brand_stats["TOPLAM"]) * 100
        brand_stats = brand_stats.sort_values("EKSİK", ascending=False)

        event = st.dataframe(
            brand_stats,
            column_config={
                "MARKA": st.column_config.TextColumn("Marka"),
                "HAZIR": st.column_config.NumberColumn("Hazır ✅"),
                "EKSİK": st.column_config.NumberColumn("Eksik ❌"),
                "TOPLAM": st.column_config.NumberColumn("Toplam"),
                "DURUM": st.column_config.ProgressColumn("Tamamlanma Oranı", format="%.0f%%", min_value=0, max_value=100),
            },
            use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun", key="brand_table"
        )

        if event.selection.rows:
            st.session_state.secili_marka_filtre = [brand_stats.iloc[event.selection.rows[0]]["MARKA"]]
            st.session_state.goto_page = "📋 Detaylı Takip"
            st.rerun()

        st.write("") 
        st.divider()
        st.write("**📊 Genel Üretim Özeti**")
        
        total = len(aktif_veri)
        ready = len(aktif_veri[aktif_veri["HAZIR"] == "HAZIR"])
        oran_yuzde = (ready/total*100) if total > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        with c1: st.info(f"**📦 Toplam Ürün:** {total}")
        with c2: st.success(f"**✅ Tamamlanan:** {ready}")
        with c3:
            if oran_yuzde >= 80: st.success(f"**🎯 Başarı Oranı:** %{oran_yuzde:.1f}")
            elif oran_yuzde >= 40: st.warning(f"**🎯 Başarı Oranı:** %{oran_yuzde:.1f}")
            else: st.error(f"**🎯 Başarı Oranı:** %{oran_yuzde:.1f}")

        st.divider()
        pdf_matris = []
        for _, r in brand_stats.iterrows():
            pdf_matris.append([str(r['MARKA']), str(r['HAZIR']), str(r['EKSİK']), str(r['TOPLAM']), f"%{r['DURUM']:.0f}"])
            
        dash_pdf = pdf_olustur("Marka Uretim Durum Raporu", ["MARKA", "HAZIR", "EKSIK", "TOPLAM", "BASARI"], pdf_matris, [150, 80, 80, 80, 90])
        if dash_pdf:
            st.download_button(label="📥 Bu Tabloyu PDF Olarak İndir", data=dash_pdf, file_name=f"delfiee_ozet_{date.today()}.pdf", mime="application/pdf", type="primary", use_container_width=True)

# --- SAYFA 2: DETAYLI TAKİP ---
elif page == "📋 Detaylı Takip":
    st.title("📋 Akıllı Filtreleme Paneli")
    st.caption(ust_guncellik_metni)
    
    if aktif_veri is not None and not aktif_veri.empty:
        with st.expander("🔍 Tüm Medya ve Stok Filtreleri", expanded=True):
            with st.form("filter_form"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    f_marka = st.multiselect("Markalar", options=sorted(aktif_veri["MARKA"].unique()), default=[m for m in st.session_state.get("secili_marka_filtre", []) if m in aktif_veri["MARKA"].unique()])
                    f_genel = st.selectbox("Genel Durum", ["Hepsi", "Sadece Hazırlar", "Sadece Eksikler"])
                    inv_min, inv_max = int(aktif_veri["INVENTORY"].min()), int(aktif_veri["INVENTORY"].max())
                    f_inv = st.slider("Envanter (Stok) Aralığı", inv_min, inv_max, (inv_min, inv_max))
                with c2:
                    st.write("**Medya Var Analizi**")
                    f_has_jpg, f_has_vid = st.checkbox("Resmi Olanlar"), st.checkbox("Videosu Olanlar")
                    f_has_kj, f_has_km = st.checkbox("Kolaj JPG Olanlar"), st.checkbox("Kolaj MP4 Olanlar")
                with c3:
                    st.write("**Eksik Analizi**")
                    f_no_jpg, f_no_vid = st.checkbox("Resmi Yok"), st.checkbox("Videosu Yok")
                    f_no_kj, f_no_km = st.checkbox("Kolaj JPG Yok"), st.checkbox("Kolaj MP4 Yok")
                    f_no_nebim = st.checkbox("Nebim'de Yok")
                st.form_submit_button("Süzgeci Çalıştır", type="primary", use_container_width=True)

        df = aktif_veri.copy()
        df = df[(df["INVENTORY"] >= f_inv[0]) & (df["INVENTORY"] <= f_inv[1])]
        if f_marka: df = df[df["MARKA"].isin(f_marka)]
        if f_genel == "Sadece Hazırlar": df = df[df["HAZIR"] == "HAZIR"]
        elif f_genel == "Sadece Eksikler": df = df[df["HAZIR"] == "EKSİK"]
        
        if f_has_jpg: df = df[df["JPG_ADET"] > 0]
        if f_has_vid: df = df[df["VIDEO_VAR"] == True]
        if f_has_kj:  df = df[df["KOLAJ_JPG_VAR"] == True]
        if f_has_km:  df = df[df["KOLAJ_MP4_VAR"] == True]
        if f_no_jpg:  df = df[df["JPG_ADET"] == 0]
        if f_no_vid:  df = df[df["VIDEO_VAR"] == False]
        if f_no_kj:   df = df[df["KOLAJ_JPG_VAR"] == False]
        if f_no_km:   df = df[df["KOLAJ_MP4_VAR"] == False]
        if f_no_nebim: df = df[df["NEBIM"] == "❌"]

        st.subheader(f"🔍 Bulunan Ürün: {len(df)}")
        st.dataframe(df[["BARKOD", "URUN_KODU", "RENK", "MARKA", "INVENTORY", "JPG_ADET", "VIDEO", "KOLAJ_JPG", "KOLAJ_MP4", "NEBIM", "HAZIR"]], use_container_width=True, hide_index=True)

        if not df.empty:
            st.divider()
            markalar = df["MARKA"].unique()
            pdf_baslik = f"{markalar[0]} Urun Raporu" if len(markalar) == 1 else "Filtrelenmis Urun Raporu"

            pdf_matris = [[r.get("BARKOD", ""), r.get("URUN_KODU", ""), r.get("KATEGORI", ""), r.get("RENK", ""), r.get("BEDEN", "")] for _, r in df.iterrows()]
            detay_pdf = pdf_olustur(pdf_baslik, ["BARCODE", "CODE", "CATEGORY", "COLOR", "BEDEN"], pdf_matris, [110, 110, 110, 110, 95])
            
            if detay_pdf:
                st.download_button(label="📥 Bu Listeyi PDF Olarak İndir", data=detay_pdf, file_name=f"{pdf_baslik.replace(' ', '_')}_{date.today()}.pdf", mime="application/pdf", type="primary", use_container_width=True)

# --- SAYFA 3: BARKOD & KOD KONTROL ---
elif page == "📷 Barkod Kontrol":
    st.title("📷 Anlık Barkod & Medya Kontrolü")
    st.caption(ust_guncellik_metni)
    st.write("El terminali ile barkodu okutabilir veya aradığınız Ürün Kodunu manuel yazabilirsiniz.")
    
    c_ara1, c_ara2 = st.columns(2)
    with c_ara1:
        okunan_barkod = st.text_input("🔍 Barkod Okutunuz:", key="barkod_okuyucu")
    with c_ara2:
        okunan_kod = st.text_input("🔍 Ürün Kodu Giriniz (Örn: AMH26...):", key="kod_okuyucu")
    
    if okunan_barkod or okunan_kod:
        if aktif_veri is not None:
            sonuc = pd.DataFrame()
            aranan_gorsel_barkod = ""
            
            if okunan_barkod:
                aranan = str(okunan_barkod).strip()
                sonuc = aktif_veri[aktif_veri["BARKOD"] == aranan]
                aranan_gorsel_barkod = aranan
                
            elif okunan_kod:
                aranan = str(okunan_kod).strip().upper()
                sonuc = aktif_veri[aktif_veri["URUN_KODU"].str.upper() == aranan]
                if sonuc.empty:
                    sonuc = aktif_veri[aktif_veri["URUN_KODU"].str.upper().str.contains(aranan, na=False)]
                if not sonuc.empty:
                    aranan_gorsel_barkod = sonuc.iloc[0]["BARKOD"]
            
            if not sonuc.empty:
                urun = sonuc.iloc[0]
                
                if urun['HAZIR'] == "HAZIR":
                    st.success(f"✅ Bu Ürün TAMAMLANMIŞ! ({urun['MARKA']} - {urun['URUN_KODU']})")
                else:
                    st.warning(f"⚠️ Bu Ürünün EKSİKLERİ VAR! ({urun['MARKA']} - {urun['URUN_KODU']})")
                
                c1, c2 = st.columns([1, 1])
                
                with c1:
                    st.subheader("📦 Ürün Detayları")
                    st.write(f"**Marka:** {urun['MARKA']}")
                    st.write(f"**Ürün Kodu:** {urun['URUN_KODU']}")
                    st.write(f"**Kategori:** {urun['KATEGORI']}")
                    st.write(f"**Renk / Beden:** {urun['RENK']} / {urun['BEDEN']}")
                    st.write(f"**Stok (Inventory):** {urun['INVENTORY']}")
                    
                    st.divider()
                    st.subheader("🎬 Medya Durumu")
                    
                    resim_durum = f"✅ ÇEKİLMİŞ ({urun['JPG_ADET']} adet)" if urun['JPG_ADET'] > 0 else "❌ ÇEKİLMEMİŞ"
                    video_durum = "✅ ÇEKİLMİŞ" if urun['VIDEO_VAR'] else "❌ ÇEKİLMEMİŞ"
                    
                    st.write(f"**📸 Ürün Fotoğrafı:** {resim_durum}")
                    st.write(f"**🎥 Ürün Videosu:** {video_durum}")
                    st.write(f"**🖼️ Kolaj (JPG/MP4):** {urun['KOLAJ_JPG']} / {urun['KOLAJ_MP4']}")

                with c2:
                    if urun['JPG_ADET'] > 0:
                        jpg_klasoru = st.session_state.yollar.get("jpg", "")
                        gorsel_gosterildi = False
                        
                        if os.path.exists(jpg_klasoru):
                            for dosya in os.listdir(jpg_klasoru):
                                if dosya.lower().startswith(f"{aranan_gorsel_barkod.lower()}_("):
                                    tam_yol = os.path.join(jpg_klasoru, dosya)
                                    try:
                                        st.image(tam_yol, caption=f"{urun['URUN_KODU']} - {urun['RENK']}", width=350)
                                        gorsel_gosterildi = True
                                        break
                                    except: pass
                        
                        if not gorsel_gosterildi:
                            st.info("⚠️ Resim var görünüyor ancak klasörde açılamadı.")
                    else:
                        st.info("📷 Bu ürün için henüz görsel bulunmamaktadır.")
                        
                st.divider()
                st.subheader("🎨 Bu Ürünün Diğer Renk & Beden Seçenekleri")
                
                varyantlar = aktif_veri[aktif_veri["URUN_KODU"] == urun["URUN_KODU"]].copy()
                varyant_gosterim = varyantlar[["BARKOD", "RENK", "BEDEN", "INVENTORY", "HAZIR"]]
                st.dataframe(varyant_gosterim, hide_index=True, use_container_width=True)

            else:
                st.error("❌ Okutulan barkod veya girilen ürün kodu Excel verilerinde bulunamadı!")
        else:
            st.warning("⚠️ Lütfen önce sol menüden 'Verileri Yenile' butonuna basarak sistemi güncelleyin.")

# --- SAYFA 4: EKSİK LİSTESİ ---
else:
    st.title("📥 Çekilecekler ve Eksikler Listesi")
    st.caption(ust_guncellik_metni)
    
    if aktif_veri is not None and not aktif_veri.empty:
        eksik_df = aktif_veri[aktif_veri["HAZIR"] == "EKSİK"].copy()
        
        with st.form("eksik_filtre"):
            c1, c2, c3 = st.columns([2,2,1])
            f_m_eksik = c1.multiselect("Markayı Süz", options=sorted(eksik_df["MARKA"].unique()))
            f_t_eksik = c2.radio("Eksik Türüne Odaklan", ["Hepsi", "Video Eksik", "Resim Eksik", "Kolaj Eksik"], horizontal=True)
            inv_min_e, inv_max_e = (int(eksik_df["INVENTORY"].min()), int(eksik_df["INVENTORY"].max())) if not eksik_df.empty else (0,0)
            f_inv_e = c3.number_input("Min Stok", value=inv_min_e)
            st.form_submit_button("Listeyi Hazırla", use_container_width=True)

        if f_m_eksik: eksik_df = eksik_df[eksik_df["MARKA"].isin(f_m_eksik)]
        eksik_df = eksik_df[eksik_df["INVENTORY"] >= f_inv_e]
        
        if f_t_eksik == "Video Eksik": eksik_df = eksik_df[eksik_df["VIDEO_VAR"] == False]
        elif f_t_eksik == "Resim Eksik": eksik_df = eksik_df[eksik_df["JPG_ADET"] == 0]
        elif f_t_eksik == "Kolaj Eksik": eksik_df = eksik_df[(eksik_df["KOLAJ_JPG_VAR"] == False) | (eksik_df["KOLAJ_MP4_VAR"] == False)]

        st.dataframe(eksik_df[["BARKOD", "URUN_KODU", "KATEGORI", "RENK", "BEDEN", "MARKA", "INVENTORY", "JPG_ADET", "VIDEO"]], use_container_width=True, hide_index=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            eksik_df[["BARKOD", "URUN_KODU", "KATEGORI", "RENK", "BEDEN"]].to_excel(writer, index=False, sheet_name="Cekilecekler")
        st.download_button("📥 Seçili Eksikleri Excel İndir", data=output.getvalue(), file_name=f"delfiee_eksik_listesi_{date.today()}.xlsx", use_container_width=True)