import json
import logging
import os
from typing import Any, Dict, List

import requests

from services.gnn_ranker import gnn_ranker

logger = logging.getLogger("CookingGuide")


def _step(title: str, instruction: str, visual: str, timer_seconds: int = 0) -> Dict[str, Any]:
    return {
        "title": title,
        "instruction": instruction,
        "visual": visual,
        "timerSeconds": timer_seconds,
    }


COOKING_STEPS: Dict[str, List[Dict[str, Any]]] = {
    "REC_PALAK_PANEER": [
        _step("Prepare the ingredients", "Rinse the spinach well. Chop the onion and tomato, mince the ginger and garlic, and cut the paneer into cubes.", "🥬"),
        _step("Blanch the spinach", "Briefly boil the spinach until just wilted, then drain and cool it. Blend to a smooth puree.", "♨️", 120),
        _step("Cook the masala", "Warm a little cooking oil in a pan. Cook the onion until soft, then add ginger, garlic and tomato. Stir until the tomato breaks down.", "🧅"),
        _step("Simmer the curry", "Stir in the spinach puree and a splash of water. Simmer gently, then add the paneer cubes and heat them through without breaking them.", "🍲", 300),
        _step("Check and serve", "Check that the curry is steaming hot. Taste, adjust seasoning, and serve.", "🍽️"),
    ],
    "REC_DAL_TADKA": [
        _step("Rinse and cook the dal", "Rinse the toor dal. Cook it with water until completely soft, following your pressure cooker's instructions, then mash lightly.", "🫘"),
        _step("Prepare the tempering", "Warm the ghee in a small pan. Add cumin if available, then cook the chopped onion until soft.", "🫕"),
        _step("Finish the dal", "Add garlic and tomato to the tempering and cook until softened. Stir the tempering into the cooked dal and simmer until the texture is right.", "🍲", 180),
        _step("Check and serve", "Check the dal is piping hot, adjust salt and water, and serve.", "🍽️"),
    ],
    "REC_RAJMA": [
        _step("Soak the beans", "Rinse the kidney beans and soak them in plenty of water for at least 8 hours. Drain and discard the soaking water.", "🫘"),
        _step("Cook the beans safely", "Boil the soaked kidney beans vigorously for at least 10 minutes, then pressure-cook according to the cooker instructions until fully tender. Never taste undercooked kidney beans.", "♨️", 600),
        _step("Make the masala", "Warm oil in a pan. Cook chopped onion until soft, then add ginger, garlic and tomato. Stir until the mixture is thick.", "🧅"),
        _step("Simmer together", "Add the cooked beans and some cooking liquid to the masala. Simmer gently so the flavors combine and the beans stay intact.", "🍲", 600),
        _step("Check and serve", "Confirm the beans are completely soft and the curry is piping hot. Adjust seasoning and serve.", "🍽️"),
    ],
    "REC_UPMA": [
        _step("Prepare the ingredients", "Measure the semolina. Chop the onion and tomato. Keep water ready beside the stove.", "🥣"),
        _step("Toast the semolina", "Dry-toast the semolina in a pan over low heat, stirring constantly until fragrant. Transfer it to a plate.", "🌾"),
        _step("Cook the vegetables", "Warm a little ghee or oil. Cook the onion until soft, add tomato and cook until it softens, then add water and bring it to a boil.", "🫕", 120),
        _step("Stir in the semolina", "Lower the heat. Add semolina slowly while stirring continuously to prevent lumps. Cover and cook until thick and tender.", "🍲", 180),
        _step("Check and serve", "Turn off the heat, rest briefly, and serve while hot.", "🍽️"),
    ],
    "REC_POHA": [
        _step("Rinse the poha", "Place the flattened rice in a sieve and rinse briefly. Let it drain until soft but not mushy.", "🌾"),
        _step("Prepare the vegetables", "Chop the potato and onion. If using raw potato, cook it in a covered pan with a splash of water until tender.", "🥔", 300),
        _step("Cook the base", "Warm oil in a pan. Cook the onion until soft, add the potato and any available spices, and stir until fragrant.", "🫕"),
        _step("Finish the poha", "Fold in the drained poha gently. Cover on low heat until hot throughout, then check seasoning and serve.", "🍲", 120),
    ],
    "REC_METHI_THEPLA": [
        _step("Prepare the dough", "Rinse and finely chop the fenugreek leaves. Mix with whole wheat flour, yogurt, salt and water a little at a time to make a soft dough.", "🌿"),
        _step("Rest and shape", "Rest the dough briefly. Divide it into balls and roll each into a thin circle on a lightly floured surface.", "🫓", 300),
        _step("Cook the theplas", "Heat a tawa over medium heat. Cook each thepla on both sides, turning until brown spots appear. Brush lightly with oil if desired.", "🔥"),
        _step("Check and serve", "Make sure each thepla is cooked through. Serve warm.", "🍽️"),
    ],
    "REC_MASOOR_DAL": [
        _step("Rinse the lentils", "Rinse the red lentils until the water runs mostly clear. Chop the onion and tomato.", "🫘"),
        _step("Simmer until soft", "Add lentils and water to a pot. Simmer, stirring occasionally, until the lentils are soft and beginning to break down.", "🍲", 900),
        _step("Add the masala", "In a small pan, warm oil and cook onion, garlic and tomato until soft. Stir this into the lentils and simmer briefly.", "🫕", 180),
        _step("Check and serve", "Check the lentils are fully tender and the dal is piping hot. Adjust seasoning and serve.", "🍽️"),
    ],
    "REC_ALOO_GOBI": [
        _step("Prepare the vegetables", "Wash the potato and cauliflower. Cut them into even, bite-sized pieces and chop the onion and tomato.", "🥔"),
        _step("Start the masala", "Warm oil in a wide pan. Cook the onion until soft, then add tomato and available spices until fragrant.", "🧅"),
        _step("Cook the vegetables", "Add potato, cauliflower and a small splash of water. Cover and cook over medium-low heat, stirring occasionally, until both are tender.", "🥦", 900),
        _step("Check and serve", "Check the thickest potato pieces are fully cooked. Adjust seasoning and serve hot.", "🍽️"),
    ],
    "REC_CHANA_MASALA": [
        _step("Soak the chickpeas", "Rinse the chickpeas and soak in plenty of water for at least 8 hours. Drain and discard the soaking water.", "🫘"),
        _step("Cook until tender", "Pressure-cook the soaked chickpeas with fresh water according to your cooker instructions until completely tender.", "♨️", 1200),
        _step("Make the masala", "Warm oil in a pan. Cook chopped onion until soft, then add ginger, garlic and tomato. Stir until thick and well cooked.", "🧅"),
        _step("Simmer together", "Add the cooked chickpeas and some cooking liquid. Simmer gently, stirring occasionally, until the sauce coats the chickpeas.", "🍲", 600),
        _step("Check and serve", "Check the chickpeas are fully tender and the curry is piping hot. Adjust seasoning and serve.", "🍽️"),
    ],
    "REC_BAINGAN_BHARTA": [
        _step("Roast the eggplant", "Wash and dry the eggplant. Roast it over a flame or in a hot oven, turning carefully, until the skin is charred and the inside is completely soft.", "🍆", 1200),
        _step("Peel and mash", "Let the eggplant cool enough to handle. Peel away the charred skin and mash the cooked flesh. Discard the stem and skin.", "🥣"),
        _step("Cook the masala", "Warm oil in a pan. Cook onion until soft, then add garlic and tomato. Stir until the tomato breaks down.", "🫕", 300),
        _step("Finish and serve", "Fold in the mashed eggplant and cook until steaming hot. Adjust seasoning and serve.", "🍲", 300),
    ],
    "REC_JOWAR_BHAKRI": [
        _step("Make the dough", "Place jowar flour in a bowl. Carefully mix in hot water a little at a time with a spoon, then knead into a soft dough once cool enough to handle.", "🌾"),
        _step("Shape the bhakri", "Pat a dough ball into a flat round between your hands or on a floured surface. Patch any cracks gently with damp fingers.", "🫓"),
        _step("Cook on the tawa", "Cook on a hot tawa. Turn when the surface dries, then cook both sides until done. Use care around steam and hot cookware.", "🔥"),
        _step("Prepare the garlic chutney", "Crush the garlic with salt and a little water or oil to make a small chutney. Serve with the hot bhakri.", "🧄"),
    ],
    "REC_VEG_PULAO": [
        _step("Rinse and prepare", "Rinse the basmati rice until the water is mostly clear. Chop the onion and tomato, and prepare any vegetables you have chosen to add.", "🍚"),
        _step("Cook the aromatics", "Warm oil or ghee in a pot. Cook onion until soft, then add available whole spices and tomato.", "🫕"),
        _step("Simmer the rice", "Stir in the rice and water using the ratio on the rice package. Cover and cook on low heat until the rice is tender and water is absorbed.", "🍲", 1200),
        _step("Rest and serve", "Turn off the heat and rest covered for a few minutes. Fluff gently and serve hot.", "🍽️", 300),
    ],
    "REC_KHICHDI": [
        _step("Rinse the grains", "Rinse the moong dal and rice together until the water is mostly clear. Drain well.", "🌾"),
        _step("Cook until soft", "Add dal, rice and water to a pot or pressure cooker. Cook until both are very soft, following the appliance instructions.", "🍲", 1200),
        _step("Finish the khichdi", "Stir in ghee and salt. Add hot water if needed to reach a soft, porridge-like consistency.", "🥣"),
        _step("Check and serve", "Check the grains are fully cooked and serve hot.", "🍽️"),
    ],
    "REC_SAMBAR": [
        _step("Cook the dal", "Rinse the toor dal and cook it with water until completely soft. Mash lightly.", "🫘"),
        _step("Prepare the vegetables", "Wash and cut the vegetables into even pieces. Soak tamarind in warm water and squeeze out the pulp.", "🥕"),
        _step("Simmer the vegetables", "Cook the vegetables with water until tender. Add tamarind pulp and sambar powder if available.", "🍲", 600),
        _step("Combine with dal", "Stir the cooked dal into the vegetables. Simmer gently until the flavors combine and the sambar is hot throughout.", "🫕", 300),
        _step("Check and serve", "Check all vegetables are tender. Adjust seasoning and serve hot.", "🍽️"),
    ],
    "REC_PANEER_BHURJI": [
        _step("Prepare the ingredients", "Crumble the paneer. Chop the onion and tomato, and mince the ginger and garlic.", "🧀"),
        _step("Cook the aromatics", "Warm oil in a pan. Cook onion until soft, then add ginger and garlic and stir until fragrant.", "🧅"),
        _step("Cook the bhurji", "Add tomato and cook until soft. Fold in the crumbled paneer and cook gently until hot throughout.", "🍳", 180),
        _step("Check and serve", "Adjust seasoning and serve while hot.", "🍽️"),
    ],
}


