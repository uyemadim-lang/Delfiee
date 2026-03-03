# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Veri Yönetimi")
    page = st.radio("Menü", ["📊 Özet Panel", "📋 Detaylı Takip", "🔍 Barkod Sorgu", "📥 Eksik Listesi"])
    
    st.divider()
    st.write("📂 **Dosya Yükleme Alanı**")
    
    # 1. Ana Excel Yükleme ve Kaydetme
    main_file = st.file_uploader("1. Ana Ürün Listesi (Excel)", type=['xlsx'])
    if main_file:
        with open("gecici_ana_liste.xlsx", "wb") as f:
            f.write(main_file.getbuffer())
        st.success("Ana Liste belleğe kaydedildi!")
    elif os.path.exists("gecici_ana_liste.xlsx"):
        st.info("📌 Önceki Ana Liste hafızada kayıtlı.")

    # 2. Medya Excel Yükleme ve Kaydetme
    media_file = st.file_uploader("2. Medya Barkod Listesi (Excel)", type=['xlsx'])
    if media_file:
        with open("gecici_medya_liste.xlsx", "wb") as f:
            f.write(media_file.getbuffer())
        st.success("Medya Listesi belleğe kaydedildi!")
    elif os.path.exists("gecici_medya_liste.xlsx"):
        st.info("📌 Önceki Medya Listesi hafızada kayıtlı.")

    # 3. Nebim TXT
    nebim_file = st.file_uploader("3. Nebim TXT (Opsiyonel)", type=['txt'])
    if nebim_file:
        with open(NEBIM_CACHE_FILE, "wb") as f: 
            f.write(nebim_file.getbuffer())

    st.divider()
    bas_tarih = st.date_input("Fiyat Başlangıç Tarihi", yollar["secili_tarih"])

    if st.button("🚀 ANALİZİ BAŞLAT", use_container_width=True, type="primary"):
        # Artık file_uploader kutusunun dolu olmasına değil, kaydettiğimiz dosyaların varlığına bakıyoruz
        if os.path.exists("gecici_ana_liste.xlsx") and os.path.exists("gecici_medya_liste.xlsx"):
            with st.spinner("Veriler birleştiriliyor..."):
                try:
                    # Dosyaları hafızadaki kayıtlı yerlerinden oku
                    df_prod = pd.read_excel("gecici_ana_liste.xlsx", sheet_name='DmProducts1')
                    df_media = pd.read_excel("gecici_medya_liste.xlsx")
                    
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
                except Exception as e:
                    st.error(f"Beklenmeyen bir hata oluştu: {e}")
        else:
            st.error("⚠️ Lütfen analizi başlatmadan önce iki Excel dosyasını da yükleyin!!")
