"""
GNN Ranker — Graph-Neural-Network-style recipe ranking for FoodCoach AI.
Uses Neo4j graph data (with NetworkX-based scoring) and a rich in-memory fallback.
Algorithm:
  1. Load recipes from Neo4j (or fallback DB)
  2. For each recipe compute:
      - pantry_match_score   (% of ingredients available)
      - expiry_urgency_score (uses about-to-expire items first)
      - nutrition_fit_score  (how well macros match user targets)
      - viruddha_penalty     (penalise incompatible recipes)
  3. Weighted aggregate → final score
  4. Run NetworkX PageRank over a user-recipe-ingredient bipartite graph
     to boost interconnected high-scoring recipes.
  5. Return ranked recommended + filtered lists.
"""
import logging
from typing import Dict, Any, List, Set, Optional

import networkx as nx

from services.viruddha_ahaar_engine import viruddha_engine

logger = logging.getLogger("GNNRanker")

# ─────────────────────────────────────────────────────────────────────────────
# In-memory fallback recipe database (used when Neo4j is unavailable)
# ─────────────────────────────────────────────────────────────────────────────
FALLBACK_RECIPES: List[Dict[str, Any]] = [
    {
        "id": "REC_PALAK_PANEER", "title": "Palak Paneer", "cuisine": "Punjabi",
        "cookingProcess": "simmered", "servings": 2, "dietType": "Vegetarian",
        "prepTimeMinutes": 15, "cookTimeMinutes": 25, "difficultyLevel": "Medium",
        "description": "Creamy spinach curry with fresh cottage cheese, rich in iron and protein",
        "totalCaloriesPerServing": 320, "proteinGPerServing": 18,
        "beneficiaries": ["HC_ANEMIA", "HC_BONE"],
        "ingredients": [
            {"id": "ING_SPINACH", "name": "Spinach", "quantity": 200, "unit": "g"},
            {"id": "ING_PANEER",  "name": "Paneer",  "quantity": 150, "unit": "g"},
            {"id": "ING_TOMATO",  "name": "Tomato",  "quantity": 100, "unit": "g"},
            {"id": "ING_ONION",   "name": "Onion",   "quantity": 80,  "unit": "g"},
            {"id": "ING_GARLIC",  "name": "Garlic",  "quantity": 10,  "unit": "g"},
            {"id": "ING_GINGER",  "name": "Ginger",  "quantity": 10,  "unit": "g"},
        ],
    },
    {
        "id": "REC_DAL_TADKA", "title": "Dal Tadka", "cuisine": "Pan-Indian",
        "cookingProcess": "simmered", "servings": 4, "dietType": "Vegetarian",
        "prepTimeMinutes": 10, "cookTimeMinutes": 30, "difficultyLevel": "Easy",
        "description": "Golden toor dal tempered with cumin, garlic and ghee",
        "totalCaloriesPerServing": 220, "proteinGPerServing": 12,
        "beneficiaries": ["HC_DIABETES", "HC_CARDIAC"],
        "ingredients": [
            {"id": "ING_TOOR_DAL", "name": "Toor Dal", "quantity": 200, "unit": "g"},
            {"id": "ING_TOMATO",   "name": "Tomato",   "quantity": 100, "unit": "g"},
            {"id": "ING_ONION",    "name": "Onion",    "quantity": 80,  "unit": "g"},
            {"id": "ING_GARLIC",   "name": "Garlic",   "quantity": 10,  "unit": "g"},
            {"id": "ING_GHEE",     "name": "Ghee",     "quantity": 15,  "unit": "g"},
        ],
    },
    {
        "id": "REC_RAJMA", "title": "Rajma Masala", "cuisine": "Punjabi",
        "cookingProcess": "slow_simmered", "servings": 4, "dietType": "Vegan",
        "prepTimeMinutes": 15, "cookTimeMinutes": 45, "difficultyLevel": "Medium",
        "description": "Hearty kidney bean curry in a rich tomato-onion masala",
        "totalCaloriesPerServing": 280, "proteinGPerServing": 16,
        "beneficiaries": ["HC_DIABETES", "HC_OBESITY", "HC_ANEMIA"],
        "ingredients": [
            {"id": "ING_RAJMA",  "name": "Kidney Beans", "quantity": 200, "unit": "g"},
            {"id": "ING_TOMATO", "name": "Tomato",       "quantity": 150, "unit": "g"},
            {"id": "ING_ONION",  "name": "Onion",        "quantity": 100, "unit": "g"},
            {"id": "ING_GARLIC", "name": "Garlic",       "quantity": 10,  "unit": "g"},
            {"id": "ING_GINGER", "name": "Ginger",       "quantity": 10,  "unit": "g"},
        ],
    },
    {
        "id": "REC_UPMA", "title": "Vegetable Upma", "cuisine": "South Indian",
        "cookingProcess": "sauteed", "servings": 2, "dietType": "Vegetarian",
        "prepTimeMinutes": 5, "cookTimeMinutes": 15, "difficultyLevel": "Easy",
        "description": "Savory semolina porridge with vegetables and tempered spices",
        "totalCaloriesPerServing": 250, "proteinGPerServing": 7,
        "beneficiaries": ["HC_DIGESTION"],
        "ingredients": [
            {"id": "ING_SEMOLINA", "name": "Semolina", "quantity": 100, "unit": "g"},
            {"id": "ING_ONION",    "name": "Onion",    "quantity": 60,  "unit": "g"},
            {"id": "ING_TOMATO",   "name": "Tomato",   "quantity": 50,  "unit": "g"},
            {"id": "ING_GHEE",     "name": "Ghee",     "quantity": 5,   "unit": "g"},
        ],
    },
    {
        "id": "REC_POHA", "title": "Kanda Batata Poha", "cuisine": "Maharashtrian",
        "cookingProcess": "sauteed", "servings": 2, "dietType": "Vegan",
        "prepTimeMinutes": 10, "cookTimeMinutes": 15, "difficultyLevel": "Easy",
        "description": "Light flattened rice with potato, onion, and peanuts",
        "totalCaloriesPerServing": 280, "proteinGPerServing": 8,
        "beneficiaries": ["HC_ANEMIA"],
        "ingredients": [
            {"id": "ING_POHA",   "name": "Flattened Rice", "quantity": 150, "unit": "g"},
            {"id": "ING_POTATO", "name": "Potato",         "quantity": 100, "unit": "g"},
            {"id": "ING_ONION",  "name": "Onion",          "quantity": 80,  "unit": "g"},
            {"id": "ING_PEANUT", "name": "Peanuts",        "quantity": 30,  "unit": "g"},
        ],
    },
    {
        "id": "REC_CHANA_MASALA", "title": "Chana Masala", "cuisine": "Punjabi",
        "cookingProcess": "slow_simmered", "servings": 4, "dietType": "Vegan",
        "prepTimeMinutes": 15, "cookTimeMinutes": 40, "difficultyLevel": "Medium",
        "description": "Spiced chickpea curry in a tangy tomato-based gravy",
        "totalCaloriesPerServing": 290, "proteinGPerServing": 15,
        "beneficiaries": ["HC_DIGESTION", "HC_DIABETES"],
        "ingredients": [
            {"id": "ING_CHICKPEA", "name": "Chickpeas", "quantity": 200, "unit": "g"},
            {"id": "ING_TOMATO",   "name": "Tomato",    "quantity": 150, "unit": "g"},
            {"id": "ING_ONION",    "name": "Onion",     "quantity": 100, "unit": "g"},
            {"id": "ING_GARLIC",   "name": "Garlic",    "quantity": 10,  "unit": "g"},
            {"id": "ING_GINGER",   "name": "Ginger",    "quantity": 10,  "unit": "g"},
        ],
    },
    {
        "id": "REC_MASOOR_DAL", "title": "Masoor Dal", "cuisine": "Pan-Indian",
        "cookingProcess": "simmered", "servings": 3, "dietType": "Vegan",
        "prepTimeMinutes": 5, "cookTimeMinutes": 25, "difficultyLevel": "Easy",
        "description": "Red lentil soup with tempered onion, tomato and spices",
        "totalCaloriesPerServing": 190, "proteinGPerServing": 14,
        "beneficiaries": ["HC_ANEMIA", "HC_IMMUNITY"],
        "ingredients": [
            {"id": "ING_MASOOR", "name": "Red Lentils", "quantity": 150, "unit": "g"},
            {"id": "ING_TOMATO", "name": "Tomato",      "quantity": 100, "unit": "g"},
            {"id": "ING_ONION",  "name": "Onion",       "quantity": 60,  "unit": "g"},
            {"id": "ING_GARLIC", "name": "Garlic",      "quantity": 8,   "unit": "g"},
        ],
    },
    {
        "id": "REC_ALOO_GOBI", "title": "Aloo Gobi", "cuisine": "Punjabi",
        "cookingProcess": "sauteed", "servings": 3, "dietType": "Vegan",
        "prepTimeMinutes": 10, "cookTimeMinutes": 20, "difficultyLevel": "Easy",
        "description": "Dry curry of potato and cauliflower with turmeric and spices",
        "totalCaloriesPerServing": 170, "proteinGPerServing": 4,
        "beneficiaries": [],
        "ingredients": [
            {"id": "ING_POTATO",      "name": "Potato",      "quantity": 200, "unit": "g"},
            {"id": "ING_CAULIFLOWER", "name": "Cauliflower", "quantity": 300, "unit": "g"},
            {"id": "ING_ONION",       "name": "Onion",       "quantity": 80,  "unit": "g"},
            {"id": "ING_TOMATO",      "name": "Tomato",      "quantity": 80,  "unit": "g"},
        ],
    },
    {
        "id": "REC_KHICHDI", "title": "Moong Dal Khichdi", "cuisine": "Pan-Indian",
        "cookingProcess": "simmered", "servings": 3, "dietType": "Vegetarian",
        "prepTimeMinutes": 5, "cookTimeMinutes": 30, "difficultyLevel": "Easy",
        "description": "Comforting one-pot rice and moong dal, ideal for all ages and recovery",
        "totalCaloriesPerServing": 240, "proteinGPerServing": 10,
        "beneficiaries": ["HC_DIGESTION"],
        "ingredients": [
            {"id": "ING_MOONG", "name": "Yellow Moong Dal", "quantity": 100, "unit": "g"},
            {"id": "ING_RICE",  "name": "Basmati Rice",     "quantity": 100, "unit": "g"},
            {"id": "ING_GHEE",  "name": "Ghee",             "quantity": 10,  "unit": "g"},
        ],
    },
    {
        "id": "REC_PANEER_BHURJI", "title": "Paneer Bhurji", "cuisine": "Punjabi",
        "cookingProcess": "sauteed", "servings": 2, "dietType": "Vegetarian",
        "prepTimeMinutes": 10, "cookTimeMinutes": 15, "difficultyLevel": "Easy",
        "description": "Scrambled cottage cheese with onion, tomato and bell pepper",
        "totalCaloriesPerServing": 280, "proteinGPerServing": 20,
        "beneficiaries": ["HC_IMMUNITY", "HC_BONE"],
        "ingredients": [
            {"id": "ING_PANEER", "name": "Paneer", "quantity": 200, "unit": "g"},
            {"id": "ING_ONION",  "name": "Onion",  "quantity": 100, "unit": "g"},
            {"id": "ING_TOMATO", "name": "Tomato", "quantity": 100, "unit": "g"},
            {"id": "ING_GARLIC", "name": "Garlic", "quantity": 10,  "unit": "g"},
            {"id": "ING_GINGER", "name": "Ginger", "quantity": 8,   "unit": "g"},
        ],
    },
    {
        "id": "REC_JOWAR_BHAKRI", "title": "Jowar Bhakri with Garlic Chutney",
        "cuisine": "Maharashtrian",
        "cookingProcess": "baked", "servings": 2, "dietType": "Vegan",
        "prepTimeMinutes": 10, "cookTimeMinutes": 15, "difficultyLevel": "Medium",
        "description": "Gluten-free sorghum flatbread with spicy garlic chutney",
        "totalCaloriesPerServing": 210, "proteinGPerServing": 8,
        "beneficiaries": ["HC_DIGESTION", "HC_ANEMIA"],
        "ingredients": [
            {"id": "ING_JOWAR",  "name": "Jowar Flour", "quantity": 200, "unit": "g"},
            {"id": "ING_GARLIC", "name": "Garlic",      "quantity": 15,  "unit": "g"},
        ],
    },
    {
        "id": "REC_BAINGAN_BHARTA", "title": "Baingan Bharta", "cuisine": "Punjabi",
        "cookingProcess": "baked", "servings": 3, "dietType": "Vegan",
        "prepTimeMinutes": 15, "cookTimeMinutes": 30, "difficultyLevel": "Medium",
        "description": "Smoky roasted eggplant mashed with onion, tomato and spices",
        "totalCaloriesPerServing": 120, "proteinGPerServing": 3,
        "beneficiaries": [],
        "ingredients": [
            {"id": "ING_EGGPLANT", "name": "Eggplant", "quantity": 400, "unit": "g"},
            {"id": "ING_TOMATO",   "name": "Tomato",   "quantity": 100, "unit": "g"},
            {"id": "ING_ONION",    "name": "Onion",    "quantity": 80,  "unit": "g"},
            {"id": "ING_GARLIC",   "name": "Garlic",   "quantity": 10,  "unit": "g"},
        ],
    },
    {
        "id": "REC_METHI_THEPLA", "title": "Methi Thepla", "cuisine": "Gujarati",
        "cookingProcess": "baked", "servings": 4, "dietType": "Vegetarian",
        "prepTimeMinutes": 20, "cookTimeMinutes": 20, "difficultyLevel": "Medium",
        "description": "Whole wheat flatbread packed with fresh fenugreek leaves",
        "totalCaloriesPerServing": 180, "proteinGPerServing": 6,
        "beneficiaries": ["HC_DIABETES"],
        "ingredients": [
            {"id": "ING_WHEAT",   "name": "Whole Wheat Flour",   "quantity": 150, "unit": "g"},
            {"id": "ING_METHI",   "name": "Fenugreek Leaves",    "quantity": 100, "unit": "g"},
            {"id": "ING_YOGURT",  "name": "Yogurt",              "quantity": 50,  "unit": "g"},
        ],
    },
    {
        "id": "REC_SAMBAR", "title": "Sambar", "cuisine": "South Indian",
        "cookingProcess": "simmered", "servings": 4, "dietType": "Vegan",
        "prepTimeMinutes": 15, "cookTimeMinutes": 35, "difficultyLevel": "Medium",
        "description": "Tangy toor dal soup with drumstick, tamarind and sambar powder",
        "totalCaloriesPerServing": 150, "proteinGPerServing": 8,
        "beneficiaries": ["HC_DIGESTION", "HC_ANEMIA"],
        "ingredients": [
            {"id": "ING_TOOR_DAL", "name": "Toor Dal",  "quantity": 150, "unit": "g"},
            {"id": "ING_TOMATO",   "name": "Tomato",    "quantity": 60,  "unit": "g"},
            {"id": "ING_TAMARIND", "name": "Tamarind",  "quantity": 30,  "unit": "g"},
            {"id": "ING_EGGPLANT", "name": "Eggplant",  "quantity": 60,  "unit": "g"},
        ],
    },
    {
        "id": "REC_VEG_PULAO", "title": "Vegetable Pulao", "cuisine": "Pan-Indian",
        "cookingProcess": "simmered", "servings": 4, "dietType": "Vegan",
        "prepTimeMinutes": 15, "cookTimeMinutes": 25, "difficultyLevel": "Easy",
        "description": "Fragrant basmati rice with seasonal vegetables and whole spices",
        "totalCaloriesPerServing": 260, "proteinGPerServing": 5,
        "beneficiaries": [],
        "ingredients": [
            {"id": "ING_RICE",   "name": "Basmati Rice", "quantity": 200, "unit": "g"},
            {"id": "ING_ONION",  "name": "Onion",        "quantity": 100, "unit": "g"},
            {"id": "ING_TOMATO", "name": "Tomato",       "quantity": 100, "unit": "g"},
            {"id": "ING_GHEE",   "name": "Ghee",         "quantity": 10,  "unit": "g"},
        ],
    },
]


