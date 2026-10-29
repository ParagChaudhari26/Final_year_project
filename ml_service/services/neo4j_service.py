"""
Neo4j connection service for FoodCoach AI.
Provides a singleton driver with graceful fallback if Neo4j is unavailable.
"""
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("Neo4jService")


class Neo4jService:
    def __init__(self):
        self.driver = None
        self._connected = False
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "foodcoach123")
        self._try_connect(uri, user, password)

    def _try_connect(self, uri: str, user: str, password: str):
        try:
            # pyrefly: ignore[missing-import]
            from neo4j import GraphDatabase
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.driver.verify_connectivity()
            self._connected = True
            logger.info(f"✅ Connected to Neo4j at {uri}")
        except Exception as exc:
            logger.warning(
                f"⚠️  Neo4j unavailable ({exc}). Will use in-memory fallback data."
            )
            self.driver = None
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def run_query(
        self, query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return all records as dicts."""
        if not self.driver:
            return []
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]
        except Exception as exc:
            logger.error(f"Query failed: {exc}\nQuery: {query[:200]}")
            return []

    def run_write(
        self, query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Execute a write Cypher query. Returns True on success."""
        if not self.driver:
            return False
        try:
            with self.driver.session() as session:
                session.execute_write(
                    lambda tx: tx.run(query, parameters or {})
                )
            return True
        except Exception as exc:
            logger.error(f"Write query failed: {exc}")
            return False

    def get_all_recipes(self, diet_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch all recipes, optionally filtered by dietType."""
        filter_clause = ""
        params: Dict[str, Any] = {}
        if diet_type and diet_type.lower() != "any":
            filter_clause = "WHERE r.dietType = $dietType OR r.dietType = 'Vegan'"
            params["dietType"] = diet_type

        query = f"""
        MATCH (r:Recipe)-[:BELONGS_TO_CUISINE]->(c:Cuisine)
        {filter_clause}
        OPTIONAL MATCH (r)-[:IS_BENEFICIAL_FOR]->(h:HealthCondition)
        RETURN r, c.name AS cuisine,
               collect(DISTINCT h.id) AS beneficiaries
        """
        rows = self.run_query(query, params)
        recipes = []
        for row in rows:
            rec = dict(row["r"])
            rec["cuisineName"] = row["cuisine"]
            rec["beneficiaries"] = row.get("beneficiaries", [])
            recipes.append(rec)
        return recipes

    def get_recipe_ingredients(self, recipe_id: str) -> List[Dict[str, Any]]:
        """Fetch all ingredients for a given recipe id."""
        query = """
        MATCH (r:Recipe {id: $rid})-[rel:HAS_INGREDIENT]->(i:Ingredient)
        RETURN i.id AS id, i.name AS name, i.ifctCode AS ifctCode,
               i.category AS category,
               rel.quantity AS quantity, rel.unit AS unit
        """
        return self.run_query(query, {"rid": recipe_id})

    def get_viruddha_pairs(self) -> List[Dict[str, Any]]:
        """Return all Viruddha Ahaar ingredient pairs from the graph."""
        query = """
        MATCH (a:Ingredient)-[v:VIRUDDHA_AHAAR]->(b:Ingredient)
        RETURN a.name AS ing1, b.name AS ing2,
               v.type AS type, v.severity AS severity,
               v.reason AS reason,
               v.condition AS condition,
               v.ayurvedicText AS ayurvedicText
        """
        return self.run_query(query)

    def close(self):
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed.")


# Singleton instance
neo4j_service = Neo4jService()
