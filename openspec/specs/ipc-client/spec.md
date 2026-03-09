# Capability: IPC Client

## Purpose
The IPC Client capability provides a high-level, decoupled connection between the HUD and the Flow Engine daemon. It ensures that HUD can receive real-time updates (pushes) and send requests to the engine without direct package dependencies, following an anti-corruption layer pattern.

## Requirements

### Requirement: Plugin Initialization and Connection
The IpcClientPlugin MUST establish an asynchronous connection to the main engine's Unix Domain Socket upon setup.

#### Scenario: Successful connection
- **WHEN** the plugin is initialized via `setup(ctx)`
- **THEN** it starts a background thread that connects to `~/.flow_engine/daemon.sock`

#### Scenario: Connection fails
- **WHEN** the daemon is not running or the socket is unavailable
- **THEN** it must log a warning and begin an exponential backoff retry mechanism (e.g., up to 10 seconds between retries) without crashing the HUD.

### Requirement: Receive and Dispatch Pushes
The plugin MUST continuously listen for Push messages from the daemon and dispatch them as HUD events.

#### Scenario: Push received
- **WHEN** the daemon sends a Push message (e.g., `{"type": "push", "event": "timer.tick", "data": {"tick": 1}}`)
- **THEN** the plugin attempts to parse it into a specialized dataclass via adapters, falling back to an `IpcMessageReceivedPayload`, and calls `ctx.event_bus.emit_background`.

### Requirement: Send Request messages (Future / MVP Preparation)
The plugin MUST prepare a mechanism to send Request messages to the daemon, although the primary MVP focus is listening to pushes.

#### Scenario: Request dispatched
- **WHEN** HUD internal components request to send an IPC message
- **THEN** the plugin routes the Request over the socket and awaits the Response, ensuring it does not block the Qt Main Event Loop.
