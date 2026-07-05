AI Music Traffic Production System 完整优化方案（Markdown 正式文档）
文档信息
适用人群：个人独立开发、低成本试水 AI 音乐流量变现
首发目标平台：二选一固定（Douyin / Tomato Music）
技术栈：Python CLI 本地程序、文件存储、模块化可替换 AI 服务商
迭代路线：原 4 阶段架构增量升级，新增 Phase5 流量优化闭环
1 项目核心目标（修正原模糊 Traffic 定义）
1.1 项目定位
面向单一音乐流量平台，搭建半自动化 AI 歌曲批量生产流水线，产出符合平台规范、可直接手动上传发布的完整歌曲素材包，以流量收益为核心目标。
1.2 明确目标文案（二选一写入项目文档）
方案 A（抖音短视频 BGM 赛道）
Build a traffic-first AI music production system for Douyin short video background music publishing.
方案 B（番茄音乐完整单曲赛道）
Build a traffic-first AI music production system for Tomato Music original song release.
1.3 平台全局适配规则
配置文件统一字段 target_platform，全链路自动适配对应平台标准：
歌曲时长、副歌前置结构
封面尺寸、画风、文字排版规范
发布标题、简介、标签字数模板
情绪、曲风关键词库
2 底层通用核心模块（全流程共用）
2.1 Metadata Generator 统一元数据生成器
作用
作为全链路统一数据载体，串联选题、生成、打分、审核、流量复盘全流程，每首作品独立生成 metadata.json 存档。
标准 metadata.json 示例
json
{
  "song_id": "song_20260705_001",
  "target_platform": "douyin",
  "origin_topic": "毕业校园遗憾",
  "trend_info": {
    "core_keywords": ["青春", "离别", "晚风"],
    "main_emotion": "soft_emo",
    "audience": "学生群体",
    "hot_style": "慢抒情流行"
  },
  "lyric_setting": {
    "word_count": 650,
    "section_marks": ["Verse1","Pre-Chorus","Chorus","Bridge","Outro"],
    "rhyme_type": "伤感温柔韵脚"
  },
  "music_setting": {
    "duration": 90,
    "ref_audio_path": "./ref_audio/emo_pop.wav",
    "vocal_timbre": "轻柔女声"
  },
  "cover_prompt": "1024×1024写实黄昏校园少女，氛围感emo，柔和光影，专辑封面",
  "publish_info": {
    "title": "雨停之后再告别",
    "desc": "写给毕业季藏在心底的遗憾",
    "tags": ["毕业歌曲","emo情歌","校园治愈"]
  },
  "quality_score": 92,
  "file_paths": {
    "lyric_txt": "./output/song_20260705_001/lyric.txt",
    "audio_mp3": "./output/song_20260705_001/song.mp3",
    "cover_png": "./output/song_20260705_001/cover_1440.png",
    "meta_json": "./output/song_20260705_001/metadata.json"
  },
  "review_status": "pending",
  "traffic_data": {}
}
2.2 统一抽象 Provider 架构层
设计规范
所有 AI 服务商统一顶层父类，强制标准化 generate() 方法，统一返回结构体，切换模型仅修改配置，不改动业务流水线代码。
统一返回结构体 ProviderResult
python
运行
class ProviderResult:
    success: bool               # 是否生成成功
    error_msg: str | None       # 失败错误信息
    content: str | bytes | list # 输出内容：歌词文本/音频字节/图片字节
    cost: float                 # 消耗统计：Token/绘图代金券
    raw_response: dict          # 服务商原始返回数据
