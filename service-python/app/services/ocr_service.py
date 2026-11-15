import gc
import re
import datetime
from typing import List, Optional
import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

from app.schemas.ocr import ReceiptParsedData, OCRExtractResponse


class OCRService:
    _instance = None
    _reader: Optional[RapidOCR] = None

    @classmethod
    def get_reader(cls) -> RapidOCR:
        if cls._reader is None:
            cls._reader = RapidOCR()
        return cls._reader

    @classmethod
    def preprocess_image(cls, image_bytes: bytes) -> np.ndarray:
        """
        Melakukan preprocessing gambar menggunakan OpenCV:
        1. Decode bytes ke array numpy OpenCV
        2. Resize proporsional jika lebar > 1000px (mencegah lonjakan RAM EasyOCR)
        3. Konversi ke Grayscale
        4. Denoising Gaussian Blur
        5. CLAHE untuk penajaman kontras teks struk
        """
        np_arr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("File gambar tidak valid atau rusak.")

        # Batasi lebar maksimal 1000px untuk mencegah OOM saat inferensi
        max_width = 1000
        h, w = image.shape[:2]
        if w > max_width:
            scale = max_width / float(w)
            image = cv2.resize(image, (max_width, int(h * scale)), interpolation=cv2.INTER_AREA)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)

        return enhanced

    @classmethod
    def clean_ocr_number_noise(cls, text: str) -> str:
        """
        Membersihkan noise OCR yang menempel pada angka:
        - Ubah huruf 'o' atau 'O' yang menempel dengan digit menjadi '0'
        - Ubah huruf 'l' atau 'I' yang menempel dengan digit menjadi '1'
        """
        cleaned = text.strip()
        cleaned = re.sub(r'(?<=\d)[oO]|[oO](?=\d)', '0', cleaned)
        cleaned = re.sub(r'(?<=\d)[lI]|[lI](?=\d)', '1', cleaned)
        return cleaned

    @classmethod
    def parse_amount(cls, text: str) -> Optional[float]:
        """
        Mengonversi teks nominal Rupiah ke integer/float utuh:
        1. Konversi noise OCR o/O menjadi 0 terlebih dahulu SEBELUM menghapus huruf/simbol non-digit
           (Contoh: "Rp11.00o" -> "Rp11.000")
        2. Perbaiki pola '.00' setelah Rp / nominal ribuan jika 1 digit nol terpotong OCR
           (Contoh: "Rp11.00" -> "Rp11.000")
        3. Hapus simbol mata uang, spasi, dan seluruh pemisah ribuan ('.' dan ',')
        4. Konversi int() utuh tanpa konversi float() sebelum pembersihan ribuan
        """
        if not text:
            return None

        # 1. Konversi Noise OCR o/O menjadi 0 terlebih dahulu
        # Contoh: "Rp11.00o" -> "Rp11.000"
        s = re.sub(r'(?<=\d)[oO]|[oO](?=\d)', '0', text.strip())
        s = re.sub(r'(?<=\d)[lI]|[lI](?=\d)', '1', s)

        has_rp = bool(re.search(r'(?:rp\.?|idr)', s, re.IGNORECASE))

        # Bersihkan prefix mata uang dan label umum
        cleaned = re.sub(
            r'^(?:rp\.?|idr|total|bayar|kamu\s*membayar|nominal|netto|net)[:\s=]*',
            '',
            s,
            flags=re.IGNORECASE
        ).strip()

        # Sisakan hanya digit, titik, dan koma
        cleaned = re.sub(r'[^\d,\.]', '', cleaned)
        if not cleaned:
            return None

        # 2. Tangani Sen di Akhir Angka jika ada format desimal sah (,00 atau ribuan diikuti .00)
        # Contoh: 11.000,00 -> 11.000
        cleaned = re.sub(r',00$', '', cleaned)
        # Jika ada pemisah ribuan jelas diikuti .00 (misal 11,000.00 atau 1.250.000.00)
        if re.search(r'[,\.]\d{3}\.00$', cleaned):
            cleaned = re.sub(r'\.00$', '', cleaned)

        # Fallback Noise OCR: Jika ada format ribuan dengan hanya 2 nol (misal Rp11.00 atau 11.00 atau 74.00)
        # akibat 1 digit nol di belakang terpotong oleh EasyOCR
        if (has_rp and re.search(r'^\d{1,3}\.00$', cleaned)) or re.search(r'^\d{2,3}\.00$', cleaned):
            cleaned = cleaned + "0"

        # 3. Hapus SELURUH pemisah ribuan ('.' dan ',')
        cleaned = cleaned.replace('.', '').replace(',', '')

        # 4. Pastikan tidak ada konversi float() sebelum pembersihan ribuan
        if not cleaned or not cleaned.isdigit():
            return None

        try:
            val = float(int(cleaned))
            return val if val > 0 else None
        except (ValueError, TypeError):
            return None

    @classmethod
    def extract_total(cls, lines: List[str]) -> Optional[float]:
        """
        Pencarian Total Pembayaran / Transfer (Struk Fisik + Bukti QRIS / E-Wallet):
        1. Prioritaskan kata kunci e-wallet & struk:
           - Kamu Membayar, Total Pembayaran, Total Bayar, Nominal, Jumlah Transfer, dsb.
        2. Periksa nominal pada baris yang sama setelah kata kunci maupun 1-2 baris setelahnya.
        3. Cegah tahun (2020-2035) dan nomor referensi/SN panjang terbaca sebagai nominal pada logika fallback.
        """
        # Daftar keyword pembayaran spesifik (diurutkan berdasarkan prioritas)
        payment_keywords = [
            r'kamu\s*membayar',
            r'total\s*pembayaran',
            r'total\s*bayar',
            r'total\s*transaksi',
            r'total\s*tagihan',
            r'total\s*belanja',
            r'grand\s*total',
            r'nominal\s*transfer',
            r'nominal\s*transaksi',
            r'nominal\s*pembayaran',
            r'nominal',
            r'jumlah\s*transfer',
            r'jumlah\s*pembayaran',
            r'jumlah\s*bayar',
            r'nilai\s*transaksi',
            r'transfer\s*berhasil',
            r'pembayaran\s*berhasil',
            r'bayar',
            r'tunai',
            r'total',  # Wajib mengecualikan subtotal
        ]

        # Pola token nominal (menjaga prefix Rp/IDR jika ada)
        token_regex = re.compile(r'(?:(?:rp\.?|idr)\s*)?[0-9oO\.,]{3,}', re.IGNORECASE)

        # Prioritas 1: Cari pada baris yang mengandung keyword di atas
        for kw in payment_keywords:
            pattern = re.compile(rf'\b{kw}\b', re.IGNORECASE)
            for idx, raw_line in enumerate(lines):
                line = raw_line.strip()

                # Selalu abaikan jika baris mengandung Subtotal
                if re.search(r'sub\s*total', line, re.IGNORECASE):
                    continue

                if pattern.search(line):
                    # 1a. Periksa apakah ada nominal di baris yang sama
                    same_line_tokens = token_regex.findall(line)
                    for token in same_line_tokens:
                        amount = cls.parse_amount(token)
                        if amount and not cls._is_invalid_amount_candidate(amount, line):
                            return amount

                    # 1b. Periksa 1 hingga 2 baris tepat setelahnya
                    for offset in [1, 2]:
                        next_idx = idx + offset
                        if next_idx < len(lines):
                            next_line = lines[next_idx].strip()

                            # Lewati jika baris lanjutan adalah label lain
                            if re.search(r'^(cash|change|kembali|kembalian|subtotal|pajak|tax|disc|metode|waktu|tanggal|transaksi)', next_line, re.IGNORECASE):
                                continue

                            next_tokens = token_regex.findall(next_line)
                            for token in next_tokens:
                                amount = cls.parse_amount(token)
                                if amount and not cls._is_invalid_amount_candidate(amount, next_line):
                                    return amount

        # Prioritas 2: Fallback pencarian nominal terbesar yang valid (membersihkan tahun dan nomor referensi)
        candidates = []
        for line in lines:
            line_str = line.strip()

            # Abaikan subtotal atau baris nomor referensi/SN/ID/VA/No
            if re.search(r'sub\s*total', line_str, re.IGNORECASE):
                continue
            if cls._is_reference_line(line_str):
                continue

            found_tokens = token_regex.findall(line_str)
            for t in found_tokens:
                parsed = cls.parse_amount(t)
                if parsed and not cls._is_invalid_amount_candidate(parsed, line_str):
                    # Rentang realistis nominal belanja / transfer (Rp 500 s/d Rp 100.000.000)
                    if 500 <= parsed <= 100_000_000:
                        candidates.append(parsed)

        return max(candidates) if candidates else None

    @classmethod
    def _is_invalid_amount_candidate(cls, amount: float, line_context: str) -> bool:
        """
        Mendeteksi apakah sebuah angka BUKAN nominal harga:
        - Angka tahun (2020 - 2035) yang berdiri sendiri atau di baris tanggal/waktu
        - Nomor referensi / SN / VA / ID yang panjangnya lebih dari 9 digit
        """
        # 1. Cek tahun (2020 s/d 2035)
        if 2020 <= amount <= 2035:
            # Jika tepat sama dengan tahun dan baris mengandung kata/simbol tanggal/waktu
            if any(term in line_context.lower() for term in ['wib', 'wita', 'wit', 'tgl', 'tanggal', 'date', 'time', 'jam', ':', '/', '-']):
                return True
            # Jika nominal persis 4 digit tahun (jarang sekali pengeluaran Rp 2.026)
            if float(int(amount)) == amount:
                return True

        # 2. Cek apakah angka berasal dari deretan digit panjang (> 9 digit) misal order ID
        digits_only = re.sub(r'\D', '', line_context)
        if len(digits_only) >= 9 and str(int(amount)) in digits_only:
            return True

        return False

    @classmethod
    def _is_reference_line(cls, line: str) -> bool:
        """
        Mengecek apakah baris berisi nomor referensi, SN, kode transaksi, dsb.
        """
        ref_keywords = [
            r'transaksi\s*sn', r'order\s*sn', r'ref', r'\bid\b', r'\bva\b',
            r'\bno\b', r'no\.', r'nomor', r'kode\s*transaksi', r'invoice',
            r'terminal', r'trace', r'merchant\s*pan', r'rrn'
        ]
        line_lower = line.lower()
        return any(re.search(kw, line_lower) for kw in ref_keywords)

    @classmethod
    def extract_date(cls, lines: List[str]) -> Optional[str]:
        """
        Ekstraksi dan normalisasi tanggal di seluruh baris teks:
        - Format teks nama bulan ID / EN: '12 Nov 2026', '12 November 2026', '12-Nov-2026'
        - Format numerik: 'YYYY-MM-DD', 'DD/MM/YYYY', 'DD-MM-YYYY'
        - Mengembalikan format ISO: 'YYYY-MM-DD'
        """
        months_map = {
            'jan': 1, 'januari': 1, 'january': 1,
            'feb': 2, 'februari': 2, 'february': 2,
            'mar': 3, 'maret': 3, 'march': 3,
            'apr': 4, 'april': 4,
            'mei': 5, 'may': 5,
            'jun': 6, 'juni': 6, 'june': 6,
            'jul': 7, 'juli': 7, 'july': 7,
            'agt': 8, 'agu': 8, 'agustus': 8, 'aug': 8, 'august': 8,
            'sep': 9, 'september': 9,
            'okt': 10, 'oktober': 10, 'oct': 10, 'october': 10,
            'nov': 11, 'november': 11,
            'des': 12, 'desember': 12, 'dec': 12, 'december': 12
        }

        month_names_regex = r'(\d{1,2})[\s\-\/\.]([A-Za-z]{3,9})[\s\-\/\.](\d{4})'
        full_text = "\n".join(lines)

        for match in re.finditer(month_names_regex, full_text):
            day_str, month_str, year_str = match.groups()
            month_key = month_str.lower()
            if month_key in months_map:
                try:
                    d = int(day_str)
                    m = months_map[month_key]
                    y = int(year_str)
                    if 2000 <= y <= 2035 and 1 <= m <= 12 and 1 <= d <= 31:
                        return f"{y:04d}-{m:02d}-{d:02d}"
                except ValueError:
                    continue

        numeric_patterns = [
            r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})',     # YYYY-MM-DD
            r'(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})',     # DD-MM-YYYY
        ]

        for p in numeric_patterns:
            for match in re.finditer(p, full_text):
                groups = match.groups()
                try:
                    if len(groups[0]) == 4:
                        y, m, d = int(groups[0]), int(groups[1]), int(groups[2])
                    else:
                        d, m, y = int(groups[0]), int(groups[1]), int(groups[2])

                    if 2000 <= y <= 2035 and 1 <= m <= 12 and 1 <= d <= 31:
                        return f"{y:04d}-{m:02d}-{d:02d}"
                except ValueError:
                    continue

        return datetime.date.today().strftime("%Y-%m-%d")

    @classmethod
    def extract_merchant(cls, lines: List[str]) -> Optional[str]:
        """
        Ekstraksi merchant_name untuk struk fisik & QRIS / Bukti Transfer E-Wallet:
        1. Deteksi label penerima QRIS / E-Wallet / Outlet:
           'Bayar Ke', 'Penerima', 'Merchant', 'Nama Merchant', 'Kepada', 'Tujuan', 'Outlet Name', 'Outlet'
        2. Deteksi brand khusus terkemuka (misal Kopi Kenangan, Starbucks, Indomaret, dll).
        3. Jika ada brand + outlet, gabungkan (misal: 'Kopi Kenangan - Ruko Telagamas Semarang').
        4. Abaikan judul/label umum e-wallet (Rincian Pesanan, Detail Transaksi, Bukti Pembayaran, Saldo ShopeePay, dll).
        """
        full_text_upper = "\n".join(lines).upper()

        # 1. Deteksi Brand Khusus Terkenal
        brand_mapping = {
            "KENANGAN": "Kopi Kenangan",
            "KOPI KENANGAN": "Kopi Kenangan",
            "STARBUCKS": "Starbucks",
            "JANJI JIWA": "Kopi Janji Jiwa",
            "POINT COFFEE": "Point Coffee",
            "INDOMARET": "Indomaret",
            "ALFAMART": "Alfamart",
            "ALFAMIDI": "Alfamidi",
            "SUPERINDO": "Super Indo",
            "HYPERMART": "Hypermart",
            "TRANSMART": "Transmart",
            "MCDONALD": "McDonald's",
            "MCD": "McDonald's",
            "KFC": "KFC",
            "BURGER KING": "Burger King",
            "J.CO": "J.CO Donuts & Coffee",
            "CHATIME": "Chatime",
            "PIZZA HUT": "Pizza Hut",
            "DOMINO": "Domino's Pizza",
            "PERTAMINA": "SPBU Pertamina",
            "SHELL": "SPBU Shell",
            "GUARDIAN": "Guardian",
            "WATSONS": "Watsons"
        }

        detected_brand = None
        for key, brand_official in brand_mapping.items():
            if re.search(rf'\b{re.escape(key)}\b', full_text_upper):
                detected_brand = brand_official
                break

        # 2. Deteksi label penerima QRIS / Transfer / Outlet Name
        recipient_labels = [
            r'bayar\s*ke',
            r'penerima',
            r'nama\s*merchant',
            r'merchant',
            r'transfer\s*ke',
            r'tujuan',
            r'kepada',
            r'outlet\s*name',
            r'outlet'
        ]

        detected_recipient = None
        for i, line in enumerate(lines):
            clean = line.strip()
            for label in recipient_labels:
                match = re.search(rf'^{label}\s*[:=]?\s*(.*)', clean, re.IGNORECASE)
                if match:
                    val = match.group(1).strip()
                    val = re.sub(r'^[:=\-\s]+', '', val).strip()
                    if val and len(val) >= 3 and not cls._is_generic_metadata(val):
                        detected_recipient = val
                        break
                    elif i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if len(next_line) >= 3 and not cls._is_generic_metadata(next_line):
                            detected_recipient = next_line
                            break
            if detected_recipient:
                break

        # Jika ditemukan brand dan outlet/penerima
        if detected_brand:
            if detected_recipient and detected_recipient.lower() not in detected_brand.lower():
                return f"{detected_brand} - {detected_recipient}"
            return detected_brand

        # Jika ditemukan penerima dari QRIS/E-Wallet (misal 'Padang Murah Hasanudin')
        if detected_recipient:
            return detected_recipient

        # 3. Fallback: Cari baris teratas yang bukan metadata generik / header aplikasi
        for line in lines[:8]:
            clean_line = line.strip()
            if cls._is_generic_metadata(clean_line):
                continue
            # Jika mengandung setidaknya 3 karakter huruf alfabet
            if len(re.findall(r'[A-Za-z]', clean_line)) >= 3:
                return clean_line

        return "Merchant Tidak Dikenal"

    @classmethod
    def _is_generic_metadata(cls, text: str) -> bool:
        """
        Mengecek apakah sebuah baris hanya berisi metadata struk atau label UI generik e-wallet.
        Wajib mengecualikan 'Rincian Pesanan', 'Saldo ShopeePay', 'Transaksi Berhasil', dll.
        """
        clean = text.strip().upper()
        if not clean or len(clean) < 3:
            return True

        generic_keywords = [
            # Header Struk Tradisional
            "RECEIPT", "TRANSACTION", "INVOICE", "NOTA", "STRUK", "SELAMAT DATANG",
            "TERIMA KASIH", "THANK YOU", "ORDER ID", "REF NO", "TAX INVOICE",
            "QRIS", "MERCHANT ID", "TERMINAL ID", "BILL NO", "TABLE NO", "CASHIER",

            # Header / Label UI E-Wallet & M-Banking (Blacklist)
            "RINCIAN PESANAN", "DETAIL TRANSAKSI", "RINCIAN TRANSAKSI",
            "BUKTI PEMBAYARAN", "BUKTI TRANSFER", "BUKTI TRANSAKSI",
            "TRANSAKSI BERHASIL", "PEMBAYARAN BERHASIL", "TRANSFER BERHASIL", "BERHASIL",
            "SALDO SHOPEEPAY", "SHOPEEPAY", "GOPAY", "DANA", "OVO", "LINKAJA",
            "NAMA PENGAKUISISI", "NAMA PENERBIT", "PENGAKUISISI", "PENERBIT",
            "METODE PEMBAYARAN", "WAKTU PEMBAYARAN", "WAKTU TRANSAKSI", "TANGGAL TRANSAKSI",
            "NO. TRANSAKSI", "NOMOR TRANSAKSI", "NO. REFERENSI", "NOMOR REFERENSI", "NOMOR PESANAN",
            "BIAYA TRANSAKSI", "BIAYA ADMIN", "TOTAL DISKON", "PROMO", "KAMU MEMBAYAR",
            "TOTAL PEMBAYARAN", "TOTAL BAYAR", "TOTAL BELANJA", "TOTAL", "SUBTOTAL"
        ]

        # Cek jika sama persis atau diawali dengan keyword generik
        for kw in generic_keywords:
            if clean == kw or clean.startswith(kw + ":") or clean.startswith(kw + " "):
                return True

        # Jika baris didominasi angka / nomor referensi panjang (misal 10+ digit)
        digit_count = len(re.findall(r'\d', clean))
        if digit_count >= 9 and digit_count / len(clean) > 0.5:
            return True

        return False

    @classmethod
    def suggest_category(cls, merchant: str, raw_text: str) -> str:
        """
        Menentukan kategori otomatis dengan dukungan kuliner lokal Indonesia:
        padang, warung, wm, soto, ayam, bakso, mie, nasi, geprek, pecel, kedai, dll.
        """
        text = f"{merchant} {raw_text}".lower()

        categories_map = {
            "Makanan & Minuman": [
                # Kuliner lokal Indonesia
                "padang", "warung", "wm", "soto", "ayam", "bakso", "mie", "nasi",
                "geprek", "pecel", "kedai", "resto", "restaurant", "cafe", "kopi",
                "coffee", "kenangan", "teh", "boba", "martabak", "sate", "bebek",
                "seblak", "roti", "kue", "juice", "jus", "dapur", "kantin", "makan",
                "kfc", "mcd", "burger", "pizza", "starbucks", "chatime", "drink",
                "beverage", "j.co", "point coffee"
            ],
            "Transportasi": [
                "spbu", "pertamina", "shell", "bensin", "pertalite", "pertamax", "solar",
                "grab", "gojek", "gocar", "goride", "maxim", "parkir", "parking", "tol", "toll",
                "krl", "kai", "kereta", "flight", "taxi", "bluebird"
            ],
            "Belanja": [
                "indomaret", "alfamart", "alfamidi", "superindo", "hypermart", "transmart",
                "minimarket", "supermarket", "mall", "fashion", "zara", "uniqlo", "h&m",
                "toko", "store", "shopee", "tokopedia", "lazada", "bukalapak"
            ],
            "Tagihan": [
                "pln", "listrik", "pdam", "air", "bpjs", "telkom", "indihome", "wifi", "biznet",
                "myrepublic", "pbb", "asuransi", "tagihan", "token"
            ],
            "Hiburan": [
                "cinema", "bioskop", "xxi", "cgv", "cinepolis", "tiket", "game", "steam",
                "playstation", "timezone", "karaoke", "netflix", "spotify", "disney"
            ]
        }

        for category, keywords in categories_map.items():
            for kw in keywords:
                # Pencocokan kata kunci dengan word boundary atau substring
                if kw in text:
                    return category

        return "Makanan & Minuman"

   @classmethod
    def extract_from_image(cls, image_bytes: bytes) -> OCRExtractResponse:
        """
        Fungsi utama pipeline OCR:
        1. Preprocess OpenCV
        2. Inferensi RapidOCR (ONNX Runtime)
        3. Regex parsing yang diperbarui
        """
        processed_img = cls.preprocess_image(image_bytes)
        reader = cls.get_reader()

        results, _ = reader(processed_img)
        del processed_img
        gc.collect()

        lines = []
        confidences = []

        if results:
            for bbox, text, conf in results:
                clean = text.strip()
                if clean:
                    lines.append(clean)
                    confidences.append(float(conf))

        raw_text = "\n".join(lines)
        avg_confidence = float(np.mean(confidences)) if confidences else 0.0

        merchant_name = cls.extract_merchant(lines)
        total_amount = cls.extract_total(lines)
        transaction_date = cls.extract_date(lines)
        suggested_cat = cls.suggest_category(merchant_name or "", raw_text)

        parsed_data = ReceiptParsedData(
            merchant_name=merchant_name,
            total_amount=total_amount,
            transaction_date=transaction_date,
            suggested_category=suggested_cat
        )

        return OCRExtractResponse(
            success=True,
            confidence_score=round(avg_confidence, 4),
            data=parsed_data,
            raw_text=raw_text,
            lines=lines
        )