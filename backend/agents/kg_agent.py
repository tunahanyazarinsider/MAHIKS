"""
Knowledge Graph Agent for MAHIKS-TR
Responsible for extracting entities and relationships to build the knowledge graph
"""
import spacy
from typing import List, Dict, Tuple, Optional
import re


class KnowledgeGraphAgent:
    """Agent for building and populating the knowledge graph"""

    def __init__(self, neo4j_handler):
        """
        Initialize the Knowledge Graph agent

        Args:
            neo4j_handler: Instance of Neo4jHandler
        """
        self.neo4j = neo4j_handler

        # Load Turkish spaCy model
        try:
            print("Loading Turkish NLP model...")
            self.nlp = spacy.load("tr_core_news_lg")
            print("✓ Knowledge Graph agent initialized with Turkish NLP")
        except OSError:
            print("⚠ Turkish model not found. Attempting to download...")
            import subprocess
            result = subprocess.run(
                ["python", "-m", "spacy", "download", "tr_core_news_lg"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                raise OSError(
                    f"Failed to download Turkish spaCy model. "
                    f"Please install manually: python -m spacy download tr_core_news_lg"
                )
            self.nlp = spacy.load("tr_core_news_lg")
            print("✓ Turkish model downloaded and loaded")

        # Medical domain-specific entity types
        self.medical_entity_types = {
            'DISEASE': 'Disease',
            'DRUG': 'Drug',
            'TREATMENT': 'Treatment',
            'ORG': 'Organization',
            'PROCEDURE': 'Procedure'
        }

        # Turkish medical keywords for entity recognition enhancement
        self.medical_keywords = {
            'disease': ['hastalık', 'hastalığı', 'sendrom', 'diyabet', 'kanser', 'enfeksiyon'],
            'drug': ['ilaç', 'ilacı', 'tablet', 'kapsül', 'serum', 'enjeksiyon'],
            'organization': ['SGK', 'bakanlık', 'hastane', 'kurum', 'sağlık'],
            'treatment': ['tedavi', 'ameliyat', 'operasyon', 'terapi', 'muayene']
        }

    def extract_entities(self, text: str) -> List[Dict]:
        """
        Extract named entities from text

        Args:
            text: Input text

        Returns:
            List of entity dictionaries
        """
        doc = self.nlp(text)
        entities = []

        for ent in doc.ents:
            # Map entity type
            entity_type = self.medical_entity_types.get(ent.label_, ent.label_)

            entities.append({
                'text': ent.text,
                'label': entity_type,
                'start': ent.start_char,
                'end': ent.end_char
            })

        return entities

    def enhance_entity_recognition(self, text: str) -> List[Dict]:
        """
        Enhanced entity recognition using domain keywords

        Args:
            text: Input text

        Returns:
            List of enhanced entities
        """
        entities = self.extract_entities(text)

        # Add keyword-based entities
        doc = self.nlp(text)

        for token in doc:
            token_lower = token.text.lower()

            # Check against medical keywords
            for category, keywords in self.medical_keywords.items():
                if any(keyword in token_lower for keyword in keywords):
                    # Check if not already in entities
                    if not any(e['text'] == token.text for e in entities):
                        entities.append({
                            'text': token.text,
                            'label': category.capitalize(),
                            'start': token.idx,
                            'end': token.idx + len(token.text)
                        })

        return entities

    def extract_triplets(self, text: str) -> List[Tuple[str, str, str]]:
        """
        Extract Subject-Predicate-Object triplets from text

        Args:
            text: Input text

        Returns:
            List of (subject, predicate, object) tuples
        """
        doc = self.nlp(text)
        triplets = []

        for sent in doc.sents:
            # Method 1: Dependency-based extraction
            for token in sent:
                # Look for subject-verb-object patterns
                if token.dep_ in ['nsubj', 'nsubjpass']:  # Subject
                    subject = token.text
                    predicate = token.head.text

                    # Find the object
                    for child in token.head.children:
                        if child.dep_ in ['dobj', 'attr', 'pobj']:  # Object
                            obj = child.text
                            triplets.append((subject, predicate, obj))

                        # Handle prepositional phrases
                        elif child.dep_ == 'prep':
                            for grandchild in child.children:
                                if grandchild.dep_ == 'pobj':
                                    obj = grandchild.text
                                    combined_predicate = f"{predicate} {child.text}"
                                    triplets.append((subject, combined_predicate, obj))

        return triplets

    def extract_medical_triplets(self, text: str) -> List[Tuple[str, str, str, str, str]]:
        """
        Extract medical-domain triplets with entity types

        Args:
            text: Input text

        Returns:
            List of (subject, predicate, object, subject_type, object_type) tuples
        """
        entities = self.enhance_entity_recognition(text)
        triplets = self.extract_triplets(text)

        # Enhance triplets with entity type information
        enhanced_triplets = []

        for subj, pred, obj in triplets:
            # Find entity types
            subj_type = self._find_entity_type(subj, entities)
            obj_type = self._find_entity_type(obj, entities)

            enhanced_triplets.append((subj, pred, obj, subj_type, obj_type))

        return enhanced_triplets

    def _find_entity_type(self, text: str, entities: List[Dict]) -> str:
        """
        Find the entity type for a given text

        Args:
            text: Entity text
            entities: List of recognized entities

        Returns:
            Entity type or 'Entity' as default
        """
        for ent in entities:
            if text.lower() in ent['text'].lower() or ent['text'].lower() in text.lower():
                return ent['label']
        return 'Entity'

    def extract_coverage_relations(self, text: str) -> List[Tuple[str, str, str]]:
        """
        Extract insurance coverage relationships specifically

        Args:
            text: Input text

        Returns:
            List of coverage triplets
        """
        coverage_triplets = []

        # Patterns for coverage (Turkish)
        coverage_patterns = [
            r'(\w+)\s+(kapsar|karşılar|öder|kapsam[ıi]nda)\s+(\w+)',
            r'(\w+)\s+için\s+(\w+)\s+(geçerli|uygulan[ıi]r)',
        ]

        for pattern in coverage_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                groups = match.groups()
                if len(groups) >= 2:
                    subject = groups[0]
                    predicate = "covers" if "kapsar" in match.group() else "pays_for"
                    obj = groups[-1]
                    coverage_triplets.append((subject, predicate, obj))

        return coverage_triplets

    def populate_graph(self, text: str) -> int:
        """
        Extract triplets and populate the Neo4j knowledge graph

        Args:
            text: Source text

        Returns:
            Number of triplets created
        """
        print("    Extracting entities and relationships...")

        # Extract enhanced triplets
        triplets = self.extract_medical_triplets(text)

        # Also extract coverage-specific relations
        coverage_triplets = self.extract_coverage_relations(text)

        # Combine all triplets
        all_triplets = []

        # Add enhanced triplets with type info
        for subj, pred, obj, subj_type, obj_type in triplets:
            if len(subj) > 2 and len(obj) > 2:  # Filter out very short entities
                all_triplets.append((subj, pred, obj, subj_type, obj_type))

        # Add coverage triplets
        for subj, pred, obj in coverage_triplets:
            all_triplets.append((subj, pred, obj, 'Organization', 'Treatment'))

        # Batch insert into Neo4j
        if all_triplets:
            for subj, pred, obj, subj_type, obj_type in all_triplets:
                self.neo4j.create_triplet(
                    subject=subj,
                    predicate=pred,
                    obj=obj,
                    subject_type=subj_type,
                    object_type=obj_type
                )

        print(f"      ✓ Extracted and stored {len(all_triplets)} triplets")
        return len(all_triplets)

    def process_document(self, text: str, batch_size: int = 1000) -> Dict:
        """
        Process entire document and extract all knowledge

        Args:
            text: Document text
            batch_size: Process text in batches of this many characters

        Returns:
            Statistics dictionary
        """
        total_triplets = 0
        total_entities = 0

        # Split into batches if text is very long
        if len(text) > batch_size:
            chunks = [text[i:i+batch_size] for i in range(0, len(text), batch_size)]
        else:
            chunks = [text]

        for chunk in chunks:
            triplets = self.populate_graph(chunk)
            entities = self.extract_entities(chunk)

            total_triplets += triplets
            total_entities += len(entities)

        return {
            'triplets_extracted': total_triplets,
            'entities_found': total_entities,
            'chunks_processed': len(chunks)
        }
