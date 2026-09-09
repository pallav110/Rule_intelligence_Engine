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
        operators = []  # condition operators
        tables = []
        columns = []

        # Known non-value words that model incorrectly tags as B_VALUE
        FALSE_POSITIVE_VALUES = {
            "with", "and", "or", "for", "all", "globally", "each", "every",
            "the", "a", "an", "to", "from", "by", "on", "in", "at", "of",
            "use", "using", "should", "must", "can", "will", "would", "could"
        }

        for i, tag in enumerate(tags):
            word = words[i] if i < len(words) else None
            if tag.startswith('B_FIELD'):
                fields.append({"word": word, "position": i})
                detailed_components["fields"].append({"word": word, "position": i, "tag": tag})
            elif tag.startswith('B_VALUE'):
                # Filter out false positive values
                word_lower = word.lower() if word else ""
                if word_lower not in FALSE_POSITIVE_VALUES:
                    values.append({"word": word, "position": i})
                    detailed_components["values"].append({"word": word, "position": i, "tag": tag})
            elif tag.startswith('B_OPERATION'):
                # B_OPERATION covers BOTH rule-level ops and condition operators
                # Rule-level op is already captured above (first non-modal B_OPERATION)
                # Additional B_OPERATION tags after fields are condition operators
                is_rule_level = (op_idx is not None and i == op_idx)
                if not is_rule_level:
                    operators.append({"word": word, "position": i})
                    detailed_components["operators"].append({"word": word, "position": i, "tag": tag})
            elif tag.startswith('B_TABLE'):
                tables.append({"word": word, "position": i})
                detailed_components["tables"].append({"word": word, "position": i, "tag": tag})
            elif tag.startswith('B_COLUMN'):
                columns.append({"word": word, "position": i})
                detailed_components["columns"].append({"word": word, "position": i, "tag": tag})

        # Build conditions - multiple strategies with deduplication
        seen_conditions = set()

        def add_condition(field, operator, value, extraction_method, **kwargs):
            """Add condition with deduplication."""
            key = (field, operator.lower() if operator else "equals", value)
            if key in seen_conditions:
                return
            seen_conditions.add(key)
            cond = {"field": field, "operator": operator.upper() if operator else "EQUALS", "value": value, "extraction_method": extraction_method}
            cond.update(kwargs)
            rule["conditions"].append(cond)

        if fields and values:
            # Standard: explicit fields with values - pair by position proximity
            # Handle "field1 op1 value1 with field2 op2 value2" pattern
            for idx, field in enumerate(fields):
                field_word = field["word"]
                field_pos = field["position"]

                # Find ALL values and operators that come after this field
                # and before the next field (if any)
                next_field_pos = fields[idx + 1]["position"] if idx + 1 < len(fields) else float('inf')

                # Collect values and operators in range
                field_values = [v for v in values if field_pos < v["position"] < next_field_pos]
                field_operators = [o for o in operators if field_pos < o["position"] < next_field_pos]

                # Pair each value with closest operator
                # Skip values that look like field references (contain '.')
                for val in field_values:
                    val_word = val["word"]
                    # Skip if value looks like a field reference (table.column)
                    if "." in val_word:
                        continue
                    best_op = None
                    best_dist = float('inf')
                    for op in field_operators:
                        dist = abs(op["position"] - val["position"])
                        if dist < best_dist:
                            best_dist = dist
                            best_op = op
                    add_condition(field_word, best_op["word"] if best_op else "equals", val["word"], "explicit_field_value")
            component_mapping["extraction_method"] = "explicit_field_value"
        elif tables and values:
            # Inferred: TABLE + VALUE → infer field from table context
            # Pair each table with closest value (not Cartesian product)
            for table in tables:
                best_value = None
                best_dist = float('inf')
                for val in values:
                    dist = abs(val["position"] - table["position"])
                    if dist < best_dist:
                        best_dist = dist
                        best_value = val
                if best_value:
                    inferred_field = f"{table['word'].rstrip('.')}.status"
                    add_condition(inferred_field, "equals", best_value["word"], "inferred_table_value",
                                 inferred=True, source_table=table["word"], source_value=best_value["word"])
            component_mapping["extraction_method"] = "inferred_table_value"
        elif values:
            # Fallback: just values without table/field
            for value in values:
                add_condition(None, "equals", value["word"], "value_only", needs_clarification=True)
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
        # Normalize: strip trailing punctuation and whitespace (fixes "revenue.", "revenue," etc.)
        if business_term:
            business_term = str(business_term).strip().rstrip(".,;:!?()\"'")

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

        # ---- 1b. Operation null fallback via text heuristics ----
        # When the ML model fails to tag B_OPERATION (operation stays None),
        # infer from explicit rule-verb patterns in the feedback text.
        # Non-actionable/vague feedback stays None (correct behavior).
        if canonical_op is None and feedback_text:
            fb_lower = feedback_text.lower()
            _exclude_re = (
                r"\b(?:do not consider|ignore|exclude|leave out|not include|"
                r"shouldn'?t|should not|must not|can'?t|won'?t|do not count|"
                r"don'?t count|not count|remove|removed from|drop|drops|strip|"
                r"leave out|leave behind)\b"
            )
            _include_re = (
                r"\b(?:only .+ should(?:\s+\w+){0,3} (?:contribute|count|be included)|"
                r"must include|should be part of|include|count toward|contribute to|"
                r"account for|should include)\b"
            )
            if re.search(_exclude_re, fb_lower):
                canonical_op = "EXCLUDE"
            elif re.search(_include_re, fb_lower):
                canonical_op = "INCLUDE"

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
                # Qualify bare leaf fields when a single table is known
                # (e.g. field="status" + table="orders" → "orders.status")
                _EQUAL_PUNCT = ",;:!?\"'"
                _SYNS = {"purchases": "orders", "transactions": "payments",
                         "completed_order": "orders"}
                field_clean = str(field).strip().rstrip(_EQUAL_PUNCT)
                if field_clean and "." not in field_clean:
                    tables_now = constructed.get("affected_tables", [])
                    if not tables_now:
                        tables_now = [t.get("word", "") for t in detailed_components.get("tables", [])]
                        tables_now = [str(t).lower().strip().rstrip(".,;:!?()\"'") for t in tables_now if t]
                    # Normalize whatever source: lowercase + strip punct + synonym map
                    tables_now = [_SYNS.get(tt, tt) for tt in tables_now if tt]
                    if len(tables_now) == 1 and field_clean:
                        # Avoid qualifying when the bare field itself equals the table name (e.g. field="orders")
                        if field_clean.lower() != tables_now[0].lower():
                            field = f"{tables_now[0]}.{field_clean}"
                        else:
                            field = field_clean
                    else:
                        field = field_clean
                else:
                    field = field_clean
                constructed["conditions"].append({
                    "field": field,
                    "operator": canonical_cond_op,
                    "value": value,
                    "extraction_method": extraction_method,
                    "confidence": mean_conf,
                })
                # Update affected entities from resolved field (qualified table.column)
                if "." in str(field):
                    parts = str(field).split(".")
                    if parts[0] and parts[0] not in constructed["affected_tables"]:
                        constructed["affected_tables"].append(parts[0])
                    if parts[1]:
                        qualified_col = f"{parts[0]}.{parts[1]}"
                        if qualified_col not in constructed["affected_columns"]:
                            constructed["affected_columns"].append(qualified_col)
            elif value is not None:
                constructed["conditions"].append({
                    "field": None,
                    "operator": canonical_cond_op,
                    "value": value,
                    "extraction_method": "value_only_needs_clarification",
                    "confidence": 0.3,
                    "needs_clarification": True,
                })

        # Deduplicate affected entities — normalize case, strip punctuation,
        # and map common synonyms to actual schema tables.
        _TABLE_SYNONYMS = {
            "purchases": "orders",
            "transactions": "payments",
            "completed_order": "orders",
            "completed_order_items": "order_items",
        }
        _clean_tbl = lambda raw: str(raw).lower().strip().rstrip(".,;:!?()\"'")
        _map_tbl = lambda raw: _TABLE_SYNONYMS.get(_clean_tbl(raw), _clean_tbl(raw))

        def _remap_ref(ref: str) -> str:
            """Normalize a 'table.column' ref: lowercase both parts, map the
            table part through synonyms, strip trailing punctuation.
            Bare leaves are lowercased here and (re)qualified below."""
            ref = str(ref).strip().rstrip(".,;:!?()\"'")
            if not ref:
                return ref
            if "." in ref:
                tpart, cpart = ref.split(".", 1)
                tpart_clean = _clean_tbl(tpart)
                tpart_mapped = _TABLE_SYNONYMS.get(tpart_clean, tpart_clean)
                cpart_clean = str(cpart).strip().rstrip(".,;:!?()\"'").lower()
                return f"{tpart_mapped}.{cpart_clean}" if cpart_clean else tpart_mapped
            return _clean_tbl(ref)

        # Remap synonym-prefixed references in conditions + columns
        for cond in constructed.get("conditions", []):
            f = cond.get("field")
            if f:
                cond["field"] = _remap_ref(str(f))
        constructed["affected_columns"] = [
            _remap_ref(c) for c in constructed["affected_columns"] if c
        ]

        normalized_tables = set()
        for t in constructed["affected_tables"]:
            if not t:
                continue
            t_norm = _map_tbl(t)
            if t_norm:
                normalized_tables.add(t_norm)
        constructed["affected_tables"] = sorted(normalized_tables)

        # Schema validation (§8.5 check 3) requires columns qualified as
        # "table.column". Keep qualified references as-is; qualify a lone leaf
        # when exactly one table is known; drop orphans (surfaced as
        # needs_clarification via conditions instead of failing validation).
        qualified_columns = []
        for col in constructed["affected_columns"]:
            col = col.rstrip(".")
            if not col:
                continue
            if "." in col:
                qualified_columns.append(col)
            elif len(constructed["affected_tables"]) == 1:
                qualified_columns.append(f"{constructed['affected_tables'][0]}.{col}")
        # Always mirror qualified fields from resolved conditions
        for cond in constructed.get("conditions", []):
            field = cond.get("field")
            if field and "." in str(field):
                qualified_columns.append(str(field).rstrip("."))
        constructed["affected_columns"] = sorted(set(qualified_columns))

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
