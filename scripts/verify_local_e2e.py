from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "data" / "songs"
EXPORT_ROOT = PROJECT_ROOT / "data" / "exports"
MOCK_CONFIG_PATH = PROJECT_ROOT / "config" / "providers.local.json"
MOCK_TOPICS_PATH = PROJECT_ROOT / "data" / "topics" / "topics_verify.csv"


def main() -> None:
    _cleanup_previous_outputs()
    png_bytes = _build_png_bytes()
    mp3_bytes = b"ID3" + (b"\x00" * 256)
    server = _start_mock_server(png_bytes, mp3_bytes)
    try:
        port = server.server_address[1]
        _write_mock_config(port)
        _write_mock_topics()
        env = os.environ.copy()
        env["DEEPSEEK_API_KEY"] = "verify-deepseek"
        env["MINIMAX_API_KEY"] = "verify-minimax"
        env["AGNES_API_KEY"] = "verify-agnes"

        _run_cli(["run-batch", "--topics-file", str(MOCK_TOPICS_PATH)], env)
        _assert_song_outputs()
        _run_cli(
            [
                "approve-song",
                "--song-id",
                "song_verify_001",
                "--hook-score",
                "4",
                "--vocal-score",
                "4",
                "--cover-score",
                "4",
                "--notes",
                "Local e2e verification",
            ],
            env,
        )
        _run_cli(["export-approved"], env)
        _assert_export_outputs()
        print("E2E verification passed.")
    finally:
        server.shutdown()
        server.server_close()
        if MOCK_CONFIG_PATH.exists():
            MOCK_CONFIG_PATH.unlink()
        if MOCK_TOPICS_PATH.exists():
            MOCK_TOPICS_PATH.unlink()


def _run_cli(arguments: list[str], env: dict[str, str]) -> None:
    subprocess.run(
        [sys.executable, "-m", "ai_music_system.cli", *arguments],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )


def _cleanup_previous_outputs() -> None:
    for path in [OUTPUT_ROOT, EXPORT_ROOT]:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def _write_mock_config(port: int) -> None:
    payload = {
        "lyrics_provider": {
            "base_url": f"http://127.0.0.1:{port}/deepseek",
            "model": "mock-deepseek",
            "timeout_seconds": 10,
        },
        "music_provider": {
            "base_url": f"http://127.0.0.1:{port}/minimax",
            "model": "mock-minimax",
            "output_format": "url",
            "timeout_seconds": 10,
        },
        "image_provider": {
            "base_url": f"http://127.0.0.1:{port}/agnes",
            "model": "mock-agnes",
            "return_base64": False,
            "timeout_seconds": 10,
        },
    }
    MOCK_CONFIG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_mock_topics() -> None:
    rows = [
        {
            "topic_id": "tp_verify_001",
            "batch_id": "batch_verify",
            "topic": "深夜想起一个不会再联系的人",
            "audience": "都市情绪人群",
            "mood": "伤感",
            "scene": "夜晚刷视频",
            "style_hint": "中文流行抒情",
            "publish_platform": "douyin",
            "status": "pending",
        }
    ]
    with MOCK_TOPICS_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _start_mock_server(png_bytes: bytes, mp3_bytes: bytes) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            if self.path == "/deepseek/chat/completions":
                body = {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    "[Verse 1]\n夜里我又翻开旧对白\n\n"
                                    "[Chorus]\n你没回来我还在等待\n\n"
                                    "[Verse 2]\n城市的风吹过窗台\n\n"
                                    "[Chorus]\n你没回来我还在等待\n\n"
                                    "[Bridge]\n把遗憾慢慢唱出来\n\n"
                                    "[Chorus]\n你没回来我还在等待\n"
                                )
                            }
                        }
                    ],
                    "received_model": payload.get("model"),
                }
                _send_json(self, body)
                return
            if self.path == "/minimax/music_generation":
                body = {
                    "data": {
                        "audio": f"http://127.0.0.1:{self.server.server_address[1]}/assets/audio.mp3"
                    },
                    "received_model": payload.get("model"),
                }
                _send_json(self, body)
                return
            if self.path == "/agnes/images/generations":
                body = {
                    "data": [
                        {
                            "url": f"http://127.0.0.1:{self.server.server_address[1]}/assets/cover.png"
                        }
                    ],
                    "received_model": payload.get("model"),
                }
                _send_json(self, body)
                return
            self.send_response(404)
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/assets/audio.mp3":
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(mp3_bytes)))
                self.end_headers()
                self.wfile.write(mp3_bytes)
                return
            if self.path == "/assets/cover.png":
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(png_bytes)))
                self.end_headers()
                self.wfile.write(png_bytes)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _send_json(handler: BaseHTTPRequestHandler, body: dict) -> None:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _build_png_bytes() -> bytes:
    image = Image.new("RGB", (1024, 1024), color=(24, 30, 44))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _assert_song_outputs() -> None:
    song_dir = OUTPUT_ROOT / "song_verify_001"
    required_paths = [
        song_dir / "lyrics_raw.txt",
        song_dir / "lyrics_clean.txt",
        song_dir / "audio.mp3",
        song_dir / "cover_raw.png",
        song_dir / "cover_publish.png",
        song_dir / "cover_hd.jpg",
        song_dir / "meta.json",
        song_dir / "caption.txt",
        song_dir / "review.json",
        song_dir / "song.json",
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise AssertionError(f"Missing expected output files: {missing}")
    song_payload = json.loads((song_dir / "song.json").read_text(encoding="utf-8"))
    if song_payload["status"] != "generated":
        raise AssertionError(f"Expected generated status, got {song_payload['status']}")
    caption = (song_dir / "caption.txt").read_text(encoding="utf-8")
    if "AI音乐" not in caption:
        raise AssertionError("Caption content was not generated correctly.")


def _assert_export_outputs() -> None:
    export_dirs = [path for path in EXPORT_ROOT.iterdir() if path.is_dir()]
    if not export_dirs:
        raise AssertionError("No export directory was created.")
    latest_export = max(export_dirs, key=lambda path: path.stat().st_mtime)
    song_export_dir = latest_export / "song_verify_001"
    required_paths = [
        song_export_dir / "audio.mp3",
        song_export_dir / "lyrics_clean.txt",
        song_export_dir / "cover_publish.png",
        song_export_dir / "cover_hd.jpg",
        song_export_dir / "meta.json",
        song_export_dir / "caption.txt",
        song_export_dir / "review.json",
        song_export_dir / "review_summary.json",
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise AssertionError(f"Missing expected exported files: {missing}")


if __name__ == "__main__":
    main()
