"""
Deduplication state manager.
Tracks seen item IDs per source, auto-expires entries after 7 days.
State is persisted to state/seen_items.json and committed to git by GitHub Actions.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

STATE_FILE = Path("state/seen_items.json")
EXPIRY_DAYS = 7

# Sources tracked
SOURCES = ["tweets", "podcasts", "blogs", "github", "reddit", "hackernews"]


class SeenItemsState:
    def __init__(self, state_file: Path = STATE_FILE):
        self.state_file = state_file
        self._state: Dict[str, Dict[str, str]] = {s: {} for s in SOURCES}
        self._loaded = False

    def load(self):
        """Load state from disk. Safe to call even if file doesn't exist."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    data = json.load(f)
                for source in SOURCES:
                    self._state[source] = data.get(source, {})
                total = sum(len(v) for v in self._state.values())
                logger.info(f"Loaded dedup state: {total} known items")
            except Exception as e:
                logger.warning(f"Could not load state file, starting fresh: {e}")
                self._state = {s: {} for s in SOURCES}
        else:
            logger.info("No state file found, starting fresh")
        self._loaded = True

    def is_seen(self, item_id: str, source: str) -> bool:
        """Return True if this item has been processed before."""
        if not self._loaded:
            self.load()
        return item_id in self._state.get(source, {})

    def mark_seen(self, item_id: str, source: str):
        """Mark an item as processed."""
        if source not in self._state:
            self._state[source] = {}
        self._state[source][item_id] = datetime.now(tz=timezone.utc).isoformat()

    def mark_seen_batch(self, items, source: str, id_field: str = "id"):
        """Mark a list of dicts as seen."""
        for item in items:
            item_id = item.get(id_field) or item.get("url") or item.get("title", "")
            if item_id:
                self.mark_seen(str(item_id), source)

    def filter_unseen(self, items: list, source: str, id_field: str = "id") -> list:
        """Return only items not yet seen. Does NOT mark them — call mark_seen_batch after processing."""
        if not self._loaded:
            self.load()
        unseen = []
        for item in items:
            item_id = str(item.get(id_field) or item.get("url") or item.get("title", ""))
            if not self.is_seen(item_id, source):
                unseen.append(item)
        skipped = len(items) - len(unseen)
        if skipped:
            logger.info(f"Dedup [{source}]: skipped {skipped} already-seen items, kept {len(unseen)}")
        return unseen

    def cleanup_expired(self):
        """Remove entries older than EXPIRY_DAYS to keep the file small."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=EXPIRY_DAYS)
        total_removed = 0
        for source in SOURCES:
            before = len(self._state[source])
            self._state[source] = {
                k: v for k, v in self._state[source].items()
                if datetime.fromisoformat(v) > cutoff
            }
            total_removed += before - len(self._state[source])
        if total_removed:
            logger.info(f"Dedup cleanup: removed {total_removed} expired entries")

    def save(self):
        """Write state to disk."""
        self.cleanup_expired()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self._state, f, indent=2)
        total = sum(len(v) for v in self._state.values())
        logger.info(f"Saved dedup state: {total} items to {self.state_file}")
