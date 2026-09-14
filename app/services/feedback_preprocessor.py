"""Feedback preprocessing service for normalizing and cleaning feedback text.

Performs step-by-step preprocessing with detailed logging:
1. Unicode normalization
2. Whitespace normalization
3. Sentence segmentation
4. Tokenization
5. Punctuation removal
6. Basic spelling correction (using domain-pack vocabulary when available)
7. Business keyword detection (domain-aware)
8. Schema reference detection
9. Language normalization
"""

import re
import json
import unicodedata
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from app.logging_config import preprocessing_logger
from app.services.pii_masking import mask_feedback_text


# ---------------------------------------------------------------------------
# Hardcoded fallback vocabulary (used only when no domain pack is available).
# In production, domain packs provide tables, columns, glossary terms, etc.
# ---------------------------------------------------------------------------
FALLBACK_VOCABULARY = {
    "revenue", "order", "customer", "product", "payment", "shipping",
    "invoice", "refund", "discount", "tax", "metric", "filter",
    "access", "rule", "calculation", "definition", "include", "exclude",
    "cancelled", "status", "amount", "date", "time", "field", "table",
    "schema", "database", "condition", "value", "operator", "range",
}

# Cache per domain pack — avoids re-parsing JSON/Markdown on every request.
_domain_vocab_cache: Dict[str, set] = {}


