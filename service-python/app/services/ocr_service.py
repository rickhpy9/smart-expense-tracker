import re
import datetime
from typing import List, Optional
import cv2
import numpy as np
import easyocr

from app.schemas.ocr import ReceiptParsedData, OCRExtractResponse


class OCRService:
    _instance = None
    _reader: Optional[easyocr.Reader] = None

    @classmethod
    def get_reader(cls) -> easyocr.Reader:
        if cls._reader is None:
            # Menggunakan bahasa Indonesia dan Inggris
            cls._reader = easyocr.Reader(['id', 'en'], gpu=False)
        return cls._reader

    @classmethod
    def preprocess_image(cls, image_bytes: bytes) -> np.ndarray:
        """
        Melakukan preprocessing gambar menggunakan OpenCV:
        1. Decode bytes ke array numpy OpenCV
        2. Konversi ke Grayscale
        3. Denoising Gaussian Blur
        4. CLAHE untuk penajaman kontras teks struk
        """
        np_arr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("File gambar tidak valid atau rusak.")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)

        return enhanced

    @classmethod
    def clean_ocr_number_noise(cls, text: str) -> str:
        """
        Membersihkan noise OCR yang menempel pada angka:
        - Huruf 'o' atau 'O' setelah/di antara digit diubah menjadi '0' (misal: 74.00o -> 74.000)
        - Huruf 'l' atau 'I' di antara/sebelum digit diubah menjadi '1'
        - Menghilangkan prefix Rp, IDR, dll.
        """
        cleaned = text.strip()

        # Bersihkan prefix mata uang
        cleaned = re.sub(r'^(?:rp\.?|idr|total|bayar|netto|net)[:\s=]*', '', cleaned, flags=re.IGNORECASE).strip()

        # Ubah 'o' atau 'O' yang menempel dengan angka menjadi '0'
        # Contoh: 74.00o -> 74.000, 7400o -> 74000, 1o0 -> 100
        cleaned = re.sub(r'(?<=\d)[oO]', '0', cleaned)
        cleaned = re.sub(r'[oO](?=\d)', '0', cleaned)

        # Ubah 'l' atau 'I' yang menempel dengan angka menjadi '1'
        cleaned = re.sub(r'(?<=\d)[lI]', '1', cleaned)
        cleaned = re.sub(r'[lI](?=\d)', '1', cleaned)

        return cleaned

    @classmethod
    def parse_amount(cls, text: str) -> Optional[float]:
        """
        Mengonversi teks nominal ke angka desimal/float utuh (misal: '74.000' -> 74000.0, '74.00o' -> 74000.0)
        """
        cleaned = cls.clean_ocr_number_noise(text)

        # Sisakan hanya digit, titik, dan koma
        cleaned = re.sub(r'[^\d,\.]', '', cleaned)
        if not cleaned:
            return None

        # Format dengan titik dan koma, misal: 74.000,00 atau 74,000.00
        if '.' in cleaned and ',' in cleaned:
            if cleaned.rfind(',') > cleaned.rfind('.'):
                # Format Indonesia / Eropa: 74.000,00 -> 74000.00
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                # Format US: 74,000.00 -> 74000.00
                cleaned = cleaned.replace(',', '')
        elif '.' in cleaned:
            # Jika ada titik: periksa apakah separator ribuan (misal: 74.000 atau 1.500.000)
            parts = cleaned.split('.')
            if len(parts[-1]) == 3 or len(parts) > 2:
                # Pemisah ribuan Indonesia standard: 74.000 -> 74000
                cleaned = cleaned.replace('.', '')
            elif len(parts[-1]) == 2:
                # Kemungkinan dua angka desimal, misal 74.50
                pass
            else:
                cleaned = cleaned.replace('.', '')
        elif ',' in cleaned:
            parts = cleaned.split(',')
            if len(parts[-1]) == 3 or len(parts) > 2:
                cleaned = cleaned.replace(',', '')
            elif len(parts[-1]) == 2:
                cleaned = cleaned.replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')

        try:
            val = float(cleaned)
            return val if val > 0 else None
        except ValueError:
            return None

    @classmethod
    def extract_total(cls, lines: List[str]) -> Optional[float]:
        """
        Pencarian Total Multi-Baris (Line-by-Line):
        1. Cari baris yang mengandung 'Total' namun WAJIB mengecualikan 'Subtotal' / 'Sub Total'.
        2. Jika nominal tidak ditemukan di baris yang sama, periksa 1 hingga 2 baris tepat setelahnya.
        3. Normalisasi noise OCR seperti '74.00o'.
        """
        # Keyword total utama (mengecualikan subtotal)
        total_line_indices = []
        for i, raw_line in enumerate(lines):
            line = raw_line.strip()
            # Abaikan jika mengandung subtotal
            if re.search(r'sub\s*total', line, re.IGNORECASE):
                continue
            if re.search(r'\btotal\b', line, re.IGNORECASE) or re.search(r'\bgrand\s*total\b', line, re.IGNORECASE):
                total_line_indices.append(i)

        # Periksa tiap baris kandidat Total
        for idx in total_line_indices:
            current_line = lines[idx]

            # 1. Cari nominal pada baris yang sama
            tokens = re.findall(r'(?:rp\.?|idr)?\s*([0-9oO\.,]{3,})', current_line, re.IGNORECASE)
            for token in tokens:
                amount = cls.parse_amount(token)
                if amount and amount >= 500:
                    return amount

            # 2. Jika tidak ada di baris yang sama, periksa baris ke-(idx + 1) dan ke-(idx + 2)
            for offset in [1, 2]:
                next_idx = idx + offset
                if next_idx < len(lines):
                    next_line = lines[next_idx].strip()
                    # Lewati jika baris berikutnya adalah label keyword lain
                    if re.search(r'^(cash|tunai|change|kembali|kembalian|subtotal|pajak|tax|disc)', next_line, re.IGNORECASE):
                        continue

                    # Cari token angka pada baris lanjutan
                    next_tokens = re.findall(r'(?:rp\.?|idr)?\s*([0-9oO\.,]{3,})', next_line, re.IGNORECASE)
                    for token in next_tokens:
                        amount = cls.parse_amount(token)
                        if amount and amount >= 500:
                            return amount

        # Fallback 1: Cari keyword tunai / bayar / jumlah
        fallback_keywords = [r'total\s*bayar', r'jumlah\s*bayar', r'jumlah\s*rp', r'tunai', r'qris', r'bayar']
        for keyword in fallback_keywords:
            pattern = re.compile(rf'{keyword}\s*[:=]?\s*(?:rp\.?|idr)?\s*([0-9oO\.,]{3,})', re.IGNORECASE)
            for line in lines:
                if re.search(r'sub\s*total', line, re.IGNORECASE):
                    continue
                match = pattern.search(line)
                if match:
                    val = cls.parse_amount(match.group(1))
                    if val and val >= 500:
                        return val

        # Fallback 2: Ambil nominal terbesar yang realistis di separuh bawah struk
        lower_half = lines[len(lines) // 3:]
        amounts = []
        for line in lower_half:
            if re.search(r'sub\s*total', line, re.IGNORECASE):
                continue
            found = re.findall(r'(?:rp\.?|idr)?\s*([0-9oO\.,]{4,})', line, re.IGNORECASE)
            for f in found:
                parsed = cls.parse_amount(f)
                if parsed and 500 <= parsed <= 100_000_000:
                    amounts.append(parsed)

        return max(amounts) if amounts else None

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

        # 1. Regex untuk format teks nama bulan (contoh: '12 Nov 2026', '12-Nov-2026', '12 November 2026')
        month_names_regex = r'(\d{1,2})[\s\-\/\.]([A-Za-z]{3,9})[\s\-\/\.](\d{4})'

        # Gabungkan seluruh lines untuk pengecekan teks
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

        # 2. Regex untuk format numerik: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY
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
        Ekstraksi merchant_name yang lebih akurat:
        1. Deteksi brand terkemuka (misal: 'Kenangan' -> 'Kopi Kenangan').
        2. Jika ada baris 'Outlet Name' atau 'Outlet:', ambil nilai baris berikutnya.
        3. Filter baris metadata generik (Receipt, Transaction, ID, nomor referensi panjang).
        """
        # 1. Pengecekan outlet name (misal: baris 'Outlet Name:' atau 'Outlet Name' diikuti nama outlet)
        outlet_name = None
        for i, line in enumerate(lines):
            clean = line.strip()
            outlet_match = re.search(r'outlet\s*name\s*[:=]?\s*(.*)', clean, re.IGNORECASE)
            if outlet_match:
                candidate = outlet_match.group(1).strip()
                if candidate and len(candidate) > 2:
                    outlet_name = candidate
                    break
                elif i + 1 < len(lines):
                    next_candidate = lines[i + 1].strip()
                    if len(next_candidate) > 2 and not cls._is_generic_metadata(next_candidate):
                        outlet_name = next_candidate
                        break

        # 2. Pengecekan Brand Khusus
        full_text_upper = "\n".join(lines).upper()

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

        # Jika ditemukan brand dan juga nama outlet
        if detected_brand:
            if outlet_name and outlet_name.lower() not in detected_brand.lower():
                return f"{detected_brand} - {outlet_name}"
            return detected_brand

        # Jika hanya ada nama outlet
        if outlet_name:
            return outlet_name

        # 3. Fallback: Ambil baris pertama teratas yang bukan metadata generik
        for line in lines[:6]:
            clean_line = line.strip()
            if cls._is_generic_metadata(clean_line):
                continue
            # Jika mengandung setidaknya 3 karakter alfabet
            if len(re.findall(r'[A-Za-z]', clean_line)) >= 3:
                return clean_line

        return "Merchant Tidak Dikenal"

    @classmethod
    def _is_generic_metadata(cls, text: str) -> bool:
        """
        Mengecek apakah sebuah baris hanya berisi metadata struk generik
        """
        clean = text.strip().upper()
        if not clean or len(clean) < 3:
            return True

        generic_keywords = [
            "RECEIPT", "TRANSACTION", "INVOICE", "NOTA", "STRUK", "SELAMAT DATANG",
            "TERIMA KASIH", "THANK YOU", "ORDER ID", "REF NO", "TAX INVOICE",
            "QRIS", "MERCHANT ID", "TERMINAL ID", "BILL NO", "TABLE NO", "CASHIER"
        ]

        if any(kw == clean or clean.startswith(kw) for kw in generic_keywords):
            return True

        # Jika baris didominasi angka / nomor referensi panjang (misal 10+ digit)
        digit_count = len(re.findall(r'\d', clean))
        if digit_count >= 10 and digit_count / len(clean) > 0.6:
            return True

        return False

    @classmethod
    def suggest_category(cls, merchant: str, raw_text: str) -> str:
        text = f"{merchant} {raw_text}".lower()

        categories_map = {
            "Makanan & Minuman": [
                "kopi", "coffee", "kenangan", "cafe", "resto", "restaurant", "makan", "bakso", "mie", "soto",
                "ayam", "kfc", "mcd", "burger", "pizza", "starbucks", "chatime", "tea", "roti",
                "dapur", "warung", "drink", "beverage", "j.co", "point coffee", "boba"
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
                if kw in text:
                    return category

        return "Makanan & Minuman"

    @classmethod
    def extract_from_image(cls, image_bytes: bytes) -> OCRExtractResponse:
        """
        Fungsi utama pipeline OCR:
        1. Preprocess OpenCV
        2. Inferensi EasyOCR
        3. Regex parsing yang diperbaiki
        """
        processed_img = cls.preprocess_image(image_bytes)
        reader = cls.get_reader()

        results = reader.readtext(processed_img)

        lines = []
        confidences = []

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
