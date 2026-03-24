"""Re-export MatchingEngine from services for backward compatibility."""

from src.services.bank.matching_engine import MatchingEngine

__all__ = ["MatchingEngine"]
