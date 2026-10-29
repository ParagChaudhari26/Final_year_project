"""
RAG (Retrieval-Augmented Generation) Food Coaching Assistant
Uses TF-IDF + Cosine Similarity over a curated Indian food/nutrition knowledge base.
Falls back gracefully if scikit-learn is unavailable.
"""
import logging
import json
import os
import re
from typing import List, Dict, Any, Tuple, Optional

import requests

logger = logging.getLogger("RAGAssistant")

# ─────────────────────────────────────────────────────────────────────────────
# KNOWLEDGE BASE  (50+ facts about Indian food, nutrition, Ayurveda)
# ─────────────────────────────────────────────────────────────────────────────
KNOWLEDGE_BASE: List[Dict[str, str]] = [
    # Ayurvedic Principles
    {"id":"AY001","topic":"Ayurveda","text":"Viruddha Ahaar means incompatible food combinations. According to Charaka Samhita, consuming milk with fish creates Veerya Viruddha (potency conflict) as milk is Sheeta (cooling) and fish is Ushna (heating).","category":"Ayurveda"},
    {"id":"AY002","topic":"Ayurveda","text":"Matra Viruddha is a dose-related incompatibility. Honey and ghee in equal quantities by weight create toxic ama compounds in the body according to Ashtanga Hridayam 7.47.","category":"Ayurveda"},
    {"id":"AY003","topic":"Ayurveda","text":"Samyoga Viruddha refers to combinations that create unwanted chemical reactions. Milk and citrus fruits curdle the milk proteins causing heavy, hard-to-digest ama.","category":"Ayurveda"},
    {"id":"AY004","topic":"Ayurveda","text":"Kala Viruddha means wrong time of consumption. Yogurt (curd) should not be consumed at night as it aggravates Kapha and can cause respiratory issues.","category":"Ayurveda"},
    {"id":"AY005","topic":"Ayurveda","text":"Heating honey above 40°C (104°F) destroys its medicinal properties and creates toxic compounds. Always add honey to lukewarm water or food, never hot.","category":"Ayurveda"},
    {"id":"AY006","topic":"Ayurveda","text":"Ghee is considered Sattvic and aids digestion in Ayurveda. 1-2 tsp of ghee daily improves fat metabolism, lubricates joints and aids nutrient absorption.","category":"Ayurveda"},
    {"id":"AY007","topic":"Ayurveda","text":"Triphala (three fruits: Amla, Haritaki, Vibhitaki) is recommended in Ayurveda for digestion, detoxification and as a Rasayana (rejuvenator).","category":"Ayurveda"},
    {"id":"AY008","topic":"Ayurveda","text":"Agni (digestive fire) is central to Ayurvedic nutrition. Ginger, cumin and black pepper are Agni-stimulating spices that improve digestion and nutrient absorption.","category":"Ayurveda"},
    {"id":"AY009","topic":"Ayurveda","text":"Kapha dosha is balanced by warm, light, dry and spicy foods. Avoid heavy, oily and cold foods if you have Kapha constitution.","category":"Ayurveda"},
    {"id":"AY010","topic":"Ayurveda","text":"Vata dosha is balanced by warm, moist, slightly oily and grounding foods like sesame oil, warm milk, root vegetables and cooked grains.","category":"Ayurveda"},
    {"id":"AY011","topic":"Ayurveda","text":"Pitta dosha is calmed by cooling, sweet and bitter foods. Cucumber, coconut water, mint and coriander are excellent Pitta-pacifying foods.","category":"Ayurveda"},
    {"id":"AY012","topic":"Ayurveda","text":"Eating in the right order matters: Start with sweet (Madhura), then sour-salt (Amla-Lavana), then pungent-bitter (Katu-Tikta). This stimulates digestive enzymes progressively.","category":"Ayurveda"},

    # IFCT 2017 and Nutrition
    {"id":"NUT001","topic":"Nutrition","text":"IFCT 2017 (Indian Food Composition Tables) published by ICMR-NIN provides nutritional data for 528 Indian foods. It is the gold standard for Indian food nutrition analysis.","category":"Nutrition Science"},
    {"id":"NUT002","topic":"Nutrition","text":"Spinach (Palak) per 100g contains 26 kcal, 2g protein, 1.1mg iron, 73mg calcium, 28mg Vitamin C. It is one of the best plant-based iron sources in Indian cooking.","category":"Nutrition Science"},
    {"id":"NUT003","topic":"Nutrition","text":"Toor Dal (Pigeon Pea) per 100g (raw) contains 335 kcal, 22.3g protein, 5.3mg iron, 15g dietary fibre. It is a complete protein source when combined with rice.","category":"Nutrition Science"},
    {"id":"NUT004","topic":"Nutrition","text":"Masoor Dal (Red Lentils) is among the richest plant iron sources with 7.6mg per 100g. Consuming with Vitamin C-rich foods like tomato increases iron absorption by up to 3x.","category":"Nutrition Science"},
    {"id":"NUT005","topic":"Nutrition","text":"Jowar (Sorghum) is gluten-free and contains 349 kcal, 10.4g protein, 4.1mg iron per 100g. Its high fiber (9.7g) makes it excellent for diabetes management.","category":"Nutrition Science"},
    {"id":"NUT006","topic":"Nutrition","text":"Fenugreek (Methi) leaves contain soluble fiber (galactomannan) that helps regulate blood glucose. Regular consumption can reduce fasting blood sugar by 10-15%.","category":"Nutrition Science"},
    {"id":"NUT007","topic":"Nutrition","text":"Chickpeas (Chana) have a low glycemic index of 33 and provide 17.1g protein and 17g fiber per 100g. Excellent for diabetes, weight management and cardiovascular health.","category":"Nutrition Science"},
    {"id":"NUT008","topic":"Nutrition","text":"Paneer provides 18.3g protein and 208mg calcium per 100g. It is one of the best calcium sources for vegetarians and supports bone density and muscle repair.","category":"Nutrition Science"},
    {"id":"NUT009","topic":"Nutrition","text":"Cooking retention factors: Boiling reduces Vitamin C by 40-50%. Sauteing retains 75% Vitamin C. Raw consumption gives 100% Vitamin C from vegetables.","category":"Nutrition Science"},
    {"id":"NUT010","topic":"Nutrition","text":"Iron from plant sources (non-heme iron) has lower bioavailability (5-12%) compared to meat iron (15-35%). Combining with Vitamin C dramatically increases non-heme iron absorption.","category":"Nutrition Science"},
    {"id":"NUT011","topic":"Nutrition","text":"ICMR daily protein requirement for adult Indians: 0.8-1.0g per kg body weight. Active individuals need 1.2-1.6g/kg. Plant-protein meals require 10-15% more for bioavailability.","category":"Nutrition Science"},
    {"id":"NUT012","topic":"Nutrition","text":"Dietary fiber recommendations: 25-30g per day for adults. High fiber foods include rajma (15.2g/100g), jowar (9.7g/100g), chickpeas (17g/100g) and whole wheat (11.2g/100g).","category":"Nutrition Science"},

    # Indian Foods and Health
    {"id":"IND001","topic":"Indian Food","text":"Palak Paneer is an iron + calcium powerhouse. The Vitamin C in tomatoes and onions in the gravy helps absorb the non-heme iron from spinach efficiently.","category":"Indian Food"},
    {"id":"IND002","topic":"Indian Food","text":"Rajma (Kidney Beans) with rice creates a complete protein combination as their amino acid profiles complement each other perfectly.","category":"Indian Food"},
    {"id":"IND003","topic":"Indian Food","text":"Khichdi (rice + moong dal) is the most digestive Indian meal. Ayurveda recommends it during illness, fasting recovery and for gut health maintenance.","category":"Indian Food"},
    {"id":"IND004","topic":"Indian Food","text":"Poha (flattened rice) is lower in calories than regular rice (350 vs 345 kcal/100g) but has 2.7mg iron per 100g making it a good breakfast for iron deficiency.","category":"Indian Food"},
    {"id":"IND005","topic":"Indian Food","text":"Sambar made with toor dal and vegetables like drumstick (Moringa) is a nutritional powerhouse with protein, iron, beta-carotene and anti-inflammatory compounds.","category":"Indian Food"},
    {"id":"IND006","topic":"Indian Food","text":"Methi Thepla combines whole wheat, fenugreek and yogurt. It is rich in fiber, protein and B-vitamins. Excellent as a blood-sugar-friendly meal for diabetics.","category":"Indian Food"},
    {"id":"IND007","topic":"Indian Food","text":"Turmeric (Haldi) contains curcumin which has potent anti-inflammatory properties. Adding black pepper increases curcumin absorption by 2000%. Use in cooking daily.","category":"Indian Food"},
    {"id":"IND008","topic":"Indian Food","text":"Jowar Bhakri is a traditional Maharashtrian flatbread that is naturally gluten-free, high in fiber and antioxidants. Ideal for people with celiac disease or gluten sensitivity.","category":"Indian Food"},
    {"id":"IND009","topic":"Indian Food","text":"Indian cooking with iron vessels (kadai/tawa) naturally fortifies food with iron. Cooking acidic foods like tomato in iron pans can increase iron content by 80-100%.","category":"Indian Food"},
    {"id":"IND010","topic":"Indian Food","text":"Ghee made from grass-fed cows contains Conjugated Linoleic Acid (CLA) and butyrate which are beneficial for gut health and inflammation reduction.","category":"Indian Food"},

    # Health Conditions and Diet
    {"id":"HLT001","topic":"Health","text":"For anemia (iron deficiency): Eat masoor dal, rajma, jowar bhakri, palak paneer. Consume Vitamin C (amla, lemon) with iron-rich foods. Avoid tea and coffee with meals as tannins block iron absorption.","category":"Health Conditions"},
    {"id":"HLT002","topic":"Health","text":"For diabetes management: Low glycemic index foods include jowar roti, rajma, moong dal khichdi and chickpeas. Avoid refined carbs, white rice in excess, and sugary beverages.","category":"Health Conditions"},
    {"id":"HLT003","topic":"Health","text":"For cardiovascular health: Focus on soluble fiber (oats, rajma), omega-3 rich foods (flaxseed, walnuts), and reduce sodium to under 2300mg/day. Dal tadka and sambar are heart-healthy choices.","category":"Health Conditions"},
    {"id":"HLT004","topic":"Health","text":"For weight management: High protein, high fiber meals increase satiety. Chana masala, dal tadka and vegetable curries with minimal oil are excellent weight-management meals.","category":"Health Conditions"},
    {"id":"HLT005","topic":"Health","text":"For bone health: Calcium-rich foods include paneer (208mg/100g), yogurt (149mg/100g), fenugreek leaves (395mg/100g) and sesame seeds (975mg/100g). Vitamin D aids calcium absorption.","category":"Health Conditions"},
    {"id":"HLT006","topic":"Health","text":"For digestive health: Khichdi, upma, and sambar are easily digestible. Probiotic-rich foods like yogurt (when fresh) support gut microbiome. Avoid combining incompatible foods (Viruddha Ahaar).","category":"Health Conditions"},
    {"id":"HLT007","topic":"Health","text":"For immunity: Vitamin C rich foods (amla, orange, tomato), zinc-rich foods (chickpeas, rajma) and anti-inflammatory spices (turmeric, ginger) boost immune function.","category":"Health Conditions"},

    # Meal Planning
    {"id":"MP001","topic":"Meal Planning","text":"A balanced Indian thali should include: 1 dal (protein), 1 sabzi (vegetables), roti/rice (carbs), yogurt (probiotics), salad (fiber) and a small sweet if desired.","category":"Meal Planning"},
    {"id":"MP002","topic":"Meal Planning","text":"The 1:2:3 Indian meal ratio recommended by ICMR: 1 part protein (dal/paneer), 2 parts vegetables, 3 parts complex carbohydrates (roti/brown rice).","category":"Meal Planning"},
    {"id":"MP003","topic":"Meal Planning","text":"Meal timing in Ayurveda: Breakfast 7-9am (Kapha time), Lunch 12-1pm (Pitta peak for digestion), Dinner before 7pm (allow 2-3 hours before sleep). Avoid heavy late-night meals.","category":"Meal Planning"},
    {"id":"MP004","topic":"Meal Planning","text":"Batch cooking tip: Cook large batches of dal, rajma or chickpeas and refrigerate for 3-4 days. This makes healthy meal prep faster and ensures protein availability daily.","category":"Meal Planning"},
    {"id":"MP005","topic":"Meal Planning","text":"For 7-day balanced meal planning: Rotate 3 protein sources (dal, paneer, legumes), 4 vegetables, 2 grains. This ensures micronutrient diversity and prevents boredom.","category":"Meal Planning"},

    # Pantry Management
    {"id":"PAN001","topic":"Pantry","text":"Essential Indian pantry staples: Toor dal, masoor dal, moong dal, rice, wheat flour, jowar flour, turmeric, cumin, coriander, mustard seeds, asafoetida (hing).","category":"Pantry"},
    {"id":"PAN002","topic":"Pantry","text":"Pantry shelf life: Whole grains (1 year), dal (1 year), wheat flour (3-6 months), fresh vegetables (3-7 days). Store in airtight containers away from heat and moisture.","category":"Pantry"},
    {"id":"PAN003","topic":"Pantry","text":"Spices lose potency over time. Replace whole spices every 2-3 years, ground spices every 1-2 years. Store away from light and heat. Fresh spices improve both flavor and medicinal value.","category":"Pantry"},
]

