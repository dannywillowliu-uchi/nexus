from nexus.harness.event_store import EventStore
from nexus.harness.harness import Harness
from nexus.harness.models import Event, HarnessConfig


def test_harness_config_defaults():
	config = HarnessConfig()
	assert config.max_iterations_per_hypothesis == 10
	assert config.max_total_tool_calls == 50
	assert config.timeout_minutes == 30


def test_event_creation():
	event = Event(
		event_id="evt-1",
		session_id="sess-1",
		event_type="tool_call",
		hypothesis_id="hyp-1",
		tool_name="compound_lookup",
		input_data={"compound_name": "aspirin"},
		output_data={"status": "success"},
		confidence_snapshot=0.5,
		timestamp="2024-01-01T00:00:00Z",
	)
	assert event.event_id == "evt-1"
	assert event.session_id == "sess-1"
	assert event.event_type == "tool_call"
	assert event.hypothesis_id == "hyp-1"
	assert event.tool_name == "compound_lookup"
	assert event.input_data == {"compound_name": "aspirin"}
	assert event.output_data == {"status": "success"}
	assert event.confidence_snapshot == 0.5


def test_event_defaults():
	event = Event(event_id="evt-2", session_id="sess-2", event_type="verdict")
	assert event.hypothesis_id is None
	assert event.tool_name is None
	assert event.input_data is None
	assert event.output_data is None
	assert event.confidence_snapshot is None
	assert event.timestamp == ""


def test_event_store_add_and_get_by_session():
	store = EventStore()
	e1 = Event(event_id="1", session_id="s1", event_type="tool_call")
	e2 = Event(event_id="2", session_id="s2", event_type="tool_call")
	e3 = Event(event_id="3", session_id="s1", event_type="verdict")
	store.add(e1)
	store.add(e2)
	store.add(e3)

	s1_events = store.get_by_session("s1")
	assert len(s1_events) == 2
	assert s1_events[0].event_id == "1"
	assert s1_events[1].event_id == "3"

	s2_events = store.get_by_session("s2")
	assert len(s2_events) == 1


def test_event_store_get_by_hypothesis():
	store = EventStore()
	e1 = Event(event_id="1", session_id="s1", event_type="tool_call", hypothesis_id="h1")
	e2 = Event(event_id="2", session_id="s1", event_type="tool_call", hypothesis_id="h2")
	e3 = Event(event_id="3", session_id="s1", event_type="verdict", hypothesis_id="h1")
	store.add(e1)
	store.add(e2)
	store.add(e3)

	h1_events = store.get_by_hypothesis("h1")
	assert len(h1_events) == 2

	h2_events = store.get_by_hypothesis("h2")
	assert len(h2_events) == 1


def test_event_store_callback():
	store = EventStore()
	captured: list[Event] = []
	store.register_callback(lambda e: captured.append(e))

	e1 = Event(event_id="1", session_id="s1", event_type="tool_call")
	store.add(e1)

	assert len(captured) == 1
	assert captured[0].event_id == "1"


def test_event_store_multiple_callbacks():
	store = EventStore()
	captured_a: list[Event] = []
	captured_b: list[Event] = []
	store.register_callback(lambda e: captured_a.append(e))
	store.register_callback(lambda e: captured_b.append(e))

	store.add(Event(event_id="1", session_id="s1", event_type="tool_call"))
	assert len(captured_a) == 1
	assert len(captured_b) == 1


def test_harness_can_continue_within_budget():
	config = HarnessConfig(max_iterations_per_hypothesis=5, max_total_tool_calls=10)
	store = EventStore()
	harness = Harness(config, store)

	assert harness.can_continue("hyp-1") is True


def test_harness_can_continue_hypothesis_budget_exceeded():
	config = HarnessConfig(max_iterations_per_hypothesis=2, max_total_tool_calls=100)
	store = EventStore()
	harness = Harness(config, store)

	# Record 2 tool calls for the same hypothesis
	for _ in range(2):
		harness.record_tool_call(
			session_id="s1",
			hypothesis_id="hyp-1",
			tool_name="compound_lookup",
			input_data={},
			output_data={"status": "success"},
			confidence=0.5,
		)

	assert harness.can_continue("hyp-1") is False
	# Other hypotheses should still be fine
	assert harness.can_continue("hyp-2") is True


def test_harness_can_continue_total_budget_exceeded():
	config = HarnessConfig(max_iterations_per_hypothesis=100, max_total_tool_calls=3)
	store = EventStore()
	harness = Harness(config, store)

	for i in range(3):
		harness.record_tool_call(
			session_id="s1",
			hypothesis_id=f"hyp-{i}",
			tool_name="compound_lookup",
			input_data={},
			output_data={"status": "success"},
			confidence=0.5,
		)

	assert harness.can_continue("hyp-new") is False


def test_harness_record_tool_call_creates_event():
	config = HarnessConfig()
	store = EventStore()
	harness = Harness(config, store)

	event = harness.record_tool_call(
		session_id="s1",
		hypothesis_id="hyp-1",
		tool_name="compound_lookup",
		input_data={"compound_name": "aspirin"},
		output_data={"status": "success"},
		confidence=0.5,
	)

	assert event.event_type == "tool_call"
	assert event.tool_name == "compound_lookup"
	assert event.session_id == "s1"
	assert event.hypothesis_id == "hyp-1"
	assert event.confidence_snapshot == 0.5
	assert len(store.events) == 1


def test_harness_consecutive_failure_tracking():
	config = HarnessConfig()
	store = EventStore()
	harness = Harness(config, store)

	# 3 consecutive failures should disable the tool
	for _ in range(3):
		harness.record_tool_call(
			session_id="s1",
			hypothesis_id="hyp-1",
			tool_name="broken_tool",
			input_data={},
			output_data={"status": "error"},
			confidence=0.0,
		)

	assert "broken_tool" in harness._disabled_tools
	assert harness._consecutive_failures["broken_tool"] == 3


def test_harness_failure_reset_on_success():
	config = HarnessConfig()
	store = EventStore()
	harness = Harness(config, store)

	# 2 failures
	for _ in range(2):
		harness.record_tool_call(
			session_id="s1",
			hypothesis_id="hyp-1",
			tool_name="flaky_tool",
			input_data={},
			output_data={"status": "error"},
			confidence=0.0,
		)

	assert harness._consecutive_failures["flaky_tool"] == 2

	# Success resets counter
	harness.record_tool_call(
		session_id="s1",
		hypothesis_id="hyp-1",
		tool_name="flaky_tool",
		input_data={},
		output_data={"status": "success"},
		confidence=0.5,
	)

	assert harness._consecutive_failures["flaky_tool"] == 0
	assert "flaky_tool" not in harness._disabled_tools


def test_harness_get_available_tools_filters_disabled():
	config = HarnessConfig()
	store = EventStore()
	harness = Harness(config, store)

	registry = {
		"tool_a": lambda: None,
		"tool_b": lambda: None,
		"tool_c": lambda: None,
	}

	# Disable tool_b
	harness._disabled_tools.add("tool_b")

	available = harness.get_available_tools(registry)
	assert "tool_a" in available
	assert "tool_b" not in available
	assert "tool_c" in available
	assert len(available) == 2
