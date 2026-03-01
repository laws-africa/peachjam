import json
import logging
import os

from openai import OpenAI

from peachjam.models.settings import pj_settings

log = logging.getLogger(__name__)


class FlynoteLLMMapper:
    """Uses OpenAI to clean up duplicate/messy flynote taxonomy topics.

    Three-phase approach:
      Phase 1 — Within-batch dedup: find obvious duplicates (casing, plurals, etc).
      Phase 2 — Cross-batch reconciliation: every batch sees the full list of
                canonical names found so far, so "admin law" in batch 5 gets
                matched to "Administrative law" found in batch 1.
      Phase 3 — Rename suggestions: topics that survived dedup but have poor
                names get LLM-suggested improvements (e.g. "stealing money" →
                "Theft").
    """

    MODEL = "gpt-4o"

    PHASE1_PROMPT = (
        "You are a legal taxonomy deduplication expert. You will receive a list of "
        "taxonomy topic names (with their IDs) from a legal database.\n\n"
        "Your job is to find GROUPS of topics that are TRUE duplicates of each other. "
        "Duplicates include:\n"
        "- Different casing: 'Administrative law' vs 'administrative law'\n"
        "- Singular vs plural: 'Estate' vs 'Estates'\n"
        "- Extra/missing spaces or punctuation\n"
        "- Slight spelling variations of the SAME concept\n"
        "- Abbreviations vs full names: 'Admin law' vs 'Administrative law'\n"
        "- Semantically identical phrases: 'right to a fair hearing' vs "
        "'right to fair trial' vs 'fair hearing rights'\n\n"
        "CRITICAL — these are NOT duplicates (do NOT group them):\n"
        "- A broad topic and a narrower subtopic: 'Administrative law' and "
        "'Administrative justice (s33)' are DIFFERENT topics\n"
        "- Topics that share a prefix but refer to different concepts: "
        "'Administrative law' vs 'Administrative discretion' vs "
        "'Administrative action' are all DISTINCT\n"
        "- Topics with specific section references: 'Prescription (s11)' and "
        "'Prescription' may be related but are different entries\n"
        "- Parent-child relationships: 'Criminal law' and 'Criminal procedure' "
        "are separate branches of law, NOT duplicates\n\n"
        "Only group topics that mean EXACTLY the same thing, just written "
        "differently. When in doubt, do NOT group them.\n\n"
        "For each group of duplicates, pick the BEST canonical name "
        "(properly capitalised, clean spelling, standard legal terminology).\n\n"
        "Return a JSON array of groups. Each group is an object with:\n"
        "- 'canonical': the best clean name for this topic\n"
        "- 'keep_id': the ID of the topic to keep (pick any one from the group)\n"
        "- 'duplicates': array of objects with 'id' and 'name' for ALL topics in the "
        "group (including the one to keep)\n\n"
        "ONLY return groups that have 2 or more topics (actual duplicates). "
        "Skip topics that have no duplicates. Return ONLY the JSON array, nothing else."
    )

    PHASE2_PROMPT = (
        "You are a legal taxonomy deduplication expert. You will receive:\n"
        "1. A MASTER LIST of canonical topic names that already exist.\n"
        "2. A BATCH of new topic names (with IDs) to check.\n\n"
        "For each topic in the BATCH, determine if it is a TRUE duplicate of "
        "any topic in the MASTER LIST. Consider:\n"
        "- Different casing, singular/plural, spelling variations\n"
        "- Abbreviations vs full names\n"
        "- Synonyms and legal equivalents: 'tort' vs 'delict', "
        "'labor law' vs 'employment law'\n\n"
        "CRITICAL — do NOT match these:\n"
        "- A subtopic to a broad parent: 'Administrative justice' is NOT a "
        "duplicate of 'Administrative law'\n"
        "- Topics that share a prefix but are distinct concepts: "
        "'Criminal procedure' is NOT 'Criminal law'\n"
        "- Topics with specific statutory references (s33, s11, etc.) are "
        "distinct from the general topic\n"
        "- Related but different concepts: 'Eviction' is NOT 'Property law'\n\n"
        "Only match topics that mean EXACTLY the same thing, just written "
        "differently. When in doubt, do NOT match.\n\n"
        "Return a JSON array of matches. Each match is an object with:\n"
        "- 'canonical': the matching name from the MASTER LIST\n"
        "- 'topic_id': the ID of the batch topic that matches\n"
        "- 'topic_name': the name of the batch topic\n\n"
        "ONLY include topics that genuinely match something in the master list. "
        "If a topic is unique and does not match anything, skip it. "
        "Return ONLY the JSON array, nothing else."
    )

    PHASE3_PROMPT = (
        "You are a legal taxonomy naming expert. You will receive a list of "
        "taxonomy topic names (with their IDs) from a legal database.\n\n"
        "These topics survived deduplication — they are NOT duplicates of each "
        "other. However, some may have poor names: informal language, overly "
        "descriptive phrases, grammatical issues, or non-standard terminology.\n\n"
        "For each topic, decide if its name should be improved. Consider:\n"
        "- Informal → formal: 'stealing money' → 'Theft'\n"
        "- Plural → singular (or vice versa) for consistency: 'men' → 'Man'\n"
        "- Verbose → concise: 'the right of a person to remain silent' → "
        "'Right to silence'\n"
        "- Non-standard → standard legal term: 'kicking someone out of their "
        "house' → 'Eviction'\n"
        "- Fix capitalisation to Title Case for top-level legal concepts\n\n"
        "Return a JSON array of rename suggestions. Each is an object with:\n"
        "- 'topic_id': the ID of the topic\n"
        "- 'old_name': the current name\n"
        "- 'new_name': the suggested better name\n\n"
        "ONLY include topics that genuinely need renaming. If a topic name is "
        "already good, skip it. Return ONLY the JSON array, nothing else."
    )

    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY", "") or self._read_api_key_from_env()
        self.client = OpenAI(api_key=api_key, timeout=120.0)
        self._root = None

    @staticmethod
    def _read_api_key_from_env():
        from django.conf import settings

        env_path = os.path.join(settings.BASE_DIR, ".env")
        if not os.path.exists(env_path):
            return ""
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENAI_API_KEY"):
                    _, _, value = line.partition("=")
                    return value.strip().strip('"').strip("'")
        return ""

    @property
    def root(self):
        if self._root is None:
            self._root = pj_settings().flynote_taxonomy_root
        return self._root

    def _call_llm(self, system_prompt, user_content):
        response = self.client.chat.completions.create(
            model=self.MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0,
        )
        return (response.choices[0].message.content or "").strip()

    def find_duplicates_in_batch(self, topics):
        """Phase 1: find duplicate groups within a single batch."""
        if not topics:
            return []

        topic_lines = "\n".join(f"ID:{t['id']} | {t['name']}" for t in topics)
        content = self._call_llm(self.PHASE1_PROMPT, topic_lines)
        return self._parse_groups_response(content)

    def find_rename_suggestions(self, topics):
        """Phase 3: suggest better names for poorly named topics."""
        if not topics:
            return []

        topic_lines = "\n".join(f"ID:{t['id']} | {t['name']}" for t in topics)
        content = self._call_llm(self.PHASE3_PROMPT, topic_lines)
        return self._parse_renames_response(content)

    def find_cross_batch_matches(self, master_names, batch_topics):
        """Phase 2: match batch topics against the master canonical list."""
        if not master_names or not batch_topics:
            return []

        user_content = (
            "=== MASTER LIST (existing canonical topics) ===\n"
            + "\n".join(master_names)
            + "\n\n=== BATCH TO CHECK ===\n"
            + "\n".join(f"ID:{t['id']} | {t['name']}" for t in batch_topics)
        )
        content = self._call_llm(self.PHASE2_PROMPT, user_content)
        return self._parse_matches_response(content)

    def find_all_duplicates(self, progress_callback=None, limit=None):
        """Full three-phase scan of all flynote taxonomy topics.

        Phase 1: batch-by-batch dedup to find obvious duplicates.
        Phase 2: cross-batch reconciliation using the master canonical list.
        Phase 3: rename suggestions for poorly named surviving topics.

        Args:
            limit: max number of topics to scan (None = all).
        """
        if not self.root:
            return []

        all_topics = list(
            self.root.get_descendants().order_by("name").values_list("id", "name")
        )
        if limit:
            all_topics = all_topics[:limit]
        topic_dicts = [{"id": t_id, "name": name} for t_id, name in all_topics]

        batch_size = 80
        batches = [
            topic_dicts[i : i + batch_size]
            for i in range(0, len(topic_dicts), batch_size)
        ]
        # Phase 1 + Phase 2 + Phase 3 (estimate: same as Phase 1 batches)
        total_steps = len(batches) * 3
        all_groups = []
        # Maps canonical name -> group dict (for merging cross-batch matches)
        canonical_map = {}

        # ── Phase 1: within-batch dedup ──
        for batch_num, batch in enumerate(batches, 1):
            try:
                groups = self.find_duplicates_in_batch(batch)
                for g in groups:
                    canon = g["canonical"]
                    if canon in canonical_map:
                        existing = canonical_map[canon]
                        existing_ids = {d["id"] for d in existing["duplicates"]}
                        for d in g["duplicates"]:
                            if d["id"] not in existing_ids:
                                existing["duplicates"].append(d)
                    else:
                        canonical_map[canon] = g
                        all_groups.append(g)
            except Exception:
                log.exception(f"Phase 1 error on batch {batch_num}")
                groups = []

            if progress_callback:
                progress_callback(
                    batch_num,
                    total_steps,
                    batch,
                    groups,
                    phase="Phase 1: Finding duplicates",
                )

        # Collect IDs already claimed by Phase 1 groups
        claimed_ids = set()
        for g in all_groups:
            for d in g["duplicates"]:
                claimed_ids.add(d["id"])

        master_names = sorted(canonical_map.keys())

        # ── Phase 2: cross-batch reconciliation ──
        unclaimed = [t for t in topic_dicts if t["id"] not in claimed_ids]
        unclaimed_batches = [
            unclaimed[i : i + batch_size] for i in range(0, len(unclaimed), batch_size)
        ]

        for batch_num, batch in enumerate(unclaimed_batches, 1):
            step = len(batches) + batch_num
            try:
                matches = self.find_cross_batch_matches(master_names, batch)
                new_groups_from_matches = []
                for m in matches:
                    canon = m.get("canonical", "")
                    tid = m.get("topic_id")
                    tname = m.get("topic_name", "")
                    if not canon or not tid:
                        continue
                    if tid in claimed_ids:
                        continue
                    claimed_ids.add(tid)

                    if canon in canonical_map:
                        canonical_map[canon]["duplicates"].append(
                            {"id": tid, "name": tname}
                        )
                    else:
                        new_group = {
                            "canonical": canon,
                            "keep_id": tid,
                            "duplicates": [{"id": tid, "name": tname}],
                        }
                        canonical_map[canon] = new_group
                        new_groups_from_matches.append(new_group)

                for g in new_groups_from_matches:
                    if len(g["duplicates"]) >= 2:
                        all_groups.append(g)
            except Exception:
                log.exception(f"Phase 2 error on batch {batch_num}")
                matches = []

            if progress_callback:
                progress_callback(
                    step,
                    total_steps,
                    batch,
                    [
                        {"canonical": m.get("canonical"), "duplicates": []}
                        for m in (matches if isinstance(matches, list) else [])
                    ],
                    phase="Phase 2: Cross-batch reconciliation",
                )

        # ── Phase 3: rename poorly named topics ──
        still_unclaimed = [t for t in topic_dicts if t["id"] not in claimed_ids]
        rename_batches = [
            still_unclaimed[i : i + batch_size]
            for i in range(0, len(still_unclaimed), batch_size)
        ]
        # Recalculate: Phase 1 batches + Phase 2 batches + Phase 3 batches
        phase12_steps = len(batches) + len(unclaimed_batches)
        total_all_steps = phase12_steps + len(rename_batches)
        rename_suggestions = []

        for batch_num, batch in enumerate(rename_batches, 1):
            step = phase12_steps + batch_num
            try:
                renames = self.find_rename_suggestions(batch)
                rename_suggestions.extend(renames)
            except Exception:
                log.exception(f"Phase 3 error on batch {batch_num}")
                renames = []

            if progress_callback:
                progress_callback(
                    step,
                    total_all_steps,
                    batch,
                    [
                        {"canonical": r.get("new_name", ""), "duplicates": []}
                        for r in (renames if isinstance(renames, list) else [])
                    ],
                    phase="Phase 3: Suggesting better names",
                )

        for r in rename_suggestions:
            tid = r.get("topic_id")
            old_name = r.get("old_name", "")
            new_name = r.get("new_name", "")
            if not tid or not new_name or new_name == old_name:
                continue
            all_groups.append(
                {
                    "canonical": new_name,
                    "keep_id": tid,
                    "duplicates": [{"id": tid, "name": old_name}],
                    "is_rename": True,
                }
            )

        final = [
            g
            for g in all_groups
            if len(g["duplicates"]) >= 1
            and (len(g["duplicates"]) >= 2 or g.get("is_rename"))
        ]

        for g in final:
            dup_ids = {d["id"] for d in g["duplicates"]}
            if g.get("keep_id") not in dup_ids:
                g["keep_id"] = g["duplicates"][0]["id"]

        return final

    @staticmethod
    def _parse_groups_response(content):
        """Parse Phase 1 JSON array of duplicate groups."""
        content = FlynoteLLMMapper._strip_fences(content)
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return [
                    g
                    for g in data
                    if isinstance(g, dict)
                    and "canonical" in g
                    and "duplicates" in g
                    and len(g["duplicates"]) >= 2
                ]
        except (json.JSONDecodeError, KeyError, TypeError):
            log.warning("Phase 1 parse error: %s", content[:200])
        return []

    @staticmethod
    def _parse_matches_response(content):
        """Parse Phase 2 JSON array of cross-batch matches."""
        content = FlynoteLLMMapper._strip_fences(content)
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return [
                    m
                    for m in data
                    if isinstance(m, dict) and "canonical" in m and "topic_id" in m
                ]
        except (json.JSONDecodeError, KeyError, TypeError):
            log.warning("Phase 2 parse error: %s", content[:200])
        return []

    @staticmethod
    def _parse_renames_response(content):
        """Parse Phase 3 JSON array of rename suggestions."""
        content = FlynoteLLMMapper._strip_fences(content)
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return [
                    r
                    for r in data
                    if isinstance(r, dict) and "topic_id" in r and "new_name" in r
                ]
        except (json.JSONDecodeError, KeyError, TypeError):
            log.warning("Phase 3 parse error: %s", content[:200])
        return []

    @staticmethod
    def _strip_fences(content):
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])
        return content