def _translate_guide(steps: List[Dict[str, Any]], language: str) -> List[Dict[str, Any]]:
    base_url = os.getenv("OLLAMA_BASE_URL", "").rstrip("/")
    if language == "en" or not base_url:
        return steps

    language_name = {"hi": "Hindi", "mr": "Marathi"}[language]
    payload = {
        "steps": [{"title": step["title"], "instruction": step["instruction"]} for step in steps]
    }
    try:
        response = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
                "format": "json",
                "stream": False,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            f"Translate only the title and instruction fields into {language_name}. "
                            "Preserve the JSON structure, quantities, units, safety warnings, order, and number of steps. "
                            "Return JSON only with a steps array."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                "options": {"temperature": 0.1, "num_predict": 1600},
            },
            timeout=180,
        )
        response.raise_for_status()
        translated = json.loads(response.json()["message"]["content"]).get("steps", [])
        if len(translated) != len(steps):
            return steps
        return [
            {
                **step,
                "title": str(translated[index].get("title", step["title"])),
                "instruction": str(translated[index].get("instruction", step["instruction"])),
            }
            for index, step in enumerate(steps)
        ]
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        logger.warning("Cooking guide translation unavailable; using English: %s", exc)
        return steps


def create_cooking_guide(recipe_id: str, servings: int | None, language: str) -> Dict[str, Any]:
    recipes = gnn_ranker._load_recipes("Any")
    recipe = next((item for item in recipes if item.get("id") == recipe_id), None)
    if recipe is None:
        raise KeyError(f"Recipe '{recipe_id}' was not found.")

    steps = COOKING_STEPS.get(recipe_id)
    if not steps:
        raise KeyError(f"No guided cooking steps are available for '{recipe.get('title', recipe_id)}'.")

    base_servings = max(int(recipe.get("servings", 1) or 1), 1)
    target_servings = servings or base_servings
    quantity_scale = target_servings / base_servings
    ingredients = [
        {
            "ingredientId": item.get("id"),
            "name": item["name"],
            "quantity": round(float(item.get("quantity", 0) or 0) * quantity_scale, 2),
            "unit": item.get("unit") or "g",
        }
        for item in recipe.get("ingredients", [])
    ]
    translated_steps = _translate_guide(steps, language)
    guide_language = language if translated_steps is not steps or language == "en" else "en"

    return {
        "recipeId": recipe_id,
        "title": recipe.get("title", recipe_id),
        "servings": target_servings,
        "baseServings": base_servings,
        "prepTimeMinutes": recipe.get("prepTimeMinutes", 0),
        "cookTimeMinutes": recipe.get("cookTimeMinutes", 0),
        "ingredients": ingredients,
        "steps": translated_steps,
        "language": guide_language,
        "preparationNote": (
            "Recipe-specific salt, cooking oil, and spices are assumed only when listed as available; "
            "they are not deducted unless present in the recipe ingredient list."
        ),
    }