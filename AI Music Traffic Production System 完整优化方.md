AI Music Traffic Production System 最终整合设计文档
文档基础信息
适用人群：个人独立开发、低成本 AI 音乐流量变现（赚零花钱）
目标发行平台：二选一固定（Douyin / 汽水音乐 或 Tomato Music 番茄音乐）
技术架构：Python CLI 本地程序、文件存储、模块化可替换 AI 服务商
迭代思路：先最小可用 MVP 快速跑通流水线，复杂能力后置增量开发
核心约束：全链路留存创作证据，满足平台 AI 原创合规审核
1 项目核心目标
1.1 项目定位
面向单一音乐流量平台，搭建半自动化 AI 歌曲批量生产流水线，产出符合平台规范、可直接手动上传发布的完整歌曲素材包，以流量播放、商用 BGM 分成作为核心收益目标。
1.2 标准化项目描述（二选一固定写入配置）
方案 A（抖音 / 汽水音乐短视频 BGM 赛道）
Build a traffic-first AI music production system for Douyin short video background music publishing.
方案 B（番茄音乐单曲发行赛道）
Build a traffic-first AI music production system for Tomato Music original song release.
1.3 全局平台适配规则
配置文件统一字段 target_platform，全链路自动适配平台标准：
歌曲时长、副歌前置结构要求
封面尺寸、画风、文字排版规范
发布标题、简介、标签字数模板
情绪、曲风关键词专属库
2 底层通用核心模块（全部采纳历次优化建议）
2.1 Metadata Generator 扁平化元数据规范（适配未来 SQLite 入库）
设计规范
全程保留metadata.json本地文件存储；
全部字段扁平化，无多层嵌套对象，字段统一前缀，后期迁移数据库无需重构；
新增run_id批次 ID、prompt_version版本追溯、多维度质量细分打分、模型溯源字段；
完整保存原始 Prompt，用于复盘爆款创作逻辑。
标准完整 metadata.json 示例
json
{
  "run_id": "run_202607051230",
  "song_id": "song_20260705_001",
  "target_platform": "douyin",
  "origin_topic": "毕业校园遗憾",
  "experiment_group": "sad_emo_version",
  "prompt_version": "v1.2.3",

  "trend_keywords": ["青春", "离别", "晚风"],
  "trend_emotion": "soft_emo",
  "trend_audience": "学生群体",
  "trend_style": "慢抒情流行",

  "lyric_word_count": 650,
  "lyric_sections": ["Verse1","Pre-Chorus","Chorus","Bridge","Outro"],
  "lyric_rhyme_type": "伤感温柔韵脚",
  "raw_lyric_prompt": "完整原始歌词生成prompt文本",

  "music_duration": 90,
  "music_ref_audio_path": "./asset_library/reference_audio/emo_pop.wav",
  "music_vocal_timbre": "轻柔女声",

  "cover_prompt": "1024×1024写实黄昏校园少女，氛围感emo，柔和光影，专辑封面",
  "raw_cover_prompt": "完整未裁剪原始封面prompt",

  "publish_title": "雨停之后再告别",
  "publish_desc": "写给毕业季藏在心底的遗憾",
  "publish_tags": ["毕业歌曲","emo情歌","校园治愈"],

  "lyric_quality_detail": {
    "rhyme": 93,
    "emotion_consistent": 95,
    "structure": 90,
    "platform_fit": 91
  },
  "lyric_quality_total": 92,
  "song_quality_detail": {
    "hook_catch": 92,
    "emotion_match": 95,
    "melody_coherence": 88,
    "lyric_matching": 91,
    "audio_production": 84
  },
  "song_quality_total": 90,

  "provider_lyric": {"provider": "deepseek", "model": "deepseek-v3"},
  "provider_music": {"provider": "minimax", "model": "music-2.6-free"},
  "provider_cover": {"provider": "agnes", "model": "agnes-image-2.1-flash"},

  "path_lyric_txt": "./output/run_202607051230/song_20260705_001/lyric.txt",
  "path_audio_mp3": "./output/run_202607051230/song_20260705_001/song.mp3",
  "path_cover_png": "./output/run_202607051230/song_20260705_001/cover_1440.png",
  "path_meta_json": "./output/run_202607051230/song_20260705_001/metadata.json",

  "review_status": "pending",
  "traffic_data": {}
}
2.2 统一抽象 Provider 调用层
顶层设计
所有 AI 服务商共用统一父类，强制实现generate()方法，切换模型仅修改配置，业务代码无需改动。
统一返回结构体 ProviderResult（新增模型溯源字段）
python
运行
class ProviderResult:
    success: bool               # 是否生成成功
    error_msg: str | None       # 失败错误信息
    content: str | bytes | list # 输出内容：歌词/音频/图片
    cost: float                 # 消耗统计：Token/绘图代金券
    raw_response: dict          # 服务商原始返回数据
    provider_name: str          # 服务商名称 deepseek/agnes/minimax
    model_name: str             # 具体模型版本