支持接入服务商分类
歌词生成：DeepSeek、Gemini、Claude
音乐生成：MiniMax Music、字节妙响 SeedMusic、HeartMuLa 本地开源模型
封面绘图：Agnes、通义万相、本地 SD 写实模型
2.3 Trend Engine 热点选题引擎（替代简易 Topic Input）
执行链路
平台热歌榜单 / 热门评论手动导入 → LLM 热点拆解分析 → 输出标准化创作参数写入 metadata
输出标准化字段
核心关键词、主流情绪、目标受众、爆款曲风特征
价值
规避随机冷门选题，让生成作品天然贴合平台流量偏好，提升播放基础盘。
2.4 Quality Layer 质量评估过滤层
执行节点
歌词生成完成后：单主题批量生成 3~5 版歌词，LLM 打分筛选最优
完整歌曲生成后：综合词曲匹配度、适配平台、完整度二次打分
打分模型
复用已有 DeepSeek API，无需额外付费资源
过滤逻辑
按分数排序，仅保留最高分素材进入封面生成、打包环节，低分素材自动丢弃，节省免费 API 额度。
3 五阶段完整迭代规划（增量兼容原有设计）
Phase 1：基础工程基建
阶段目标
搭建可扩展本地 CLI 项目骨架，统一数据模型与服务商抽象层，为后续开发标准化底座。
开发范围
标准化项目目录、全局配置文件（新增 target_platform 平台配置项）
定义 Metadata、ProviderResult 全局数据模型
顶层通用 Provider 抽象父类封装
统一 CLI 程序入口、本地文件存储规范
完成验收标准
单条 CLI 命令可启动完整流水线调度
目录、元数据文件格式统一规范
新增 / 替换 AI 服务商无需重构主流程代码
Phase 2：核心生成流水线（核心产出链路）
阶段目标
输入热点选题，全自动生成带打分、完整元数据、可待审核的歌曲素材包。
开发完整流程
热点选题：Trend Engine 解析标准化创作参数
歌词生成 + 正则清洗分段标记
Quality Layer 歌词多版本打分筛选
AI 音乐生成（支持 reference_audio 参考曲风）
Quality Layer 完整歌曲综合质量打分
Agnes 1024×1024 写实封面图生成
PIL 封面后处理：1440×1440 超分 + 底部歌名文字渲染
Metadata Generator 自动输出 metadata.json
素材统一打包归档
完成验收标准
输入单一热点主题，全自动输出标准化歌曲包；低分劣质素材自动拦截，不进入打包流程。
Phase 3：人工审核发布闭环
阶段目标
增加人工审核流程，记录作品状态，支持导出合格作品直接手动上传平台。
开发范围
基于 metadata.json 记录审核状态：pending / pass / reject
单步骤独立重试功能（重写歌词 / 重生成音乐 / 重绘封面）
批量导出所有审核通过歌曲包
全局运行日志：API 消耗、生成耗时、质量分数记录
完成验收标准
可快速筛选可发布成品，导出文件夹素材完全满足平台上传规范。
Phase 4：批量自动化效率提升
阶段目标
基础流程稳定后，降低人工重复操作，支持批量批量产出。
开发范围
多主题批量调度、批量任务队列
服务商自动降级规则：免费额度不足自动切换备用模型
接口失败自动重试、素材本地缓存机制
API 消耗简易统计（Agnes 代金券、DeepSeek Token）
完成验收标准
一次性批量处理多个热点选题，大幅减少人工干预。
Phase 5：Traffic Optimization 流量增长闭环（新增变现放大阶段，有稳定收益后开发）
阶段目标
打通作品流量数据反馈，自动迭代创作逻辑，持续放大播放与收益。
四大核心模块
热门歌曲学习模块
解析平台爆款单曲，提取标题、曲风、歌词、封面特征存入本地素材库
Prompt 自动优化模块
根据历史高分、高流量作品 metadata，自动迭代歌词 / 封面生成 Prompt
封面 AB 测试工具
同一首歌生成两套封面，分开发布记录互动数据，沉淀高转化封面模板
数据反馈闭环
手动录入单歌播放、收藏、收益数据，绑定 metadata，反向输入 Trend Engine 指导选题
完成验收标准
系统可依托历史流量数据自主优化创作方向，持续提升作品自然流量。
4 单人开发落地执行优先级
第一优先级（1-3 天快速落地，无需复杂开发）
锁定单一目标发布平台，完善全局配置
开发 Metadata Generator，全链路输出标准 metadata.json
第二优先级（基础流水线跑通后开发）
轻量化 Trend Engine 热点选题模块
Quality Layer 质量打分过滤层，节约免费 API 额度
第三优先级（频繁切换多服务商时重构）
统一标准化 Provider 抽象接口层
第四优先级（能稳定产出少量作品、有小额零花钱收益）
开发 Phase4 批量调度、额度统计自动化能力
第五优先级（稳定持续变现，计划放大账号流量）
完整开发 Phase5 流量优化闭环
5 方案整体优势总结
完全兼容原始项目架构，全部增量迭代，无需推翻重写；
补齐「选题预判、质量筛选、流量数据复盘」三大变现核心短板，从单纯生成工具升级为流量变现产品；
适配个人低成本试错场景，新增模块全部复用现有免费 AI 接口，无大额额外投入；
分层清晰，严格遵循「先产出、再优化、最后放大流量」，贴合个人先试水赚零花钱的核心诉求。