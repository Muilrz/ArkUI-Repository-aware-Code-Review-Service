"""Platform-neutral foundations for the Code Review Service.

The package is organized as inward-pointing layers:

``domain <- ports <- application`` and ``domain/ports <- adapters``.

R0 provides the reusable contracts. Fast-MVP M1 adds a minimal GitCode REST adapter
and PR-context CLI. M2 adds a platform-neutral Code Agent port and its first Codex
backend; knowledge, publishing, MCP, and scheduling remain outside this milestone.
"""
