# Song Style Tags

Use one value in the `style_tag` column. The tag expands into the detailed lyric and music-generation rules automatically.

| 中文标签 | Internal tag | Use for |
| --- | --- | --- |
| 自然治愈 | `nature_healing` | Slow healing Chinese pop built from wind, rain, clouds, flowers, trees, water, light, and other natural imagery; non-narrative by default. |
| 温柔治愈 | `healing_gentle` | Warm, slow, reassuring healing pop with spacious vocal phrasing. |
| 氛围情绪 | `mood_atmosphere` | Sensory, immersive atmosphere-first pop with minimal narrative. |
| 生活切片 | `slice_of_life` | Concrete everyday snapshots with light narrative and recurring motifs. |

For a music-platform release, set `distribution_target` to `music_platform` as usual. To select the nature-healing profile, use either the Chinese label or the internal tag:

```csv
style_tag
自然治愈
```
