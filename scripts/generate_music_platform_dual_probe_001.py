from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ai_music_system.config import load_app_config
from ai_music_system.http import JsonHttpClient
from ai_music_system.models import ReviewRecord, SongRecord, TopicRecord
from ai_music_system.pipeline.cover_renderer import render_publish_covers
from ai_music_system.pipeline.package_builder import build_caption, build_song_metadata
from ai_music_system.providers.image.agnes_provider import AgnesImageProvider
from ai_music_system.providers.music.minimax_provider import MiniMaxMusicProvider


SPEC = {
    "song_id": "song_20260709_218",
    "topic_id": "tp_20260709_218",
    "batch_id": "batch_20260709_music_platform_dual_probe",
    "title": "先把天亮等出来",
    "topic": "做一首同时适合汽水音乐和番茄音乐发布的中文长歌单曲，情绪从深夜低谷慢慢抬升到重新愿意往前走。",
    "audience": "喜欢治愈流行、夜晚陪伴感、适合完整单曲循环的汽水音乐和番茄音乐用户。",
    "mood": "克制、真诚、逐渐明亮、带一点重整自己的力量。",
    "scene": "深夜快到天亮的时候，一个人把情绪慢慢理顺，决定继续好好生活。",
    "style_hint": (
        "中文流行单曲，适合汽水音乐和番茄音乐这类长歌平台发布。"
        "允许自然短前奏，但尽量控制在5到10秒，最晚15秒内进入清晰稳定主人声。"
        "不要先唱一句再回前奏，不要长时间纯器乐铺垫。"
        "整首歌目标时长3分到4分，结构完整，主歌叙述，预副歌抬升，副歌温暖上口，"
        "整体适合完整单曲收听和循环播放，不要做成短视频BGM。"
        "编曲以钢琴、吉他、轻鼓组、少量氛围铺底为主，旋律清晰，情绪有递进。"
    ),
    "lyrics": """[Verse 1]
窗外的天还没有亮
路灯把安静拉得很长
我把今晚没说出口的话
一遍一遍在心里轻轻放
原来有些委屈不会立刻散
原来人也会一边走一边慢慢还
还给昨天那些没收好的遗憾
还给自己一点重新开始的勇敢

[Pre-Chorus]
我知道不是每个夜晚
都能马上把答案照亮
可只要心里还有一点光
就不算真的走到绝望

[Chorus]
先把天亮等出来
把心里的阴天慢慢拨开
就算现在的我还没有多厉害
至少没有转身离开
先把天亮等出来
等风把旧情绪轻轻吹开
我会在新的清晨里面明白
有些路值得自己重来

[Verse 2]
桌上的水已经有点凉
像很多故事停在半章
我也曾以为只要足够坚强
就不会再被情绪推着晃
后来才懂温柔不是逞强
承认疲惫也不是投降
只要还能听见胸口那点回响
人就还能把明天再接上

[Pre-Chorus]
也许生活不会突然善良
也许未来还是偶尔迷茫
可我不想再为了看起来平静
把真正的自己藏起来受伤

[Chorus]
先把天亮等出来
把心里的阴天慢慢拨开
就算现在的我还没有多厉害
至少没有转身离开
先把天亮等出来
等风把旧情绪轻轻吹开
我会在新的清晨里面明白
有些路值得自己重来

[Bridge]
如果这一夜还是有点长
那就让旋律陪我慢慢唱
让没说完的话在歌里找到地方
让快熄灭的心重新发烫
不是所有黑夜都只剩失望
不是每次沉默都没有回响
等第一束光真的落在肩膀
我会知道自己没有白扛

[Final Chorus]
先把天亮等出来
把还没愈合的部分看开
就算明天的路还会有风吹来
我也想继续往前迈
先把天亮等出来
等我和自己重新和解以后明白
原来真正能把我带到未来
一直都是那个没放弃的我在

[Outro]
先把天亮等出来
我会陪自己走到天亮""",
    "cover_prompt": (
        "Square album cover, pure illustration, soft Japanese-inspired hand-painted anime style, "
        "young woman sitting by a window before sunrise with faint blue dawn light, gentle indoor plants, calm sky outside, "
        "healing and reflective mood, not urban neon, not realistic photo, elegant album-cover composition, no text."
    ),
}


