from dataclasses import dataclass, field

from agents import TaskSpanData, TracingProcessor, TurnSpanData

from evals.models import TraceMetrics


@dataclass()
class EvalTraceCollector:
    mapped_metrics: dict[str, TraceMetrics] = field(default_factory=dict)

    def metrics_for(self, trace_id: str) -> TraceMetrics:
        """Return the accumulated metrics for a trace, creating zero totals if needed."""
        return self.mapped_metrics.setdefault(
            trace_id,
            TraceMetrics(
                requests=0,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cached_input_tokens=0,
                agent_turns=0,
            ),
        )


class EvalTraceProcessor(TracingProcessor):
    def __init__(self):
        self.metrics_collection = EvalTraceCollector()

    def on_trace_start(self, trace):
        pass

    def on_trace_end(self, trace):
        # Process completed trace
        pass

    def on_span_start(self, span):
        pass

    def on_span_end(self, span):

        if isinstance(span.span_data, TaskSpanData) and span.span_data.usage:
            run_trace_metrics = self.metrics_collection.metrics_for(span.trace_id)
            try:
                self.metrics_collection.mapped_metrics[
                    span.trace_id
                ].requests += span.span_data.usage["requests"]
                run_trace_metrics.input_tokens += span.span_data.usage["input_tokens"]
                run_trace_metrics.output_tokens += span.span_data.usage["output_tokens"]
                run_trace_metrics.total_tokens += span.span_data.usage["total_tokens"]
                run_trace_metrics.cached_input_tokens += span.span_data.usage[
                    "cached_input_tokens"
                ]
            except KeyError as err:
                raise RuntimeError(f"Unexpected span_data form: {err}")

        elif isinstance(span.span_data, TurnSpanData):
            run_trace_metrics = self.metrics_collection.metrics_for(span.trace_id)
            run_trace_metrics.agent_turns += 1

    def shutdown(self):
        # Clean up resources
        pass

    def force_flush(self):
        # Force processing of any queued items
        pass
