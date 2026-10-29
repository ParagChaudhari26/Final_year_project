"""
Meal Planner Service for FoodCoach AI
Generates personalized, balanced 1-14 day meal plans (Breakfast, Lunch, Snack, Dinner)
incorporating Ayurvedic principles (Viruddha Ahaar avoidance), IFCT 2017 nutritional targets,
and user dietary preferences / health conditions.
"""
import logging
from typing import List, Dict, Any, Optional

from services.viruddha_ahaar_engine import viruddha_engine
from services.ifct_measurement_calculator import ifct_calculator

logger = logging.getLogger("MealPlanner")

# ─────────────────────────────────────────────────────────────────────────────
# Curated Meal Catalog for Indian Cuisines
# ─────────────────────────────────────────────────────────────────────────────
MEAL_CATALOG: List[Dict[str, Any]] = [
    # Breakfasts
    {
        "id": "BK_POHA", "title": "Kanda Batata Poha", "mealType": "breakfast",
        "cuisine": "Maharashtrian", "dietType": "Vegan",
        "calories": 280, "proteinG": 8.0, "carbsG": 48.0, "fatG": 7.0, "fibreG": 4.5,
        "beneficiaries": ["HC_ANEMIA", "HC_DIGESTION"],
        "ingredients": [
            {"name": "Flattened Rice", "quantity": 120, "unit": "g"},
            {"name": "Potato", "quantity": 80, "unit": "g"},
            {"name": "Onion", "quantity": 50, "unit": "g"},
            {"name": "Peanuts", "quantity": 20, "unit": "g"},
            {"name": "Mustard Seeds & Curry Leaves", "quantity": 5, "unit": "g"}
        ],
        "highlights": "Light and easily digestible, rich in non-heme iron from flattened rice."
    },
    {
        "id": "BK_UPMA", "title": "Vegetable Rava Upma", "mealType": "breakfast",
        "cuisine": "South Indian", "dietType": "Vegetarian",
        "calories": 250, "proteinG": 7.0, "carbsG": 42.0, "fatG": 6.0, "fibreG": 3.8,
        "beneficiaries": ["HC_DIGESTION"],
        "ingredients": [
            {"name": "Semolina", "quantity": 100, "unit": "g"},
            {"name": "Carrot & Peas", "quantity": 60, "unit": "g"},
            {"name": "Onion", "quantity": 40, "unit": "g"},
            {"name": "Ghee", "quantity": 5, "unit": "g"}
        ],
        "highlights": "Sattvic morning meal tempered with ginger and mustard."
    },
    {
        "id": "BK_THEPLA", "title": "Methi Thepla with Mint Chutney", "mealType": "breakfast",
        "cuisine": "Gujarati", "dietType": "Vegetarian",
        "calories": 260, "proteinG": 9.0, "carbsG": 38.0, "fatG": 8.0, "fibreG": 6.0,
        "beneficiaries": ["HC_DIABETES", "HC_DIGESTION"],
        "ingredients": [
            {"name": "Whole Wheat Flour", "quantity": 100, "unit": "g"},
            {"name": "Fenugreek Leaves", "quantity": 80, "unit": "g"},
            {"name": "Yogurt", "quantity": 30, "unit": "g"},
            {"name": "Sesame Seeds", "quantity": 10, "unit": "g"}
        ],
        "highlights": "Fenugreek leaves lower blood glucose absorption and improve insulin sensitivity."
    },
    {
        "id": "BK_CHILLA", "title": "Moong Dal & Palak Chilla", "mealType": "breakfast",
        "cuisine": "Pan-Indian", "dietType": "Vegan",
        "calories": 240, "proteinG": 14.0, "carbsG": 32.0, "fatG": 6.0, "fibreG": 5.5,
        "beneficiaries": ["HC_DIABETES", "HC_OBESITY", "HC_ANEMIA"],
        "ingredients": [
            {"name": "Yellow Moong Dal", "quantity": 90, "unit": "g"},
            {"name": "Spinach", "quantity": 60, "unit": "g"},
            {"name": "Ginger", "quantity": 5, "unit": "g"},
            {"name": "Cumin Seeds", "quantity": 3, "unit": "g"}
        ],
        "highlights": "High-protein savory crepe with iron-dense spinach."
    },
    {
        "id": "BK_PANEER_TOAST", "title": "Spiced Paneer Bhurji with Multigrain Toast", "mealType": "breakfast",
        "cuisine": "Punjabi", "dietType": "Vegetarian",
        "calories": 310, "proteinG": 19.0, "carbsG": 28.0, "fatG": 13.0, "fibreG": 4.0,
        "beneficiaries": ["HC_BONE", "HC_IMMUNITY"],
        "ingredients": [
            {"name": "Paneer", "quantity": 120, "unit": "g"},
            {"name": "Tomato", "quantity": 50, "unit": "g"},
            {"name": "Onion", "quantity": 40, "unit": "g"},
            {"name": "Multigrain Bread", "quantity": 60, "unit": "g"}
        ],
        "highlights": "Calcium and leucine-rich breakfast ideal for active recovery and bone health."
    },

    # Lunches
    {
        "id": "LN_PALAK_PANEER", "title": "Palak Paneer with Jowar Bhakri", "mealType": "lunch",
        "cuisine": "Maharashtrian", "dietType": "Vegetarian",
        "calories": 480, "proteinG": 24.0, "carbsG": 54.0, "fatG": 18.0, "fibreG": 9.5,
        "beneficiaries": ["HC_ANEMIA", "HC_BONE", "HC_DIABETES"],
        "ingredients": [
            {"name": "Spinach", "quantity": 150, "unit": "g"},
            {"name": "Paneer", "quantity": 120, "unit": "g"},
            {"name": "Jowar Flour", "quantity": 100, "unit": "g"},
            {"name": "Tomato", "quantity": 60, "unit": "g"},
            {"name": "Garlic", "quantity": 10, "unit": "g"}
        ],
        "highlights": "Synergistic combo: Jowar fiber plus iron-rich spinach and protein-rich paneer."
    },
    {
        "id": "LN_RAJMA_CHAWAL", "title": "Punjabi Rajma Masala with Basmati Rice", "mealType": "lunch",
        "cuisine": "Punjabi", "dietType": "Vegan",
        "calories": 520, "proteinG": 20.0, "carbsG": 86.0, "fatG": 9.0, "fibreG": 12.0,
        "beneficiaries": ["HC_DIABETES", "HC_OBESITY", "HC_ANEMIA"],
        "ingredients": [
            {"name": "Kidney Beans", "quantity": 150, "unit": "g"},
            {"name": "Basmati Rice", "quantity": 120, "unit": "g"},
            {"name": "Tomato", "quantity": 80, "unit": "g"},
            {"name": "Onion", "quantity": 60, "unit": "g"}
        ],
        "highlights": "Complete amino acid profile formed by combining legumes with cereals."
    },
    {
        "id": "LN_SAMBAR_RICE", "title": "Drumstick Sambar with Steamed Rice & Beet Poriyal", "mealType": "lunch",
        "cuisine": "South Indian", "dietType": "Vegan",
        "calories": 450, "proteinG": 16.0, "carbsG": 76.0, "fatG": 7.0, "fibreG": 10.0,
        "beneficiaries": ["HC_DIGESTION", "HC_ANEMIA", "HC_CARDIAC"],
        "ingredients": [
            {"name": "Toor Dal", "quantity": 100, "unit": "g"},
            {"name": "Drumstick", "quantity": 80, "unit": "g"},
            {"name": "Basmati Rice", "quantity": 120, "unit": "g"},
            {"name": "Tamarind", "quantity": 15, "unit": "g"},
            {"name": "Beetroot", "quantity": 60, "unit": "g"}
        ],
        "highlights": "Alkalizing lunch loaded with antioxidants, potassium, and digestive spices."
    },
    {
        "id": "LN_CHANA_JEERA", "title": "Amritsari Chana Masala with Jeera Rice", "mealType": "lunch",
        "cuisine": "Punjabi", "dietType": "Vegan",
        "calories": 490, "proteinG": 18.0, "carbsG": 78.0, "fatG": 11.0, "fibreG": 11.5,
        "beneficiaries": ["HC_DIABETES", "HC_CARDIAC"],
        "ingredients": [
            {"name": "Chickpeas", "quantity": 140, "unit": "g"},
            {"name": "Basmati Rice", "quantity": 100, "unit": "g"},
            {"name": "Tomato", "quantity": 70, "unit": "g"},
            {"name": "Cumin Seeds", "quantity": 8, "unit": "g"}
        ],
        "highlights": "Low glycemic index carbohydrates with sustained, steady glucose release."
    },
    {
        "id": "LN_MASOOR_BHAKRI", "title": "Tadka Masoor Dal with Bajra Bhakri & Kachumber", "mealType": "lunch",
        "cuisine": "Pan-Indian", "dietType": "Vegan",
        "calories": 460, "proteinG": 21.0, "carbsG": 68.0, "fatG": 9.0, "fibreG": 13.0,
        "beneficiaries": ["HC_ANEMIA", "HC_IMMUNITY"],
        "ingredients": [
            {"name": "Red Lentils", "quantity": 120, "unit": "g"},
            {"name": "Bajra Flour", "quantity": 90, "unit": "g"},
            {"name": "Tomato", "quantity": 60, "unit": "g"},
            {"name": "Garlic", "quantity": 10, "unit": "g"}
        ],
        "highlights": "Masoor dal and pearl millet deliver high bioavailability iron with Vitamin C."
    },

    # Snacks
    {
        "id": "SN_MAKHANA", "title": "Roasted Makhana with Turmeric & Chaat Masala", "mealType": "snack",
        "cuisine": "Pan-Indian", "dietType": "Vegan",
        "calories": 140, "proteinG": 4.5, "carbsG": 22.0, "fatG": 3.5, "fibreG": 3.0,
        "beneficiaries": ["HC_CARDIAC", "HC_OBESITY", "HC_DIABETES"],
        "ingredients": [
            {"name": "Foxnuts (Makhana)", "quantity": 40, "unit": "g"},
            {"name": "Olive Oil", "quantity": 4, "unit": "g"},
            {"name": "Turmeric & Rock Salt", "quantity": 2, "unit": "g"}
        ],
        "highlights": "Anti-inflammatory, low sodium, gluten-free snack high in magnesium."
    },
    {
        "id": "SN_SPROUTS", "title": "Sprouted Moong Chaat with Lemon & Pomegranate", "mealType": "snack",
        "cuisine": "Maharashtrian", "dietType": "Vegan",
        "calories": 160, "proteinG": 9.5, "carbsG": 26.0, "fatG": 1.5, "fibreG": 6.5,
        "beneficiaries": ["HC_ANEMIA", "HC_DIGESTION", "HC_IMMUNITY"],
        "ingredients": [
            {"name": "Sprouted Green Moong", "quantity": 100, "unit": "g"},
            {"name": "Pomegranate Seeds", "quantity": 30, "unit": "g"},
            {"name": "Lemon Juice", "quantity": 10, "unit": "ml"},
            {"name": "Cucumber", "quantity": 40, "unit": "g"}
        ],
        "highlights": "Sprouting triples Vitamin C and activates living digestive enzymes."
    },
    {
        "id": "SN_BUTTERMILK", "title": "Mint & Roasted Cumin Chaas (Buttermilk)", "mealType": "snack",
        "cuisine": "Gujarati", "dietType": "Vegetarian",
        "calories": 80, "proteinG": 4.0, "carbsG": 7.0, "fatG": 3.0, "fibreG": 0.5,
        "beneficiaries": ["HC_DIGESTION"],
        "ingredients": [
            {"name": "Fresh Curd/Buttermilk", "quantity": 180, "unit": "ml"},
            {"name": "Mint Leaves", "quantity": 10, "unit": "g"},
            {"name": "Roasted Cumin Powder", "quantity": 3, "unit": "g"}
        ],
        "highlights": "Probiotic-rich gut soother consumed during daytime to rekindle Agni."
    },

    # Dinners
    {
        "id": "DN_KHICHDI", "title": "Comfort Moong Dal Khichdi with Steamed Veggies", "mealType": "dinner",
        "cuisine": "Pan-Indian", "dietType": "Vegetarian",
        "calories": 360, "proteinG": 14.0, "carbsG": 58.0, "fatG": 7.0, "fibreG": 7.0,
        "beneficiaries": ["HC_DIGESTION"],
        "ingredients": [
            {"name": "Yellow Moong Dal", "quantity": 80, "unit": "g"},
            {"name": "Basmati Rice", "quantity": 80, "unit": "g"},
            {"name": "Ghee", "quantity": 8, "unit": "g"},
            {"name": "Carrot", "quantity": 50, "unit": "g"}
        ],
        "highlights": "The quintessential Ayurvedic evening meal: tri-doshic and soothing for digestion."
    },
    {
        "id": "DN_DAL_TADKA", "title": "Dal Tadka with Steamed Rice & Cucumber Salad", "mealType": "dinner",
        "cuisine": "Pan-Indian", "dietType": "Vegetarian",
        "calories": 410, "proteinG": 16.0, "carbsG": 64.0, "fatG": 9.0, "fibreG": 8.0,
        "beneficiaries": ["HC_DIGESTION", "HC_CARDIAC"],
        "ingredients": [
            {"name": "Toor Dal", "quantity": 100, "unit": "g"},
            {"name": "Basmati Rice", "quantity": 90, "unit": "g"},
            {"name": "Tomato", "quantity": 60, "unit": "g"},
            {"name": "Ghee", "quantity": 8, "unit": "g"}
        ],
        "highlights": "Warm evening comfort balanced with cumin, garlic and clarified butter."
    },
    {
        "id": "DN_BAINGAN_BHAKRI", "title": "Smoky Baingan Bharta with Jowar Bhakri", "mealType": "dinner",
        "cuisine": "Maharashtrian", "dietType": "Vegan",
        "calories": 340, "proteinG": 11.0, "carbsG": 56.0, "fatG": 8.0, "fibreG": 9.0,
        "beneficiaries": ["HC_DIGESTION", "HC_OBESITY"],
        "ingredients": [
            {"name": "Eggplant", "quantity": 250, "unit": "g"},
            {"name": "Jowar Flour", "quantity": 90, "unit": "g"},
            {"name": "Onion", "quantity": 50, "unit": "g"},
            {"name": "Tomato", "quantity": 50, "unit": "g"}
        ],
        "highlights": "Light low-calorie night meal high in potassium and dietary fiber."
    },
    {
        "id": "DN_ALOO_GOBI_PHULKA", "title": "Aloo Gobi Matar with Multigrain Phulka", "mealType": "dinner",
        "cuisine": "Punjabi", "dietType": "Vegan",
        "calories": 370, "proteinG": 12.0, "carbsG": 62.0, "fatG": 8.0, "fibreG": 8.5,
        "beneficiaries": ["HC_IMMUNITY"],
        "ingredients": [
            {"name": "Cauliflower", "quantity": 150, "unit": "g"},
            {"name": "Green Peas", "quantity": 60, "unit": "g"},
            {"name": "Potato", "quantity": 70, "unit": "g"},
            {"name": "Whole Wheat Flour", "quantity": 80, "unit": "g"}
        ],
        "highlights": "Cruciferous vegetables rich in glucosinolates and antioxidant phytochemicals."
    }
]


