from __future__ import annotations

import sys
from pathlib import Path

try:
    from flow_ipc import Frame, decode_frame, encode_frame
except ModuleNotFoundError:
    shared_dir = Path(__file__).resolve().parents[4] / "shared"
    if str(shared_dir) not in sys.path:
        sys.path.insert(0, str(shared_dir))
    from flow_ipc import Frame, decode_frame, encode_frame  # type: ignore[no-redef]


def encode_message(msg: Frame) -> bytes:
    return encode_frame(msg)


def decode_message(data: bytes) -> Frame:
    return decode_frame(data)

