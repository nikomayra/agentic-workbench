from unittest.mock import Mock

import pytest
from agents import CustomSpanData, Span, TaskSpanData, TurnSpanData

from evals.models import TraceMetrics
from evals.observability import EvalTraceProcessor


def make_task_span_with_mock() -> Mock:
    span = Mock(spec=Span)
    span.trace_id = "namespace_trace_id"
    span.span_id = "test_task_span_id"
    span.span_data = TaskSpanData(
        name="sample_task_span",
        usage={
            "requests": 1,
            "input_tokens": 100,
            "output_tokens": 5,
            "total_tokens": 105,
            "cached_input_tokens": 80,
        },
    )
    return span


def make_turn_span_with_mock() -> Mock:
    span = Mock(spec=Span)
    span.trace_id = "mock_trace_id"
    span.span_id = "test_turn_span_id"
    span.span_data = TurnSpanData(
        turn=2,
        agent_name="test_agent_name",
    )
    return span


def make_custom_span_with_mock() -> Mock:
    span = Mock(spec=Span)
    span.trace_id = "mock_trace_id"
    span.span_id = "test_custom_span_id"
    span.span_data = CustomSpanData(
        name="test_custom_name",
        data={
            "test-data-propery-1": 0,
            "test-data-propery-2": 0,
        },
    )
    return span


def test_on_span_end_flow():
    processor = EvalTraceProcessor()

    turn_span = make_turn_span_with_mock()
    processor.on_span_start(turn_span)
    processor.on_span_end(turn_span)
    assert (
        processor.metrics_collection.mapped_metrics[turn_span.trace_id].agent_turns == 1
    )
    assert TraceMetrics.model_validate(
        processor.metrics_collection.mapped_metrics[turn_span.trace_id],
        from_attributes=True,
    )

    task_span = make_task_span_with_mock()
    processor.on_span_start(task_span)
    processor.on_span_end(task_span)
    assert (
        processor.metrics_collection.mapped_metrics[task_span.trace_id].input_tokens
        == 100
    )
    assert TraceMetrics.model_validate(
        processor.metrics_collection.mapped_metrics[task_span.trace_id],
        from_attributes=True,
    )

    after_task_span_metric_state = processor.metrics_collection.mapped_metrics[
        task_span.trace_id
    ]
    custom_span = make_custom_span_with_mock()
    processor.on_span_start(custom_span)
    processor.on_span_end(custom_span)
    assert (
        processor.metrics_collection.mapped_metrics[task_span.trace_id]
        == after_task_span_metric_state
    )


def test_task_data_missing_keys():
    processor = EvalTraceProcessor()
    task_span = make_task_span_with_mock()

    processor.on_span_start(task_span)
    processor.on_span_end(task_span)

    if task_span.span_data.usage:
        del task_span.span_data.usage["input_tokens"]

    processor.on_span_start(task_span)

    with pytest.raises(RuntimeError, match="Unexpected span_data form: 'input_tokens'"):
        processor.on_span_end(task_span)
