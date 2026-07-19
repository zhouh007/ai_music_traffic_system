from __future__ import annotations

from pathlib import Path

from .models import TopicRecord
from .platform_profiles import infer_distribution_target


PROMPT_FILE_MAP = {
    "short_video": "lyrics_prompt_short_video.txt",
    "hybrid": "lyrics_prompt_hybrid.txt",
    "music_platform": "lyrics_prompt_music_platform.txt",
}


def _u(value: str) -> str:
    normalized = value
    for _ in range(3):
        normalized = normalized.replace("\\\\u", "\\u")
    escaped = normalized.encode("unicode_escape").decode("ascii")
    return escaped.encode("ascii").decode("unicode_escape")


PRODUCT_PROMPT = _u(
    "\\u4f60\\u662f\\u4e2d\\u6587\\u6b4c\\u66f2\\u521b\\u4f5c\\u4eba\\u3002\\u8bf7\\u5148\\u7406\\u89e3\\u521b\\u4f5c\\u7b80\\u62a5\\u518d\\u5199\\u6b4c\\u8bcd\\u3002\\n"
    "\\u4e3b\\u9898\\uff1a{topic}\\n\\u76ee\\u6807\\u542c\\u4f17\\uff1a{audience}\\n\\u7528\\u6237\\u4f7f\\u7528\\u9700\\u6c42\\uff1a{user_need}\\n"
    "\\u6838\\u5fc3\\u51b2\\u7a81\\uff1a{core_conflict}\\n\\u72ec\\u7279\\u89c2\\u5bdf\\uff1a{unique_observation}\\n"
    "\\u60c5\\u7eea\\u56de\\u62a5\\uff1a{emotional_payoff}\\n\\u5177\\u4f53\\u753b\\u9762\\uff1a{visual_scene}\\n"
    "\\u573a\\u666f\\uff1a{scene}\\n\\u7cfb\\u5217\\uff1a{series_name}\\n\\u97f3\\u4e50\\u98ce\\u683c\\uff1a{style_hint}\\n"
    "\\u53d1\\u884c\\u76ee\\u6807\\uff1a{distribution_target}\\n\\n"
    "\\u5171\\u540c\\u8981\\u6c42\\uff1a\\n"
    "1. \\\u53ea\\u5199\\u81ea\\u7136\\u3001\\u53ef\\u6f14\\u5531\\u7684\\u4e2d\\u6587\\u6b4c\\u8bcd\\uff0c\\u4e0d\\u5199\\u89e3\\u91ca\\u3002\\n"
    "2. \\\u81f3\\u5c11\\u51fa\\u73b0\\u4e24\\u4e2a\\u5177\\u4f53\\u7269\\u4ef6\\u6216\\u52a8\\u4f5c\\uff0c\\u907f\\u514d\\u5806\\u53e0\\u62bd\\u8c61\\u8bcd\\u3002\\n"
    "3. \\\u5fc5\\u987b\\u628a\\u72ec\\u7279\\u89c2\\u5bdf\\u8f6c\\u5316\\u4e3a\\u6b4c\\u8bcd\\u4e2d\\u7684\\u5177\\u4f53\\u8868\\u8fbe\\u3002\\n"
    "4. \\\u526f\\u6b4c\\u8981\\u6709\\u4e00\\u53e5\\u77ed\\u800c\\u53ef\\u590d\\u8ff0\\u7684\\u8bb0\\u5fc6\\u70b9\\uff0c\\u4e0d\\u5199\\u6210\\u5e7f\\u544a\\u53e3\\u53f7\\u3002\\n"
    "5. \\\u60c5\\u7eea\\u5fc5\\u987b\\u53d1\\u751f\\u53d8\\u5316\\uff0c\\u7ed3\\u5c3e\\u7ed9\\u542c\\u4f17\\u660e\\u786e\\u7684\\u60c5\\u7eea\\u56de\\u62a5\\u3002"
)

