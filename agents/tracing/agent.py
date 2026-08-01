from contextlib import contextmanager
from langfuse import Langfuse
import agents.config


class TracingAgent:

    def __init__(self):
        try:
            _, lf_config, _ = agents.config.get_config()
            if lf_config.enabled and lf_config.public_key and lf_config.secret_key:
                self.client = Langfuse(
                    public_key=lf_config.public_key,
                    secret_key=lf_config.secret_key,
                    base_url=lf_config.host,
                )
            else:
                self.client = None
        except Exception as e:
            print(f"[Tracing Notice] Could not initialize Langfuse client: {e}")
            self.client = None

    @contextmanager
    def create_trace(self, name: str, input_data: dict = None):
        """Context manager for an agent trace."""
        if not self.client:
            yield TraceWrapper(None)
            return

        try:
            with self.client.start_as_current_observation(
                name=name,
                as_type="agent",
                input=input_data or {},
            ):
                yield TraceWrapper(self.client)
        except Exception as e:
            print(f"[Tracing Warning] Trace '{name}' failed: {e}")
            yield TraceWrapper(None)

    def shutdown(self):
        if self.client:
            try:
                self.client.shutdown()
            except Exception:
                pass


class TraceWrapper:
    """Wrapper that exposes .span() and .update() matching Langfuse observation contexts."""

    def __init__(self, client):
        self.client = client

    @contextmanager
    def span(self, name: str, input_data: dict = None):
        if not self.client:
            yield SpanWrapper(None)
            return

        try:
            with self.client.start_as_current_observation(
                name=name,
                as_type="span",
                input=input_data or {},
            ):
                yield SpanWrapper(self.client)
        except Exception as e:
            print(f"[Tracing Warning] Span '{name}' failed: {e}")
            yield SpanWrapper(None)

    def update(self, output=None, metadata: dict = None):
        if self.client:
            try:
                self.client.update_current_observation(
                    output=output,
                    metadata=metadata,
                )
            except Exception:
                pass


class SpanWrapper:

    def __init__(self, client):
        self.client = client

    def end(self, output=None, metadata: dict = None):
        if self.client:
            try:
                self.client.update_current_span(
                    output=output,
                    metadata=metadata,
                )
            except Exception:
                pass


tracer = TracingAgent()