def _pantry_set(pantry_items: List[Dict[str, Any]]) -> Set[str]:
    """Return a set of normalised ingredient IDs + names from pantry."""
    ids = set()
    for item in pantry_items:
        if item.get("ingredientId"):
            ids.add(item["ingredientId"].upper())
        if item.get("name"):
            ids.add(item["name"].strip().lower())
    return ids


def _expiry_score(ingredient_id: str, pantry_items: List[Dict[str, Any]]) -> float:
    """Return urgency score for an ingredient based on days until expiry."""
    for item in pantry_items:
        iid = (item.get("ingredientId") or "").upper()
        if iid == ingredient_id.upper():
            days = item.get("daysUntilExpiry", 30)
            if days <= 1:
                return 1.0
            elif days <= 3:
                return 0.8
            elif days <= 7:
                return 0.5
            else:
                return 0.1
    return 0.0


def _compute_scores(
    recipe: Dict[str, Any],
    pantry_items: List[Dict[str, Any]],
    pantry_set: Set[str],
    user_profile: Dict[str, Any],
    health_conditions: List[str],
) -> Dict[str, float]:
    ingredients = recipe.get("ingredients", [])
    if not ingredients:
        return {"pantry": 0.0, "expiry": 0.0, "nutrition": 0.5, "condition": 0.0}

    # 1. Pantry match (% of recipe ingredients in pantry)
    matched = 0
    expiry_total = 0.0
    for ing in ingredients:
        iid = ing.get("id", "").upper()
        iname = ing.get("name", "").lower()
        in_pantry = iid in pantry_set or iname in pantry_set
        if in_pantry:
            matched += 1
            expiry_total += _expiry_score(iid, pantry_items)

    pantry_score = matched / len(ingredients)
    expiry_score = expiry_total / max(matched, 1) if matched > 0 else 0.0

    # 2. Nutrition fitness (simple heuristic vs macro targets)
    macro_targets = user_profile.get("macroTargets", {}) or {}
    target_cal = float(macro_targets.get("calories", 2000))
    target_prot = float(macro_targets.get("protein", 80))
    recipe_cal = float(recipe.get("totalCaloriesPerServing", 300))
    recipe_prot = float(recipe.get("proteinGPerServing", 10))

    cal_fit = 1.0 - abs(recipe_cal - target_cal / 3) / (target_cal / 3)
    prot_fit = min(recipe_prot / (target_prot / 3), 1.0)
    nutrition_score = max(0.0, (cal_fit + prot_fit) / 2)

    # 3. Health condition match
    recipe_beneficiaries = recipe.get("beneficiaries", [])
    condition_score = 0.0
    if health_conditions and recipe_beneficiaries:
        matches = len(set(health_conditions) & set(recipe_beneficiaries))
        condition_score = matches / len(health_conditions)

    return {
        "pantry": round(pantry_score, 3),
        "expiry": round(expiry_score, 3),
        "nutrition": round(nutrition_score, 3),
        "condition": round(condition_score, 3),
    }


