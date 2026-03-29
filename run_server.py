#!/usr/bin/env python3
"""
run_server.py — Start ResumeEnv locally without Docker.
Usage:  python run_server.py
        python run_server.py --port 8080
"""
import argparse
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", default=True)
    args = parser.parse_args()

    print(f"🚀 Starting ResumeEnv on http://localhost:{args.port}")
    print(f"   Web UI: http://localhost:{args.port}/web")
    print(f"   Docs:   http://localhost:{args.port}/docs")
    print(f"   Press Ctrl+C to stop\n")

    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