def build_song(
    *,
    project_root: Path,
    config,
    music_provider: MiniMaxMusicProvider,
    image_provider: AgnesImageProvider,
) -> dict:
    now = datetime.now().replace(microsecond=0)
    song_dir = project_root / "data" / "songs" / SPEC["song_id"]
    song_dir.mkdir(parents=True, exist_ok=True)

    topic = TopicRecord(
        topic_id=SPEC["topic_id"],
        batch_id=SPEC["batch_id"],
        topic=SPEC["topic"],
        audience=SPEC["audience"],
        mood=SPEC["mood"],
        scene=SPEC["scene"],
        style_hint=SPEC["style_hint"],
        publish_platform="qishui_music",
        generation_mode="text_to_music",
        reference_audio_url="",
        distribution_target="music_platform",
    )

    song = SongRecord(
        song_id=SPEC["song_id"],
        topic_id=topic.topic_id,
        batch_id=topic.batch_id,
        run_id=f"run_{now:%Y%m%d_%H%M%S}_{SPEC['song_id']}",
        prompt_version=config.prompt_version,
        title=SPEC["title"],
        mode=topic.generation_mode,
        status="generating",
        generated_at=now.isoformat(),
        song_dir=song_dir,
        lyrics_raw_path=song_dir / "lyrics_raw.txt",
        lyrics_clean_path=song_dir / "lyrics_clean.txt",
        audio_path=song_dir / "audio.mp3",
        cover_raw_path=song_dir / "cover_raw.png",
        cover_publish_path=song_dir / "cover_publish.png",
        cover_hd_path=song_dir / "cover_hd.jpg",
        meta_path=song_dir / "meta.json",
        caption_path=song_dir / "caption.txt",
        review_path=song_dir / "review.json",
    )

    (song_dir / "topic.json").write_text(topic.model_dump_json(indent=2), encoding="utf-8")
    song.lyrics_raw_path.write_text(SPEC["lyrics"], encoding="utf-8")
    song.lyrics_clean_path.write_text(SPEC["lyrics"], encoding="utf-8")

    music_response = music_provider.generate_music(
        lyrics=SPEC["lyrics"],
        title=SPEC["title"],
        style_hint=topic.style_hint,
        output_path=song.audio_path,
        generation_mode=topic.generation_mode,
        reference_audio_url=topic.reference_audio_url,
    )
    image_response = image_provider.generate_cover(SPEC["cover_prompt"], song.cover_raw_path)
    render_publish_covers(
        source_path=song.cover_raw_path,
        publish_path=song.cover_publish_path,
        hd_path=song.cover_hd_path,
        title=SPEC["title"],
        publish_size=config.cover_publish_size,
        hd_size=config.cover_hd_size,
    )

    (song_dir / "cover_prompt.txt").write_text(SPEC["cover_prompt"], encoding="utf-8")
    (song_dir / "cover_response.json").write_text(
        json.dumps(image_response, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    meta = build_song_metadata(song, topic, config)
    meta["generation_debug"] = {
        "music_response_keys": list(music_response.keys()),
        "image_response_keys": list(image_response.keys()),
        "manual_lyrics": True,
        "probe_type": "music_platform_dual_001",
        "intro_target_seconds_max": 15,
        "intended_platforms": ["qishui_music", "fanqie_music"],
    }
    song.meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    song.caption_path.write_text(build_caption(song, topic), encoding="utf-8")

    review = ReviewRecord(
        song_id=song.song_id,
        run_id=song.run_id,
        prompt_version=config.prompt_version,
        hook_score=4,
        vocal_score=4,
        cover_score=4,
        publishable=False,
        review_source="manual_precheck",
        notes="Generated as a dual music-platform probe candidate. Pending listening review.",
        reviewed_at=datetime.now().replace(microsecond=0).isoformat(),
    )
    song.review_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")

    song.status = "generated"
    song.generated_at = datetime.now().replace(microsecond=0).isoformat()
    (song_dir / "song.json").write_text(song.model_dump_json(indent=2), encoding="utf-8")
    return {
        "song_id": SPEC["song_id"],
        "title": SPEC["title"],
        "audio_path": str(song.audio_path),
        "cover_path": str(song.cover_publish_path),
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    config = load_app_config(project_root)
    http_client = JsonHttpClient()
    music_provider = MiniMaxMusicProvider(config.music_provider, http_client)
    image_provider = AgnesImageProvider(config.image_provider, http_client)

    result = build_song(
        project_root=project_root,
        config=config,
        music_provider=music_provider,
        image_provider=image_provider,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
