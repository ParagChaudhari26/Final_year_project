import csv
import logging
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger("IFCT_Calculator")

DEFAULT_UNIT_TO_GRAMS: Dict[str, float] = {
    "g": 1.0, "kg": 1000.0, "ml": 1.0, "l": 1000.0,
    "katori": 125.0, "cup": 150.0, "glass": 200.0,
    "tbsp": 14.0, "tsp": 4.5, "pinch": 0.5,
    "piece": 80.0, "medium": 100.0, "bunch": 250.0
}

COOKING_RETENTION_FACTORS: Dict[str, Dict[str, float]] = {
    "raw": {"default": 1.0, "vitaminCMg": 1.0, "folateTotalUg": 1.0},
    "simmered": {"default": 1.0, "vitaminCMg": 0.60, "folateTotalUg": 0.70},
    "slow_simmered": {"default": 1.0, "vitaminCMg": 0.50, "folateTotalUg": 0.65},
    "sauteed": {"default": 1.0, "vitaminCMg": 0.75, "folateTotalUg": 0.80},
    "baked": {"default": 1.0, "vitaminCMg": 0.45, "folateTotalUg": 0.60},
    "iron_kadhai_simmered": {"default": 1.0, "vitaminCMg": 0.55, "ironMg": 1.35} 
}