支持接入服务商分类
歌词生成：DeepSeek、Gemini、Claude
音乐生成：MiniMax Music、字节妙响 SeedMusic、HeartMuLa 本地开源模型
封面绘图：Agnes、通义万相、本地 SD 写实模型
2.3 拆分双独立 Quality Layer 质量评估层
Quality Layer A：歌词质量打分模块
运行节点：歌词清洗完成后
打分维度：韵脚统一度、情绪一致性、段落结构完整性、平台适配度
输出：细分维度分数 + 加权总分存入 metadata
Quality Layer B：成品歌曲综合打分模块
运行节点：音频生成完毕后
打分维度：副歌抓耳度、情绪匹配度、旋律流畅度、词曲契合度、音频成品音质
输出：细分维度分数 + 加权总分存入 metadata
核心价值
两套独立打分逻辑、独立 Prompt，后期优化互不干扰，可精准定位作品短板。
2.4 Asset Library 标准化资产库（Phase4 开发，长期核心模块）
目录结构
plaintext
asset_library/
├── reference_audio/     # 参考伴奏、哼唱素材
├── lyric_templates/     # 历史高分歌词段落模板
├── title_templates/     # 高播放标题、简介模板
├── cover_style_prompts/ # 分类封面Prompt存档
├── prompt_versions/     # 所有迭代版本Prompt完整归档
└── high_score_examples/ # 爆款完整metadata样本库
作用
生成前优先检索历史验证有效的创作素材，持续拉高成品下限；为 Experiment Layer、流量优化层提供底层复用素材。
2.5 Experiment Layer 实验分层模块（Phase4 开发）
同一基础 Topic 自动生成多组差异化创作分支（不同曲风 / 情绪 / Prompt），每组独立生成完整歌曲包，标记experiment_group分组存入元数据。
后期录入播放、收益数据后，系统自动对比不同实验组转化效果，沉淀高收益 Prompt 模板。
2.6 Trend Engine 热点选题引擎（后置至 Phase4）
后置原因
榜单爬取、热点解析、缓存逻辑开发量大，不占用第一版 MVP 开发周期；Phase2 仅保留人工输入 Topic 极简模式。
执行链路
平台热歌榜单 / 热门评论手动导入 → LLM 热点拆解 → 输出标准化创作参数写入 metadata
3 五阶段完整迭代规划（增量兼容，先 MVP 再优化）
Phase 1：基础工程基建
阶段目标
搭建可扩展本地 CLI 项目骨架，统一数据模型与服务商抽象层，标准化底层底座。
开发范围
标准化项目目录、全局配置文件（target_platform平台配置）
定义扁平化 Metadata、ProviderResult 全局数据模型
顶层通用 Provider 抽象父类封装
统一 CLI 程序入口、本地文件存储规范
验收标准
单条 CLI 命令可调度流水线；目录、元数据格式统一；新增 AI 服务商无需重构主流程。
Phase 2：核心生成流水线（极简 MVP，优先快速跑通）
阶段目标
人工手动输入固定 Topic，全自动生成带细分质量分、完整元数据、待审核歌曲素材包，不含 Trend、Experiment、资产库复杂模块。
完整执行流程
人工输入固定 Topic（毕业、失恋、夏天等）
歌词生成 + 正则清洗分段标记
Quality Layer A 歌词多版本打分筛选
AI 音乐生成（支持 reference_audio 参考曲风）
Quality Layer B 完整歌曲综合质量打分
Agnes 1024×1024 写实封面生成
PIL 封面后处理：1440×1440 超分 + 底部歌名文字渲染
Metadata Generator 输出标准化扁平 json 元数据
素材按 run_id 批次打包归档
验收标准
人工输入单一主题，全自动输出完整标准化歌曲包；低分素材自动拦截，不进入打包流程。
Phase 3：人工审核发布闭环
阶段目标
搭建人工审核流程，记录作品状态，支持批量导出合格素材直接上传平台。
开发范围
metadata 记录审核状态：pending / pass / reject
单步骤独立重试功能（重写歌词 / 重生成音乐 / 重绘封面）
按 run_id 批量导出同一批次审核通过歌曲包
全局运行日志：批次消耗、生成耗时、双维度质量分数记录
验收标准
可快速筛选可发布成品，导出素材完全满足汽水 / 番茄上传规范。
Phase 4：批量自动化 & 实验 & 热点 & 资产库
阶段目标
基础流程稳定、可稳定产出作品后，提升批量产能，新增长期数据迭代底层能力。
开发范围
多主题批量调度、按 run_id 批量任务队列
AI 服务商自动降级：免费额度不足自动切换备用模型
接口失败自动重试、素材本地缓存机制
API 消耗统计：按批次统计 Agnes 代金券、DeepSeek Token 消耗
Experiment Layer 实验分层：同一主题多风格实验组批量生成
Trend Engine 热点选题引擎：榜单解析、自动生成标准化 Topic
Asset Library 资产库管理、素材检索复用逻辑
验收标准
批量处理多主题；同一主题自动输出多版本实验组；支持自动抓取平台热点替代人工输入。
Phase 5：Traffic Optimization 流量增长闭环（稳定变现后开发）
阶段目标
打通作品流量数据反馈，自动迭代创作逻辑，放大播放与收益。
四大核心模块
热门歌曲学习模块：解析平台爆款，提取标题、曲风、歌词、封面特征存入资产库
Prompt 自动优化模块：基于高分、高流量 metadata+prompt_version 自动迭代生成 Prompt
封面 AB 测试工具：依托 Experiment 实验组做封面对照投放，沉淀高转化封面模板
数据反馈闭环：手动录入播放、收藏、收益数据，绑定 run_id、实验组、Prompt 版本，反向指导 Trend Engine 选题
验收标准
系统可依托历史流量数据自主优化创作方向，持续提升作品自然流量。
4 单人开发落地执行优先级（适配低成本快速变现）
第一优先级（1-3 天快速落地，无复杂开发）
锁定单一目标发布平台，完善全局配置
标准化扁平化 Metadata 结构，新增 run_id、prompt_version、细分质量分、模型溯源字段
第二优先级（Phase2 核心 MVP 开发）
实现两套独立 Quality Layer 打分模块
完整搭建人工 Topic 输入→生成→封面→打包基础流水线
第三优先级（基础流水线稳定跑通后）
开发 Phase3 人工审核、批量导出、日志统计功能
第四优先级（稳定产出少量作品、产生小额收益）
开发 Phase4 批量调度、Experiment 实验层、Trend 热点引擎、Asset Library 资产库
第五优先级（稳定持续变现，计划放大账号流量）
完整开发 Phase5 流量数据反馈闭环、Prompt 自动优化
5 平台发布配套实操规范（汽水 / 番茄音乐）
5.1 发布形式
个人批量铺货统一选择单曲发布；积攒 5 首以上同主题歌曲后，再创建专辑归集。
5.2 原创与 AI 标注规则
两个平台统一勾选：原创作品 + 勾选 AI 辅助创作，如实填写使用 AI 工具（DeepSeek、MiniMax、Agnes）；系统完整留存 metadata、多版本草稿作为权属合规证据。
5.3 番茄音乐授权选择策略
新手全部选择非独家授权，单首歌独立签约，不锁其他平台分发渠道；
单曲跑爆、番茄收益显著高于其他平台后，单独对该歌曲升级独家；
独家歌曲仅在番茄分发，其余全新歌曲可正常同步汽水音乐，合规无违约。
5.4 商用收益开关
汽水音乐发布时开启商用 BGM 授权，获取短视频商用分成（核心收入来源）。