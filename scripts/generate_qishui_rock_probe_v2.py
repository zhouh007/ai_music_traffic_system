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
    "song_id": "song_20260708_216",
    "topic_id": "tp_20260708_216",
    "batch_id": "batch_20260708_qishui_rock_probe_v2",
    "title": "风太大就迎着走",
    "topic": "在被现实推着走的阶段，想做一首更成熟的中文摇滚流行单曲，先给短前奏，再自然进入主歌，不做突兀的人声抢开。",
    "audience": "喜欢旋律型中文流行摇滚、适合单曲循环和深夜通勤收听的汽水音乐用户。",
    "mood": "冷静起步，逐渐抬升，坚定，带克制后的爆发。",
    "scene": "夜路、耳机、风很大，但人没有想退，适合一个人边走边听。",
    "style_hint": (
        "中文流行摇滚单曲，女声或偏中性声线。开头必须是完整且连续的短前奏，"
        "长度控制在3到5秒，只允许电吉他、鼓点或贝斯带出情绪，然后自然进入主歌第一句。"
        "严禁先唱一句人声再回到前奏，严禁人声抢开后中断。"
        "整首歌目标时长3分到4分，结构完整，主歌有叙述感，预副歌抬升，副歌有释放感和记忆点。"
        "编曲以真实乐队感为主，不要做成短视频BGM。"
    ),
    "lyrics": """[Verse 1]
风吹过空街像没说完的话
鞋底敲着节拍一步一步往下
白天那些劝我算了吧的人啊
到了夜里却比我更安静啊
我不是没有怀疑过自己
也不是天生就擅长撑下去
只是每次快被现实压低
心里总有一点声音不肯关机

[Pre-Chorus]
如果这世界要我学会沉默
至少今晚我想先诚实活着
把那些吞回去的话还给风
让它们替我往更远的地方冲

[Chorus]
风太大就迎着走
就算眼睛被吹得有点红
我不要再把自己藏在
每一句算了以后
风太大就迎着走
哪怕明天还会有乌云压头
至少这一刻我敢承认
我还想发光 我还想往前冲

[Verse 2]
远处灯火把山城照得模糊
像很多答案不必急着看清楚
有些失去并不是谁的错误
有些慢慢长大本来就会辛苦
我学着和不甘并肩站着
学着不把眼泪当成软弱
原来最难的不是被谁懂得
是一个人的时候也别放弃自我

[Pre-Chorus]
如果连我都不替自己发声
那些梦要怎么穿过人海回声
就让鼓点推着胸口继续热
让吉他把忍耐都割出裂缝

[Chorus]
风太大就迎着走
就算眼睛被吹得有点红
我不要再把自己藏在
每一句算了以后
风太大就迎着走
哪怕明天还会有乌云压头
至少这一刻我敢承认
我还想发光 我还想往前冲

[Bridge]
也许路不会突然变平整
也许掌声不会刚好在此刻发生
可我终于不想再为了体面
把真正的心跳一层层关灯
让夜色见证我的倔强
让风声替我把名字唱响
如果未来真的还有长路要闯
那就从今夜开始别再投降

[Final Chorus]
风太大就迎着走
把所有迟疑都唱成怒吼
我知道生活不会因为我
一首歌就变得温柔
可风太大就迎着走
总有人要先学会不低头
等天亮照见一路汗水以后
我会知道这一次没有白走

[Outro]
风太大就迎着走
我听见心还在胸口发热""",
    "cover_prompt": (
        "Square album cover, pure illustration, Japanese-inspired painted anime style, "
        "young woman alone on a grassy hillside in strong night wind, distant mountains and soft town lights far below, "
        "guitar case by her side, expressive but not urban, no subway, no neon city street, painterly rock-single mood, no text."
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
        "probe_type": "qishui_rock_v2",
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
        notes="Generated as a Qishui rock probe v2 candidate. Pending listening review.",
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
