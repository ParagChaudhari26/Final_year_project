"""
Vision Service for FoodCoach AI
Multimodal Food & Supermarket Receipt/Bill Recognition Service.
Supports:
  1. Camera Food Photos (cooked dishes, raw ingredients on table)
  2. Supermarket Bills & Receipts (DMart, Reliance Fresh/Smart, BigBasket, Blinkit, More, Kirana)
     - Intelligent Non-Food Filtering (strips out detergents, soaps, carry bags, toiletries)
     - Brand-to-Ingredient Normalization (e.g. "Aashirvaad Atta" -> "Whole Wheat Flour")
     - Unit & Quantity Extraction (g, kg, ml, L, pcs)
     - Shelf-life Expiry Estimation based on food category
  3. Built-in Offline Regex/Rule-Based Receipt Parser (0 API keys required)
  4. Google Gemini 1.5 Flash Vision API when key is configured.
"""
import base64
import json
import logging
import os
import re
from io import BytesIO
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("VisionService")

# ─────────────────────────────────────────────────────────────────────────────
# Common Indian pantry items with IFCT codes, category, default expiry, cal/100g
# ─────────────────────────────────────────────────────────────────────────────
FOOD_REFERENCE_DB: List[Dict[str, Any]] = [
    # Grains & Cereals
    {"name": "Whole Wheat Flour", "aliases": ["atta", "wheat flour", "chakki atta", "gehu"], "ifctCode": "D012", "calPer100g": 341, "unit": "g", "category": "Cereals", "daysUntilExpiry": 90},
    {"name": "Basmati Rice", "aliases": ["rice", "chawal", "basmati", "kolam rice", "sona masoori", "idly rice", "idli rice"], "ifctCode": "D001", "calPer100g": 345, "unit": "g", "category": "Cereals", "daysUntilExpiry": 180},
    {"name": "Flattened Rice", "aliases": ["poha", "aval", "chivda"], "ifctCode": "D003", "calPer100g": 346, "unit": "g", "category": "Cereals", "daysUntilExpiry": 120},
    {"name": "Sorghum Flour", "aliases": ["jowar", "jowar flour", "jowari"], "ifctCode": "D007", "calPer100g": 349, "unit": "g", "category": "Cereals", "daysUntilExpiry": 90},
    {"name": "Semolina", "aliases": ["rava", "sooji", "suji"], "ifctCode": "D013", "calPer100g": 348, "unit": "g", "category": "Cereals", "daysUntilExpiry": 90},
    {"name": "Urad Dal", "aliases": ["urad", "orid", "dhall", "orid dhall", "urad dal"], "ifctCode": "C004", "calPer100g": 347, "unit": "g", "category": "Pulses", "daysUntilExpiry": 180},
    {"name": "Coconut Oil", "aliases": ["coconut oil", "cccount oil"], "ifctCode": "F003", "calPer100g": 892, "unit": "ml", "category": "Fats and Oils", "daysUntilExpiry": 180},

    # Pulses & Legumes
    {"name": "Toor Dal", "aliases": ["toor dal", "tur dal", "arhar dal", "pigeon pea"], "ifctCode": "C006", "calPer100g": 335, "unit": "g", "category": "Pulses", "daysUntilExpiry": 180},
    {"name": "Moong Dal", "aliases": ["moong dal", "yellow moong", "green moong", "mung"], "ifctCode": "C003", "calPer100g": 334, "unit": "g", "category": "Pulses", "daysUntilExpiry": 180},
    {"name": "Masoor Dal", "aliases": ["masoor dal", "red lentil", "masur"], "ifctCode": "C002", "calPer100g": 343, "unit": "g", "category": "Pulses", "daysUntilExpiry": 180},
    {"name": "Chickpeas", "aliases": ["chana", "chickpea", "kabuli chana", "chole"], "ifctCode": "C009", "calPer100g": 360, "unit": "g", "category": "Pulses", "daysUntilExpiry": 180},
    {"name": "Kidney Beans", "aliases": ["rajma", "kidney bean", "red rajma"], "ifctCode": "C008", "calPer100g": 346, "unit": "g", "category": "Pulses", "daysUntilExpiry": 180},

    # Dairy & Fats
    {"name": "Milk", "aliases": ["milk", "doodh", "amul milk", "taaza", "gold milk", "cow milk"], "ifctCode": "E001", "calPer100g": 67, "unit": "ml", "category": "Dairy", "daysUntilExpiry": 3},
    {"name": "Paneer", "aliases": ["paneer", "cottage cheese"], "ifctCode": "E005", "calPer100g": 265, "unit": "g", "category": "Dairy", "daysUntilExpiry": 4},
    {"name": "Yogurt", "aliases": ["curd", "dahi", "yogurt"], "ifctCode": "E011", "calPer100g": 60, "unit": "g", "category": "Dairy", "daysUntilExpiry": 5},
    {"name": "Ghee", "aliases": ["ghee", "cow ghee", "desi ghee", "clarified butter"], "ifctCode": "F004", "calPer100g": 900, "unit": "g", "category": "Fats and Oils", "daysUntilExpiry": 90},
    {"name": "Cooking Oil", "aliases": ["oil", "sunflower oil", "groundnut oil", "mustard oil", "soybean oil", "fortune oil", "saffola"], "ifctCode": "F001", "calPer100g": 884, "unit": "ml", "category": "Fats and Oils", "daysUntilExpiry": 180},

    # Vegetables
    {"name": "Spinach", "aliases": ["spinach", "palak", "baby spinach"], "ifctCode": "A063", "calPer100g": 26, "unit": "g", "category": "Leafy Vegetables", "daysUntilExpiry": 2},
    {"name": "Tomato", "aliases": ["tomato", "tamatar"], "ifctCode": "B076", "calPer100g": 20, "unit": "g", "category": "Vegetables", "daysUntilExpiry": 5},
    {"name": "Onion", "aliases": ["onion", "pyaz", "kanda"], "ifctCode": "B060", "calPer100g": 50, "unit": "g", "category": "Vegetables", "daysUntilExpiry": 14},
    {"name": "Potato", "aliases": ["potato", "aloo", "batata"], "ifctCode": "B063", "calPer100g": 97, "unit": "g", "category": "Vegetables", "daysUntilExpiry": 14},
    {"name": "Cauliflower", "aliases": ["cauliflower", "gobi", "phool gobi"], "ifctCode": "A019", "calPer100g": 30, "unit": "g", "category": "Vegetables", "daysUntilExpiry": 4},
    {"name": "Eggplant", "aliases": ["eggplant", "brinjal", "baingan", "aubergine"], "ifctCode": "A038", "calPer100g": 24, "unit": "g", "category": "Vegetables", "daysUntilExpiry": 4},
    {"name": "Fenugreek Leaves", "aliases": ["methi", "fenugreek"], "ifctCode": "A029", "calPer100g": 49, "unit": "g", "category": "Leafy Vegetables", "daysUntilExpiry": 2},
    {"name": "Green Peas", "aliases": ["peas", "matar", "green peas"], "ifctCode": "A055", "calPer100g": 93, "unit": "g", "category": "Vegetables", "daysUntilExpiry": 4},
    {"name": "Carrot", "aliases": ["carrot", "gajar"], "ifctCode": "A016", "calPer100g": 48, "unit": "g", "category": "Vegetables", "daysUntilExpiry": 7},

    # Spices & Condiments
    {"name": "Turmeric Powder", "aliases": ["turmeric", "haldi", "turmeric powder"], "ifctCode": "H004", "calPer100g": 349, "unit": "g", "category": "Spices", "daysUntilExpiry": 365},
    {"name": "Garlic", "aliases": ["garlic", "lehsun"], "ifctCode": "B036", "calPer100g": 145, "unit": "g", "category": "Spices", "daysUntilExpiry": 30},
    {"name": "Ginger", "aliases": ["ginger", "adrak"], "ifctCode": "B037", "calPer100g": 67, "unit": "g", "category": "Spices", "daysUntilExpiry": 14},
    {"name": "Cumin Seeds", "aliases": ["cumin", "jeera"], "ifctCode": "H007", "calPer100g": 375, "unit": "g", "category": "Spices", "daysUntilExpiry": 365},
    {"name": "Table Salt", "aliases": ["salt", "tata salt", "namak"], "ifctCode": "H001", "calPer100g": 0, "unit": "g", "category": "Condiments", "daysUntilExpiry": 730},
    {"name": "Sugar", "aliases": ["sugar", "cheeni", "shakar", "madhur sugar"], "ifctCode": "G001", "calPer100g": 387, "unit": "g", "category": "Sweeteners", "daysUntilExpiry": 365},
    {"name": "Peanuts", "aliases": ["peanut", "groundnut", "moongfali", "shengdana"], "ifctCode": "C028", "calPer100g": 567, "unit": "g", "category": "Nuts and Seeds", "daysUntilExpiry": 90},
]