class GNNRanker:
    """
    Graph-based recipe ranker that integrates Neo4j knowledge graph
    with NetworkX PageRank-style scoring.
    """

    def rank_recipes(
        self,
        user_profile: Dict[str, Any],
        pantry_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        # Load recipes from Neo4j or fallback
        recipes = self._load_recipes(user_profile.get("dietType", "Vegetarian"))

        # Filter by dietary restriction
        diet = (user_profile.get("dietType") or "Vegetarian").lower()
        if diet == "vegan":
            recipes = [r for r in recipes if r.get("dietType", "").lower() == "vegan"]

        # Filter by allergies (simple name-match)
        allergies = {a.lower() for a in (user_profile.get("allergies") or [])}
        if allergies:
            filtered_by_allergy = []
            for r in recipes:
                ing_names = {i["name"].lower() for i in r.get("ingredients", [])}
                if not ing_names & allergies:
                    filtered_by_allergy.append(r)
            recipes = filtered_by_allergy

        # Filter by preferred cuisines
        pref_cuisines = [c.lower() for c in (user_profile.get("preferredCuisines") or [])]
        if pref_cuisines:
            cuisine_filtered = [
                r for r in recipes if r.get("cuisine", "").lower() in pref_cuisines
            ]
            if cuisine_filtered:
                recipes = cuisine_filtered

        p_set = _pantry_set(pantry_items)
        health_conditions = user_profile.get("healthConditions") or []
        strict_mode = user_profile.get("viruddhaStrictMode", "FILTER")

        # Build NetworkX bipartite graph for PageRank
        G = nx.DiGraph()
        user_node = "USER_PROFILE"
        G.add_node(user_node, type="user")

        scored_recipes = []
        for recipe in recipes:
            scores = _compute_scores(recipe, pantry_items, p_set, user_profile, health_conditions)

            # Weighted aggregate score
            w = {"pantry": 0.35, "expiry": 0.25, "nutrition": 0.25, "condition": 0.15}
            agg = sum(scores[k] * w[k] for k in scores)

            # Viruddha check
            va = viruddha_engine.evaluate(recipe.get("ingredients", []))
            if not va["isCompatible"]:
                agg *= (0.3 if strict_mode == "FILTER" else 0.7)

            recipe["_scores"] = scores
            recipe["_agg"] = agg
            recipe["_va"] = va

            # Add to graph
            rid = recipe["id"]
            G.add_node(rid, type="recipe", score=agg)
            G.add_edge(user_node, rid, weight=agg + 0.01)

            # Add ingredient nodes
            for ing in recipe.get("ingredients", []):
                iid = ing.get("id", ing["name"])
                G.add_node(iid, type="ingredient")
                G.add_edge(rid, iid, weight=1.0)
                if iid in p_set or ing["name"].lower() in p_set:
                    G.add_edge(user_node, iid, weight=0.5)

            scored_recipes.append(recipe)

        # NetworkX PageRank to boost well-connected recipes
        try:
            pagerank = nx.pagerank(G, alpha=0.85, max_iter=100)
        except Exception:
            pagerank = {r["id"]: r["_agg"] for r in scored_recipes}

        # Merge PageRank into final score
        for recipe in scored_recipes:
            pr = pagerank.get(recipe["id"], 0.0)
            recipe["_final_score"] = round(recipe["_agg"] * 0.7 + pr * 0.3, 4)

        # Sort descending
        scored_recipes.sort(key=lambda x: x["_final_score"], reverse=True)

        # Build response
        recommended = []
        filtered = []

        for recipe in scored_recipes:
            va = recipe["_va"]
            scores = recipe["_scores"]
            ingredients = recipe.get("ingredients", [])
            ing_ids_names = {i.get("id", "").upper() for i in ingredients} | {i["name"].lower() for i in ingredients}
            used = [i["name"] for i in ingredients if i.get("id", "").upper() in p_set or i["name"].lower() in p_set]
            missing = [i["name"] for i in ingredients if i.get("id", "").upper() not in p_set and i["name"].lower() not in p_set]

            if not va["isCompatible"] and strict_mode == "FILTER":
                filtered.append({
                    "recipeId": recipe["id"],
                    "title": recipe["title"],
                    "violations": va["violations"],
                    "severity": va["overallSeverity"],
                })
            else:
                recommended.append({
                    "recipeId": recipe["id"],
                    "title": recipe["title"],
                    "cuisine": recipe.get("cuisine", ""),
                    "dietType": recipe.get("dietType", ""),
                    "score": recipe["_final_score"],
                    "pantryMatchPct": round(scores["pantry"] * 100, 1),
                    "expiryUrgencyScore": scores["expiry"],
                    "nutritionFitScore": scores["nutrition"],
                    "prepTimeMinutes": recipe.get("prepTimeMinutes", 0),
                    "cookTimeMinutes": recipe.get("cookTimeMinutes", 0),
                    "difficultyLevel": recipe.get("difficultyLevel", "Medium"),
                    "description": recipe.get("description", ""),
                    "usedIngredients": used,
                    "missingIngredients": missing,
                    "beneficiaries": recipe.get("beneficiaries", []),
                    "nutritionPerServing": {
                        "calories": recipe.get("totalCaloriesPerServing", 0),
                        "proteinG": recipe.get("proteinGPerServing", 0),
                    },
                })

        return {
            "recommended": recommended,
            "filtered": filtered,
            "totalEvaluated": len(scored_recipes),
        }

    def _load_recipes(self, diet_type: str = "Vegetarian") -> List[Dict[str, Any]]:
        """Load recipes from Neo4j, fall back to in-memory DB."""
        try:
            from services.neo4j_service import neo4j_service
            if neo4j_service.is_connected:
                raw_recipes = neo4j_service.get_all_recipes(diet_type)
                if raw_recipes:
                    enriched = []
                    for r in raw_recipes:
                        ings = neo4j_service.get_recipe_ingredients(r.get("id", ""))
                        r["ingredients"] = [
                            {"id": i["id"], "name": i["name"], "quantity": i["quantity"], "unit": i["unit"]}
                            for i in ings
                        ]
                        enriched.append(r)
                    logger.info(f"Loaded {len(enriched)} recipes from Neo4j")
                    return enriched
        except Exception as exc:
            logger.warning(f"Neo4j recipe load failed: {exc}")

        logger.info("Using in-memory fallback recipe database")
        return [dict(r) for r in FALLBACK_RECIPES]


gnn_ranker = GNNRanker()
