"""
Neo4j Handler for MAHIKS-TR
Manages knowledge graph for medical entities and relationships
"""
from neo4j import GraphDatabase
from typing import List, Dict, Optional, Tuple


class Neo4jHandler:
    """Handler for Neo4j graph database operations"""

    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize Neo4j connection

        Args:
            uri: Neo4j connection URI (e.g., bolt://localhost:7687)
            user: Neo4j username
            password: Neo4j password
        """
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            print(f"✓ Connected to Neo4j at {uri}")
        except Exception as e:
            print(f"✗ Error connecting to Neo4j: {e}")
            raise

    def close(self):
        """Close the Neo4j driver connection"""
        if self.driver:
            self.driver.close()
            print("✓ Neo4j connection closed")

    def create_indexes(self):
        """Create indexes for better query performance"""
        with self.driver.session() as session:
            try:
                # Index on Entity name
                session.run(
                    "CREATE INDEX entity_name_idx IF NOT EXISTS "
                    "FOR (n:Entity) ON (n.name)"
                )
                # Index on Disease name
                session.run(
                    "CREATE INDEX disease_name_idx IF NOT EXISTS "
                    "FOR (n:Disease) ON (n.name)"
                )
                # Index on Drug name
                session.run(
                    "CREATE INDEX drug_name_idx IF NOT EXISTS "
                    "FOR (n:Drug) ON (n.name)"
                )
                # Index on Organization name
                session.run(
                    "CREATE INDEX org_name_idx IF NOT EXISTS "
                    "FOR (n:Organization) ON (n.name)"
                )
                print("✓ Neo4j indexes created")
            except Exception as e:
                print(f"✗ Error creating indexes: {e}")

    def create_triplet(self, subject: str, predicate: str, obj: str,
                      subject_type: str = "Entity",
                      object_type: str = "Entity",
                      properties: Optional[Dict] = None):
        """
        Create a triplet (Subject-Predicate-Object) in the graph

        Args:
            subject: Subject entity name
            predicate: Relationship/predicate
            obj: Object entity name
            subject_type: Node type for subject (Entity, Disease, Drug, etc.)
            object_type: Node type for object
            properties: Optional properties for the relationship
        """
        # Clean predicate for Cypher (replace spaces and special chars)
        predicate_clean = predicate.replace(" ", "_").replace("-", "_").upper()
        # Limit predicate length
        if len(predicate_clean) > 50:
            predicate_clean = predicate_clean[:50]

        with self.driver.session() as session:
            try:
                query = f"""
                MERGE (s:{subject_type} {{name: $subject}})
                MERGE (o:{object_type} {{name: $object}})
                MERGE (s)-[r:{predicate_clean}]->(o)
                """
                if properties:
                    query += "\nSET r += $properties"

                session.run(
                    query,
                    subject=subject,
                    object=obj,
                    properties=properties
                )
            except Exception as e:
                print(f"  Warning: Could not create triplet ({subject}, {predicate}, {obj}): {e}")

    def batch_create_triplets(self, triplets: List[Tuple[str, str, str]],
                             subject_type: str = "Entity",
                             object_type: str = "Entity"):
        """
        Create multiple triplets in a batch for better performance

        Args:
            triplets: List of (subject, predicate, object) tuples
            subject_type: Default subject node type
            object_type: Default object node type
        """
        if not triplets:
            return

        with self.driver.session() as session:
            for subject, predicate, obj in triplets:
                self.create_triplet(subject, predicate, obj, subject_type, object_type)

        print(f"  ✓ Created {len(triplets)} triplets in knowledge graph")

    def query_related_entities(self, entity_name: str,
                               max_depth: int = 2,
                               limit: int = 20) -> List[Dict]:
        """
        Find entities related to the given entity

        Args:
            entity_name: Name of the entity to search
            max_depth: Maximum relationship depth to traverse
            limit: Maximum number of results

        Returns:
            List of related entities with relationship info
        """
        with self.driver.session() as session:
            try:
                result = session.run(f"""
                    MATCH (n {{name: $entity_name}})-[r*1..{max_depth}]-(related)
                    RETURN DISTINCT related.name AS entity,
                           type(r[0]) AS relationship,
                           labels(related) AS labels
                    LIMIT {limit}
                    """,
                    entity_name=entity_name
                )

                return [
                    {
                        "entity": record["entity"],
                        "relationship": record["relationship"],
                        "labels": record["labels"]
                    }
                    for record in result
                ]
            except Exception as e:
                print(f"✗ Error querying related entities: {e}")
                return []

    def find_path(self, start_entity: str, end_entity: str,
                  max_length: int = 5) -> Optional[List[Dict]]:
        """
        Find shortest path between two entities

        Args:
            start_entity: Starting entity name
            end_entity: Target entity name
            max_length: Maximum path length

        Returns:
            Path as list of nodes and relationships, or None if no path found
        """
        with self.driver.session() as session:
            try:
                result = session.run(f"""
                    MATCH path = shortestPath(
                        (start {{name: $start}})-[*..{max_length}]-(end {{name: $end}})
                    )
                    RETURN [node in nodes(path) | node.name] AS nodes,
                           [rel in relationships(path) | type(rel)] AS relationships
                    """,
                    start=start_entity,
                    end=end_entity
                )

                record = result.single()
                if record:
                    return {
                        "nodes": record["nodes"],
                        "relationships": record["relationships"]
                    }
                return None
            except Exception as e:
                print(f"✗ Error finding path: {e}")
                return None

    def query_by_relationship(self, relationship_type: str,
                             limit: int = 50) -> List[Dict]:
        """
        Find all triplets with a specific relationship type

        Args:
            relationship_type: Type of relationship
            limit: Maximum results

        Returns:
            List of triplets
        """
        relationship_clean = relationship_type.replace(" ", "_").upper()

        with self.driver.session() as session:
            try:
                result = session.run(f"""
                    MATCH (s)-[r:{relationship_clean}]->(o)
                    RETURN s.name AS subject, type(r) AS predicate, o.name AS object
                    LIMIT {limit}
                    """
                )

                return [
                    {
                        "subject": record["subject"],
                        "predicate": record["predicate"],
                        "object": record["object"]
                    }
                    for record in result
                ]
            except Exception as e:
                print(f"✗ Error querying by relationship: {e}")
                return []

    def get_entity_info(self, entity_name: str) -> Optional[Dict]:
        """
        Get detailed information about an entity

        Args:
            entity_name: Name of the entity

        Returns:
            Dictionary with entity info including relationships
        """
        with self.driver.session() as session:
            try:
                # Get node properties and labels
                result = session.run("""
                    MATCH (n {name: $name})
                    RETURN properties(n) AS props, labels(n) AS labels
                    """,
                    name=entity_name
                )

                record = result.single()
                if not record:
                    return None

                # Get outgoing relationships
                out_rels = session.run("""
                    MATCH (n {name: $name})-[r]->(o)
                    RETURN type(r) AS relationship, o.name AS target
                    LIMIT 10
                    """,
                    name=entity_name
                )

                # Get incoming relationships
                in_rels = session.run("""
                    MATCH (s)-[r]->(n {name: $name})
                    RETURN type(r) AS relationship, s.name AS source
                    LIMIT 10
                    """,
                    name=entity_name
                )

                return {
                    "name": entity_name,
                    "labels": record["labels"],
                    "properties": record["props"],
                    "outgoing": [
                        {"relation": r["relationship"], "target": r["target"]}
                        for r in out_rels
                    ],
                    "incoming": [
                        {"relation": r["relationship"], "source": r["source"]}
                        for r in in_rels
                    ]
                }
            except Exception as e:
                print(f"✗ Error getting entity info: {e}")
                return None

    def get_statistics(self) -> Dict:
        """Get statistics about the knowledge graph"""
        with self.driver.session() as session:
            try:
                # Count nodes
                node_count = session.run("MATCH (n) RETURN count(n) AS count").single()["count"]

                # Count relationships
                rel_count = session.run("MATCH ()-[r]->() RETURN count(r) AS count").single()["count"]

                # Get node labels
                labels = session.run("""
                    CALL db.labels() YIELD label
                    RETURN collect(label) AS labels
                    """).single()["labels"]

                # Get relationship types
                rel_types = session.run("""
                    CALL db.relationshipTypes() YIELD relationshipType
                    RETURN collect(relationshipType) AS types
                    """).single()["types"]

                return {
                    "node_count": node_count,
                    "relationship_count": rel_count,
                    "node_labels": labels,
                    "relationship_types": rel_types
                }
            except Exception as e:
                print(f"✗ Error getting statistics: {e}")
                return {}

    def clear_all(self):
        """Clear all nodes and relationships (USE WITH CAUTION!)"""
        with self.driver.session() as session:
            try:
                session.run("MATCH (n) DETACH DELETE n")
                print("⚠ All graph data cleared")
            except Exception as e:
                print(f"✗ Error clearing graph: {e}")