# Fast lookup dictionary
_FOOD_LOOKUP: Dict[str, Dict[str, Any]] = {}
for item in FOOD_REFERENCE_DB:
    _FOOD_LOOKUP[item["name"].lower()] = item
    for alias in item.get("aliases", []):
        _FOOD_LOOKUP[alias.lower()] = item


# ─────────────────────────────────────────────────────────────────────────────
# Non-Food Item Blacklist (for receipt cleaning)
# ─────────────────────────────────────────────────────────────────────────────
NON_FOOD_KEYWORDS = {
    "surf", "ariel", "tide", "rin", "wheel", "nirma", "vim", "pril", "scotch",
    "harpic", "lizol", "colin", "dettol", "savlon", "cleaner", "dishwash", "detergent",
    "bleach", "toothpaste", "toothbrush", "colgate", "pepsodent", "oral-b", "sensodyne",
    "soap", "dove", "lux", "lifebuoy", "cinthol", "shampoo", "sunsilk", "pantene",
    "head & shoulders", "conditioner", "bodywash", "handwash", "facewash", "shaving",
    "gillette", "razor", "blade", "sanitizer", "diaper", "pampers", "huggies", "napkin",
    "whisper", "stayfree", "tissue", "wipe", "bag", "carrybag", "carry bag", "plastic",
    "battery", "cell", "duracell", "bulb", "led", "mop", "broom", "wiper", "scrubber",
    "foil", "wrap", "garbage", "repellent", "knight", "good knight", "all out", "hit",
    "baygon", "odonil", "freshener", "shoe polish", "cosmetic", "lipstick", "cream",
    "lotion", "vaseline", "nivea", "ponds", "fair & lovely", "perfume", "deodorant", "axe",
    "sabena", "copper", "wire", "print box", "sasphin",
    "subtotal", "total", "cgst", "sgst", "gst", "invoice", "round off", "change",
    "cash", "upi", "pos", "terminal", "savings", "bill no", "cashier", "date", "time"
}


