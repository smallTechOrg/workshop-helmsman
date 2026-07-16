"""Module entrypoint — boots uvicorn against 0.0.0.0:8001."""

import os

import uvicorn


def main() -> None:
    host = os.environ.get("BIND_HOST", "0.0.0.0")
    port = int(os.environ.get("BIND_PORT", "8001"))
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        log_level=os.environ.get("LOG_LEVEL", "info"),
        reload=False,
    )


if __name__ == "__main__":
    main()
