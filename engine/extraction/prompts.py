EXTRACTION_PROMPTS = {
    #general
    0: """
Extract entities and factual relationships from the text for
knowledge-graph-based RAG and question answering.

RULES:
- Extract meaningful entities, key facts, and relationships
  explicitly supported by the text.
- Include important attributes, definitions, causes, dependencies,
  ownership, and comparisons when stated.
- Use canonical entity names and avoid duplicates.
- Every relation's source and target must exactly match extracted
  entity names.
- Use concise, text-grounded entity descriptions.
- Preserve relationship direction, conditions, dates, and uncertainty.
- Never invent facts or use outside knowledge.
- Use specific snake_case relation names.
- Exclude trivial details and duplicate relations.
- Include aliases when the text provides alternative names.
- Return valid JSON only, without Markdown or commentary.
""",
#reasoning
    1: """
Extract entities, factual relationships, and explicitly supported
reasoning structures from the text for knowledge-graph-based RAG
and question answering.

RULES:
- Identify the main claims, supporting facts, conclusions, causes,
  effects, dependencies, conditions, and constraints stated in the text.
- Extract relationships that explain why something happens, how
  something works, or what follows from a stated condition.
- Represent premises, evidence, and conclusions as relationships
  between entities when those relationships are explicitly supported.
- Preserve the direction of cause-and-effect relationships.
- Distinguish correlation from causation.
- Preserve uncertainty, assumptions, qualifications, and exceptions.
- Do not convert a possibility into a certainty.
- Do not treat an author's unsupported opinion as an established fact.
- Do not invent missing premises or conclusions.
- Do not introduce outside knowledge or unstated reasoning.
- Use canonical entity names and avoid duplicate entities.
- Every relation's source and target must exactly match extracted
  entity names.
- Use concise, text-grounded descriptions.
- Use specific snake_case relation names.
- Exclude trivial details and duplicate relations.
- Include aliases when explicitly provided by the text.
- Return valid JSON only, without Markdown or commentary.
""",
#concept
    2: """
Extract concepts, definitions, properties, principles, and conceptual
relationships from the text for knowledge-graph-based RAG and
question answering.

RULES:
- Identify important concepts, technical terms, theories, principles,
  methods, models, algorithms, and abstractions.
- Extract definitions explicitly stated in the text.
- Capture essential properties, characteristics, components, and purposes.
- Identify conceptual relationships such as is_a, instance_of,
  part_of, consists_of, uses, requires, depends_on, and applies_to
  when supported by the text.
- Identify differences, similarities, limitations, and prerequisites
  when explicitly stated.
- Preserve the distinction between a concept and an instance of it.
- Distinguish a component from the whole system it belongs to.
- Preserve technical terminology and the meaning intended by the author.
- Use canonical concept names and avoid duplicate entities.
- Every relation's source and target must exactly match extracted
  entity names.
- Write concise descriptions that preserve the concept's essential
  meaning without introducing unsupported information.
- Use specific snake_case relation names.
- Preserve conditions, qualifications, and uncertainty.
- Never invent definitions or use outside knowledge.
- Exclude incidental mentions and duplicate relations.
- Include explicitly provided alternative names as aliases.
- Return valid JSON only, without Markdown or commentary.
"""
}

EXTRACTION_FORMAT="""
FORMAT:
{
  "entities": [
    {
      "name": "...",
      "entity_type": "...",
      "description": "...",
      "aliases": []
    }
  ],
  "relations": [
    {
      "source": "...",
      "target": "...",
      "relation": "..."
    }
  ]
}

TEXT:
---
{chunk_text}
---
"""
