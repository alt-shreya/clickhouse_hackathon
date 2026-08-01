"""
ContextAgent -- the single object every other agent talks to for context.

Business context is ONE whole Markdown document, not decomposed into rows.
It lives in analytics_context.business_context (doc_id, content, version,
changelog_summary, updated_at), a ReplacingMergeTree keyed on doc_id: every
change -- the initial seed, a new table being auto-documented, an audit
finding a flag, a flag being resolved -- INSERTs a new version rather than
mutating any row in place, so the table doubles as the full audit trail.
Callers always read the latest version and inject `content` directly into
their prompts; there is no per-row filtering to do because the document is
the atomic unit.

Fixed interface: load_v1, get_latest_context, update_context, run_audit, resolve_flag.
"""

import json
import re
from datetime import datetime, timezone

import clickhouse_connect

from .load_base_context import DOC_ID, AUTO_TABLES_MARKER, OPEN_FLAGS_MARKER, NONE_YET, NONE_OPEN, build_seed_content
from .audit_base_context import freshness_check, AUDIT_PROMPT, parse_llm_json

UPDATE_PROMPT = """A new ClickHouse table was just created for a feature spec. Write a SHORT
Markdown blurb (3-6 lines, a single bullet or short sub-list, no heading) for a living
business-context document: what the table captures, its key columns, and how it joins to
existing entities (user_id / application_id, or a spec-specific id if that's what it
actually uses). If -- and only if -- the spec clearly implies a NEW metric formula or a
known-issue-style caveat not already covered below, add ONE short bullet for each;
otherwise don't invent one.

Current "Auto-instrumented tables" entries (context only -- don't duplicate an existing
metric or caveat):
{current_entries}

NEW TABLE: {new_table}
DDL:
{schema_ddl}

SPEC IT CAME FROM:
{source_spec}

Respond as JSON: {{"table_blurb_markdown": "- **{new_table}** -- ...", "changelog_summary": "one line"}}
No prose, no markdown fences outside the JSON string values.
"""

RESOLVE_PROMPT = """You are resolving an open flag in a business-context document.
Entity: {entity}
Key: {key}
Flag line: {flag_line}

Provide a short resolution note explaining how this should be understood/fixed going
forward (1-3 sentences). Respond in JSON: {{"resolution_notes": "..."}}
No prose, no markdown fences.
"""

# A flag is rendered as one bullet line, in a format that's both readable and
# machine-parseable so re-auditing an unchanged document doesn't re-flag the
# same issue every time (see _existing_flag_keys()).
_FLAG_LINE_RE = re.compile(r"^- \*\*\[(?P<flag_type>[^\]]+)\]\*\* `(?P<entity>[^`]*)` */ *`(?P<key>[^`]*)`", re.MULTILINE)

# Stops a spliced region at the next top-level heading, the next `---` section
# divider, or end of document -- whichever comes first. Keeps the divider
# between sections intact across replacements instead of it being swallowed
# into whatever gets spliced in.
_SECTION_STOP = r"(?=\n---\s*\n|\n##\s|\Z)"


def _extract_entries(markdown: str, marker: str) -> str:
    pattern = re.compile(re.escape(marker) + r"\n(.*?)" + _SECTION_STOP, re.DOTALL)
    match = pattern.search(markdown)
    return match.group(1) if match else ""


def _replace_entries(markdown: str, marker: str, new_body: str) -> str:
    pattern = re.compile("(" + re.escape(marker) + r"\n)(.*?)" + _SECTION_STOP, re.DOTALL)
    match = pattern.search(markdown)
    if not match:
        raise ValueError(f"Marker {marker!r} not found in document -- was it seeded via build_seed_content()?")
    return markdown[:match.start(2)] + new_body.strip() + "\n" + markdown[match.end(2):]


def _is_empty_placeholder(entries: str) -> bool:
    stripped = entries.strip()
    return stripped in ("", NONE_YET, NONE_OPEN)