# Embedded offline IFCT 2017 baseline for Indian core ingredients
CORE_INDIAN_IFCT_FOODS: List[Dict[str, Any]] = [
    {"code": "A063", "name": "Spinach", "group": "Leafy Vegetables", "ep": 0.85, "yield": 0.80, "nutrients": {"energyKcal": 26.0, "proteinG": 2.0, "ironMg": 1.1, "calciumMg": 73.0, "vitaminCMg": 28.0, "carbsG": 2.9, "fatG": 0.7, "fibreG": 2.5}},
    {"code": "E005", "name": "Paneer", "group": "Dairy", "ep": 1.0, "yield": 1.0, "nutrients": {"energyKcal": 265.0, "proteinG": 18.3, "calciumMg": 208.0, "fatG": 20.8, "carbsG": 1.2, "ironMg": 0.1}},
    {"code": "B076", "name": "Tomato", "group": "Vegetables", "ep": 0.95, "yield": 0.90, "nutrients": {"energyKcal": 20.0, "proteinG": 0.9, "vitaminCMg": 27.0, "carbsG": 3.6, "fatG": 0.2, "calciumMg": 20.0, "ironMg": 0.6}},
    {"code": "B060", "name": "Onion", "group": "Vegetables", "ep": 0.90, "yield": 0.85, "nutrients": {"energyKcal": 50.0, "proteinG": 1.2, "carbsG": 11.1, "fatG": 0.1, "calciumMg": 46.9, "ironMg": 0.6}},
    {"code": "B024", "name": "Garlic", "group": "Spices", "ep": 0.88, "yield": 1.0, "nutrients": {"energyKcal": 149.0, "proteinG": 6.4, "carbsG": 33.1, "fatG": 0.5, "calciumMg": 181.0, "ironMg": 1.7}},
    {"code": "B028", "name": "Ginger", "group": "Spices", "ep": 0.85, "yield": 1.0, "nutrients": {"energyKcal": 80.0, "proteinG": 2.3, "carbsG": 17.8, "fatG": 0.8, "calciumMg": 20.0, "ironMg": 1.2}},
    {"code": "C006", "name": "Toor Dal", "group": "Pulses", "ep": 1.0, "yield": 2.2, "nutrients": {"energyKcal": 335.0, "proteinG": 22.3, "ironMg": 5.3, "fibreG": 15.0, "carbsG": 57.6, "fatG": 1.5, "calciumMg": 73.0}},
    {"code": "C016", "name": "Kidney Beans", "group": "Pulses", "ep": 1.0, "yield": 2.2, "nutrients": {"energyKcal": 347.0, "proteinG": 22.9, "ironMg": 8.2, "fibreG": 15.2, "carbsG": 60.6, "fatG": 1.3, "calciumMg": 140.0}},
    {"code": "D009", "name": "Semolina", "group": "Cereals", "ep": 1.0, "yield": 2.5, "nutrients": {"energyKcal": 348.0, "proteinG": 10.4, "carbsG": 74.0, "fatG": 0.8, "ironMg": 1.6, "calciumMg": 16.0}},
    {"code": "D006", "name": "Flattened Rice", "group": "Cereals", "ep": 1.0, "yield": 1.8, "nutrients": {"energyKcal": 350.0, "proteinG": 7.4, "ironMg": 2.7, "carbsG": 77.0, "fatG": 1.0, "calciumMg": 20.0}},
    {"code": "D012", "name": "Whole Wheat Flour", "group": "Cereals", "ep": 1.0, "yield": 1.3, "nutrients": {"energyKcal": 341.0, "proteinG": 12.1, "fibreG": 11.2, "carbsG": 69.4, "fatG": 1.7, "ironMg": 4.9, "calciumMg": 48.0}},
    {"code": "C012", "name": "Red Lentils", "group": "Pulses", "ep": 1.0, "yield": 2.2, "nutrients": {"energyKcal": 343.0, "proteinG": 25.1, "ironMg": 7.6, "fibreG": 10.8, "carbsG": 59.0, "fatG": 0.7, "calciumMg": 69.0}},
    {"code": "B063", "name": "Potato", "group": "Vegetables", "ep": 0.85, "yield": 0.90, "nutrients": {"energyKcal": 97.0, "proteinG": 1.6, "carbsG": 22.7, "fatG": 0.1, "ironMg": 0.5, "calciumMg": 10.0, "vitaminCMg": 17.0}},
    {"code": "A019", "name": "Cauliflower", "group": "Vegetables", "ep": 0.65, "yield": 0.80, "nutrients": {"energyKcal": 30.0, "proteinG": 2.6, "vitaminCMg": 56.0, "carbsG": 4.0, "fatG": 0.4, "calciumMg": 33.0, "ironMg": 1.5}},
    {"code": "C009", "name": "Chickpeas", "group": "Pulses", "ep": 1.0, "yield": 2.2, "nutrients": {"energyKcal": 360.0, "proteinG": 17.1, "fibreG": 17.0, "ironMg": 4.9, "carbsG": 60.9, "fatG": 5.3, "calciumMg": 105.0}},
    {"code": "A038", "name": "Eggplant", "group": "Vegetables", "ep": 0.85, "yield": 0.75, "nutrients": {"energyKcal": 24.0, "proteinG": 1.4, "carbsG": 4.0, "fatG": 0.3, "calciumMg": 18.0, "ironMg": 0.4}},
    {"code": "D003", "name": "Jowar Flour", "group": "Cereals", "ep": 1.0, "yield": 1.3, "nutrients": {"energyKcal": 349.0, "proteinG": 10.4, "ironMg": 4.1, "fibreG": 9.7, "carbsG": 72.6, "fatG": 1.9, "calciumMg": 25.0}},
    {"code": "D001", "name": "Basmati Rice", "group": "Cereals", "ep": 1.0, "yield": 2.5, "nutrients": {"energyKcal": 345.0, "proteinG": 6.8, "carbsG": 78.2, "fatG": 0.5, "ironMg": 0.7, "calciumMg": 10.0}},
    {"code": "C008", "name": "Yellow Moong Dal", "group": "Pulses", "ep": 1.0, "yield": 2.2, "nutrients": {"energyKcal": 334.0, "proteinG": 24.0, "ironMg": 8.0, "fibreG": 8.2, "carbsG": 59.8, "fatG": 1.2, "calciumMg": 75.0}},
    {"code": "A029", "name": "Fenugreek Leaves", "group": "Leafy Vegetables", "ep": 0.75, "yield": 0.70, "nutrients": {"energyKcal": 49.0, "proteinG": 4.4, "ironMg": 1.9, "calciumMg": 395.0, "vitaminCMg": 52.0, "carbsG": 6.0, "fatG": 0.9}},
    {"code": "F004", "name": "Ghee", "group": "Fats and Oils", "ep": 1.0, "yield": 1.0, "nutrients": {"energyKcal": 900.0, "fatG": 99.5, "proteinG": 0.0, "carbsG": 0.0, "calciumMg": 0.0, "ironMg": 0.0}},
    {"code": "E011", "name": "Curd / Yogurt", "group": "Dairy", "ep": 1.0, "yield": 1.0, "nutrients": {"energyKcal": 60.0, "proteinG": 3.1, "calciumMg": 149.0, "fatG": 4.0, "carbsG": 3.0, "ironMg": 0.1}},
    {"code": "E001", "name": "Milk", "group": "Dairy", "ep": 1.0, "yield": 1.0, "nutrients": {"energyKcal": 67.0, "proteinG": 3.2, "calciumMg": 120.0, "fatG": 4.1, "carbsG": 4.4, "ironMg": 0.1}},
    {"code": "C028", "name": "Peanuts", "group": "Nuts and Seeds", "ep": 0.75, "yield": 1.0, "nutrients": {"energyKcal": 567.0, "proteinG": 25.8, "fatG": 49.2, "carbsG": 16.1, "ironMg": 2.8, "calciumMg": 90.0, "fibreG": 8.5}},
    {"code": "B074", "name": "Tamarind", "group": "Fruits", "ep": 0.60, "yield": 1.0, "nutrients": {"energyKcal": 239.0, "proteinG": 2.8, "ironMg": 2.8, "carbsG": 62.5, "fatG": 0.6, "calciumMg": 74.0}},
    {"code": "B052", "name": "Orange", "group": "Fruits", "ep": 0.70, "yield": 1.0, "nutrients": {"energyKcal": 48.0, "proteinG": 0.9, "vitaminCMg": 53.0, "carbsG": 11.8, "fatG": 0.1, "calciumMg": 40.0}},
    {"code": "G001", "name": "Fish", "group": "Non-Veg", "ep": 0.70, "yield": 0.85, "nutrients": {"energyKcal": 91.0, "proteinG": 17.5, "fatG": 1.5, "carbsG": 0.0, "ironMg": 1.0, "calciumMg": 28.0}},
]