PROFILE_PROMPTS = {
    "short_video": _u("\\u77ed\\u89c6\\u9891\\u7248\\u672c\\uff1a\\u524d 3 \\u79d2\\u8fdb\\u5165\\u6838\\u5fc3\\u60c5\\u7eea\\uff1b\\u524d 20 \\u79d2\\u53ef\\u72ec\\u7acb\\u622a\\u53d6\\u4f7f\\u7528\\uff1b\\u603b\\u957f\\u5ea6 180-280 \\u5b57\\u3002"),
    "hybrid": _u("\\u6df7\\u5408\\u7248\\u672c\\uff1a\\u65e2\\u8981\\u6709\\u524d 10-20 \\u79d2\\u53ef\\u622a\\u53d6\\u7684\\u8bb0\\u5fc6\\u70b9\\uff0c\\u4e5f\\u8981\\u4fdd\\u7559\\u5b8c\\u6574\\u60c5\\u7eea\\u63a8\\u8fdb\\uff1b\\u603b\\u957f\\u5ea6 260-420 \\u5b57\\u3002"),
    "music_platform": _u("\\u5b8c\\u6574\\u5355\\u66f2\\u7248\\u672c\\uff1a\\u6309 3-4 \\u5206\\u949f\\u6b63\\u5f0f\\u5355\\u66f2\\u521b\\u4f5c\\uff0c\\u9700\\u8981\\u5b8c\\u6574\\u53d9\\u4e8b\\u3001\\u60c5\\u7eea\\u9012\\u8fdb\\u548c\\u7b2c\\u4e8c\\u904d\\u8046\\u542c\\u4ef7\\u503c\\u3002\\u603b\\u957f\\u5ea6 320-520 \\u5b57\\u3002"),
}

CREATIVE_MODE_RULES = {
    "narrative": "CREATIVE_MODE: narrative song; use scene progression and character change.",
    "mood": "CREATIVE_MODE: mood song; prioritize atmosphere and sensory immersion; no plot is required.",
    "healing_gentle": "CREATIVE_MODE: healing gentle song; use a low-pressure opening, spacious melody-friendly lines, restrained emotional lift, and a warm release; no plot or character narration is required. Prefer nature and sensory imagery such as wind, grass, flowers, trees, rain, clouds, water, light, mist, and distant landscape. Let the scene carry the feeling instead of explaining it. Alternate short and long lines, one image or breath per line, use delicate parallel repetition, an easy-to-sing refrain, a simple 4-8 syllable hummable hook, and a brief wordless vocalise such as la-la, na-na, wu-wu, or open-vowel ah. Leave deliberate space for held notes, breaths, instrumental replies, and melodic tails. Do not force conflict, twists, motivational conclusions, dense metaphors, direct-address comfort language, or uniform line lengths.",
    "playful_hook": "CREATIVE_MODE: playful hook song; prioritize cute repeatable phrases and teasing interaction; keep plot minimal.",
    "slice_of_life": "CREATIVE_MODE: life-slice song; use independent moments or snapshots instead of one continuous story.",
    "anthemic": "CREATIVE_MODE: anthemic song; prioritize a communal chorus and lift; avoid diary-like exposition.",
}


