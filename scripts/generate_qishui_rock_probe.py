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
    "song_id": "song_20260708_215",
    "topic_id": "tp_20260708_215",
    "batch_id": "batch_20260708_qishui_rock_probe",
    "title": "别把夜晚让给沉默",
    "topic": "在情绪快要被现实压住的时候，想用一首带力量感的中文摇滚流行把人重新点燃。",
    "audience": "喜欢有旋律、有爆发力、适合循环播放的汽水音乐中文流行摇滚用户。",
    "mood": "克制起步，随后上扬，坚定，带一点不服输。",
    "scene": "深夜开车、一个人走回家、耳机音量稍微开大，想把闷着的话唱出来。",
    "style_hint": (
        "中文流行摇滚女声/中性声线，前2到3秒内必须直接进入清晰人声，"
        "不要长前奏，不要纯器乐铺垫。完整歌曲目标时长3分到4分，"
        "结构完整，主歌克制，预副歌抬升，副歌有明显记忆点与释放感。"
        "编曲以真实乐队感为主：电吉他、鼓组、贝斯，允许少量铺底合成器，"
        "整体适合汽水音乐单曲收听，不要做成短视频BGM。"
    ),
    "lyrics": """[Intro]
别把夜晚让给沉默

[Verse 1]
楼下的风又吹乱广告灯
像一句没说完的话在晃动
白天那些体面的笑容
一到深夜就开始变重
我把钥匙攥得有点发疼
像攥住最后一点冲动
世界总要我们安静成熟
可我偏想把心事吼成歌

[Pre-Chorus]
如果连我都不替自己发声
还有谁会听见这点滚烫体温
那些被现实压低的灵魂
也该有一次抬头的可能

[Chorus]
别把夜晚让给沉默
把胸口那团火用力唱破
哪怕明天还是一样奔波
至少这一刻我没有退缩
别把眼泪交给夜色
把每一道裂缝都变成轮廓
我知道生活从不会温柔
可我还能倔强地亮着

[Verse 2]
地铁尽头的人群散得很快
只剩我和影子走在站外
有些答案不会立刻到来
有些失败也不是被淘汰
我听见鞋底敲着空街拍
像在给心跳重新打节拍
原来不是非得谁来拯救
我也可以自己把自己抬起来

[Pre-Chorus]
那些被误解的、不被看好的
都在黑夜里偷偷练习活着
既然天亮之前总要穿过冷风
那就唱得比沉默更响彻

[Chorus]
别把夜晚让给沉默
把胸口那团火用力唱破
哪怕明天还是一样奔波
至少这一刻我没有退缩
别把眼泪交给夜色
把每一道裂缝都变成轮廓
我知道生活从不会温柔
可我还能倔强地亮着

[Bridge]
也许我没有传说里的天赋
也许我只是普通得太清楚
可普通的人也该有资格
在自己的故事里全力以赴
让吉他把犹豫全部撕开
让鼓点替我把答案说出来
如果前方还是风很大的路
那我就迎着风继续迈步

[Final Chorus]
别把夜晚让给沉默
我要把所有不甘唱成烟火
哪怕世界依旧催我认错
我也不想再把自己错过
别把未来交给如果
从今夜开始让我真的活过
等天亮照见汗水和轮廓
我会知道我没有白熬过

[Outro]
别把夜晚让给沉默
今晚我先为自己唱着""",
    "cover_prompt": (
        "Square album cover, pure illustration, Japanese-inspired hand-painted anime style, "
        "young woman standing alone on a windy hillside at night with guitar case, "
        "distant warm town lights below, deep blue sky, strong wind in hair and coat, "
        "emotional but not urban, expressive rock mood, painterly texture, no neon city street, no text."
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
        "probe_type": "qishui_rock",
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
        notes="Generated as a Qishui rock probe candidate. Pending listening review.",
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
