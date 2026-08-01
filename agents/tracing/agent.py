"""
Tracing Agent
Langfuse v4 integration for full pipeline tracing.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path
import json
import os
import uuid


@dataclass
class TraceSpan:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    status: str = "running"
    error: Optional[str] = None


class TracingAgent:
    def __init__(
        self,
        public_key: str = None,
        secret_key: str = None,
        host: str = None,
        enabled: bool = True,
    ):
        self.enabled = enabled
        self.spans: Dict[str, TraceSpan] = {}
        self.current_trace_id: Optional[str] = None
        self.current_span_id: Optional[str] = None
        self._active_trace_ctx = None
        self._active_span_ctx_stack: List[Any] = []
        self._fallback_events: List[Dict[str, Any]] = []
        self.langfuse = None

        if enabled:
            try:
                from langfuse import Langfuse

                self.langfuse = Langfuse(
                    public_key=public_key or os.getenv("LANGFUSE_PUBLIC_KEY"),
                    secret_key=secret_key or os.getenv("LANGFUSE_SECRET_KEY"),
                    base_url=host or os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com",
                )

                if not self.langfuse:
                    self.enabled = False
            except Exception as e:
                print(f"Failed to initialize Langfuse client: {e}")
                self.enabled = False

    def _record_fallback(self, kind: str, payload: Dict[str, Any]):
        self._fallback_events.append(
            {
                "kind": kind,
                "trace_id": self.current_trace_id,
                "timestamp": datetime.now().isoformat(),
                **payload,
            }
        )

    def start_trace(self, name: str, metadata: Dict[str, Any] = None) -> str:
        trace_id = str(uuid.uuid4())
        self.current_trace_id = trace_id

        if self.enabled and self.langfuse:
            try:
                self._active_trace_ctx = self.langfuse.start_as_current_observation(
                    name=name,
                    as_type="agent",
                    input=metadata or {},
                    metadata=metadata or {},
                    end_on_exit=False,
                )
                self._active_trace_ctx.__enter__()
            except Exception as e:
                print(f"Warning: failed to start Langfuse trace: {e}")
                self._record_fallback("trace_error", {"name": name, "metadata": metadata or {}, "error": str(e)})
        return trace_id

    def start_span(self, name: str, metadata: Dict[str, Any] = None, input_data: Dict[str, Any] = None) -> str:
        if not self.current_trace_id:
            self.start_trace("pipeline")

        span_id = str(uuid.uuid4())
        parent_id = self.current_span_id
        self.current_span_id = span_id

        self.spans[span_id] = TraceSpan(
            name=name,
            trace_id=self.current_trace_id,
            span_id=span_id,
            parent_span_id=parent_id,
            metadata=metadata or {},
            input_data=input_data or {},
        )

        if self.enabled and self.langfuse:
            try:
                span_ctx = self.langfuse.start_as_current_observation(
                    name=name,
                    as_type="span",
                    input=input_data or {},
                    metadata=metadata or {},
                    end_on_exit=False,
                )
                self._active_span_ctx_stack.append(span_ctx)
                span_ctx.__enter__()
            except Exception as e:
                self._record_fallback("span_error", {"span_id": span_id, "name": name, "error": str(e)})

        return span_id

    def end_span(self, span_id: str, output_data: Dict[str, Any] = None, status: str = "success", error: str = None):
        if span_id not in self.spans:
            return

        span = self.spans[span_id]
        span.end_time = datetime.now()
        span.output_data = output_data or {}
        span.status = status
        span.error = error

        if self.enabled and self.langfuse:
            try:
                self.langfuse.update_current_span(
                    output=output_data or {},
                    metadata={**span.metadata, "status": status, **({"error": error} if error else {})},
                    level="ERROR" if status == "error" else "DEFAULT",
                    status_message=error,
                )
            except Exception as e:
                self._record_fallback("end_span_error", {"span_id": span_id, "status": status, "error": str(e)})

        if self._active_span_ctx_stack:
            span_ctx = self._active_span_ctx_stack.pop()
            try:
                span_ctx.__exit__(None, None, None)
            except Exception as e:
                self._record_fallback("span_exit_error", {"span_id": span_id, "error": str(e)})

        self.current_span_id = span.parent_span_id

    @contextmanager
    def trace_span(self, name: str, metadata: Dict[str, Any] = None, input_data: Dict[str, Any] = None):
        span_id = self.start_span(name, metadata, input_data)
        try:
            yield span_id
            self.end_span(span_id, status="success")
        except Exception as e:
            self.end_span(span_id, status="error", error=str(e))
            raise

    def log_generation(self, name: str, model: str, prompt: str, completion: str, metadata: Dict[str, Any] = None):
        if not self.current_trace_id:
            self.start_trace("llm_generation")

        if self.enabled and self.langfuse:
            try:
                self.langfuse.start_as_current_observation(
                    name=name,
                    as_type="generation",
                    trace_id=self.current_trace_id,
                    input={"prompt": prompt},
                    output={"completion": completion},
                    metadata={**(metadata or {}), "model": model},
                )
            except Exception as e:
                self._record_fallback("generation_error", {"name": name, "model": model, "error": str(e)})

    def log_event(self, name: str, properties: Dict[str, Any] = None):
        if self.enabled and self.langfuse:
            try:
                self.langfuse.create_event(
                    trace_id=self.current_trace_id,
                    name=name,
                    metadata=properties or {},
                )
            except Exception as e:
                self._record_fallback("event_error", {"name": name, "error": str(e)})

    def flush(self):
        if self.enabled and self.langfuse:
            try:
                if self._active_trace_ctx is not None:
                    try:
                        self._active_trace_ctx.__exit__(None, None, None)
                    finally:
                        self._active_trace_ctx = None
                self.langfuse.flush()
            except Exception as e:
                self._record_fallback("flush_error", {"error": str(e)})

        if self._fallback_events:
            out_dir = Path("traces")
            out_dir.mkdir(exist_ok=True)
            fallback_file = out_dir / f"{self.current_trace_id or 'trace'}.jsonl"
            with fallback_file.open("a", encoding="utf-8") as f:
                for event in self._fallback_events:
                    f.write(json.dumps(event, default=str) + "\n")

    def get_trace_summary(self, trace_id: str = None) -> Dict[str, Any]:
        tid = trace_id or self.current_trace_id
        if not tid:
            return {}

        trace_spans = [s for s in self.spans.values() if s.trace_id == tid]
        return {
            "trace_id": tid,
            "span_count": len(trace_spans),
            "spans": [
                {
                    "name": s.name,
                    "span_id": s.span_id,
                    "parent_span_id": s.parent_span_id,
                    "duration_ms": (s.end_time - s.start_time).total_seconds() * 1000 if s.end_time else None,
                    "status": s.status,
                    "error": s.error,
                }
                for s in trace_spans
            ],
        }


_default_tracer: Optional[TracingAgent] = None


def get_tracer() -> TracingAgent:
    global _default_tracer
    if _default_tracer is None:
        _default_tracer = TracingAgent()
    return _default_tracer


def set_tracer(tracer: TracingAgent):
    global _default_tracer
    _default_tracer = tracer
