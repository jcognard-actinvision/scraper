from typing import Iterable, Optional

from bs4.element import Tag


def make_tag_remove_predicate(
    *,
    classes_any: Optional[Iterable[str]] = None,
    text_contains_any: Optional[Iterable[str]] = None,
):
    classes_any = set(classes_any or [])
    text_contains_any = list(text_contains_any or [])

    def _predicate(tag) -> bool:
        # Blindage total
        if tag is None or not isinstance(tag, Tag):
            return False

        # Test sur les classes
        if classes_any:
            try:
                tag_classes = set(tag.get("class") or [])
            except Exception:
                tag_classes = set()
            if tag_classes & classes_any:
                return True

        # Test sur le texte
        if text_contains_any:
            try:
                txt = (tag.get_text(strip=True) or "").lower()
            except Exception:
                txt = ""
            for needle in text_contains_any:
                if needle.lower() in txt:
                    return True

        return False

    return _predicate
