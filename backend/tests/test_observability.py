from typing import Any

import pytest
from agents import Span, SpanError, TaskSpanData, TurnSpanData

from evals.models import TraceMetrics
from evals.observability import EvalTraceProcessor


class SampleTaskSpan(Span):
    def __init__(self) -> None:
        self.usage: dict[str, dict[str, int]] | None = {
            "usage": {
                "input_tokens": 100,
                "output_tokens": 5,
                "cached_input_tokens": 80,
                "cache_write_input_tokens": 50,
                "requests": 2,
                "total_tokens": 105,
            },
        }

        super().__init__()

    @property
    def trace_id(self) -> str:
        return "test_trace_id"

    @property
    def span_data(self) -> Any:
        return TaskSpanData(
            name="sample_task_span",
            usage=self.usage["usage"] if self.usage is not None else None,
        )

    @property
    def span_id(self) -> str:
        return "test_task_span_id"

    def start(self, mark_as_current: bool = False):
        raise NotImplementedError

    def finish(self, reset_current: bool = False) -> None:
        raise NotImplementedError

    def __enter__(self) -> Span:
        raise NotImplementedError

    def __exit__(self, exc_type, exc_val, exc_tb):
        raise NotImplementedError

    @property
    def parent_id(self) -> str | None:
        raise NotImplementedError

    def set_error(self, error: SpanError) -> None:
        raise NotImplementedError

    @property
    def error(self) -> SpanError | None:
        raise NotImplementedError

    def export(self) -> dict[str, Any] | None:
        raise NotImplementedError

    @property
    def started_at(self) -> str | None:
        raise NotImplementedError

    @property
    def ended_at(self) -> str | None:
        raise NotImplementedError

    @property
    def tracing_api_key(self) -> str | None:
        raise NotImplementedError


class SampleTurnSpan(Span):
    def __init__(self) -> None:
        super().__init__()

    @property
    def trace_id(self) -> str:
        return "test_trace_id"

    @property
    def span_id(self) -> str:
        return "test_turn_span_id"

    @property
    def span_data(self) -> Any:
        return TurnSpanData(
            turn=2,
            agent_name="test_agent_name",
            usage={
                "input_tokens": 100,
                "output_tokens": 5,
                "cached_input_tokens": 80,
                "cache_write_input_tokens": 50,
            },
        )

    def start(self, mark_as_current: bool = False):
        return super().start(mark_as_current)

    def finish(self, reset_current: bool = False) -> None:
        return super().finish(reset_current)

    def __enter__(self) -> Span:
        return super().__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return super().__exit__(exc_type, exc_val, exc_tb)

    @property
    def parent_id(self) -> str | None:
        return super().parent_id

    def set_error(self, error: SpanError) -> None:
        return super().set_error(error)

    @property
    def error(self) -> SpanError | None:
        return super().error

    def export(self) -> dict[str, Any] | None:
        return super().export()

    @property
    def started_at(self) -> str | None:
        return super().started_at

    @property
    def ended_at(self) -> str | None:
        return super().ended_at

    @property
    def trace_metadata(self) -> dict[str, Any] | None:
        return super().trace_metadata

    @property
    def tracing_api_key(self) -> str | None:
        return super().tracing_api_key


def test_on_span_end_init_task():

    processor = EvalTraceProcessor()
    task_span = SampleTaskSpan()

    processor.on_span_start(task_span)
    processor.on_span_end(task_span)
    assert (
        processor.metrics_collection.mapped_metrics[task_span.trace_id].agent_turns == 0
    )
    assert TraceMetrics.model_validate(
        processor.metrics_collection.mapped_metrics[task_span.trace_id],
        from_attributes=True,
    )


def test_on_span_end_task_turn_happy_flow():
    processor = EvalTraceProcessor()
    task_span = SampleTaskSpan()
    turn_span = SampleTurnSpan()

    processor.on_span_start(task_span)
    processor.on_span_end(task_span)
    assert (
        processor.metrics_collection.mapped_metrics[task_span.trace_id].agent_turns == 0
    )
    assert TraceMetrics.model_validate(
        processor.metrics_collection.mapped_metrics[task_span.trace_id],
        from_attributes=True,
    )

    processor.on_span_start(turn_span)
    processor.on_span_end(turn_span)
    assert (
        processor.metrics_collection.mapped_metrics[turn_span.trace_id].agent_turns == 2
    )
    assert TraceMetrics.model_validate(
        processor.metrics_collection.mapped_metrics[turn_span.trace_id],
        from_attributes=True,
    )

    processor.on_span_start(turn_span)
    processor.on_span_end(turn_span)
    assert (
        processor.metrics_collection.mapped_metrics[turn_span.trace_id].agent_turns == 4
    )


def test_turn_span_first():
    processor = EvalTraceProcessor()
    turn_span = SampleTurnSpan()

    processor.on_span_start(turn_span)
    with pytest.raises(RuntimeError, match="Unexpected turn_span as first trace"):
        processor.on_span_end(turn_span)


def test_init_task_data_missing_keys():
    processor = EvalTraceProcessor()
    task_span = SampleTaskSpan()

    if task_span.usage:
        del task_span.usage["usage"]["requests"]

    processor.on_span_start(task_span)

    with pytest.raises(RuntimeError, match="Unexpected span_data form: 'requests'"):
        processor.on_span_end(task_span)


def test_task_data_missing_keys():
    processor = EvalTraceProcessor()
    task_span = SampleTaskSpan()

    processor.on_span_start(task_span)
    processor.on_span_end(task_span)

    if task_span.usage:
        del task_span.usage["usage"]["input_tokens"]

    processor.on_span_start(task_span)

    with pytest.raises(RuntimeError, match="Unexpected span_data form: 'input_tokens'"):
        processor.on_span_end(task_span)


def test_all_usage_data_missing():
    processor = EvalTraceProcessor()
    task_span = SampleTaskSpan()
    task_span.usage = None

    processor.on_span_start(task_span)

    with pytest.raises(ValueError, match="Span missing data."):
        processor.on_span_end(task_span)
