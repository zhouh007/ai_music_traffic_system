from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

import imageio_ffmpeg
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "data" / "songs"
EXPORT_ROOT = PROJECT_ROOT / "data" / "exports"
MOCK_CONFIG_PATH = PROJECT_ROOT / "config" / "providers.local.json"
MOCK_TOPICS_PATH = PROJECT_ROOT / "data" / "topics" / "topics_verify.csv"

VERIFY_TOPICS = [
    {
        "topic_id": "tp_verify_001",
        "batch_id": "batch_verify_multi",
        "topic": "\u6df1\u591c\u60f3\u8d77\u4e00\u4e2a\u4e0d\u4f1a\u518d\u8054\u7cfb\u7684\u4eba",
        "audience": "\u90fd\u5e02\u60c5\u7eea\u4eba\u7fa4",
        "mood": "\u4f24\u611f",
        "scene": "\u591c\u665a\u5237\u89c6\u9891",
        "style_hint": "\u4e2d\u6587\u6d41\u884c\u6292\u60c5",
        "publish_platform": "douyin",
        "status": "pending",
    },
    {
        "topic_id": "tp_verify_002",
        "batch_id": "batch_verify_multi",
        "topic": "\u96e8\u505c\u4e4b\u540e\u4e00\u4e2a\u4eba\u8d70\u56de\u65e7\u5730\u65b9",
        "audience": "\u901a\u52e4\u591c\u5f52\u4eba\u7fa4",
        "mood": "\u6cbb\u6108",
        "scene": "\u57ce\u5e02\u96e8\u540e\u8857\u666f",
        "style_hint": "\u6c1b\u56f4\u611f\u7535\u5b50\u6d41\u884c",
        "publish_platform": "douyin",
        "status": "pending",
    },
    {
        "topic_id": "tp_verify_003",
        "batch_id": "batch_verify_multi",
        "topic": "\u8bf4\u4e86\u518d\u89c1\u4ee5\u540e\u624d\u61c2\u5f97\u4ec0\u4e48\u53eb\u9057\u61be",
        "audience": "\u60c5\u611f\u77ed\u89c6\u9891\u7528\u6237",
        "mood": "\u60c6\u6026",
        "scene": "\u51cc\u6668\u8033\u673a\u72ec\u5904",
        "style_hint": "\u7ebf\u6027\u53d9\u4e8b\u5973\u58f0\u60c5\u6b4c",
        "publish_platform": "douyin",
        "status": "pending",
    },
]

MOCK_LYRICS = (
    "[Verse 1]\n"
    "\u591c\u91cc\u6211\u53c8\u7ffb\u5f00\u65e7\u5bf9\u767d\n"
    "[Chorus]\n"
    "\u4f60\u6ca1\u56de\u6765\u6211\u8fd8\u5728\u7b49\u5f85\n"
    "[Verse 2]\n"
    "\u57ce\u5e02\u7684\u98ce\u5439\u8fc7\u7a97\u53f0\n\n"
    "[Chorus]\n"
    "\u4f60\u6ca1\u56de\u6765\u6211\u8fd8\u5728\u7b49\u5f85\n"
    "[Bridge]\n"
    "\u628a\u9057\u61be\u6162\u6162\u5531\u51fa\u6765\n\n"
    "[Chorus]\n"
    "\u4f60\u6ca1\u56de\u6765\u6211\u8fd8\u5728\u7b49\u5f85"
)

