"""Seed script for rule_embeddings table. Inserts placeholder embeddings for existing rules.

Usage:
    export DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
    python3 scripts/seed_rule_embeddings.py
"""

import os
import sys
import json
import uuid
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print('Please set DATABASE_URL environment variable (e.g. postgresql://user:pass@host:port/db)')
    sys.exit(1)

engine = create_engine(DATABASE_URL)

# Placeholder embedding generator (zeros) — replace with real embeddings pipeline
def zero_embedding(dim=1536):
    return [0.0] * dim


def main():
    with engine.begin() as conn:
        try:
            # Ensure table exists
            res = conn.execute(text("SELECT to_regclass('public.rule_embeddings')"))
            tbl = res.scalar()
            if not tbl:
                print('rule_embeddings table not found; ensure migrations have been applied')
                return

            # Fetch some rule ids to seed (example: rule_suggestions table)
            rows = conn.execute(text("SELECT suggestion_id FROM rule_suggestions LIMIT 50")).fetchall()
            if not rows:
                print('No suggestions found to seed. Insert suggestions first or adjust query.')
                return

            inserted = 0
            for (sid,) in rows:
                rid = str(uuid.uuid4())
                emb = zero_embedding()
                # pgvector accepts array literal syntax for INSERT
                emb_literal = 'ARRAY[' + ','.join(str(x) for x in emb) + ']'
                sql = text(
                    "INSERT INTO rule_embeddings (id, rule_id, embedding, metadata, created_at) VALUES (:id, :rule_id, %s, :metadata, :created_at) ON CONFLICT (id) DO NOTHING;" % emb_literal
                )
                conn.execute(
                    sql,
                    {
                        'id': rid,
                        'rule_id': sid,
                        'metadata': json.dumps({'seeded': True}),
                        'created_at': datetime.utcnow(),
                    }
                )
                inserted += 1

            print(f'Inserted {inserted} placeholder embeddings into rule_embeddings')
        except SQLAlchemyError as e:
            print('DB error during seeding:', e)


if __name__ == '__main__':
    main()
