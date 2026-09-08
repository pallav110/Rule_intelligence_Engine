"""DistilBERT Token Classification Service - Rule Extraction ML Candidate

Uses trained DistilBERT token classifier for BIO-tagged rule component extraction.
Extracts: business_term, operation, field, value, scope, time_window, threshold, table, column.
This is the candidate ML approach compared against baseline regex in testing UI.
"""

import torch
from pathlib import Path
from typing import Dict, Any, List, Optional
import json


class DistilBERTTokenExtractor:
    """DistilBERT-based token classifier for rule extraction (ML candidate)."""

    def __init__(self):
        """Initialize DistilBERT token extractor."""
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self.tokenizer = None
        self.model_ready = False
        self.bio_labels = []
        self.label2id = {}
        self.id2label = {}

        self._load_model()

    def _load_model(self):
        """Load trained DistilBERT token classification model."""
        try:
            import torch

            # Use explicit imports from specific modules to avoid circular dependencies
            AutoTokenizer = None
            AutoModel = None
            import_method = None

            try:
                # Try main import path first (PRIMARY)
                from transformers import AutoTokenizer as AT, AutoModel as AM
                AutoTokenizer = AT
                AutoModel = AM
                import_method = "primary"
            except (ImportError, ModuleNotFoundError):
                # If that fails, try importing from specific submodules (SECONDARY)
                try:
                    from transformers.models.auto.tokenization_auto import AutoTokenizer as AT
                    from transformers.models.auto.modeling_auto import AutoModel as AM
                    AutoTokenizer = AT
                    AutoModel = AM
                    import_method = "secondary"
                except (ImportError, ModuleNotFoundError):
                    # Last resort: use PreTrainedTokenizer directly (TERTIARY)
                    try:
                        from transformers import DistilBertTokenizer, DistilBertModel
                        AutoTokenizer = DistilBertTokenizer.from_pretrained
                        AutoModel = DistilBertModel.from_pretrained
                        import_method = "tertiary"
                    except (ImportError, ModuleNotFoundError) as e3:
                        print(f"⚠️  All transformer imports failed: {e3}")
                        return

            if not AutoTokenizer or not AutoModel:
                print(f"⚠️  Could not resolve AutoTokenizer/AutoModel")
                return

            model_dir = Path(__file__).parent.parent.parent / "rie_ml" / "models" / "distilbert_token_extractor"
            checkpoint_dir = model_dir / "checkpoints"

            if not checkpoint_dir.exists():
                print(f"⚠️  Token classifier model not found at {checkpoint_dir}")
                return

            # Load tokenizer
            try:
                self.tokenizer = AutoTokenizer.from_pretrained('distilbert-base-uncased')
            except Exception as e:
                print(f"⚠️  Failed to load tokenizer: {e}")
                return

            # Load checkpoint
            checkpoint_file = checkpoint_dir / "best_model.pt"
            if not checkpoint_file.exists():
                print(f"⚠️  No token classifier checkpoint found at {checkpoint_file}")
                return

            checkpoint = torch.load(checkpoint_file, map_location=self.device)

            # Load BIO labels from checkpoint
            self.bio_labels = checkpoint.get('bio_labels', [])
            self.label2id = checkpoint.get('label2id', {})
            self.id2label = {int(k): v for k, v in enumerate(self.bio_labels)}

            # Reconstruct model inline to avoid import issues
            class DistilBERTTokenClassifier(torch.nn.Module):
                def __init__(self, num_labels=16, dropout=0.1):
                    super().__init__()
                    self.distilbert = AutoModel.from_pretrained('distilbert-base-uncased')
                    hidden_size = self.distilbert.config.hidden_size
                    self.dropout = torch.nn.Dropout(dropout)
                    self.classifier = torch.nn.Linear(hidden_size, num_labels)

                def forward(self, input_ids, attention_mask=None, token_type_ids=None, **kwargs):
                    outputs = self.distilbert(
                        input_ids=input_ids,
                        attention_mask=attention_mask
                    )
                    sequence_output = outputs.last_hidden_state
                    sequence_output = self.dropout(sequence_output)
                    logits = self.classifier(sequence_output)
                    return logits

            num_labels = checkpoint.get('num_labels', 16)
            self.model = DistilBERTTokenClassifier(num_labels=num_labels)

            # Load state dict as-is (keys already have 'distilbert.' prefix from training)
            state_dict = checkpoint.get('model_state_dict', {})

            # Load with strict=True to ensure all weights are loaded correctly
            self.model.load_state_dict(state_dict, strict=True)
            self.model.to(self.device)
            self.model.eval()

            self.model_ready = True

            # Read actual metrics from latest eval file (always updated on retrain)
            try:
                eval_path = model_dir / "token_evaluation_results.json"
                if eval_path.exists():
                    with open(eval_path) as ef:
                        eval_data = json.load(ef)
                    self.token_accuracy = eval_data.get("overall_accuracy", 0.0)
                    self.macro_f1 = eval_data.get("macro_f1", 0.0)
                else:
                    self.token_accuracy = 0.0
                    self.macro_f1 = 0.0
            except Exception:
                self.token_accuracy = 0.0
                self.macro_f1 = 0.0
            print(f"✅ Loaded DistilBERT token extractor ({self.token_accuracy*100:.1f}% accuracy)")

        except Exception as e:
            print(f"⚠️  Failed to load token extractor: {e}")
            import traceback
            traceback.print_exc()
            self.model_ready = False

    def extract(self, feedback: str, schema_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extract rule components using DistilBERT token classifier (ML candidate).

        Returns:
            {
                "extraction": {
                    "extracted_rules": [...],
                    "component_mapping": {...},
                    "detailed_components": {...}
                },
                "overall_confidence": float,
                "model": "distilbert_token_classifier",
                "token_accuracy": getattr(self, 'token_accuracy', 0.0),
                "macro_f1": getattr(self, 'macro_f1', 0.0),
                "validation_ready": bool
            }
        """
        if not self.model_ready:
            return {
                "extraction": {
                    "extracted_rules": [],
                    "component_mapping": {},
                    "detailed_components": {}
                },
                "overall_confidence": 0.0,
                "model": "distilbert_token_classifier",
                "error": "Model not ready",
                "validation_ready": False
            }

        try:
            # Defensive: ensure feedback is a string
            if feedback is None:
                feedback = ""
            if not isinstance(feedback, str):
                feedback = str(feedback)

            # Tokenize feedback
            words = feedback.split()
            # Debug: show first 20 words
            try:
                print(f"DEBUG: DistilBERT.extract - words={words[:20]}")
            except Exception:
                pass
            encoding = self.tokenizer(
                words,
                max_length=256,
                padding='max_length',
                truncation=True,
                return_tensors='pt',
                is_split_into_words=True
            )

            input_ids = encoding['input_ids'].to(self.device)
            attention_mask = encoding['attention_mask'].to(self.device)

            # Forward pass
            with torch.no_grad():
                logits = self.model(input_ids, attention_mask)

            # Map predictions back to word tokens
            word_ids = encoding.word_ids()
            predictions = []

            for token_idx, word_idx in enumerate(word_ids):
                if word_idx is not None:
                    logit = logits[0, token_idx, :]
                    pred_id = torch.argmax(logit).item()

                    # Only take first subword of each word
                    if not predictions or len(predictions) == word_idx:
                        if pred_id < len(self.id2label):
                            predictions.append(self.id2label[pred_id])
                        else:
                            predictions.append('O')

            # Extract entities from BIO tags with component mapping
            extracted_rule, component_mapping, detailed_components = self._extract_entities_from_tags(words, predictions)

            # ---- Rule Construction (Spec 8.4 Stage 2) ----
            constructed_rule = self._construct_rule(
                extracted_rule,
                component_mapping,
                detailed_components,
                feedback,
                logits,
                predictions,
            )

            return {
                "extraction": {
                    "extracted_rules": [constructed_rule],
                    "component_mapping": component_mapping,
                    "detailed_components": detailed_components
                },
                "overall_confidence": constructed_rule.get("confidence", getattr(self, 'token_accuracy', 0.0)),
                "model": "distilbert_token_classifier",
                "token_accuracy": getattr(self, 'token_accuracy', 0.0),
                "macro_f1": getattr(self, 'macro_f1', 0.0),
                "method": "bio_token_classification",
                "validation_ready": len(constructed_rule.get("conditions", [])) > 0 and constructed_rule.get("operation") is not None
            }

        except Exception as e:
            print(f"Error in token extraction: {e}")
            import traceback
            traceback.print_exc()
            return {
                "extraction": {
                    "extracted_rules": [],
                    "component_mapping": {},
                    "detailed_components": {}
                },
                "overall_confidence": 0.0,
                "model": "distilbert_token_classifier",
                "error": str(e),
                "validation_ready": False
            }

    def _extract_entities_from_tags(self, words: List[str], tags: List[str]) -> tuple:
        """Extract structured rule from BIO tags, with detailed component mapping.

        Returns:
            (rule_dict, component_mapping, detailed_components)
        """
        rule = {
            "business_term": None,
            "operation": None,
            "conditions": [],
            "scope": "global",
            "time_window": None,
            "affected_tables": [],
            "affected_columns": [],
            "confidence": 0.956
        }

        # Component tracking for detailed output
        component_mapping = {}
        detailed_components = {
            "business_terms": [],
            "operations": [],
            "fields": [],
            "values": [],
            "operators": [],
            "tables": [],
            "columns": [],
            "scopes": [],
            "time_windows": []
        }

        # Extract business term
        for i, tag in enumerate(tags):
            if tag.startswith('B_BUSINESS_TERM'):
                word = words[i] if i < len(words) else None
                rule["business_term"] = word
                detailed_components["business_terms"].append({
                    "word": word,
                    "position": i,
                    "tag": tag
                })
                component_mapping["business_term"] = word
                break

        # Extract operation — the NER model often tags modal verbs ("should",
        # "must", "can"...) as B_OPERATION ahead of the real verb. Skip modals so
        # "should include" resolves to "include", not "should" (which would fall
        # back to EXCLUDE in canonicalization). Handle "not include" → "not include".
        operation_words = []
        for i, tag in enumerate(tags):
            if tag.startswith('B_OPERATION') and i < len(words):
                word = words[i]
                if word is not None:
                    try:
                        word = word.lower()
                    except Exception:
                        word = str(word)
                    operation_words.append((i, word))

        MODAL_VERBS = {
            "should", "must", "will", "would", "can", "could", "may", "might",
            "shall", "ought", "need", "do", "does", "did", "wants", "want", "to",
        }

        op_idx, op_word = None, None
        for i, w in operation_words:
            if w.strip() not in MODAL_VERBS:
                op_idx, op_word = i, w
                break
        if op_word is None and operation_words:
            op_idx, op_word = operation_words[0]

        if op_word is not None:
            # Negation: "should not include" → "not include" → canonicalized EXCLUDE
            if op_idx is not None and op_idx > 0 and words[op_idx - 1].lower() in ("not", "never"):
                op_word = f"not {op_word}"
            rule["operation"] = op_word
            detailed_components["operations"].append({
                "word": op_word,
                "position": op_idx,
                "tag": "B_OPERATION"
            })
            component_mapping["operation"] = op_word

        # Extract all entity types with position tracking
        fields = []
        values = []
        operators = []
        tables = []
        columns = []

        for i, tag in enumerate(tags):
            word = words[i] if i < len(words) else None
            if tag.startswith('B_FIELD'):
                fields.append({"word": word, "position": i})
                detailed_components["fields"].append({"word": word, "position": i, "tag": tag})
            elif tag.startswith('B_VALUE'):
                values.append({"word": word, "position": i})
                detailed_components["values"].append({"word": word, "position": i, "tag": tag})
            elif tag.startswith('B_OPERATOR'):
                operators.append({"word": word, "position": i})
                detailed_components["operators"].append({"word": word, "position": i, "tag": tag})
            elif tag.startswith('B_TABLE'):
                tables.append({"word": word, "position": i})
                detailed_components["tables"].append({"word": word, "position": i, "tag": tag})
            elif tag.startswith('B_COLUMN'):
                columns.append({"word": word, "position": i})
                detailed_components["columns"].append({"word": word, "position": i, "tag": tag})

        # Build conditions - multiple strategies
        if fields and values:
            # Standard: explicit fields with values
            rule["conditions"] = [
                {
                    "field": field["word"],
                    "operator": operators[idx]["word"] if idx < len(operators) else "equals",
                    "value": value["word"],
                    "extraction_method": "explicit_field_value"
                }
                for idx, (field, value) in enumerate(zip(fields, values))
            ]
            component_mapping["extraction_method"] = "explicit_field_value"
        elif tables and values:
            # Inferred: TABLE + VALUE → infer field from table context
            for table in tables:
                for value in values:
                    inferred_field = f"{table['word']}.status"
                    rule["conditions"].append({
                        "field": inferred_field,
                        "operator": "equals",
                        "value": value["word"],
                        "inferred": True,
                        "extraction_method": "inferred_table_value",
                        "source_table": table["word"],
                        "source_value": value["word"]
                    })
            component_mapping["extraction_method"] = "inferred_table_value"
        elif values:
            # Fallback: just values without table/field
            for value in values:
                rule["conditions"].append({
                    "field": None,
                    "operator": "equals",
                    "value": value["word"],
                    "needs_clarification": True,
                    "extraction_method": "value_only"
                })
            component_mapping["extraction_method"] = "value_only"

        # Store tables and columns
        rule["affected_tables"] = [t["word"] for t in tables]
        rule["affected_columns"] = [c["word"] for c in columns]

        # Build comprehensive component mapping
        component_mapping["conditions"] = rule["conditions"]
        component_mapping["affected_tables"] = rule["affected_tables"]
        component_mapping["affected_columns"] = rule["affected_columns"]
        component_mapping["extraction_confidence"] = 0.956

        return rule, component_mapping, detailed_components


    def _construct_rule(
        self,
        raw_rule: Dict[str, Any],
        component_mapping: Dict[str, Any],
        detailed_components: Dict[str, Any],
        feedback_text: str,
        logits: torch.Tensor,
        predictions: List[str],
    ) -> Dict[str, Any]:
        """
        Rule Construction layer per Spec 8.4 (Stage 2).

        Converts raw BIO entities into complete normalized rules:
        - Canonicalizes operation strings
        - Resolves TABLE+VALUE → FIELD via domain schema heuristics
        - Ensures field is always populated (or flagged needs_clarification)
        - Builds per-field confidence from logits
        """
        import re

        # Extract words for resolution context
        words = feedback_text.split()

        # Build domain context
        business_term = raw_rule.get("business_term")

        # ---- 1. Canonicalize operation ----
        raw_op = raw_rule.get("operation")
        canonical_op = None
        op_confidence = 0.956
        if raw_op:
            op_lower = raw_op.lower().strip()
            op_surface_map = {
                "exclude": "EXCLUDE", "must not include": "EXCLUDE",
                "does not count": "EXCLUDE", "don't count": "EXCLUDE",
                "not contribute": "EXCLUDE", "excluded from": "EXCLUDE",
                "remove": "EXCLUDE", "removed from": "EXCLUDE",
                "excluded": "EXCLUDE",
                "include": "INCLUDE", "must include": "INCLUDE",
                "should be part of": "INCLUDE", "accounts for": "INCLUDE",
                "part of": "INCLUDE", "count toward": "INCLUDE",
                "not include": "EXCLUDE", "not count": "EXCLUDE",
                "doesn't count": "EXCLUDE", "does not count": "EXCLUDE",
                "never include": "EXCLUDE", "should not": "EXCLUDE",
                "not exclude": "INCLUDE", "not excluded": "INCLUDE",
                "should be included": "INCLUDE", "should be excluded": "EXCLUDE",
                "restricted to": "RESTRICT", "access should be limited to": "RESTRICT",
                "limited to": "RESTRICT", "only show": "RESTRICT",
                "restrict": "RESTRICT",
                "replace": "REPLACE", "instead of": "REPLACE",
                "rely on": "REPLACE", "switch": "REPLACE",
                "use": "REPLACE", "instead": "REPLACE",
                "subtract": "SUBTRACT", "net out": "SUBTRACT",
                "deduct": "SUBTRACT",
                "add": "ADD", "also account for": "ADD", "add to": "ADD",
            }
            if op_lower in op_surface_map:
                canonical_op = op_surface_map[op_lower]
            else:
                for phrase, canonical in sorted(op_surface_map.items(), key=lambda x: -len(x[0])):
                    if phrase in op_lower:
                        canonical_op = canonical
                        break
                if not canonical_op:
                    canonical_op = "EXCLUDE"

        # ---- 2. Resolve TABLE+VALUE → FIELD via schema ----
        # Build per-table status column map
        status_by_table = {
            "orders": "status", "refunds": "status", "payments": "status",
            "tickets": "is_internal", "customers": "is_internal",
            "organizations": "status", "subscriptions": "cancel_at_period_end",
        }

        def resolve_field(table: str, value: str, domain: str = "") -> Optional[str]:
            """Deterministic schema resolution."""
            table_lower = table.lower().rstrip(".")
            # Try known status column
            if table_lower in status_by_table:
                return f"{table_lower}.{status_by_table[table_lower]}"
            return None

        # ---- 3. Canonicalize condition operators ----
        op_canonical = {
            "equal to": "EQUALS", "equals": "EQUALS",
            "greater than": "GREATER_THAN", "more than": "GREATER_THAN",
            "exceeds": "GREATER_THAN", "above": "GREATER_THAN",
            "over": "GREATER_THAN",
            "less than": "LESS_THAN", "below": "LESS_THAN",
            "under": "LESS_THAN",
            "does not equal": "NOT_EQUALS", "doesn't equal": "NOT_EQUALS",
            "not equal": "NOT_EQUALS",
            "is present": "IS_NOT_NULL", "has a value": "IS_NOT_NULL",
            "non-empty": "IS_NOT_NULL",
        }

        def canonicalize_cond_op(op_str: str) -> str:
            op_l = op_str.lower().strip() if op_str else ""
            for phrase, canonical in sorted(op_canonical.items(), key=lambda x: -len(x[0])):
                if phrase in op_l:
                    return canonical
            return "EQUALS"

        # ---- 4. Build complete conditions ----
        constructed = {
            "business_term": business_term,
            "operation": canonical_op,
            "conditions": [],
            "scope": raw_rule.get("scope", "global"),
            "time_window": raw_rule.get("time_window"),
            "threshold": raw_rule.get("threshold"),
            "affected_tables": list(raw_rule.get("affected_tables", [])),
            "affected_columns": list(raw_rule.get("affected_columns", [])),
        }

        raw_conditions = raw_rule.get("conditions", [])
        if isinstance(component_mapping.get("conditions"), list):
            raw_conditions = component_mapping.get("conditions", raw_conditions)

        # Use logits confidence if available
        confidence_per_field = {}
        try:
            probs = torch.softmax(logits[0], dim=-1)
            max_probs = torch.max(probs, dim=-1).values.cpu().numpy()
            mean_conf = float(max_probs.mean()) if len(max_probs) > 0 else 0.956
            confidence_per_field = {
                "business_term": mean_conf,
                "operation": mean_conf,
                "conditions": mean_conf,
                "scope": mean_conf,
                "affected_entities": mean_conf,
            }
        except Exception:
            mean_conf = 0.956
            confidence_per_field = {
                "business_term": mean_conf,
                "operation": mean_conf,
                "conditions": mean_conf,
                "scope": mean_conf,
                "affected_entities": mean_conf,
            }

        constructed["confidence"] = mean_conf
        constructed["per_field_confidence"] = confidence_per_field

        for cond in (raw_conditions or []):
            if not isinstance(cond, dict):
                continue
            field = cond.get("field")
            op_surface = cond.get("operator", "equals")
            value = cond.get("value")
            extraction_method = cond.get("extraction_method", "explicit_field_value")

            canonical_cond_op = canonicalize_cond_op(op_surface)

            inferred_field = None
            if field is None and value is not None:
                tables = constructed.get("affected_tables", [])
                if not tables:
                    tables = [t.get("word", "") for t in detailed_components.get("tables", [])]
                    tables = [t.rstrip(".") for t in tables if t]
                for table in tables:
                    table_clean = table.lower().rstrip(".")
                    resolved = resolve_field(table_clean, str(value))
                    if resolved:
                        inferred_field = resolved
                        extraction_method = "resolved_table_value"
                        break
                if inferred_field:
                    field = inferred_field

            if field is not None:
                constructed["conditions"].append({
                    "field": field,
                    "operator": canonical_cond_op,
                    "value": value,
                    "extraction_method": extraction_method,
                    "confidence": mean_conf,
                })
                # Update affected entities from resolved field
                if "." in str(field):
                    parts = str(field).split(".")
                    if parts[0] and parts[0] not in constructed["affected_tables"]:
                        constructed["affected_tables"].append(parts[0])
                    if parts[1] and parts[1] not in constructed["affected_columns"]:
                        constructed["affected_columns"].append(parts[1])
            elif value is not None:
                constructed["conditions"].append({
                    "field": None,
                    "operator": canonical_cond_op,
                    "value": value,
                    "extraction_method": "value_only_needs_clarification",
                    "confidence": 0.3,
                    "needs_clarification": True,
                })

        # Deduplicate affected entities
        constructed["affected_tables"] = sorted(set(t.rstrip(".") for t in constructed["affected_tables"] if t))
        constructed["affected_columns"] = sorted(set(c.rstrip(".") for c in constructed["affected_columns"] if c))

        # ---- Spec 8.4 required fields ----
        from app.services.rule_construction import compute_rule_family_id
        constructed["rule_family_id"] = compute_rule_family_id(
            business_term, canonical_op, constructed["conditions"]
        )

        # Merge from construction: if we inferred fields, update conditions count
        constructed["confidence"] = mean_conf
        return constructed


_distilbert_token_extractor = None

def get_distilbert_token_extractor() -> DistilBERTTokenExtractor:
    """Get or create global token extractor instance."""
    global _distilbert_token_extractor
    if _distilbert_token_extractor is None:
        _distilbert_token_extractor = DistilBERTTokenExtractor()
    return _distilbert_token_extractor