def load_lyrics_prompt(project_root: Path, topic: TopicRecord) -> tuple[str, str]:
    target = normalize_distribution_target(topic.distribution_target, topic.publish_platform)
    prompt = PRODUCT_PROMPT.format(
        topic=topic.topic,
        audience=topic.audience,
        user_need=topic.user_need or _u("\\u8bf7\\u4ece\\u4e3b\\u9898\\u548c\\u573a\\u666f\\u63a8\\u65ad\\u4e00\\u4e2a\\u5177\\u4f53\\u4f7f\\u7528\\u9700\\u6c42"),
        core_conflict=topic.core_conflict or _u("\\u8bf7\\u8865\\u5145\\u4e00\\u4e2a\\u5177\\u4f53\\u7684\\u4eba\\u7269\\u6216\\u5173\\u7cfb\\u51b2\\u7a81"),
        unique_observation=topic.unique_observation or _u("\\u8bf7\\u5148\\u63d0\\u70bc\\u4e00\\u4e2a\\u4e0d\\u843d\\u4fd7\\u5957\\u7684\\u751f\\u6d3b\\u89c2\\u5bdf"),
        emotional_payoff=topic.emotional_payoff or _u("\\u8bf7\\u660e\\u786e\\u542c\\u5b8c\\u540e\\u5e0c\\u671b\\u542c\\u4f17\\u83b7\\u5f97\\u7684\\u60c5\\u7eea\\u53d8\\u5316"),
        visual_scene=topic.visual_scene or topic.scene,
        scene=topic.scene,
        series_name=topic.series_name or _u("\\u72ec\\u7acb\\u5355\\u66f2"),
        style_hint=topic.style_hint,
        distribution_target=target,
    )
    clean_profile = {
        "short_video": "SHORT_VIDEO_PROFILE: enter the core emotion within 3 seconds; make the first 20 seconds independently usable; keep 180-280 Chinese characters.",
        "hybrid": "HYBRID_PROFILE: provide a memorable 10-20 second excerpt and a complete emotional progression; keep 260-420 Chinese characters.",
        "music_platform": "MUSIC_PLATFORM_PROFILE: write a complete 3-4 minute single with a coherent listening arc and second-listen value; keep roughly 300-700 Chinese characters, adjusting density to the melody. Vocal must start within the first 5-10 seconds. Choose section labels and repetition patterns that fit the creative mode; leave breathing room for instrumental motifs, ad-libs, and an outro. Do not write a short-video clip, a single chorus loop, or a long instrumental opening.",
    }[target]
    clean_prompt = (
        "You are an original Chinese songwriter. Use this creative brief.\n"
        f"Topic: {topic.topic}\nAudience: {topic.audience}\nUser need: {topic.user_need}\n"
        f"Core conflict: {topic.core_conflict}\nUnique observation: {topic.unique_observation}\n"
        f"Emotional payoff: {topic.emotional_payoff}\nVisual scene: {topic.visual_scene or topic.scene}\n"
        f"Series: {topic.series_name or 'standalone single'}\nStyle: {topic.style_hint}\nCreative mode: {topic.creative_mode}\n"
        "Rules: write only natural singable Chinese lyrics; include at least two concrete objects or actions; "
        "turn the brief into a memorable line; alternate short and long lines; avoid abstract cliche stacking; create a coherent feeling; "
        "include a short repeatable chorus hook without sounding like an advertisement; output section labels "
        "[Verse 1], [Pre-Chorus], [Chorus], [Verse 2], and [Bridge] when the profile requires them. "
        "Professional songwriting and resonance rules: the opening line must show a recognizable image, action, or sensory moment, "
        "not explain the theme; build one core line of 5-10 Chinese characters that a listener could naturally quote; "
        "make the chorus easy to sing with short balanced lines and one repeated phrase; include one fresh concrete observation "
        "that feels specific rather than universally motivational; invite the listener into the feeling without requiring a plot; for mood or healing modes, build the lyric from a small coherent set of natural images and let atmosphere replace explanation; use contrast between sections when useful; make the core hook hummable without the full lyric and include a brief wordless vocalise or open-vowel response; "
        "avoid slogans, forced rhymes, generic healing language, excessive metaphors, and lines written only to sound profound.\n"
        f"{CREATIVE_MODE_RULES.get(topic.creative_mode, 'CREATIVE_MODE: choose narrative, mood, healing_gentle, playful_hook, slice_of_life, or anthemic based on the brief.')}\n"
        f"{clean_profile}"
    )
    return clean_prompt, target


def normalize_distribution_target(value: str, publish_platform: str = "") -> str:
    candidate = infer_distribution_target(value, publish_platform)
    return candidate if candidate in PROMPT_FILE_MAP else "hybrid"