CAPTION_MARKER = "#AI"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local multi-item E2E publish rehearsal with mock providers.")
    parser.add_argument(
        "--prepare-publish",
        action="store_true",
        help="Also export approved songs and prepare primary-platform publish jobs.",
    )
    parser.add_argument(
        "--include-fanqie",
        action="store_true",
        help="Also prepare and validate a Fanqie Music package for the verify batch.",
    )
    parser.add_argument(
        "--archive-legacy",
        action="store_true",
        help="Also archive legacy_partial publish jobs after the rehearsal so active views stay clean.",
    )
    parser.add_argument(
        "--simulate-fanqie-session",
        action="store_true",
        help="After preparing Fanqie packages, simulate a local semi-auto upload session and verify job backfill.",
    )
    args = parser.parse_args()

    _cleanup_previous_outputs()
    png_bytes = _build_png_bytes()
    mp3_bytes = _build_mock_mp3_bytes()
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

        for song_id in _verify_song_ids():
            _run_cli(
                [
                    "approve-song",
                    "--song-id",
                    song_id,
                    "--hook-score",
                    "4",
                    "--vocal-score",
                    "4",
                    "--cover-score",
                    "4",
                    "--notes",
                    "Local multi-item e2e rehearsal",
                ],
                env,
            )

        _run_cli(["export-approved"], env)
        export_dir = _assert_export_outputs()

        if args.prepare_publish:
            _run_cli(["prepare-publish", "--export-dir", str(export_dir)], env)
            _assert_publish_jobs(expected_count=len(VERIFY_TOPICS))
        if args.include_fanqie:
            _run_cli(["prepare-publish", "--export-dir", str(export_dir), "--platforms", "fanqie_music"], env)
            _assert_fanqie_packages()
            if args.simulate_fanqie_session:
                _simulate_and_assert_fanqie_session(env)

        if args.archive_legacy:
            _run_cli(["publish-archive-legacy", "--label", "verify_legacy_archive"], env)

        print("Local multi-item E2E rehearsal passed.")
    finally:
        server.shutdown()
        server.server_close()
        if MOCK_CONFIG_PATH.exists():
            MOCK_CONFIG_PATH.unlink()
        if MOCK_TOPICS_PATH.exists():
            MOCK_TOPICS_PATH.unlink()


def _verify_song_ids() -> list[str]:
    return [row["topic_id"].replace("tp_", "song_") for row in VERIFY_TOPICS]


def _run_cli(arguments: list[str], env: dict[str, str]) -> None:
    subprocess.run(
        [sys.executable, "-m", "ai_music_system.cli", *arguments],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )


def _cleanup_previous_outputs() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)

    for song_id in _verify_song_ids():
        verify_song_dir = OUTPUT_ROOT / song_id
        if verify_song_dir.exists():
            shutil.rmtree(verify_song_dir)

    for export_dir in EXPORT_ROOT.glob("approved_*"):
        if not export_dir.is_dir():
            continue
        for song_id in _verify_song_ids():
            verify_export_dir = export_dir / song_id
            if verify_export_dir.exists():
                shutil.rmtree(verify_export_dir)
        residual_files = [item for item in export_dir.iterdir()]
        if not residual_files:
            shutil.rmtree(export_dir)


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
    with MOCK_TOPICS_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(VERIFY_TOPICS[0].keys()))
        writer.writeheader()
        writer.writerows(VERIFY_TOPICS)


def _start_mock_server(png_bytes: bytes, mp3_bytes: bytes) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            if self.path == "/deepseek/chat/completions":
                _send_json(
                    self,
                    {
                        "choices": [{"message": {"content": MOCK_LYRICS}}],
                        "received_model": payload.get("model"),
                    },
                )
                return
            if self.path == "/minimax/music_generation":
                _send_json(
                    self,
                    {
                        "data": {
                            "audio": f"http://127.0.0.1:{self.server.server_address[1]}/assets/audio.mp3"
                        },
                        "received_model": payload.get("model"),
                    },
                )
                return
            if self.path == "/agnes/images/generations":
                _send_json(
                    self,
                    {
                        "data": [
                            {
                                "url": f"http://127.0.0.1:{self.server.server_address[1]}/assets/cover.png"
                            }
                        ],
                        "received_model": payload.get("model"),
                    },
                )
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


