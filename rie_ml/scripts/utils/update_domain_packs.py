#!/usr/bin/env python3
"""Update domain packs with complete data from domain-pack files."""

import json
import os
import sys
from pathlib import Path

# Add app to path (resolve repo root from script location)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.db.database import SessionLocal
from app.db.models.domain_pack import DomainPack

def load_domain_pack(domain_dir):
    """Load all domain pack files from directory."""
    domain_id = os.path.basename(domain_dir)

    # Load domain_config.json
    with open(os.path.join(domain_dir, 'domain_config.json')) as f:
        config = json.load(f)

    # Load schema
    with open(os.path.join(domain_dir, 'schema/schema.json')) as f:
        schema = json.load(f)

    # Load business glossary (convert markdown to structured JSON)
    glossary = {}
    glossary_file = os.path.join(domain_dir, 'documentation/business_glossary.md')
    if os.path.exists(glossary_file):
        # Simple markdown parser for glossary
        with open(glossary_file) as f:
            content = f.read()
        # Extract terms from markdown
        import re
        # Find ### term_name sections
        terms = re.findall(r'###\s+(\w+)\n(.*?)(?=\n###|\n---|\n## |$)', content, re.DOTALL)
        for term_name, term_content in terms:
            # Extract definition
            def_match = re.search(r'\*\*Definition:\*\*\s*(.*?)\n', term_content)
            definition = def_match.group(1).strip() if def_match else ""

            # Extract tables/columns
            tables_match = re.search(r'\*\*Tables/columns:\*\*\s*(.*?)\n', term_content)
            tables_columns = tables_match.group(1).strip() if tables_match else ""

            # Extract related rules
            rules_match = re.search(r'\*\*Related rules:\*\*\s*(.*?)\n', term_content)
            related_rules = [r.strip() for r in rules_match.group(1).split(',')] if rules_match else []

            glossary[term_name] = {
                "definition": definition,
                "tables_columns": tables_columns,
                "related_rules": related_rules
            }

    # Load active rules
    active_rules_file = os.path.join(domain_dir, 'rules/active_rules.json')
    active_rules = []
    if os.path.exists(active_rules_file):
        with open(active_rules_file) as f:
            active_rules = json.load(f)

    # Load conflicting rules
    conflicting_rules_file = os.path.join(domain_dir, 'rules/conflicting_rules.json')
    conflicting_rules = []
    if os.path.exists(conflicting_rules_file):
        with open(conflicting_rules_file) as f:
            conflicting_rules = json.load(f)

    return {
        'pack_id': config.get('domain_pack_id', domain_id),
        'workspace_id': config.get('workspace_id', 'e8af6af9-3bbe-4117-a007-f55db418bc30'),
        'name': config.get('display_name', domain_id.replace('_', ' ').title()),
        'version': config.get('version', '1.0.0'),
        'schema_metadata': schema,
        'business_glossary': glossary,
        'configuration': {
            'active_rules': active_rules,
            'conflicting_rules': conflicting_rules,
            'seed_feedback_ref': config.get('seed_feedback_ref'),
            'annotation_version': config.get('annotation_version'),
            'taxonomy_ref': config.get('taxonomy_ref'),
            'schema_ref': config.get('schema_ref'),
            'relationships_ref': config.get('relationships_ref'),
            'glossary_ref': config.get('glossary_ref'),
            'annotation_guide_ref': config.get('annotation_guide_ref')
        }
    }

def update_domain_packs():
    db = SessionLocal()
    try:
        domain_packs_dir = REPO_ROOT / "rie_ml" / "domain-packs"

        for domain_name in os.listdir(domain_packs_dir):
            domain_dir = os.path.join(domain_packs_dir, domain_name)
            if not os.path.isdir(domain_dir):
                continue

            print(f"Loading domain pack: {domain_name}")
            pack_data = load_domain_pack(domain_dir)

            # Check if exists
            existing = db.query(DomainPack).filter(DomainPack.domain_pack_id == pack_data['pack_id']).first()

            if existing:
                print(f"  Updating existing pack: {pack_data['pack_id']}")
                existing.workspace_id = pack_data['workspace_id']
                existing.name = pack_data['name']
                existing.version = pack_data['version']
                existing.schema_metadata = pack_data['schema_metadata']
                existing.business_glossary = pack_data['business_glossary']
                existing.configuration = pack_data['configuration']
            else:
                print(f"  Creating new pack: {pack_data['pack_id']}")
                # Use domain_pack_id instead of pack_id
                pack_data['domain_pack_id'] = pack_data.pop('pack_id')
                new_pack = DomainPack(**pack_data)
                db.add(new_pack)

        db.commit()
        print("Domain packs updated successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == '__main__':
    update_domain_packs()