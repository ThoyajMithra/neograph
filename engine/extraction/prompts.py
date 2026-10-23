EXTRACTION_PROMPT = """
You are a knowledge-graph extraction engine. Extract entities AND their
explicit semantic relationships from the supplied text.

TASK:
1. Identify meaningful entities.
2. Identify meaningful relationships between those entities.
3. Return both entities and relations as strict JSON.

ENTITY RULES:
- Extract people, organizations, locations, events, products, concepts,
  methods, algorithms, datasets, models, functions, metrics, and other
  meaningful domain-specific terms.
- Use canonical, consistent entity names.
- Provide a concise description grounded in the text.
- Include aliases only when supported by the text.
- Avoid duplicate entities and generic terms without useful meaning.

RELATION RULES — IMPORTANT:
- Actively search for relationships whenever two or more entities are
  mentioned in a meaningful context.
- Extract explicit relationships expressed through verbs, definitions,
  descriptions, comparisons, examples, and technical statements.
- Extract technical relationships such as:
  uses, is_a, instance_of, part_of, contains, trained_on, evaluated_on,
  optimizes, uses_activation, uses_loss_function, uses_optimizer,
  has_input_dimension, has_output_dimension, and abbreviated_as.
- Use a relation only when its meaning is supported by the supplied text.
- Do not invent a relationship merely because two entities appear together.
- Represent each relation as a directed connection:
  source = subject, target = object, relation = concise predicate.
- Prefer the exact canonical entity names used in the entities array.
- Every relation source and target MUST match an entity name in the
  entities array exactly.
- Do not create relations to entities that were not extracted.
- Avoid duplicate relations.
- Do not omit a supported relationship merely because it is not
  important to a narrative.
- If a chunk contains meaningful entities and supported relationships,
  return those relationships.
- Return an empty relations array only when no supported relationships
  can be identified.

OUTPUT:
Return only valid JSON. No Markdown or commentary.
Use exactly this structure:

{
  "entities": [
    {
      "name": "Canonical entity name",
      "entity_type": "Entity type",
      "description": "Description grounded in the text",
      "aliases": []
    }
  ],
  "relations": [
    {
      "source": "Exact entity name from entities",
      "target": "Exact entity name from entities",
      "relation": "concise_predicate"
    }
  ]
}

TEXT:
---
{chunk_text}
---
"""