from dataclasses import dataclass, field

from agents import TaskSpanData, TracingProcessor, TurnSpanData

from evals.models import TraceMetrics


@dataclass()
class EvalTraceCollector:
    mapped_metrics: dict[str, TraceMetrics] = field(default_factory=dict)


class EvalTraceProcessor(TracingProcessor):
    def __init__(self):
        self.active_traces = {}
        self.active_spans = {}
        self.metrics_collection = EvalTraceCollector()

    def on_trace_start(self, trace):
        self.active_traces[trace.trace_id] = trace

    def on_trace_end(self, trace):
        # Process completed trace
        del self.active_traces[trace.trace_id]

    def on_span_start(self, span):
        self.active_spans[span.span_id] = span

    def on_span_end(self, span):

        if span.span_data.usage == None:
            raise ValueError("Span missing data.")

        run_trace_metrics = self.metrics_collection.mapped_metrics.get(
            span.trace_id, None
        )
        if run_trace_metrics and isinstance(span.span_data, TaskSpanData):
            try:
                run_trace_metrics.requests = span.span_data.usage["requests"]
                run_trace_metrics.input_tokens = span.span_data.usage["input_tokens"]
                run_trace_metrics.output_tokens = span.span_data.usage["output_tokens"]
                run_trace_metrics.total_tokens = span.span_data.usage["total_tokens"]
                run_trace_metrics.cached_input_tokens = span.span_data.usage[
                    "cached_input_tokens"
                ]
            except KeyError as err:
                raise RuntimeError(f"Unexpected span_data form: {err}")

        if run_trace_metrics and isinstance(span.span_data, TurnSpanData):
            run_trace_metrics.agent_turns += span.span_data.turn

        if run_trace_metrics == None and isinstance(span.span_data, TaskSpanData):
            try:
                self.metrics_collection.mapped_metrics[span.trace_id] = TraceMetrics(
                    requests=span.span_data.usage["requests"],
                    input_tokens=span.span_data.usage["input_tokens"],
                    output_tokens=span.span_data.usage["output_tokens"],
                    total_tokens=span.span_data.usage["total_tokens"],
                    cached_input_tokens=span.span_data.usage["cached_input_tokens"],
                    agent_turns=0,
                )

                # print(f"Init  {self.metrics_collection.mapped_metrics[span.trace_id]}")
            except KeyError as err:
                raise RuntimeError(f"Unexpected span_data form: {err}")
        elif run_trace_metrics == None and isinstance(span.span_data, TurnSpanData):
            raise RuntimeError("Unexpected turn_span as first trace")

        del self.active_spans[span.span_id]

    def shutdown(self):
        # Clean up resources
        self.active_traces.clear()
        self.active_spans.clear()

    def force_flush(self):
        # Force processing of any queued items
        pass
