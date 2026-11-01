"""System One decision model package.

Phase 1 prototype: multi-lingual, Laya-class (~421M ModernBERT backbone)
System One decision engine. Outputs only structured primitives — Choice,
Score, Noul — never free text. Synthetic-only, deny-by-default, no PHI.
"""

from __future__ import annotations

__all__ = [
    "encoder",
    "decision_heads",
    "rlcd",
    "training_pipeline",
]