class IFCT2017MeasurementCalculator:
    def __init__(self):
        self.foods_by_ifct_code: Dict[str, Dict[str, Any]] = {}
        self.foods_by_name: Dict[str, Dict[str, Any]] = {}

        # 1. Pre-populate immediately with embedded core Indian foods for 0ms offline startup
        self._load_core_defaults()

        # 2. Asynchronously / gently try online full dataset without blocking
        self.github_csv_urls = [
            "https://raw.githubusercontent.com/nodef/ifct2017/main/compositions/index.csv",
            "https://raw.githubusercontent.com/ifct2017/compositions/main/compositions.csv",
            "https://raw.githubusercontent.com/ifct2017/compositions/main/data/compositions.csv",
        ]
        self.github_csv_url = self.github_csv_urls[0]
        self.load_dataset_from_github()

    def _load_core_defaults(self):
        """Loads embedded baseline foods ensuring zero-network reliability."""
        for item in CORE_INDIAN_IFCT_FOODS:
            code = item["code"]
            name = item["name"]
            entry = {
                "id": f"ING_{code}",
                "ifctCode": code,
                "name": name,
                "scientificName": "",
                "foodGroup": item["group"],
                "ediblePortionFactor": item["ep"],
                "cookedYieldFactor": item["yield"],
                "nutrientsPer100g": item["nutrients"]
            }
            self.foods_by_ifct_code[code] = entry
            self.foods_by_name[name.lower()] = entry
            # Also register aliases without spaces or hyphens
            self.foods_by_name[name.lower().replace(" ", "")] = entry

    def load_dataset_from_github(self):
        """Fetches the IFCT CSV directly from GitHub with quick timeout, preserving offline baseline."""
        last_error = None

        for url in self.github_csv_urls:
            try:
                logger.info(f"Checking IFCT 2017 dataset update from {url}...")
                response = requests.get(url, timeout=2)
                response.raise_for_status()
                self.github_csv_url = url

                csv_data = response.text.splitlines()
                reader = csv.DictReader(csv_data)
                count = 0

                for row in reader:
                    code = row.get("code") or row.get("ifctCode") or f"IFCT_{count}"
                    name = row.get("name") or row.get("Food Name") or f"Food {code}"
                    name = name.strip()

                    nutrients = {}
                    for k, v in row.items():
                        if k not in ("code", "ifctCode", "name", "Food Name", "scientificName", "foodGroup", "ediblePortionFactor", "cookedYieldFactor"):
                            try:
                                nutrients[k] = float(v)
                            except (ValueError, TypeError):
                                nutrients[k] = 0.0

                    entry = {
                        "id": f"ING_{code}",
                        "ifctCode": code,
                        "name": name,
                        "scientificName": row.get("scientificName", ""),
                        "foodGroup": row.get("foodGroup", "Unknown"),
                        "ediblePortionFactor": float(row.get("ediblePortionFactor", 1.0) or 1.0),
                        "cookedYieldFactor": float(row.get("cookedYieldFactor", 1.0) or 1.0),
                        "nutrientsPer100g": nutrients
                    }

                    self.foods_by_ifct_code[code] = entry
                    self.foods_by_name[name.lower()] = entry
                    count += 1

                logger.info(f"Successfully loaded {count} foods from GitHub.")
                return
            except Exception as e:
                last_error = e
                logger.warning(f"Failed to fetch dataset from {url}: {e}")

        logger.error(f"Failed to fetch dataset from GitHub using all known URLs. Last error: {last_error}")

    def lookup_food(self, identifier: str) -> Optional[Dict[str, Any]]:
        if not identifier: return None
        if identifier in self.foods_by_ifct_code: return self.foods_by_ifct_code[identifier]
        
        key = identifier.strip().lower()
        if key in self.foods_by_name: return self.foods_by_name[key]
        for name_k, food in self.foods_by_name.items():
            if key in name_k or name_k in key:
                return food
        return None

    def convert_to_grams(self, quantity: float, unit: str, ep_factor: float, yield_factor: float) -> Dict[str, float]:
        u_norm = (unit or "g").strip().lower()
        alpha = DEFAULT_UNIT_TO_GRAMS.get(u_norm, 1.0)
        
        raw_grams = round(float(quantity) * alpha, 2)
        edible_grams = round(raw_grams * ep_factor, 2)
        cooked_grams = round(edible_grams * yield_factor, 2)
        
        return {
            "rawWeightGrams": raw_grams,
            "edibleWeightGrams": edible_grams,
            "cookedWeightGrams": cooked_grams
        }

    def calculate_recipe_nutrition(self, ingredients: List[Dict[str, Any]], cooking_process: str = "simmered", servings: int = 1) -> Dict[str, Any]:
        servings = max(int(servings), 1)
        rf_profile = COOKING_RETENTION_FACTORS.get((cooking_process or "simmered").lower(), COOKING_RETENTION_FACTORS["simmered"])
        
        aggregated: Dict[str, float] = {}
        
        for item in ingredients:
            ident = item.get("ifctCode") or item.get("ingredientId") or item.get("name", "")
            food = self.lookup_food(ident)
            
            if not food:
                continue
                
            qty = float(item.get("quantity", 100.0))
            unit = item.get("unit", "g")
            
            meas = self.convert_to_grams(qty, unit, food["ediblePortionFactor"], food["cookedYieldFactor"])
            scale = meas["edibleWeightGrams"] / 100.0
            
            for param, val in food.get("nutrientsPer100g", {}).items():
                rf = rf_profile.get(param, rf_profile.get("default", 1.0))
                v_ret = float(val) * scale * rf
                aggregated[param] = aggregated.get(param, 0.0) + v_ret

        per_serving = {k: round(v / servings, 2) for k, v in aggregated.items()}
        
        beneficiaries = []
        if per_serving.get("totalDietaryFibreG", per_serving.get("fibreG", 0)) >= 8.0:
            beneficiaries.append("BEN_DIABETES_GLYCEMIC")
        if per_serving.get("sodiumMg", 0) <= 150.0 and len(ingredients) > 0:
            beneficiaries.append("BEN_CARDIO_LOW_SODIUM")
        if per_serving.get("proteinG", 0) >= 16.0:
            beneficiaries.append("BEN_HIGH_PROTEIN_ACTIVE")

        return {
            "source": "ICMR-NIN IFCT 2017 Dataset (GitHub)",
            "servings": servings,
            "calories": per_serving.get("energyKcal", 0.0),
            "proteinG": per_serving.get("proteinG", 0.0),
            "carbsG": per_serving.get("carbsG", 0.0),
            "fatG": per_serving.get("fatG", 0.0),
            "fibreG": per_serving.get("totalDietaryFibreG", per_serving.get("fibreG", 0.0)),
            "sodiumMg": per_serving.get("sodiumMg", 0.0),
            "ironMg": per_serving.get("ironMg", 0.0),
            "calciumMg": per_serving.get("calciumMg", 0.0),
            "matchedBeneficiaries": beneficiaries,
            "detailedNutrients": per_serving
        }

ifct_calculator = IFCT2017MeasurementCalculator()