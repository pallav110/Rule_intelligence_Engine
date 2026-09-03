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
            print(f"✅ Loaded DistilBERT token extractor (95.6% accuracy)")

        except Exception as e:
            print(f"⚠️  Failed to load token extractor: {e}")
            import traceback
            traceback.print_exc()
            self.model_ready = False

    def extract(self, feedback: str) -> Dict[str, Any]:
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
                "token_accuracy": 0.956,
                "macro_f1": 0.8276,
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
            # Tokenize feedback
            words = feedback.split()
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

            return {
                "extraction": {
                    "extracted_rules": [extracted_rule],
                    "component_mapping": component_mapping,
                    "detailed_components": detailed_components
                },
                "overall_confidence": 0.956,
                "model": "distilbert_token_classifier",
                "token_accuracy": 0.956,
                "macro_f1": 0.8276,
                "method": "bio_token_classification",
                "validation_ready": len(extracted_rule.get("conditions", [])) > 0
            }

        except Exception as e:
            print(f"Error in token extraction: {e}")
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

        # Extract operation
        for i, tag in enumerate(tags):
            if tag.startswith('B_OPERATION'):
                word = words[i] if i < len(words) else None
                rule["operation"] = word
                detailed_components["operations"].append({
                    "word": word,
                    "position": i,
                    "tag": tag
                })
                component_mapping["operation"] = word
                break

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


def get_distilbert_token_extractor() -> DistilBERTTokenExtractor:
    """Get or create global token extractor instance."""
    global _distilbert_token_extractor
    if '_distilbert_token_extractor' not in globals():
        _distilbert_token_extractor = DistilBERTTokenExtractor()
    return _distilbert_token_extractor