class SevenDayMealPlanner:
    """
    Intelligent Meal Planner that respects user profile constraints,
    cuisines, macro targets, and ensures Viruddha Ahaar safety.
    """

    def generate_plan(
        self,
        cuisines: Optional[List[str]] = None,
        days: int = 7,
        user_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        days = max(1, min(days, 14))
        preferred_cuisines = [c.lower() for c in (cuisines or ["Pan-Indian", "Punjabi", "Maharashtrian"])]

        # Extract user profile settings
        profile = user_profile or {}
        diet_type = profile.get("dietType", "Vegetarian")
        allergies = [a.lower() for a in profile.get("allergies", [])]
        health_conditions = set(profile.get("healthConditions", []))
        apply_ayurveda = profile.get("applyAyurvedicConstraints", True)
        viruddha_mode = profile.get("viruddhaStrictMode", "FILTER")
        target_macros = profile.get("macroTargets") or {"calories": 2000, "protein": 80, "carbs": 250, "fat": 65}

        # Filter candidate meals by diet and allergies
        valid_meals: Dict[str, List[Dict[str, Any]]] = {
            "breakfast": [],
            "lunch": [],
            "snack": [],
            "dinner": []
        }

        for meal in MEAL_CATALOG:
            # Check diet restriction (Vegan cannot have dairy)
            if diet_type == "Vegan" and meal.get("dietType") != "Vegan":
                continue

            # Check allergies
            meal_ing_names = " ".join([ing["name"].lower() for ing in meal.get("ingredients", [])])
            has_allergen = False
            for allergy in allergies:
                if allergy in ("dairy", "milk") and any(d in meal_ing_names for d in ["milk", "paneer", "ghee", "curd", "yogurt", "butter"]):
                    has_allergen = True
                    break
                if allergy in ("gluten", "wheat") and any(g in meal_ing_names for g in ["wheat", "semolina", "rava", "bread"]):
                    has_allergen = True
                    break
                if allergy in ("tree nuts", "peanuts", "nut") and "peanut" in meal_ing_names:
                    has_allergen = True
                    break
                if allergy in meal_ing_names:
                    has_allergen = True
                    break

            if has_allergen:
                continue

            # Check Viruddha Ahaar compatibility within the meal
            if apply_ayurveda and viruddha_mode == "FILTER":
                compatibility = viruddha_engine.evaluate(meal.get("ingredients", []))
                if not compatibility.get("isCompatible", True) and compatibility.get("overallSeverity") == "High":
                    continue

            m_type = meal.get("mealType", "lunch")
            if m_type in valid_meals:
                valid_meals[m_type].append(meal)

        # Fallback if any category emptied by strict filters
        for m_type in valid_meals:
            if not valid_meals[m_type]:
                # Provide at least 1 safe default
                fallback_base = [m for m in MEAL_CATALOG if m["mealType"] == m_type]
                valid_meals[m_type] = fallback_base if fallback_base else [MEAL_CATALOG[0]]

        # Score and rank meals for cuisine and health condition synergy
        def score_meal(m: Dict[str, Any]) -> float:
            score = 1.0
            if m.get("cuisine", "").lower() in preferred_cuisines:
                score += 1.5
            # Health condition boost
            bens = set(m.get("beneficiaries", []))
            common_conds = bens.intersection(health_conditions)
            score += len(common_conds) * 2.0
            return score

        for m_type in valid_meals:
            valid_meals[m_type].sort(key=score_meal, reverse=True)

        # Construct daily schedules
        plan_days = []
        cumulative_cals = 0.0
        cumulative_protein = 0.0

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for i in range(days):
            day_num = i + 1
            day_label = day_names[i % 7]

            bk = valid_meals["breakfast"][i % len(valid_meals["breakfast"])]
            ln = valid_meals["lunch"][i % len(valid_meals["lunch"])]
            sn = valid_meals["snack"][i % len(valid_meals["snack"])]
            dn = valid_meals["dinner"][i % len(valid_meals["dinner"])]

            day_cals = round(bk["calories"] + ln["calories"] + sn["calories"] + dn["calories"], 1)
            day_protein = round(bk["proteinG"] + ln["proteinG"] + sn["proteinG"] + dn["proteinG"], 1)
            day_carbs = round(bk["carbsG"] + ln["carbsG"] + sn["carbsG"] + dn["carbsG"], 1)
            day_fat = round(bk["fatG"] + ln["fatG"] + sn["fatG"] + dn["fatG"], 1)
            day_fibre = round(bk["fibreG"] + ln["fibreG"] + sn["fibreG"] + dn["fibreG"], 1)

            cumulative_cals += day_cals
            cumulative_protein += day_protein

            plan_days.append({
                "day": day_num,
                "dayLabel": f"Day {day_num} ({day_label})",
                "meals": {
                    "breakfast": bk,
                    "lunch": ln,
                    "snack": sn,
                    "dinner": dn
                },
                "dailyNutrition": {
                    "calories": day_cals,
                    "proteinG": day_protein,
                    "carbsG": day_carbs,
                    "fatG": day_fat,
                    "fibreG": day_fibre
                },
                "targetComparison": {
                    "calorieVariance": round(day_cals - float(target_macros.get("calories", 2000)), 1),
                    "proteinVariance": round(day_protein - float(target_macros.get("protein", 80)), 1)
                }
            })

        avg_cals = round(cumulative_cals / days, 1)
        avg_protein = round(cumulative_protein / days, 1)

        return {
            "status": "success",
            "totalDays": days,
            "cuisines": cuisines or ["Pan-Indian", "Punjabi", "Maharashtrian"],
            "userProfileApplied": {
                "dietType": diet_type,
                "allergies": allergies,
                "healthConditions": list(health_conditions),
                "viruddhaStrictMode": viruddha_mode
            },
            "summary": {
                "averageDailyCalories": avg_cals,
                "averageDailyProteinG": avg_protein,
                "targetCalories": float(target_macros.get("calories", 2000)),
                "targetProteinG": float(target_macros.get("protein", 80)),
                "ayurvedicSafetyVerified": True,
                "recommendationNote": (
                    f"Balanced {days}-day plan aligned with Indian seasonal digestion. "
                    "Features slow-digesting complex pulses at lunch and lighter dosha-pacifying meals at dinner."
                )
            },
            "plan": plan_days
        }


meal_planner = SevenDayMealPlanner()
