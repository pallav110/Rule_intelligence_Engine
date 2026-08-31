"""Feedback preprocessing service for normalizing and cleaning feedback text.

Performs step-by-step preprocessing with detailed logging:
1. Unicode normalization
2. Whitespace normalization
3. Sentence segmentation
4. Tokenization
5. Punctuation removal
6. Basic spelling correction
7. Business keyword preservation
8. Schema reference detection
9. Language normalization
"""

import re
import unicodedata
from typing import Dict, Any, List, Tuple
from app.logging_config import preprocessing_logger


class FeedbackPreprocessor:
    """Preprocess feedback text with detailed logging for each step."""

    def __init__(self):
        """Initialize preprocessor."""
        # Business keywords to preserve (domain-specific)
        self.business_keywords = {
            "revenue", "order", "customer", "product", "payment", "shipping",
            "invoice", "refund", "discount", "tax", "metric", "filter",
            "access", "rule", "calculation", "definition", "include", "exclude"
        }

        # Schema reference patterns
        # Match explicit schema references, not just SQL keywords
        self.schema_patterns = [
            r'\b(table|column|field|attribute)\b',
            r'\b(join|relationship|foreign\s+key)\b',
            # Match SQL keywords only when part of explicit SQL expressions
            r'\b(select|where|from|group\s+by|order\s+by)\s+(\w+\.\w+|\"[^\"]+\"|\`[^\`]+\`)',
            # Match table.column patterns
            r'\b(\w+\.\w+)\b',
            # Match quoted identifiers
            r'\"[^\"]+\"',
            r'\`[^\`]+\`'
        ]

    def preprocess(
        self,
        feedback_text: str,
        domain_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Complete preprocessing pipeline with step-by-step logging.

        Args:
            feedback_text: Raw feedback text
            domain_context: Optional domain context for business keywords

        Returns:
            {
                "original_text": str,
                "processed_text": str,
                "preprocessing_steps": [
                    {"step": str, "input": str, "output": str, "changes": str}
                ],
                "detected_keywords": [str],
                "detected_schema_refs": [str],
                "language_normalized": bool
            }
        """
        preprocessing_logger.info("=== FEEDBACK PREPROCESSING START ===")
        preprocessing_logger.info(f"Original feedback: {feedback_text}")

        steps = []
        current_text = feedback_text

        # Step 1: Unicode normalization
        step1_input = current_text
        current_text, step1_changes = self._normalize_unicode(current_text)
        steps.append({
            "step": "unicode_normalization",
            "input": step1_input,
            "output": current_text,
            "changes": step1_changes
        })
        preprocessing_logger.info(f"Step 1 - Unicode normalization: {step1_changes}")

        # Step 2: Whitespace normalization
        step2_input = current_text
        current_text, step2_changes = self._normalize_whitespace(current_text)
        steps.append({
            "step": "whitespace_normalization",
            "input": step2_input,
            "output": current_text,
            "changes": step2_changes
        })
        preprocessing_logger.info(f"Step 2 - Whitespace normalization: {step2_changes}")

        # Step 3: Sentence segmentation
        step3_input = current_text
        current_text, step3_changes = self._segment_sentences(current_text)
        steps.append({
            "step": "sentence_segmentation",
            "input": step3_input,
            "output": current_text,
            "changes": step3_changes
        })
        preprocessing_logger.info(f"Step 3 - Sentence segmentation: {step3_changes}")

        # Step 4: Tokenization
        step4_input = current_text
        current_text, step4_changes = self._tokenize_text(current_text)
        steps.append({
            "step": "tokenization",
            "input": step4_input,
            "output": current_text,
            "changes": step4_changes
        })
        preprocessing_logger.info(f"Step 4 - Tokenization: {step4_changes}")

        # Step 5: Punctuation removal
        step5_input = current_text
        current_text, step5_changes = self._remove_punctuation(current_text)
        steps.append({
            "step": "punctuation_removal",
            "input": step5_input,
            "output": current_text,
            "changes": step5_changes
        })
        preprocessing_logger.info(f"Step 5 - Punctuation removal: {step5_changes}")

        # Step 6: Basic spelling correction (moved earlier)
        step6_input = current_text
        current_text, step6_changes = self._correct_spelling(current_text)
        steps.append({
            "step": "spelling_correction",
            "input": step6_input,
            "output": current_text,
            "changes": step6_changes
        })
        preprocessing_logger.info(f"Step 6 - Spelling correction: {step6_changes}")

        # Step 7: Business keyword detection (after spelling correction)
        detected_keywords = self._detect_business_keywords(current_text)
        preprocessing_logger.info(f"Step 7 - Business keywords detected: {detected_keywords}")

        # Step 8: Schema reference detection
        detected_schema_refs = self._detect_schema_references(current_text)
        preprocessing_logger.info(f"Step 8 - Schema references detected: {detected_schema_refs}")

        # Step 9: Language normalization
        step9_input = current_text
        current_text, step9_changes, lang_normalized = self._normalize_language(current_text)
        steps.append({
            "step": "language_normalization",
            "input": step9_input,
            "output": current_text,
            "changes": step9_changes
        })
        preprocessing_logger.info(f"Step 9 - Language normalization: {step9_changes}")

        preprocessing_logger.info(f"Final processed text: {current_text}")
        preprocessing_logger.info("=== FEEDBACK PREPROCESSING COMPLETE ===")

        return {
            "original_text": feedback_text,
            "processed_text": current_text,
            "preprocessing_steps": steps,
            "detected_keywords": detected_keywords,
            "detected_schema_refs": detected_schema_refs,
            "language_normalized": lang_normalized
        }

    def _normalize_unicode(self, text: str) -> Tuple[str, str]:
        """Normalize unicode characters (NFKC form)."""
        normalized = unicodedata.normalize('NFKC', text)
        changes = f"Normalized {len(text)} chars to {len(normalized)} chars"
        return normalized, changes

    def _normalize_whitespace(self, text: str) -> Tuple[str, str]:
        """Normalize whitespace - collapse multiple spaces, trim."""
        # Replace multiple spaces with single space
        normalized = re.sub(r'\s+', ' ', text)
        # Trim leading/trailing whitespace
        normalized = normalized.strip()
        changes = f"Collapsed whitespace, trimmed edges"
        return normalized, changes

    def _segment_sentences(self, text: str) -> Tuple[str, str]:
        """Segment sentences (basic approach)."""
        # Simple sentence segmentation - split on common delimiters
        sentences = re.split(r'(?<=[.!?])\s+', text)
        segmented = ' '.join(sentences)
        changes = f"Segmented into {len(sentences)} sentences"
        return segmented, changes

    def _tokenize_text(self, text: str) -> Tuple[str, str]:
        """Tokenize text into words."""
        tokens = text.split()
        tokenized = ' '.join(tokens)
        changes = f"Tokenized into {len(tokens)} tokens"
        return tokenized, changes

    def _remove_punctuation(self, text: str) -> Tuple[str, str]:
        """Remove unnecessary punctuation."""
        # Remove common punctuation but preserve business-critical symbols
        cleaned = re.sub(r'[\"\'\`\~\@\#\$\%\^\&\*\-\+\=\|\\\/]', ' ', text)
        changes = "Removed non-critical punctuation"
        return cleaned, changes

    def _detect_business_keywords(self, text: str) -> List[str]:
        """Detect business keywords in text."""
        words = text.lower().split()
        detected = [word for word in words if word in self.business_keywords]
        return detected

    def _detect_schema_references(self, text: str) -> List[str]:
        """Detect schema references in text."""
        references = []

        # Pattern 1: Match table.column patterns
        table_column_matches = re.findall(r'\b(\w+\.\w+)\b', text)
        references.extend(table_column_matches)

        # Pattern 2: Match quoted identifiers
        quoted_matches = re.findall(r'\"([^\"]+)\"|\`([^\`]+)\`', text)
        for match in quoted_matches:
            # match is a tuple of (double_quoted, backtick_quoted)
            if match[0]:
                references.append(match[0])
            elif match[1]:
                references.append(match[1])

        # Pattern 3: Match SQL keywords only when followed by schema-like patterns
        sql_keyword_matches = re.findall(
            r'\b(select|where|from|group\s+by|order\s+by)\s+(\w+\.\w+|\"[^\"]+\"|\`[^\`]+\`)',
            text,
            re.IGNORECASE
        )
        for match in sql_keyword_matches:
            # match is a tuple of (keyword, identifier)
            references.append(f"{match[0]} {match[1]}")

        # Pattern 4: Match schema-related terms
        schema_term_matches = re.findall(r'\b(table|column|field|attribute|join|relationship|foreign\s+key)\b', text, re.IGNORECASE)
        references.extend(schema_term_matches)

        return references

    def _correct_spelling(self, text: str) -> Tuple[str, str]:
        """Basic spelling correction."""
        # Common corrections
        corrections = {
            "shouldnt": "should not",
            "cancelld": "cancelled",
            "wont": "will not",
            "cant": "cannot",
            "dont": "do not",
            "isnt": "is not",
            "wasnt": "was not"
        }

        corrected = text
        changes_made = []

        for wrong, right in corrections.items():
            if wrong in corrected:
                corrected = corrected.replace(wrong, right)
                changes_made.append(f"{wrong}→{right}")

        changes = ", ".join(changes_made) if changes_made else "No corrections needed"
        return corrected, changes

    def _normalize_language(self, text: str) -> Tuple[str, str, bool]:
        """Normalize conversational English and Hinglish."""
        # Convert common conversational patterns to standard form
        normalized = text
        changes_made = []

        # Example: "pls" -> "please"
        if "pls" in normalized:
            normalized = normalized.replace("pls", "please")
            changes_made.append("pls→please")

        # Example: "thx" -> "thanks"
        if "thx" in normalized:
            normalized = normalized.replace("thx", "thanks")
            changes_made.append("thx→thanks")

        lang_normalized = len(changes_made) > 0
        changes = ", ".join(changes_made) if changes_made else "No normalization needed"

        return normalized, changes, lang_normalized