# ─────────────────────────────────────────────────────────────────────────────
# Response templates for common query types
# ─────────────────────────────────────────────────────────────────────────────
RESPONSE_TEMPLATES = {
    "greeting": "Namaste! 🙏 I'm your FoodCoach AI assistant. I can help you with Indian nutrition, Ayurvedic food principles, recipe suggestions, and meal planning. What would you like to know today?",
    "not_found": "I don't have specific information about that in my knowledge base. I can best help with Indian food nutrition, Ayurvedic compatibility, recipe suggestions, and meal planning for health conditions. Could you rephrase your question?",
}

FOLLOW_UP_SUGGESTIONS = {
    "Ayurveda": ["What are other Viruddha Ahaar combinations?", "Which foods balance Vata dosha?", "Tell me about Agni in Ayurveda"],
    "Nutrition Science": ["How much protein do I need daily?", "What are the best plant-based iron sources?", "How does cooking affect nutrients?"],
    "Indian Food": ["What is a complete Indian meal?", "Which Indian breakfast is healthiest?", "Tell me about jowar flour benefits"],
    "Health Conditions": ["Best foods for diabetes?", "How to improve iron levels naturally?", "Heart-healthy Indian meals?"],
    "Meal Planning": ["Create a 7-day meal plan for me", "What should I eat for breakfast?", "How to plan meals for weight loss?"],
    "Pantry": ["What are essential Indian pantry staples?", "How long do dals last?", "How to store spices properly?"],
}