def _render_flag_line(flag: dict) -> str:
    flag_type = flag.get("flag_type", "ambiguous_definition")
    entity = flag.get("entity", "")
    key = flag.get("key", "")
    description = flag.get("description", "")
    return f"- **[{flag_type}]** `{entity}` / `{key}` -- {description}"


def _existing_flag_keys(entries: str) -> set[tuple[str, str, str]]:
    return {
        (m.group("flag_type"), m.group("entity"), m.group("key"))
        for m in _FLAG_LINE_RE.finditer(entries)
    }


class ContextAgent:
    def __init__(self, client, llm_call_fn):
        self.client = client
        self.llm_call_fn = llm_call_fn  # Wrapped in Langfuse span at call sites

    # ============================================================
    # Reading
    # ============================================================

    def _latest_doc(self, doc_id: str = DOC_ID) -> dict:
        query = f"""
            SELECT doc_id, content, version, changelog_summary, updated_at
            FROM analytics_context.business_context
            WHERE doc_id = '{doc_id}'
            ORDER BY version DESC
            LIMIT 1
        """
        result = self.client.query(query)
        if not result.result_rows:
            return {"doc_id": doc_id, "content": "", "version": 0, "changelog_summary": "", "updated_at": None}
        return dict(zip(result.column_names, result.result_rows[0]))

    def get_latest_context(self, entities: list[str] | None = None) -> dict:
        """Returns the latest version of the unified business-context document:
        {doc_id, content, version, changelog_summary, updated_at}.

        `entities` is accepted for backward compatibility with callers written
        against the old per-row context model, but no longer filters anything --
        the document is one atomic whole now, so callers inject `content`
        directly into their prompts rather than filtering structured rows.
        """
        return self._latest_doc()

    def _insert_version(self, content: str, version: int, changelog_summary: str, doc_id: str = DOC_ID) -> None:
        # async_insert=0: forces a synchronous, durable write. This ClickHouse
        # Cloud service defaults to async_insert=1 (server-side buffering before
        # a background flush); observed live, rapid-fire small control-plane
        # inserts silently lost rows when the process moved on before the async
        # buffer flushed. Every write here is low-volume and correctness-critical.
        self.client.insert(
            "analytics_context.business_context",
            [[doc_id, content, version, changelog_summary, datetime.now(timezone.utc)]],
            column_names=["doc_id", "content", "version", "changelog_summary", "updated_at"],
            settings={"async_insert": 0},
        )

    # ============================================================
    # Seeding
    # ============================================================

    def load_v1(self, force: bool = False) -> int:
        """Seeds version 1 of the business-context document from base_context.md
        (plus the operational sections -- auto-instrumented tables, freshness
        check, open flags -- appended by build_seed_content()).

        Guarded by default: analytics_context.business_context is a plain
        ReplacingMergeTree with no dedup until merge, so calling this twice
        would leave a stray duplicate version=1 row until the background merge
        catches up. Pass force=True to reseed anyway.
        """
        if not force:
            existing = self._latest_doc()
            if existing["version"] > 0:
                print(f"analytics_context.business_context already seeded ({DOC_ID} at version {existing['version']}) -- skipping load_v1() (pass force=True to reseed anyway).")
                return 0

        content = build_seed_content()
        self._insert_version(content=content, version=1, changelog_summary="Initial seed from base_context.md")
        return 1

    # ============================================================
    # LLM plumbing
    # ============================================================

    def _call_llm_json(self, prompt: str, span_name: str):
        """Call the LLM and parse its JSON response, returning None on any
        failure (API error or malformed JSON) instead of raising -- every
        other LLM call site in this codebase already degrades gracefully on
        LLM failure, so a single flaky call doesn't take the whole pipeline down."""
        try:
            try:
                raw = self.llm_call_fn(prompt, span_name=span_name)
            except TypeError:
                raw = self.llm_call_fn(prompt)
            return parse_llm_json(raw)
        except Exception as e:
            print(f"Warning: ContextAgent LLM call ({span_name}) failed, skipping: {e}")
            return None

    # ============================================================
    # Auto-update on new tables
    # ============================================================

    def update_context(self, new_table: str, schema_ddl: str, source_spec: str) -> int | None:
        """Invoked by InstrumentationAgent right after a new table is created.
        Asks the LLM for a short blurb documenting the table (not a rewrite of
        the whole document -- see module docstring for why), appends it under
        Section 8 (Auto-instrumented tables), writes a new version, then
        re-audits so any new contradiction/gap/staleness this table introduces
        gets surfaced in the same pass.
        """
        latest = self._latest_doc()
        if latest["version"] == 0:
            print(f"Warning: business context not seeded yet -- call load_v1() first. Skipping update_context for {new_table}.")
            return None

        current_entries = _extract_entries(latest["content"], AUTO_TABLES_MARKER)
        prompt = UPDATE_PROMPT.format(
            current_entries=current_entries if not _is_empty_placeholder(current_entries) else NONE_YET,
            new_table=new_table,
            schema_ddl=schema_ddl,
            source_spec=(source_spec or "")[:4000],
        )
        parsed = self._call_llm_json(prompt, "context_update")
        if parsed is None:
            print(f"Skipping context update for {new_table} (LLM call failed) -- table was still created, just without context enrichment.")
            return None

        blurb = str(parsed.get("table_blurb_markdown", "")).strip()
        if not blurb:
            print(f"Skipping context update for {new_table} -- LLM returned no blurb.")
            return None

        new_entries = blurb if _is_empty_placeholder(current_entries) else f"{current_entries.rstrip()}\n\n{blurb}"
        new_content = _replace_entries(latest["content"], AUTO_TABLES_MARKER, new_entries)

        next_version = latest["version"] + 1
        changelog = str(parsed.get("changelog_summary") or f"Added {new_table}")
        self._insert_version(content=new_content, version=next_version, changelog_summary=changelog)
        print(f"Updated business context to version {next_version}: {changelog}")

        # Re-audit new state -- only writes yet another version if it actually finds something new.
        self.run_audit(scope=[new_table])
        return next_version

    # ============================================================
    # Auditing -- contradictions/gaps (LLM) + obsolete data (deterministic)
    # ============================================================

    def run_audit(self, scope: list[str] | None = None) -> list[dict]:
        """Surfaces contradictions, gaps, and obsolete/stale facts in the
        business-context document:
        - freshness_check(): deterministic, no LLM -- does every table
          InstrumentationAgent has registered still actually exist? This is
          exactly the check Section 9 (Data freshness check) tells readers to
          run; running it here means the document polices its own staleness.
        - An LLM pass over the full document for contradictions/ambiguity it
          can support from the text alone.

        New flags (deduped against ones already listed under Section 10) are
        appended there and a new version is written; if nothing new is found,
        no version is written and an empty list is returned -- re-running audit
        on an unchanged document doesn't pile up duplicate flags or noise the
        version history.

        Known limitation: dedup is exact-match on (flag_type, entity, key) plus
        showing the LLM the already-flagged list in-prompt -- freshness_check()'s
        flags are deterministic so this is exact, but the LLM's own entity/key
        choice for the SAME underlying contradiction isn't perfectly stable
        across independent calls (observed live: `metric.conversion_rate`/
        `session_undefined` vs `entity.session`/`session_undefined` for what's
        the same issue). Calling run_audit() repeatedly with no document change
        in between can occasionally add a near-duplicate, differently-worded
        flag rather than recognizing it as one already raised. A text-similarity
        heuristic was tried and rejected -- it scored two genuinely different
        freshness flags (different table, near-identical template sentence) as
        MORE similar than two genuinely-the-same LLM flags (same issue, very
        different phrasing), so it would suppress real distinct flags rather
        than catch true duplicates.
        """
        latest = self._latest_doc()
        if latest["version"] == 0:
            print("Warning: business context not seeded yet -- call load_v1() first. Skipping run_audit().")
            return []

        current_entries = _extract_entries(latest["content"], OPEN_FLAGS_MARKER)
        existing_keys = _existing_flag_keys(current_entries)

        flags = list(freshness_check(self.client))

        # Showing the LLM what's already flagged is the primary defense against
        # re-flagging the same issue reworded (e.g. `metric.conversion_rate` /
        # `session_undefined` vs `entity.session` / `session_undefined` on two
        # different audit passes -- observed live, since entity/key are LLM
        # free text, not a stable identifier). The exact-tuple check below is
        # a secondary safety net, not the primary mechanism.
        audit_prompt = AUDIT_PROMPT.format(
            document=latest["content"][:16000],
            existing_flags=current_entries if not _is_empty_placeholder(current_entries) else "(none yet)",
        )
        llm_flags = self._call_llm_json(audit_prompt, "context_audit")
        if isinstance(llm_flags, list):
            flags.extend(f for f in llm_flags if isinstance(f, dict))
        elif isinstance(llm_flags, dict):
            flags.append(llm_flags)

        new_flags = [
            f for f in flags
            if (f.get("flag_type", "ambiguous_definition"), f.get("entity", ""), f.get("key", "")) not in existing_keys
        ]
        if not new_flags:
            return []

        new_lines = "\n".join(_render_flag_line(f) for f in new_flags)
        updated_entries = new_lines if _is_empty_placeholder(current_entries) else f"{current_entries.rstrip()}\n{new_lines}"
        new_content = _replace_entries(latest["content"], OPEN_FLAGS_MARKER, updated_entries)

        next_version = latest["version"] + 1
        scope_note = f" (scope: {', '.join(scope)})" if scope else ""
        changelog = f"Audit found {len(new_flags)} new flag(s){scope_note}"
        self._insert_version(content=new_content, version=next_version, changelog_summary=changelog)
        print(f"Updated business context to version {next_version}: {changelog}")
        return new_flags

    # ============================================================
    # Resolving a flag
    # ============================================================

    def resolve_flag(self, entity: str, key: str) -> str | None:
        """Resolves an open flag matching (entity, key): asks the LLM for a
        resolution note, removes the flag line from Section 10, and writes a
        new version whose changelog records the resolution. Returns the
        resolution note, or None if no matching open flag was found (or the
        LLM call failed).
        """
        latest = self._latest_doc()
        if latest["version"] == 0:
            return None

        current_entries = _extract_entries(latest["content"], OPEN_FLAGS_MARKER)
        lines = current_entries.splitlines()
        matching = [ln for ln in lines if f"`{entity}`" in ln and f"`{key}`" in ln]
        if not matching:
            print(f"No open flag found for {entity}.{key}")
            return None

        prompt = RESOLVE_PROMPT.format(entity=entity, key=key, flag_line=matching[0])
        res = self._call_llm_json(prompt, "context_resolve")
        if res is None:
            print(f"Skipping resolution for {entity}.{key} (LLM call failed).")
            return None
        resolution_notes = str(res.get("resolution_notes", ""))

        remaining = [ln for ln in lines if ln not in matching]
        new_entries = "\n".join(remaining) if remaining else NONE_OPEN
        new_content = _replace_entries(latest["content"], OPEN_FLAGS_MARKER, new_entries)

        next_version = latest["version"] + 1
        changelog = f"Resolved flag {entity}.{key}: {resolution_notes}"
        self._insert_version(content=new_content, version=next_version, changelog_summary=changelog)
        print(f"Updated business context to version {next_version}: {changelog}")
        return resolution_notes


if __name__ == "__main__":
    client = clickhouse_connect.get_client(
        host="<your-service-host>", username="<user>", password="<password>", database="agent_control",
    )

    def llm_call_fn(prompt: str, span_name: str = "test") -> str:
        raise NotImplementedError("Wire to Anthropic / OpenAI API call")

    agent = ContextAgent(client, llm_call_fn)
    print("ContextAgent initialized successfully.")
