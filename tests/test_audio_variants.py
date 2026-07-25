from ai_music_system.audio_variants import extract_douyin_clip_lyrics, select_douyin_clip_selection


def test_select_douyin_clip_selection_uses_first_chorus_structure():
    lyrics = (
        "[Verse 1]\n"
        "\u6625\u98ce\u7ecf\u8fc7\u7a97\u8fb9\n"
        "[Pre-Chorus]\n"
        "\u7b49\u4e91\u6162\u6162\u6563\u5f00\n"
        "[Chorus]\n"
        "\u6162\u4e00\u70b9\u4eae\u4e00\u70b9\n"
        "[Verse 2]\n"
        "\u6811\u5f71\u843d\u5728\u8def\u4e0a\n"
    )

    selection = select_douyin_clip_selection(lyrics, first_vocal_second=10.0, duration_seconds=180.0)

    assert selection["selection_method"] == "first_chorus_lyrics_estimate"
    assert 10.0 < selection["start_seconds"] < 180.0
    assert 25.0 <= selection["recommended_duration_seconds"] <= 60.0


def test_select_douyin_clip_selection_falls_back_when_no_chorus_exists():
    selection = select_douyin_clip_selection("\u98ce\u5439\u8fc7\u8349\u5730", first_vocal_second=8.5, duration_seconds=120.0)

    assert selection["start_seconds"] == 8.5
    assert selection["recommended_duration_seconds"] == 45.0
    assert selection["selection_method"] == "first_vocal_fallback"


def test_extract_douyin_clip_lyrics_uses_first_chorus():
    lyrics = (
        "[Verse 1]\n"
        "\u5c71\u6708\u843d\u5728\u65e7\u57ce\u95e8\n"
        "[Chorus]\n"
        "\u98ce\u5165\u957f\u5b89 \u706f\u706b\u7167\u5f52\u4eba\n"
        "\u4e00\u58f0\u73cd\u91cd \u5531\u8fc7\u51e0\u91cd\u6625\n"
        "[Verse 2]\n"
        "\u9a6c\u8e44\u8f7b\u8fc7\u9752\u77f3\u75d5\n"
    )

    clip_lyrics, section = extract_douyin_clip_lyrics(lyrics)

    assert section == "first_chorus"
    assert clip_lyrics == (
        "[Chorus]\n"
        "\u98ce\u5165\u957f\u5b89 \u706f\u706b\u7167\u5f52\u4eba\n"
        "\u4e00\u58f0\u73cd\u91cd \u5531\u8fc7\u51e0\u91cd\u6625\n"
    )
