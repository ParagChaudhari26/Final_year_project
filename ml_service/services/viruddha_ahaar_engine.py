"""
Viruddha Ahaar (Ayurvedic Food Incompatibility) Engine
Implements rules from Charaka Samhita and Ashtanga Hridayam.
Enriched with Neo4j graph data when available.
"""
import logging
from typing import List, Dict, Any, Optional, Set, Tuple

logger = logging.getLogger("ViruddhaEngine")

# ── Static rule table (Ayurvedic texts) ──────────────────────────────────────
# Each rule: (ingredient_set_or_pair, type, severity, reason, ayurvedic_ref)
# ingredient_set uses lowercase names for matching

VIRUDDHA_RULES: List[Dict[str, Any]] = [
    {
        "ingredients": {"milk", "orange"}, "also": {"milk", "lemon"},
        "type": "Samyoga Viruddha",
        "severity": "High",
        "reason": "Citrus acids curdle milk proteins, forming heavy digestive toxins (ama).",
        "ayurvedicText": "Charaka Samhita 26.83",
        "recommendations": ["Use coconut milk instead", "Consume citrus and milk 2 hours apart"]
    },
    {
        "ingredients": {"milk", "fish"},
        "type": "Veerya Viruddha",
        "severity": "High",
        "reason": "Sheeta (cooling) potency of milk clashes with Ushna (heating) potency of fish, disrupting digestive fire.",
        "ayurvedicText": "Charaka Samhita 26.84",
        "recommendations": ["Never consume fish with dairy", "Use coconut milk in fish curries"]
    },
    {
        "ingredients": {"honey", "ghee"},
        "type": "Matra Viruddha",
        "severity": "High",
        "condition": "equal_weight_ratio",
        "reason": "Equal quantities of honey and ghee by weight create toxic ama compounds that are difficult to digest.",
        "ayurvedicText": "Ashtanga Hridayam 7.47",
        "recommendations": ["Use unequal quantities (e.g., 2:1 ratio)", "Avoid combining altogether"]
    },
    {
        "ingredients": {"milk", "banana"},
        "type": "Samyoga Viruddha",
        "severity": "Medium",
        "reason": "Milk and banana combination slows digestion, creates heaviness and can disrupt gut flora.",
        "ayurvedicText": "Charaka Samhita 26.86",
        "recommendations": ["Wait 30 minutes between eating banana and drinking milk", "Use ripe banana with cardamom separately"]
    },
    {
        "ingredients": {"fish", "yogurt"},
        "also": {"fish", "curd"},
        "type": "Veerya Viruddha",
        "severity": "High",
        "reason": "Fish (Ushna veerya) and yogurt (Sheeta veerya) oppose each other, producing severe digestive disturbance.",
        "ayurvedicText": "Charaka Samhita 26.84",
        "recommendations": ["Never combine fish and dairy products", "Use lime juice as a marinade alternative"]
    },
    {
        "ingredients": {"tamarind", "milk"},
        "type": "Samyoga Viruddha",
        "severity": "Medium",
        "reason": "Tamarind's acidity curdles milk and causes digestive distress.",
        "ayurvedicText": "Charaka Samhita 26.85",
        "recommendations": ["Use tamarind in non-dairy dishes only", "Substitute with dry mango powder in milk-based curries"]
    },
    {
        "ingredients": {"radish", "milk"},
        "type": "Samyoga Viruddha",
        "severity": "Medium",
        "reason": "Radish with milk creates incompatible rasas leading to skin disorders and digestive issues.",
        "ayurvedicText": "Charaka Samhita 26.87",
        "recommendations": ["Avoid radish raita", "Consume radish with plain water or ghee"]
    },
    {
        "ingredients": {"egg", "milk"},
        "type": "Samyoga Viruddha",
        "severity": "Low",
        "reason": "Both are heavy to digest; combined they significantly slow metabolism and digestion.",
        "ayurvedicText": "Ashtanga Hridayam 7.48",
        "recommendations": ["Avoid mixing eggs in milk-based desserts", "Separate by at least 1 hour"]
    },
    {
        "ingredients": {"chicken", "milk"},
        "type": "Veerya Viruddha",
        "severity": "High",
        "reason": "Chicken (Ushna) and milk (Sheeta) have opposing potencies causing toxic ama formation.",
        "ayurvedicText": "Charaka Samhita 26.84",
        "recommendations": ["Use water or broth in chicken dishes", "Avoid butter chicken with milk base — use cream in moderation only"]
    },
    {
        "ingredients": {"mango", "yogurt"},
        "also": {"mango", "curd"},
        "type": "Samyoga Viruddha",
        "severity": "Medium",
        "reason": "Mango and yogurt together can cause skin problems and digestive fermentation.",
        "ayurvedicText": "Charaka Samhita 26.89",
        "recommendations": ["Eat mango alone", "Make mango lassi only in small quantities occasionally"]
    },
    {
        "ingredients": {"hot water", "honey"},
        "type": "Kala Viruddha",
        "severity": "Medium",
        "reason": "Honey heated above 40°C (104°F) becomes toxic and is classified as a potent ama-forming agent.",
        "ayurvedicText": "Ashtanga Hridayam 7.45",
        "recommendations": ["Always add honey to lukewarm (not hot) liquids", "Never cook with honey; add at end"]
    }
]