def _build_mock_mp3_bytes() -> bytes:
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "silence.mp3"
        command = [
            ffmpeg_path,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t",
            "32",
            "-q:a",
            "2",
            str(output_path),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        return output_path.read_bytes()


def _assert_song_outputs() -> None:
    required_names = [
        "lyrics_raw.txt",
        "lyrics_clean.txt",
        "audio.mp3",
        "cover_raw.png",
        "cover_publish.png",
        "cover_hd.jpg",
        "meta.json",
        "caption.txt",
        "review.json",
        "song.json",
    ]
    for song_id in _verify_song_ids():
        song_dir = OUTPUT_ROOT / song_id
        missing = [str(song_dir / name) for name in required_names if not (song_dir / name).exists()]
        if missing:
            raise AssertionError(f"Missing expected output files for {song_id}: {missing}")
        song_payload = json.loads((song_dir / "song.json").read_text(encoding="utf-8"))
        if song_payload["status"] != "generated":
            raise AssertionError(f"Expected generated status for {song_id}, got {song_payload['status']}")
        caption = (song_dir / "caption.txt").read_text(encoding="utf-8")
        if CAPTION_MARKER not in caption:
            raise AssertionError(f"Caption content was not generated correctly for {song_id}.")


def _assert_export_outputs() -> Path:
    export_dirs = [path for path in EXPORT_ROOT.iterdir() if path.is_dir()]
    if not export_dirs:
        raise AssertionError("No export directory was created.")
    latest_export = max(export_dirs, key=lambda path: path.stat().st_mtime)
    for song_id in _verify_song_ids():
        song_export_dir = latest_export / song_id
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
            raise AssertionError(f"Missing expected exported files for {song_id}: {missing}")

    summary_path = latest_export / "export_summary.json"
    manifest_path = latest_export / "publish_manifest.json"
    if not summary_path.exists() or not manifest_path.exists():
        raise AssertionError("Expected export summary and publish manifest to exist.")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("export_count") != len(VERIFY_TOPICS):
        raise AssertionError(f"Expected export_count={len(VERIFY_TOPICS)}, got {summary.get('export_count')}")
    return latest_export


def _assert_publish_jobs(expected_count: int) -> None:
    jobs_dir = PROJECT_ROOT / "data" / "publish" / "jobs"
    verify_job_paths = sorted(jobs_dir.glob("pub_douyin_song_verify_*.json"))
    if len(verify_job_paths) < expected_count:
        raise AssertionError(
            f"Expected at least {expected_count} verify publish jobs, got {len(verify_job_paths)}."
        )


def _assert_fanqie_packages() -> None:
    for song_id in _verify_song_ids():
        package_dir = PROJECT_ROOT / "data" / "publish" / "packages" / song_id / "fanqie_music"
        required_paths = [
            package_dir / "audio.mp3",
            package_dir / "cover_publish.png",
            package_dir / "lyrics_clean.txt",
            package_dir / "meta.json",
            package_dir / "publish_text.txt",
            package_dir / "release_brief.json",
            package_dir / "operator_checklist.txt",
        ]
        missing = [str(path) for path in required_paths if not path.exists()]
        if missing:
            raise AssertionError(f"Missing expected Fanqie package files for {song_id}: {missing}")
        publish_text = (package_dir / "publish_text.txt").read_text(encoding="utf-8")
        if "短视频BGM" in publish_text:
            raise AssertionError(f"Fanqie publish text still contains short-video phrasing for {song_id}.")
        release_brief = json.loads((package_dir / "release_brief.json").read_text(encoding="utf-8"))
        if not release_brief.get("music_platform_profile"):
            raise AssertionError(f"Fanqie release brief missing music_platform_profile for {song_id}.")


def _simulate_and_assert_fanqie_session(env: dict[str, str]) -> None:
    jobs_dir = PROJECT_ROOT / "data" / "publish" / "jobs"
    verify_jobs = sorted(jobs_dir.glob("pub_fanqie_music_song_verify_*.json"))
    if not verify_jobs:
        raise AssertionError("Expected Fanqie verify jobs before simulating upload session.")
    job_id = verify_jobs[-1].stem
    _run_cli(["music-upload-run", "--job-id", job_id, "--simulate-session"], env)
    payload = json.loads((jobs_dir / f"{job_id}.json").read_text(encoding="utf-8"))
    if payload.get("status") != "saved_for_review":
        raise AssertionError(f"Expected simulated Fanqie job to be saved_for_review, got {payload.get('status')}")
    automation_summary = payload.get("automation_summary", {})
    if automation_summary.get("mode") != "simulated_local_verification":
        raise AssertionError("Expected simulated Fanqie automation summary to be backfilled into the job record.")


if __name__ == "__main__":
    main()