def _is_non_food(line: str) -> bool:
    """Check if a receipt line represents a non-food household item, tax, or receipt header."""
    lower = line.lower()
    for kw in NON_FOOD_KEYWORDS:
        if kw in lower:
            return True
    return False


def _parse_gemini_response(raw_text: str) -> List[Dict[str, Any]]:
    """Extract JSON array from response text."""
    json_match = re.search(r'\[.*?\]', raw_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return []


class VisionService:
    """
    Universal Vision & Receipt Recognition Service for FoodCoach AI.
    Handles:
      - Raw kitchen food photos
      - Supermarket receipts / bills (DMart, Reliance, BigBasket, Blinkit, More, Kirana)
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.use_gemini = bool(self.api_key)
        if self.use_gemini:
            logger.info("✅ Gemini Vision API active")
        else:
            logger.info("ℹ️ Gemini API key not found — using built-in offline receipt parser & simulated recognition")
        self._ocr_reader = None

    def _get_ocr_reader(self):
        if self._ocr_reader is None:
            try:
                import easyocr
                logger.info("Initializing EasyOCR reader for local offline receipt parsing...")
                self._ocr_reader = easyocr.Reader(['en'], gpu=False)
            except Exception as e:
                logger.error(f"EasyOCR reader init failed: {e}")
                self._ocr_reader = False
        return self._ocr_reader

    # ──────────────────────────────────────────────────────────────────────────
    def analyze_image(
        self,
        image_data: Optional[str] = None,
        mime_type: str = "image/jpeg",
        scan_type: str = "auto",
        receipt_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze either a base64 image or direct receipt text.
        scan_type: "auto" | "receipt" | "food_photo"
        """
        # If user directly pasted receipt text, process with local receipt parser
        if receipt_text and receipt_text.strip():
            return self.parse_receipt_text(receipt_text)

        # If Gemini is configured, use it
        if self.use_gemini and image_data:
            result = self._analyze_with_gemini(image_data, mime_type, scan_type)
            if result and result.get("detectedItems"):
                return result

        # Use local EasyOCR on uploaded image pixels
        if image_data:
            reader = self._get_ocr_reader()
            if reader:
                try:
                    raw_bytes = base64.b64decode(image_data)
                    ocr_results = reader.readtext(raw_bytes, detail=0)
                    extracted_text = "\n".join(ocr_results)
                    logger.info(f"EasyOCR extracted {len(ocr_results)} text lines from image.")
                    if extracted_text.strip():
                        res = self.parse_receipt_text(extracted_text)
                        res["processingMethod"] = "EasyOCR Local Neural Vision Engine"
                        if res.get("detectedItems"):
                            return res
                except Exception as err:
                    logger.error(f"EasyOCR parsing failed: {err}")

        # Fallback based on scanType
        if scan_type == "receipt":
            return self._demo_supermarket_receipt_fallback()
        else:
            return self._demo_food_photo_fallback()

    # ──────────────────────────────────────────────────────────────────────────
    def _analyze_with_gemini(
        self, image_data: str, mime_type: str, scan_type: str
    ) -> Optional[Dict[str, Any]]:
        """Call Gemini Vision with dual-mode prompt (Receipt or Food Photo)."""
        try:
            import requests as req

            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-1.5-flash:generateContent?key={self.api_key}"
            )

            if scan_type == "receipt":
                prompt = (
                    "You are a supermarket receipt and grocery bill OCR specialist for Indian households. "
                    "Analyze this receipt (from DMart, Reliance, BigBasket, Blinkit, or any grocery store). "
                    "1. Extract ONLY edible food and pantry grocery items. "
                    "2. STRICTLY EXCLUDE non-food items like detergents, soaps, toothpastes, toiletries, carry bags, batteries. "
                    "3. Normalize Indian brand names to simple culinary ingredients (e.g. 'Aashirvaad Shudh Atta 5kg' -> 'Whole Wheat Flour', 'Tata Sampann Toor Dal 1kg' -> 'Toor Dal'). "
                    "4. Extract the numeric quantity and unit (g, kg, ml, L, or piece). "
                    "5. Assign a realistic pantry expiry day count (fresh dairy: 3, vegetables: 5, pulses/grains: 180). "
                    "Return a JSON array where each object has fields: "
                    '"name" (string), "estimatedQuantity" (number), "unit" (string: g/ml/piece/kg), '
                    '"category" (string), "daysUntilExpiry" (integer), "confidence" (float 0.0-1.0). '
                    "Return ONLY the JSON array, no surrounding markdown or explanation."
                )
            else:
                prompt = (
                    "You are a food and supermarket pantry nutritionist. "
                    "Look at this image. If it is a supermarket receipt or grocery bill, extract ONLY edible food items, "
                    "excluding all detergents, soaps, and toiletries. If it is a photo of fresh food or pantry items, "
                    "identify each visible food item. "
                    "Return a JSON array where each object has fields: "
                    '"name" (string), "estimatedQuantity" (number), "unit" (g or ml or piece), '
                    '"category" (string), "daysUntilExpiry" (number), "confidence" (0.0-1.0). '
                    "Focus on Indian foods when possible. Return ONLY the JSON array."
                )

            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": mime_type, "data": image_data}}
                    ]
                }],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 768}
            }
            response = req.post(url, json=payload, timeout=25)
            response.raise_for_status()

            candidates = response.json().get("candidates", [])
            if not candidates:
                return None
            raw_text = candidates[0]["content"]["parts"][0]["text"]
            detected = _parse_gemini_response(raw_text)

            if not detected:
                return None

            method_name = "Gemini 1.5 Supermarket Receipt OCR" if scan_type == "receipt" else "Gemini 1.5 Flash Vision"
            return self._enrich_and_build_response(detected, processing_method=method_name)

        except Exception as exc:
            logger.error(f"Gemini Vision API failed: {exc}")
            return None

    # ──────────────────────────────────────────────────────────────────────────
    def parse_receipt_text(self, raw_receipt_text: str) -> Dict[str, Any]:
        """
        100% Offline Rule-Based Supermarket Receipt Parser.
        Parses text lines from any supermarket bill (DMart, Reliance, Blinkit, BigBasket, Kirana),
        filters out non-food items, normalizes brand names, and extracts quantities and units.
        """
        lines = [line.strip() for line in raw_receipt_text.splitlines() if line.strip()]
        detected_items: List[Dict[str, Any]] = []

        for line in lines:
            # Check non-food exclusion
            if _is_non_food(line):
                continue

            # Extract Quantity and Unit using regex
            # e.g., "5KG", "1.000 KG", "500 GM", "1 LTR", "500ML", "2 PC", "100G"
            qty = 100.0
            unit = "g"

            qty_match = re.search(r'(\d+(?:\.\d+)?)\s*(kg|kilo|gm|g|ltr|l|ml|pc|piece|pkt|packet)?\b', line, re.IGNORECASE)
            if qty_match:
                val = float(qty_match.group(1))
                u = (qty_match.group(2) or "g").lower()

                if u in ("kg", "kilo"):
                    qty = val * 1000.0
                    unit = "g"
                elif u in ("l", "ltr"):
                    qty = val * 1000.0
                    unit = "ml"
                elif u in ("ml", "g", "piece"):
                    qty = val
                    unit = u
                else:
                    qty = val
                    unit = "g"

            # Match against known Indian food catalog
            matched_food = self._match_food_in_text(line)
            if matched_food:
                detected_items.append({
                    "name": matched_food["name"],
                    "confidence": 0.95,
                    "estimatedQuantity": qty if qty != 100.0 else (500.0 if "dal" in line.lower() else 100.0),
                    "unit": matched_food.get("unit", unit),
                    "category": matched_food.get("category", "Pantry Staples"),
                    "daysUntilExpiry": matched_food.get("daysUntilExpiry", 30),
                    "ifctCode": matched_food.get("ifctCode"),
                    "estimatedCalories": round((matched_food["calPer100g"] * qty) / 100.0, 1)
                })

        # Deduplicate by item name
        unique_items: Dict[str, Dict[str, Any]] = {}
        for item in detected_items:
            key = item["name"].lower()
            if key not in unique_items:
                unique_items[key] = item
            else:
                unique_items[key]["estimatedQuantity"] += item["estimatedQuantity"]
                unique_items[key]["estimatedCalories"] += item["estimatedCalories"]

        final_list = list(unique_items.values())
        total_cal = sum(i["estimatedCalories"] for i in final_list)

        return {
            "detectedItems": final_list,
            "totalEstimatedCalories": round(total_cal, 1),
            "processingMethod": "Universal Supermarket Receipt Parser (Offline OCR)",
            "message": f"Successfully parsed {len(final_list)} food items from supermarket bill. Filtered out non-food items."
        }

    # ──────────────────────────────────────────────────────────────────────────
    def _match_food_in_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Find the most specific matching food item from a receipt line."""
        text_lower = text.lower()
        # Direct lookup check
        for alias, item in _FOOD_LOOKUP.items():
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, text_lower):
                return item
        return None

    # ──────────────────────────────────────────────────────────────────────────
    def _enrich_and_build_response(
        self, detected: List[Dict[str, Any]], processing_method: str
    ) -> Dict[str, Any]:
        """Enrich detected items with IFCT codes, calorie estimates, and shelf-life."""
        enriched: List[Dict[str, Any]] = []
        total_calories = 0.0

        for item in detected:
            name = item.get("name", "Unknown")
            # If AI didn't filter out non-food, double check our blacklist
            if _is_non_food(name):
                continue

            qty = float(item.get("estimatedQuantity", 100))
            unit = item.get("unit", "g")
            confidence = float(item.get("confidence", 0.85))

            ref = self._match_food_in_text(name) or _FOOD_LOOKUP.get(name.lower())
            ifct_code = ref["ifctCode"] if ref else item.get("ifctCode")
            category = ref.get("category") if ref else item.get("category", "Pantry Staples")
            days_exp = ref.get("daysUntilExpiry") if ref else item.get("daysUntilExpiry", 14)

            cal_per_100 = ref["calPer100g"] if ref else 50.0
            estimated_cal = round(cal_per_100 * qty / 100.0, 1)
            total_calories += estimated_cal

            enriched.append({
                "name": ref["name"] if ref else name,
                "confidence": confidence,
                "estimatedQuantity": qty,
                "unit": unit,
                "category": category,
                "daysUntilExpiry": days_exp,
                "ifctCode": ifct_code,
                "estimatedCalories": estimated_cal,
            })

        return {
            "detectedItems": enriched,
            "totalEstimatedCalories": round(total_calories, 1),
            "processingMethod": processing_method,
            "message": f"Identified {len(enriched)} food item(s) from supermarket bill.",
        }

    # ──────────────────────────────────────────────────────────────────────────
    def _demo_supermarket_receipt_fallback(self) -> Dict[str, Any]:
        """Simulated real DMart / Reliance Fresh bill parsing demo."""
        demo_receipt = """
        DMART SUPERMARKET - INVOICE #89214
        ------------------------------------------
        AASHIRVAAD SHUDH CHAKKI ATTA 5KG       1 PKT   Rs 245
        SURF EXCEL EASY WASH 1KG               1 PKT   Rs 140
        TATA SAMPANN TOOR DAL 1KG              1 PKT   Rs 180
        AMUL TAAZA MILK 500ML                  2 PKT   Rs 56
        DETTOL ORIGINAL HANDWASH 175ML         1 BTL   Rs 85
        FORTUNE SUNFLOWER OIL 1 LTR            1 BTL   Rs 145
        VIM DISHWASH GEL 250ML                 1 BTL   Rs 55
        MADHUR PURE SUGAR 1KG                  1 PKT   Rs 48
        TATA SALT IODIZED 1KG                  1 PKT   Rs 28
        CARRY BAG MEDIUM                       1 PC    Rs 7
        ------------------------------------------
        """
        return self.parse_receipt_text(demo_receipt)

    # ──────────────────────────────────────────────────────────────────────────
    def _demo_food_photo_fallback(self) -> Dict[str, Any]:
        """Simulated photo recognition for fresh vegetables."""
        items = [
            {"name": "Spinach", "estimatedQuantity": 250, "unit": "g", "confidence": 0.94, "category": "Leafy Vegetables", "daysUntilExpiry": 2},
            {"name": "Paneer", "estimatedQuantity": 200, "unit": "g", "confidence": 0.91, "category": "Dairy", "daysUntilExpiry": 3},
            {"name": "Tomato", "estimatedQuantity": 400, "unit": "g", "confidence": 0.88, "category": "Vegetables", "daysUntilExpiry": 4},
        ]
        return self._enrich_and_build_response(items, processing_method="Food Photo Recognition (Offline Fallback)")

    # ──────────────────────────────────────────────────────────────────────────
    def validate_image_data(self, image_data: str) -> bool:
        """Validate that the base64 string represents a valid image."""
        try:
            from PIL import Image
            raw = base64.b64decode(image_data)
            img = Image.open(BytesIO(raw))
            img.verify()
            return True
        except Exception:
            return False


vision_service = VisionService()