# Aliases for flexible matching
INGREDIENT_ALIASES: Dict[str, Set[str]] = {
    "milk": {"milk", "dairy milk", "whole milk", "skim milk", "full cream milk"},
    "yogurt": {"yogurt", "curd", "dahi", "greek yogurt"},
    "orange": {"orange", "citrus", "lemon", "lime", "grapefruit", "nimbu"},
    "fish": {"fish", "salmon", "tuna", "rohu", "catla", "hilsa", "mackerel"},
    "honey": {"honey", "madhu"},
    "ghee": {"ghee", "clarified butter"},
    "banana": {"banana", "kela", "plantain"},
    "tamarind": {"tamarind", "imli"},
    "radish": {"radish", "mooli", "daikon"},
    "egg": {"egg", "egg white", "egg yolk", "whole egg"},
    "chicken": {"chicken", "murgh", "poultry"},
    "mango": {"mango", "aam"},
}


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def _resolve_aliases(name: str) -> Set[str]:
    norm = _normalize_name(name)
    for canonical, aliases in INGREDIENT_ALIASES.items():
        if norm in aliases or norm == canonical:
            return {canonical} | aliases
    return {norm}


class ViruddhaAhaarEngine:
    """
    Evaluates a list of ingredients for Ayurvedic food incompatibilities.
    Uses static Charaka / Ashtanga Hridayam rules, extended by Neo4j graph data.
    """

    def __init__(self):
        self._neo4j_rules: List[Dict[str, Any]] = []
        self._load_neo4j_rules()

    def _load_neo4j_rules(self):
        try:
            from services.neo4j_service import neo4j_service
            if neo4j_service.is_connected:
                pairs = neo4j_service.get_viruddha_pairs()
                for p in pairs:
                    self._neo4j_rules.append({
                        "ingredients": {p["ing1"].lower(), p["ing2"].lower()},
                        "type": p.get("type", "Unknown"),
                        "severity": p.get("severity", "Medium"),
                        "reason": p.get("reason", "Ayurvedic incompatibility"),
                        "ayurvedicText": p.get("ayurvedicText", ""),
                        "recommendations": ["Avoid combining these ingredients"],
                    })
                logger.info(f"Loaded {len(self._neo4j_rules)} Viruddha rules from Neo4j")
        except Exception as exc:
            logger.warning(f"Could not load Neo4j Viruddha rules: {exc}")

    def _ingredient_names(self, ingredients: List[Dict[str, Any]]) -> List[str]:
        return [_normalize_name(i.get("name", "")) for i in ingredients]

    def _ingredient_set(self, ingredients: List[Dict[str, Any]]) -> Set[str]:
        names = self._ingredient_names(ingredients)
        resolved: Set[str] = set()
        for n in names:
            resolved |= _resolve_aliases(n)
        return resolved

    def evaluate(
        self,
        ingredients: List[Dict[str, Any]],
        cooking_process: str = "raw"
    ) -> Dict[str, Any]:
        """
        Evaluate ingredient list for Viruddha incompatibilities.
        Returns: { isCompatible, violations, overallSeverity, compatibilityScore, recommendations }
        """
        present = self._ingredient_set(ingredients)
        violations = []
        all_recommendations: List[str] = []
        severity_rank = {"High": 3, "Medium": 2, "Low": 1}
        max_severity = 0

        all_rules = VIRUDDHA_RULES + self._neo4j_rules

        for rule in all_rules:
            rule_set: Set[str] = rule["ingredients"]

            # Check primary set
            matched = rule_set.issubset(present)

            # Check alternate set ("also" key)
            if not matched and "also" in rule:
                matched = rule["also"].issubset(present)

            # Special condition checks
            if matched and rule.get("condition") == "equal_weight_ratio":
                # Only flag if we actually see both at roughly equal quantities
                # (simplified: just flag if both present at all)
                matched = True

            if matched:
                sev = rule.get("severity", "Low")
                max_severity = max(max_severity, severity_rank.get(sev, 1))
                violations.append({
                    "type": rule["type"],
                    "severity": sev,
                    "reason": rule["reason"],
                    "ingredients": list(rule_set),
                    "ayurvedicText": rule.get("ayurvedicText", ""),
                })
                all_recommendations.extend(rule.get("recommendations", []))

        severity_labels = {0: "None", 1: "Low", 2: "Medium", 3: "High"}
        overall_severity = severity_labels[max_severity]

        # Score: 1.0 = fully compatible, 0.0 = highly incompatible
        score = max(0.0, 1.0 - (len(violations) * 0.2) - (max_severity * 0.1))
        score = round(score, 2)

        return {
            "isCompatible": len(violations) == 0,
            "violations": violations,
            "overallSeverity": overall_severity,
            "compatibilityScore": score,
            "recommendations": list(set(all_recommendations)),
        }

    def check_pair(self, name1: str, name2: str) -> Dict[str, Any]:
        """Quick-check a single ingredient pair."""
        return self.evaluate([{"name": name1}, {"name": name2}])


viruddha_engine = ViruddhaAhaarEngine()