class RAGAssistant:
    """
    TF-IDF based Retrieval-Augmented Generation assistant for food coaching.
    Retrieves relevant knowledge and constructs contextual responses.
    """

    def __init__(self):
        self._vectorizer = None
        self._kb_vectors = None
        self._kb_texts = [doc["text"] for doc in KNOWLEDGE_BASE]
        self._ollama_url = os.getenv("OLLAMA_BASE_URL", "").rstrip("/")
        self._ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        self._build_index()

    def _ollama_chat(self, messages: List[Dict[str, str]]) -> str:
        response = requests.post(
            f"{self._ollama_url}/api/chat",
            json={
                "model": self._ollama_model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 750},
            },
            timeout=180,
        )
        response.raise_for_status()
        msg = response.json().get("message", {})
        content = msg.get("content", "").strip()
        if not content and msg.get("thinking"):
            content = msg.get("thinking").strip()
        return content

    def _english_search_query(self, message: str, language: str) -> str:
        if language not in {"hi", "mr"} and not re.search(r"[\u0900-\u097f]", message):
            return message
        try:
            return self._ollama_chat([
                {
                    "role": "system",
                    "content": "Translate the user's question into concise English search keywords. Return only the keywords.",
                },
                {"role": "user", "content": message},
            ]) or message
        except (requests.RequestException, KeyError, ValueError):
            return message

    def _generated_response(
        self,
        message: str,
        history: List[Dict[str, str]],
        language: str,
        docs: List[Tuple[Dict[str, str], float]],
        user_context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        language_names = {"en": "English", "hi": "Hindi", "mr": "Marathi"}
        reply_language = language if language in language_names else (
            "hi" if re.search(r"[\u0900-\u097f]", message) else "en"
        )
        language_instruction = (
            f"Reply in {language_names[reply_language]} and use its native script."
            if reply_language in language_names
            else "Reply in the same language and script as the user's latest message."
        )
        source_context = "\n".join(
            f"[{doc['id']}] ({doc['category']}) {doc['text']}"
            for doc, _ in docs
        ) or "No relevant knowledge-base facts were found."
        messages = [{
            "role": "system",
            "content": (
                "You are FoodCoach, a friendly Indian food and meal-planning assistant. "
                f"{language_instruction} Use the supplied FoodCoach knowledge facts for nutrition claims; "
                "do not invent unsupported amounts or medical advice. If the facts do not answer the question, "
                "say what is missing. Keep answers conversational and concise. Do not diagnose or replace a clinician. "
                "Cite used fact IDs in square brackets. Avoid recommending listed allergens. "
                "Use the pantry and recipe data only when relevant to the user's request.\n\n"
                "User profile and pantry context:\n" + json.dumps(user_context or {}, ensure_ascii=False) +
                "\n\nFoodCoach knowledge facts:\n" + source_context
            ),
        }]
        messages.extend(
            {"role": item["role"], "content": item["content"]}
            for item in history[-6:]
            if item.get("role") in {"user", "assistant"}
        )
        messages.append({"role": "user", "content": message})
        response = self._ollama_chat(messages)
        return {
            "response": response,
            "sources": [f"{doc['topic']} — {doc['id']}" for doc, _ in docs[:3]],
            "suggestions": [],
            "confidence": round(docs[0][1], 2) if docs else 0.0,
            "provider": "ollama",
            "language": reply_language,
        }

    def _build_index(self):
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            self._vectorizer = TfidfVectorizer(
                ngram_range=(1, 2),
                max_features=5000,
                stop_words="english"
            )
            self._kb_vectors = self._vectorizer.fit_transform(self._kb_texts)
            self._cosine_similarity = cosine_similarity
            logger.info(f"RAG index built with {len(KNOWLEDGE_BASE)} documents")
        except ImportError:
            logger.warning("scikit-learn not available; RAG will use keyword fallback")
            self._vectorizer = None

    def _retrieve(self, query: str, top_k: int = 4) -> List[Tuple[Dict[str, str], float]]:
        """Retrieve top-k relevant documents for the query."""
        if self._vectorizer is None:
            return self._keyword_retrieve(query, top_k)

        query_vec = self._vectorizer.transform([query])
        scores = self._cosine_similarity(query_vec, self._kb_vectors).flatten()
        top_indices = scores.argsort()[-top_k:][::-1]
        return [(KNOWLEDGE_BASE[i], float(scores[i])) for i in top_indices if scores[i] > 0.05]

    def _keyword_retrieve(self, query: str, top_k: int) -> List[Tuple[Dict[str, str], float]]:
        """Simple keyword-based fallback retrieval."""
        query_words = set(re.findall(r'\w+', query.lower()))
        scored = []
        for doc in KNOWLEDGE_BASE:
            doc_words = set(re.findall(r'\w+', doc["text"].lower()))
            overlap = len(query_words & doc_words)
            if overlap > 0:
                scored.append((doc, overlap / len(query_words)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def _build_response(self, query: str, docs: List[Tuple[Dict, float]]) -> Dict[str, Any]:
        """Construct a response from retrieved documents."""
        if not docs:
            return {
                "response": RESPONSE_TEMPLATES["not_found"],
                "sources": [],
                "suggestions": ["Tell me about Indian nutrition", "What is Viruddha Ahaar?"],
                "confidence": 0.0
            }

        # Combine retrieved facts into a coherent response
        top_doc, top_score = docs[0]
        category = top_doc.get("category", "General")

        # Build response by combining top facts
        facts = [doc["text"] for doc, score in docs if score > 0.05]

        if len(facts) == 1:
            response_body = facts[0]
        else:
            response_body = f"{facts[0]}\n\n**Additional context:** {facts[1]}"
            if len(facts) > 2:
                response_body += f"\n\n**Also note:** {facts[2]}"

        # Add a friendly contextual header
        query_lower = query.lower()
        if any(w in query_lower for w in ["hi", "hello", "hey", "namaste"]):
            return {
                "response": RESPONSE_TEMPLATES["greeting"],
                "sources": [],
                "suggestions": ["What can you help me with?", "Tell me about Viruddha Ahaar", "Best foods for iron deficiency?"],
                "confidence": 1.0
            }

        full_response = response_body

        # Get follow-up suggestions
        suggestions = FOLLOW_UP_SUGGESTIONS.get(
            category,
            ["Tell me more about Indian nutrition", "What is Viruddha Ahaar?", "Best foods for my health condition?"]
        )

        sources = [f"{doc.get('topic', 'General')} — {doc.get('id', '')}" for doc, _ in docs[:3]]

        return {
            "response": full_response,
            "sources": sources,
            "suggestions": suggestions[:3],
            "confidence": round(top_score, 2)
        }

    def chat(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        language: str = "auto",
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a grounded reply, using Ollama when configured."""
        if not message or not message.strip():
            return {
                "response": RESPONSE_TEMPLATES["greeting"],
                "sources": [],
                "suggestions": ["What is Viruddha Ahaar?", "Best foods for iron deficiency?", "How to plan a balanced meal?"],
                "confidence": 1.0
            }

        search_query = self._english_search_query(message, language)
        docs = self._retrieve(search_query, top_k=4)
        if self._ollama_url:
            try:
                return self._generated_response(message, conversation_history or [], language, docs, user_context)
            except (requests.RequestException, KeyError, ValueError) as exc:
                logger.warning("Ollama chat unavailable; using RAG fallback: %s", exc)

        fallback = self._build_response(message, docs)
        fallback["provider"] = "rag_fallback"
        return fallback

    def get_nutrition_advice(self, health_conditions: List[str]) -> str:
        """Generate nutritional advice based on health conditions."""
        condition_queries = {
            "HC_ANEMIA": "iron deficiency anemia plant foods",
            "HC_DIABETES": "diabetes blood sugar glycemic index",
            "HC_CARDIAC": "cardiovascular heart health sodium fiber",
            "HC_OBESITY": "weight management protein fiber satiety",
            "HC_BONE": "calcium bone health paneer dairy",
            "HC_DIGESTION": "digestive health gut fiber probiotic",
            "HC_IMMUNITY": "immunity vitamin C zinc immune boost",
        }
        advice_parts = []
        for cond in health_conditions:
            query = condition_queries.get(cond, "healthy eating Indian food")
            docs = self._retrieve(query, top_k=2)
            if docs:
                advice_parts.append(docs[0][0]["text"])

        return " | ".join(advice_parts) if advice_parts else "Eat a balanced diet with diverse whole foods."


rag_assistant = RAGAssistant()
