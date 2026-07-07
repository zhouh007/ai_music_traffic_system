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


def build_song(
    *,
    project_root: Path,
    config,
    music_provider: MiniMaxMusicProvider,
    image_provider: AgnesImageProvider,
    spec: dict,
) -> dict:
    now = datetime.now().replace(microsecond=0)
    song_dir = project_root / "data" / "songs" / spec["song_id"]
    song_dir.mkdir(parents=True, exist_ok=True)

    topic = TopicRecord(
        topic_id=spec["topic_id"],
        batch_id="batch_20260707_qishui_probe_v2",
        topic=spec["topic"],
        audience=spec["audience"],
        mood=spec["mood"],
        scene=spec["scene"],
        style_hint=spec["style_hint"],
        publish_platform="qishui_music",
        generation_mode="text_to_music",
        reference_audio_url="",
        distribution_target="music_platform",
    )

    song = SongRecord(
        song_id=spec["song_id"],
        topic_id=topic.topic_id,
        batch_id=topic.batch_id,
        run_id=f"run_{now:%Y%m%d_%H%M%S}_{spec['song_id']}",
        prompt_version=config.prompt_version,
        title=spec["title"],
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
    song.lyrics_raw_path.write_text(spec["lyrics"], encoding="utf-8")
    song.lyrics_clean_path.write_text(spec["lyrics"], encoding="utf-8")

    music_response = music_provider.generate_music(
        lyrics=spec["lyrics"],
        title=spec["title"],
        style_hint=topic.style_hint,
        output_path=song.audio_path,
        generation_mode=topic.generation_mode,
        reference_audio_url=topic.reference_audio_url,
    )
    image_response = image_provider.generate_cover(spec["cover_prompt"], song.cover_raw_path)
    render_publish_covers(
        source_path=song.cover_raw_path,
        publish_path=song.cover_publish_path,
        hd_path=song.cover_hd_path,
        title=spec["title"],
        publish_size=config.cover_publish_size,
        hd_size=config.cover_hd_size,
    )

    (song_dir / "cover_prompt.txt").write_text(spec["cover_prompt"], encoding="utf-8")
    (song_dir / "cover_response.json").write_text(
        json.dumps(image_response, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    meta = build_song_metadata(song, topic, config)
    meta["generation_debug"] = {
        "music_response_keys": list(music_response.keys()),
        "image_response_keys": list(image_response.keys()),
        "manual_lyrics": True,
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
        notes="Generated as a Qishui longform probe candidate. Pending listening review.",
        reviewed_at=datetime.now().replace(microsecond=0).isoformat(),
    )
    song.review_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")

    song.status = "generated"
    song.generated_at = datetime.now().replace(microsecond=0).isoformat()
    (song_dir / "song.json").write_text(song.model_dump_json(indent=2), encoding="utf-8")
    return {
        "song_id": spec["song_id"],
        "title": spec["title"],
        "audio_path": str(song.audio_path),
        "cover_path": str(song.cover_publish_path),
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    config = load_app_config(project_root)
    http_client = JsonHttpClient()
    music_provider = MiniMaxMusicProvider(config.music_provider, http_client)
    image_provider = AgnesImageProvider(config.image_provider, http_client)

    specs = [
        {
            "song_id": "song_20260707_212",
            "topic_id": "tp_20260707_212",
            "title": "晚风刚刚好",
            "topic": "在生活重新变轻的时候，慢慢学会温柔地喜欢自己",
            "audience": "喜欢治愈流行和松弛陪伴感歌曲的汽水音乐用户",
            "mood": "温柔、轻盈、晚风、治愈",
            "scene": "傍晚散步回家，街灯刚亮，风很轻，情绪终于没那么紧绷",
            "style_hint": "中文治愈流行女声，必须在前2秒内直接进入清晰主唱，不要纯伴奏长前奏，不要哼唱铺垫。完整歌曲长度目标3分到4分，副歌好记、旋律温柔耐听，木吉他、轻钢琴、温暖鼓点，适合循环播放和陪伴聆听。",
            "lyrics": """[Verse 1]
今天的风吹得很慢
路灯一盏一盏变暖
我把白天那些太乱的话
都留在身后不再回看
晚霞落进玻璃窗里
像谁轻轻拍了拍肩膀
原来日子没有变好得多快
只是心开始慢慢松绑

[Pre-Chorus]
我终于不再和自己争论
不再追问为什么会心闷
有些答案不需要立刻承认
先学会安稳

[Chorus]
晚风刚刚好
吹开我眉间没说完的烦恼
世界没有一下变得多热闹
可我开始听见心跳
晚风刚刚好
让我知道温柔不是讨好
我可以慢慢把自己照顾好
在平凡黄昏里重新微笑

[Verse 2]
便利店门口的光
照着路人的脚步匆忙
我忽然也没那么想
去证明谁比谁更倔强
原来放下不是忘掉
不是把回忆全都丢掉
只是终于愿意承认那些伤
不会一直把我困牢

[Pre-Chorus]
我终于不再和旧梦拉扯
不再假装什么都值得
有些遗憾就让时间轻轻收着
别再反复折磨

[Chorus]
晚风刚刚好
吹开我眉间没说完的烦恼
世界没有一下变得多热闹
可我开始听见心跳
晚风刚刚好
让我知道温柔不是讨好
我可以慢慢把自己照顾好
在平凡黄昏里重新微笑

[Bridge]
如果明天还有一点低潮
如果情绪偶尔还会迟到
也没关系我已经知道
怎样轻轻把自己抱牢

[Final Chorus]
晚风刚刚好
吹得每段旧故事都变轻了
我不需要谁来给我答案了
我已经学会和自己说
晚风刚刚好
今夜的我终于不再逃跑
我会慢慢把未来走成小路
走成一个更自在的拥抱

[Outro]
晚风刚刚好
我也刚刚好""",
            "cover_prompt": "Square album cover, pure illustration, healing hand-painted anime style, young woman walking home at dusk under soft streetlights and trees, warm green, amber and cream palette, gentle and comforting mood, no neon city emphasis, no phone, no text.",
        },
        {
            "song_id": "song_20260707_213",
            "topic_id": "tp_20260707_213",
            "title": "两点半还醒着",
            "topic": "深夜想念一个已经离开的人，理智知道结束了，情绪却还在延迟反应",
            "audience": "喜欢深夜失恋共鸣和安静情绪流行的汽水音乐用户",
            "mood": "克制、失落、深夜、回忆感",
            "scene": "凌晨两点半，房间只开一盏灯，窗外安静，心里全是没说完的话",
            "style_hint": "中文深夜情绪流行女声，前2秒内必须直接进入清晰人声，不要无人声长前奏。完整歌曲长度目标3分到4分，钢琴和轻电子鼓，主歌克制，副歌强记忆点，适合深夜单曲循环。",
            "lyrics": """[Verse 1]
两点半还醒着
房间安静得只剩时钟声
手机亮了一下又暗了
像你名字来过又回身
我明明已经把聊天删了
却还记得你每一种口吻
有些习惯不是放不下
只是深夜太会逼人承认

[Pre-Chorus]
我知道故事该停在这里
该学着把结局说得平静
可情绪总是比理智慢一点清醒

[Chorus]
两点半还醒着
我还是会想起你
想起你说别走散
最后先松开的却是你
我不是还想回去
只是没来得及
把那些没说出口的委屈
好好放回心里

[Verse 2]
窗帘缝里没一点风
连回忆都显得太认真
我试着把歌切到下一首
每一句还是像在追问
是不是所有体面的离开
都会在深夜偷偷转身
是不是先走的人
真的比较容易不心疼

[Pre-Chorus]
我知道故事早该翻篇
早该学会不再去怀念
可有些名字听见一次
还是会乱了呼吸线

[Chorus]
两点半还醒着
我还是会想起你
想起你说别走散
最后先松开的却是你
我不是还想回去
只是没来得及
把那些没说出口的委屈
好好放回心里

[Bridge]
也许等天快亮的时候
我会终于不再逞强
也许下一次回到旧梦里
也不会再慌张
我会把你留在过去
留在那段没走完的天气

[Final Chorus]
两点半还醒着
可这次我没有找你
只是安静听完自己
把眼泪留给呼吸
我会慢慢学会
和遗憾保持距离
把那段没说完的心事
留在昨天夜里

[Outro]
两点半还醒着
我会慢慢忘记你""",
            "cover_prompt": "Square album cover, soft emotional illustration, hand-painted anime-inspired style, woman sitting quietly in a dim room at night with one small lamp and soft rain-light at window, blue-gray and amber palette, intimate breakup mood, no neon skyline, no phone close-up, no text.",
        },
        {
            "song_id": "song_20260707_214",
            "topic_id": "tp_20260707_214",
            "title": "今天先快乐一下",
            "topic": "在日常压力里短暂把情绪拉起来，提醒自己先别想太多，先开心一点",
            "audience": "喜欢轻律动流行和提振情绪歌曲的汽水音乐用户",
            "mood": "轻快、明亮、轻律动、自我鼓励",
            "scene": "下班后的傍晚街头，耳机一戴，脚步跟着节奏变轻，心情也慢慢亮起来",
            "style_hint": "中文轻律动流行女声，前2秒内直接进主唱，不要长前奏。完整歌曲长度目标3分到4分，带一点city pop和dance pop质感，清晰鼓点、轻弹贝斯、上口副歌，适合日常循环和提振情绪。",
            "lyrics": """[Verse 1]
下班路上的风
今天吹得有一点轻
耳机里鼓点一响
像在帮我整理心情
那些没回复的消息
那些没做完的决定
先别急着在今晚
把它们全都说清

[Pre-Chorus]
有时候快乐也需要练习
不是逃避只是换种呼吸
让今天先亮一点点
再去面对那些问题

[Chorus]
今天先快乐一下
先别让坏情绪说话
把心事交给节奏
把脚步交给晚霞
今天先快乐一下
先只顾着喜欢自己吧
世界可以晚一点复杂
我先把笑容留下

[Verse 2]
街角咖啡店的歌
刚好唱到我想听那句
原来普通的傍晚
也可以突然很有力气
不是每次都要想明白
才配让自己松一口气
有时候只是抬起头
就能看见新的天气

[Pre-Chorus]
有时候快乐也不是运气
是我终于没再为难自己
让今天先甜一点点
再把乌云留给明天整理

[Chorus]
今天先快乐一下
先别让坏情绪说话
把心事交给节奏
把脚步交给晚霞
今天先快乐一下
先只顾着喜欢自己吧
世界可以晚一点复杂
我先把笑容留下

[Bridge]
如果明天还是会很忙
如果生活偶尔还会乱
至少今晚这一点雀跃
也值得我好好收藏

[Final Chorus]
今天先快乐一下
先把所有叹气放下
让晚风跟着旋律
把心口慢慢擦亮啊
今天先快乐一下
先重新抱紧自己吧
等世界再来问我答案
我已经轻盈出发

[Outro]
今天先快乐一下
我想先开心一下""",
            "cover_prompt": "Square album cover, stylish but soft illustration, hand-painted pop artwork, young woman walking in evening city with headphones and upbeat energy, warm pink, blue and gold palette, lively and bright mood, not dark, not photorealistic, no phone close-up, no text.",
        },
    ]

    summary = [
        build_song(
            project_root=project_root,
            config=config,
            music_provider=music_provider,
            image_provider=image_provider,
            spec=spec,
        )
        for spec in specs
    ]
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