class FeedbackPreprocessor:
    """Preprocess feedback text with detailed logging for each step."""

    def __init__(self):
        """Initialize preprocessor with core keywords and schema patterns."""
        # Core keywords always present (used as a minimum guaranteed set)
        self.business_keywords = {
            "revenue", "order", "customer", "product", "payment", "shipping",
            "invoice", "refund", "discount", "tax", "metric", "filter",
            "access", "rule", "calculation", "definition", "include", "exclude",
        }

        # Active vocabulary — rebuilt per preprocess() call from domain pack
        # or from the fallback set when no domain pack is provided.
        self._active_vocab: set = set()

        # Schema reference patterns
        self.schema_patterns = [
            r'\b(table|column|field|attribute)\b',
            r'\b(join|relationship|foreign\s+key)\b',
            r'\b(select|where|from|group\s+by|order\s+by)\s+(\w+\.\w+|"[^"]+"|`[^`]+`)',
            r'\b(\w+\.\w+)\b',
            r'"[^"]+"',
            r'`[^`]+`',
        ]

    # ------------------------------------------------------------------
    # Domain-pack vocabulary loader
    # ------------------------------------------------------------------

    def _load_domain_vocabulary(self, domain_pack_id: str) -> set:
        """Build vocabulary from a domain pack (schema + taxonomy + glossary).

        Sources:
        - schema/schema.json  → table names, column names
        - taxonomy/labels.json → operations, operators
        - documentation/business_glossary.md → glossary term names, synonym aliases

        Results are cached per domain_pack_id so repeated requests are free.
        """
        if domain_pack_id in _domain_vocab_cache:
            return _domain_vocab_cache[domain_pack_id]

        pack_path = (
            Path(__file__).parent.parent.parent
            / "rie_ml"
            / "domain-packs"
            / domain_pack_id
        )
        vocab: set = set()

        # 1. Schema — table names + column names
        schema_path = pack_path / "schema" / "schema.json"
        try:
            if schema_path.exists():
                schema = json.loads(schema_path.read_text())
                for table_name, table_def in schema.get("tables", {}).items():
                    vocab.add(table_name.lower())
                    columns = table_def.get("columns", {})
                    if isinstance(columns, dict):
                        for col in columns:
                            vocab.add(col.lower())
                            vocab.add(f"{table_name.lower()}.{col.lower()}")
        except Exception as exc:
            preprocessing_logger.warning(f"Could not load schema vocabulary: {exc}")

        # 2. Taxonomy — operations + operators
        taxonomy_path = pack_path / "taxonomy" / "labels.json"
        try:
            if taxonomy_path.exists():
                taxonomy = json.loads(taxonomy_path.read_text())
                for op in taxonomy.get("operations", []):
                    vocab.add(op.lower())
                for op in taxonomy.get("operators", []):
                    vocab.add(op.lower())
        except Exception as exc:
            preprocessing_logger.warning(f"Could not load taxonomy vocabulary: {exc}")

        # 3. Business glossary — term names + synonym aliases
        glossary_path = pack_path / "documentation" / "business_glossary.md"
        try:
            if glossary_path.exists():
                content = glossary_path.read_text()

                # Extract ### headings (term names like "cancelled_order")
                for m in re.finditer(r'^### (\w+)', content, re.MULTILINE):
                    term = m.group(1).lower()
                    vocab.add(term)
                    # Also add individual words from snake_case
                    for part in term.split("_"):
                        if len(part) > 2:
                            vocab.add(part)

                # Extract synonym aliases table
                in_synonyms = False
                for line in content.splitlines():
                    if "## Synonym" in line:
                        in_synonyms = True
                        continue
                    if in_synonyms and line.startswith("##"):
                        in_synonyms = False
                        continue
                    if in_synonyms and "|" in line and "---" not in line:
                        cells = [c.strip().lower() for c in line.split("|") if c.strip()]
                        if len(cells) >= 2:
                            for alias in cells[1].split(","):
                                alias = alias.strip()
                                if alias:
                                    vocab.add(alias)
                                    for part in alias.split():
                                        if len(part) > 2:
                                            vocab.add(part)
        except Exception as exc:
            preprocessing_logger.warning(f"Could not load glossary vocabulary: {exc}")

        preprocessing_logger.info(
            f"Loaded domain vocabulary for '{domain_pack_id}': "
            f"{len(vocab)} terms"
        )
        _domain_vocab_cache[domain_pack_id] = vocab
        return vocab

    # ------------------------------------------------------------------
    # Main preprocessing pipeline
    # ------------------------------------------------------------------

    def preprocess(
        self,
        feedback_text: str,
        domain_context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Complete preprocessing pipeline with step-by-step logging.

        Args:
            feedback_text: Raw feedback text
            domain_context: Optional domain context; if it contains
                ``domain_pack_id`` the preprocessor loads vocabulary from
                that domain pack (tables, columns, glossary, taxonomy).

        Returns:
            {
                "original_text": str,
                "processed_text": str,
                "preprocessing_steps": [ {step, input, output, changes} ],
                "detected_keywords": [str],
                "detected_schema_refs": [str],
                "language_normalized": bool,
                "vocabulary_source": str,   # "fallback" or "<domain_pack_id>"
            }
        """
        preprocessing_logger.info("=== FEEDBACK PREPROCESSING START ===")
        preprocessing_logger.info(f"Original feedback: {mask_feedback_text(feedback_text)}")

        # --- Build active vocabulary from domain pack (or fallback) ---
        domain_pack_id = (domain_context or {}).get("domain_pack_id")
        if domain_pack_id:
            self._active_vocab = self._load_domain_vocabulary(domain_pack_id)
            if self._active_vocab:
                vocab_source = domain_pack_id
            else:
                # Pack id supplied but nothing could be loaded (missing/unknown
                # pack) — degrade to the fallback set so keyword detection
                # never silently returns nothing.
                self._active_vocab = set(FALLBACK_VOCABULARY)
                vocab_source = f"fallback (unknown pack '{domain_pack_id}')"
        else:
            self._active_vocab = set(FALLBACK_VOCABULARY)
            vocab_source = "fallback"
        preprocessing_logger.info(
            f"Active vocabulary: {len(self._active_vocab)} terms "
            f"(source: {vocab_source})"
        )

        steps: list = []
        current_text = feedback_text

        # Step 1: Unicode normalization
        step1_input = current_text
        current_text, step1_changes = self._normalize_unicode(current_text)
        steps.append({"step": "unicode_normalization", "input": step1_input, "output": current_text, "changes": step1_changes})
        preprocessing_logger.info(f"Step 1 - Unicode normalization: {step1_changes}")

        # Step 2: Whitespace normalization
        step2_input = current_text
        current_text, step2_changes = self._normalize_whitespace(current_text)
        steps.append({"step": "whitespace_normalization", "input": step2_input, "output": current_text, "changes": step2_changes})
        preprocessing_logger.info(f"Step 2 - Whitespace normalization: {step2_changes}")

        # Step 3: Sentence segmentation
        step3_input = current_text
        current_text, step3_changes = self._segment_sentences(current_text)
        steps.append({"step": "sentence_segmentation", "input": step3_input, "output": current_text, "changes": step3_changes})
        preprocessing_logger.info(f"Step 3 - Sentence segmentation: {step3_changes}")

        # Step 4: Tokenization
        step4_input = current_text
        current_text, step4_changes = self._tokenize_text(current_text)
        steps.append({"step": "tokenization", "input": step4_input, "output": current_text, "changes": step4_changes})
        preprocessing_logger.info(f"Step 4 - Tokenization: {step4_changes}")

        # Step 5: Punctuation removal
        step5_input = current_text
        current_text, step5_changes = self._remove_punctuation(current_text)
        steps.append({"step": "punctuation_removal", "input": step5_input, "output": current_text, "changes": step5_changes})
        preprocessing_logger.info(f"Step 5 - Punctuation removal: {step5_changes}")

        # Step 6: Spelling correction (domain-vocabulary-aware)
        step6_input = current_text
        current_text, step6_changes = self._correct_spelling(current_text)
        steps.append({"step": "spelling_correction", "input": step6_input, "output": current_text, "changes": step6_changes})
        preprocessing_logger.info(f"Step 6 - Spelling correction: {step6_changes}")

        # Step 7: Business keyword detection
        detected_keywords = self._detect_business_keywords(current_text)
        preprocessing_logger.info(f"Step 7 - Business keywords detected: {detected_keywords}")

        # Step 8: Schema reference detection
        detected_schema_refs = self._detect_schema_references(current_text)
        preprocessing_logger.info(f"Step 8 - Schema references detected: {detected_schema_refs}")

        # Step 9: Language normalization
        step9_input = current_text
        current_text, step9_changes, lang_normalized = self._normalize_language(current_text)
        steps.append({"step": "language_normalization", "input": step9_input, "output": current_text, "changes": step9_changes})
        preprocessing_logger.info(f"Step 9 - Language normalization: {step9_changes}")

        preprocessing_logger.info(f"Final processed text: {mask_feedback_text(current_text)}")
        preprocessing_logger.info("=== FEEDBACK PREPROCESSING COMPLETE ===")

        return {
            "original_text": feedback_text,
            "processed_text": current_text,
            "preprocessing_steps": steps,
            "detected_keywords": detected_keywords,
            "detected_schema_refs": detected_schema_refs,
            "language_normalized": lang_normalized,
            "vocabulary_source": vocab_source,
        }

    # ------------------------------------------------------------------
    # Text normalizers (Steps 1–5, 9)
    # ------------------------------------------------------------------

    def _normalize_unicode(self, text: str) -> Tuple[str, str]:
        normalized = unicodedata.normalize('NFKC', text)
        return normalized, f"Normalized {len(text)} chars to {len(normalized)} chars"

    def _normalize_whitespace(self, text: str) -> Tuple[str, str]:
        normalized = re.sub(r'\s+', ' ', text).strip()
        return normalized, "Collapsed whitespace, trimmed edges"

    def _segment_sentences(self, text: str) -> Tuple[str, str]:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        segmented = ' '.join(sentences)
        return segmented, f"Segmented into {len(sentences)} sentences"

    def _tokenize_text(self, text: str) -> Tuple[str, str]:
        tokens = text.split()
        return ' '.join(tokens), f"Tokenized into {len(tokens)} tokens"

    def _remove_punctuation(self, text: str) -> Tuple[str, str]:
        cleaned = re.sub(r'[\"\'\`\~\@\#\$\%\^\&\*\-\+\=\|\\\/]', ' ', text)
        return cleaned, "Removed non-critical punctuation"

    def _normalize_language(self, text: str) -> Tuple[str, str, bool]:
        normalized = text
        changes_made = []
        if "pls" in normalized:
            normalized = normalized.replace("pls", "please")
            changes_made.append("pls→please")
        if "thx" in normalized:
            normalized = normalized.replace("thx", "thanks")
            changes_made.append("thx→thanks")
        lang_normalized = len(changes_made) > 0
        changes = ", ".join(changes_made) if changes_made else "No normalization needed"
        return normalized, changes, lang_normalized

    # ------------------------------------------------------------------
    # Domain-aware helpers
    # ------------------------------------------------------------------

    def _plural_base(self, word: str) -> Optional[str]:
        """Return the singular form if *word* is a plural of a known term.

        Protects schema/table references (e.g. "orders", "payments") from
        being treated as typos by the fuzzy spelling stage.
        """
        vocab = self._active_vocab
        if word.endswith("ies") and len(word) > 3:
            base = word[:-3] + "y"
            if base in vocab:
                return base
        if word.endswith("es") and len(word) > 2:
            base = word[:-2]
            if base in vocab:
                return base
        if word.endswith("s") and not word.endswith("ss") and len(word) > 1:
            base = word[:-1]
            if base in vocab:
                return base
        return None

    def _detect_business_keywords(self, text: str) -> List[str]:
        """Detect business keywords in text (exact match or plural inflection).

        Uses the active vocabulary built from the domain pack when available,
        so terms like ``churn``, ``gross_sales``, ``slacompliance`` etc. are
        recognised without being hardcoded.
        """
        words = text.lower().split()
        detected: List[str] = []
        for word in words:
            if word in self._active_vocab:
                detected.append(word)
            else:
                base = self._plural_base(word)
                if base and base in self._active_vocab:
                    detected.append(base)
        return detected

    def _detect_schema_references(self, text: str) -> List[str]:
        """Detect schema references in text."""
        references: List[str] = []

        # table.column patterns
        references.extend(re.findall(r'\b(\w+\.\w+)\b', text))

        # Quoted identifiers
        for match in re.findall(r'"([^"]+)"|`([^`]+)`', text):
            if match[0]:
                references.append(match[0])
            elif match[1]:
                references.append(match[1])

        # SQL keywords followed by schema-like patterns
        for m in re.findall(
            r'\b(select|where|from|group\s+by|order\s+by)\s+'
            r'(\w+\.\w+|"[^"]+"|`[^`]+`)',
            text, re.IGNORECASE,
        ):
            references.append(f"{m[0]} {m[1]}")

        # Schema-related terms
        references.extend(
            re.findall(
                r'\b(table|column|field|attribute|join|relationship|foreign\s+key)\b',
                text, re.IGNORECASE,
            )
        )
        return references

    def _correct_spelling(self, text: str) -> Tuple[str, str]:
        """Spelling correction using domain vocabulary and fuzzy matching.

        Fuzzy matching is *disabled* for words that are valid inflections
        (plurals) of known vocabulary terms — "orders" is not a typo of
        "order"; correcting it would corrupt schema references that
        downstream extractors (DistilBERT BIO model) rely on.
        """
        from difflib import SequenceMatcher

        corrections = {
            "shouldnt": "should not",
            "cancelld": "cancelled",
            "inlucde": "include",
            "includ": "include",
            "exclued": "exclude",
            "wont": "will not",
            "cant": "cannot",
            "dont": "do not",
            "isnt": "is not",
            "wasnt": "was not",
        }

        vocab = self._active_vocab

        corrected = text
        changes_made: list = []

        # Stage 1: Hardcoded corrections
        for wrong, right in corrections.items():
            if wrong in corrected:
                corrected = corrected.replace(wrong, right)
                changes_made.append(f"{wrong}→{right}")

        # Stage 2: Fuzzy match unknown words against domain vocabulary
        words = corrected.split()
        fuzzy_corrections: Dict[str, str] = {}

        for word in words:
            word_lower = word.lower().rstrip('.,!?;:')

            # Skip if already in vocabulary
            if word_lower in vocab:
                continue

            # Skip valid plural inflections of domain terms
            if self._plural_base(word_lower):
                continue

            # Fuzzy match against vocabulary
            best_match: Optional[str] = None
            best_ratio = 0.0
            for vocab_term in vocab:
                ratio = SequenceMatcher(None, word_lower, vocab_term).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = vocab_term

            if best_ratio > 0.80 and best_match and best_match != word_lower:
                fuzzy_corrections[word_lower] = best_match
                changes_made.append(f"{word_lower}→{best_match} (fuzzy, {best_ratio:.1%})")

        for wrong, right in fuzzy_corrections.items():
            corrected = re.sub(rf'\b{wrong}\b', right, corrected, flags=re.IGNORECASE)

        changes = ", ".join(changes_made) if changes_made else "No corrections needed"
        return corrected, changes
