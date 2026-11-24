# llm-planner Specification

## Purpose
Lets a user ask in everyday Traditional Chinese while keeping the LLM out of numeric computation: the planner understands the question, asks for missing information, calls only declared tools, and returns an answer only when every number can be traced to a tool result. Corresponds to modules ② and ③.

## Requirements

### Requirement: Natural-language understanding with clarification

The system SHALL extract the place, time, user group, activity and duration from a Traditional Chinese question, and SHALL ask one clarifying question when the place cannot be resolved to coordinates in a supported city.

#### Scenario: Complete question

- **WHEN** a user asks "我在高雄前金區，現在可以帶小孩去公園跑步嗎？"
- **THEN** the planner resolves 前金區 to coordinates in 高雄市, sets the group to child and the activity to exercise
- **AND** calls the data tools without asking a question first

#### Scenario: Missing place

- **WHEN** a user asks "現在適合出去跑步嗎？" without a place
- **THEN** the planner asks where the user is
- **AND** does not call any data tool before the place is known

#### Scenario: Unsupported city

- **WHEN** the place is in a city without collected data
- **THEN** the planner says which cities are supported instead of inventing data

### Requirement: Tool use through function calling

The system SHALL let the LLM call only the tools declared for the planner, SHALL execute each call with the deterministic implementation, and SHALL log every call in the answer trace.

#### Scenario: Unknown tool name

- **WHEN** the LLM requests a tool that is not declared
- **THEN** the call is rejected with an error message returned to the LLM
- **AND** the rejection is recorded in the trace

#### Scenario: Step limit

- **WHEN** the LLM has made 12 tool calls without producing an answer
- **THEN** the planner stops and returns the deterministic answer

### Requirement: Number traceability check

The system SHALL verify that every number followed by μg/m³, %, km or m/s in the final text matches a value in the tool results within rounding, and SHALL not return an answer that fails the check.

#### Scenario: Hallucinated number

- **WHEN** the LLM writes a concentration that does not appear in any tool result
- **THEN** the planner asks the LLM to rewrite once using only tool values
- **AND** if the rewrite still fails, the deterministic answer is returned and the trace records the failure

### Requirement: Model availability fallback

The system SHALL try the configured Gemini models in order and move to the next model when a model reports overload (HTTP 503) or exhausted quota (HTTP 429), and SHALL record which model produced the answer.

#### Scenario: Primary model overloaded

- **WHEN** the first model returns HTTP 503
- **THEN** the planner retries with the next model in the list
- **AND** the trace shows the model that answered

### Requirement: Deterministic fallback

The system SHALL produce a complete four-part answer without any LLM when no API key is configured or no model is available.

#### Scenario: No API key

- **WHEN** `GEMINI_API_KEY` is not set
- **THEN** the demo and the CLI still answer structured queries with the deterministic pipeline
- **AND** the answer states that the LLM is not enabled
