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
    "song_id": "song_20260708_217",
    "topic_id": "tp_20260708_217",
    "batch_id": "batch_20260708_qishui_rock_probe_v3",
    "title": "把风声开大一点",
    "topic": "做一首更适合汽水音乐发布的中文流行摇滚单曲，允许正常短前奏，但人声最晚15秒内进入，整体要有成熟单曲感。",
    "audience": "喜欢旋律型中文流行摇滚、夜路感、适合单曲循环的汽水音乐用户。",
    "mood": "安静起步，逐步抬升，坚定，带一点深夜自我鼓劲。",
    "scene": "夜里一个人往前走，风很大，耳机里需要一首能把情绪重新撑起来的歌。",
    "style_hint": (
        "中文流行摇滚单曲，女声或偏中性声线。允许有完整前奏，但前奏必须自然、连续、"
        "有乐队感，长度尽量控制在5到10秒，最晚15秒内必须进入稳定主人声。"
        "不要先唱一句再回前奏，不要过长纯器乐铺垫。"
        "整首歌目标时长3分到4分，主歌叙述，预副歌抬升，副歌有释放感和记忆点。"
        "编曲以电吉他、鼓组、贝斯为主，少量氛围铺底即可，整体服务汽水音乐完整单曲收听，不要做成短视频BGM。"
    ),
    "lyrics": """[Verse 1]
今晚的风有一点直接
把没说完的话吹到了眼前
我沿着路灯一盏一盏走远
像沿着旧情绪慢慢拆线
白天那些来不及消化的疲倦
到了深夜反而更诚实一点
我不是突然就变得勇敢
只是终于不想再躲在明天

[Pre-Chorus]
如果所有答案都还没出现
那就先让心跳把方向排练
有些路本来就要顶着风走
走着走着人才会慢慢听见自己

[Chorus]
把风声开大一点
别让沉默先占据耳边
哪怕世界还是一样喧嚣又敷衍
这一刻我想先相信直觉
把风声开大一点
把胸口的犹豫都吹远
我不一定马上就能翻过这一页
但至少今晚我没有后退

[Verse 2]
远处楼影像还没亮透的梦
忽明忽暗却还留着轮廓
我也曾在很多个快放弃的时候
假装自己其实没那么难过
后来才懂逞强不是结果
承认脆弱也不等于示弱
只要还有一点想往前的火
就值得为自己再唱一首

[Pre-Chorus]
也许明天依旧会有乌云压头
也许生活不会立刻温柔
可在天亮之前至少我能选择
不把真正的心事继续锁着

[Chorus]
把风声开大一点
别让沉默先占据耳边
哪怕世界还是一样喧嚣又敷衍
这一刻我想先相信直觉
把风声开大一点
把胸口的犹豫都吹远
我不一定马上就能翻过这一页
但至少今晚我没有后退

[Bridge]
让吉他把压抑撕开
让鼓点替我把脚步抬起来
如果路还长 那就继续走
如果夜太黑 那就继续吼
不是每个人都生来耀眼
可平凡的人也能有自己的光源
等风穿过肩膀和指尖
我会知道自己还没有熄灭

[Final Chorus]
把风声开大一点
让我听清心里那个瞬间
它说别再把希望交给遥远
就从今夜开始往前
把风声开大一点
把还没愈合的部分都照见
就算明天还是一样要面对一切
至少今晚我真的向前了一点

[Outro]
把风声开大一点
我听见自己还想走更远""",
    "cover_prompt": (
        "Square album cover, pure illustration, Japanese-inspired hand-painted anime style, "
        "young woman on a windy hillside at night, open landscape and mountains, guitar case nearby, "
        "soft distant lights only as tiny background accents, not urban, not neon, expressive rock mood, painterly texture, no text."
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
        "probe_type": "qishui_rock_v3",
        "intro_target_seconds_max": 15,
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
        notes="Generated as a Qishui rock probe v3 candidate. Pending listening review.",
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
