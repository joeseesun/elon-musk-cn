# DESIGN — 黄仁勋 × 马斯克：跨越十年的对话

## 一、全局视觉约定

### ① 画布与安全区
- 画布 1280×720；padding 上下左右各 60px；内容区 1160×600（y 60–660）
- 页尾顶边 y=670，字号 14px，全篇固定
- 头图/封面/章节/高潮页可出血；内容页元素守 60px 安全区

### ② 配色方案（科技未来 · 科技深空主题，全篇一套）
- 主色 accent：`#63A7D4`（冷蓝）
- 辅色 surface：`#232C37`；分隔线 line：`#3A4653`
- 强调色：主色 `#63A7D4`；点缀冷蓝紫 `#4DA3FF`；暖色对比（英伟达/黄仁勋侧）用 `#76B900`→统一改为 `#8ED1A8` 以贴合蓝绿；关键"绿"仅作身份标识
- 底色 bg：`#0B1521`
- 文字四级：一级 `#FFFFFF` / 二级 `#A9CFE7` / 正文 `#E7E8E9` / 辅助 `#C9CCCE`
- 6 系列色：`#24428F` `#3A5CBC` `#63A7D4` `#8FBCE4` `#E3F1F8` `#13263B`
- 深色底 deep_bg：`#0B1521`；on_deep：`#FFFFFF`
- 面积纪律：主色 ≤60%、辅色 ≤30%、强调色 ≤10%

### ③ 字体系统
- 中文标题/大字：思源黑体 Bold（`'Source Han Sans SC','Noto Sans CJK SC',sans-serif`，fontWeight 700）
- 西文/数字：Barlow Condensed（仅标题/大数字，开 tnum），正文西文随黑体
- 字号阶梯：封面主标 84px / 章节大字 68px / 巨型数据 96–120px / 页面主标 34px / 卡片小标 24px / 正文 18–20px / 脚注 14px

### ④ 视觉母题（贯穿全篇）
- 页眉：左侧 4px×20px 冷蓝竖条 + 眉题小字（14px，`#8FBCE4`），每页复用
- 主标题下 1px 贯通细线（底色向主色混 35%），仅内容页
- 章节编号以超大数字（120px，深蓝 `#13263B`）作背景锚点
- 底纹：右上角极淡径向光晕（`#3A5CBC`, opacity 0.12），内容页统一

### ⑤ 配图清单（ImageGen，统一 3D/科技氛围风）
| 文件 | 用途 | 生成方式 | 真实内容 | 使用页 |
|---|---|---|---|---|
| cover.png | 主视觉 | ImageGen | 深色空间中两枚相对的发光芯片/算力核心，冷暖蓝光交汇 | P1 |
| gtc_stage.png | 氛围/证据 | ImageGen | 2015 科技大会舞台，两个剪影人物对谈，暖色聚光 | P4 |
| saudi_forum.png | 氛围 | ImageGen | 国际投资论坛舞台，三人同台对谈，深蓝金色 | P7 |
| gpu_cluster.png | 主视觉 | ImageGen | 深色数据中心 GPU 机架阵列，蓝色光带 | P10 |
| space_datacenter.png | 主视觉 | ImageGen | 轨道上的太空数据中心与太阳能板，地球弧线 | P11 |
| ai_factory.png | 主视觉 | ImageGen | 未来 AI 工厂/数字孪生城市，蓝绿数据流 | P12 |

配图风格词统一：cinematic, dark tech atmosphere, cool blue glow, volumetric light, high detail, no text, no watermark。逐张生成后 Read 核对。

## 二、逐页设计（16 页）

### P01 封面
- type cover / role hero / rhythm peak / layout 满版图+渐变蒙层
- visual L1 cover.png 全出血；深色蒙层压左下标题
- density 字数约 40 / 图1 / 留白约 45%
- title「黄仁勋 × 马斯克」副标「跨越十年的对话 · 从 651 段文稿里读出的算力与赌注」
- anti_pattern 禁文字投影、禁居中三等分

### P02 目录
- type catalog / role transition / rhythm transition / layout 经典纵排
- 三章：01 缘起·GTC 2015｜02 同台·美沙论坛 2025｜03 回响
- density 字数约 60 / 图0 / 留白约 55%
- anti_pattern 禁卡片容器、禁章节简述

### P03 数据概览（本 PPT 从哪里来）
- type content / role supporting / rhythm valley / layout 左标题色块+右内容(m)
- 左窄栏深色块放"651"大数字+说明；右栏三行 KPI：588 份英文文稿 / 21 篇中文精读 / 2015→2026 时间跨度
- 底部结论条：黄仁勋的名字，贯穿了马斯克十年最重要的技术转向
- density 字数约 180 / 图0 / 留白约 25%
- anti_pattern 禁等宽卡片平铺

### P04 章节页 01 缘起·GTC 2015
- type section / role transition / rhythm transition / layout 章节大字(a)
- visual gtc_stage.png 半幅氛围 + 超大"01"
- density 字数约 45 / 图1 / 留白约 50%
- anti_pattern 禁正文段落、禁四卡预览

### P05 AI 危险论之问
- type content / role supporting / rhythm valley / layout 对比式(h)
- 左：黄仁勋抛问"AI 比核武器更危险"；右：马斯克当场修正——自动驾驶是"窄 AI"，像电梯一样
- 底部结论条：同一个小时，同一个话题，两种语气
- density 字数约 220 / 图0 / 留白约 22%
- anti_pattern 禁对称等分无结论

### P06 两个赌注
- type content / role supporting / rhythm valley / layout 横向时间轴/流程(g)
- 黄仁勋押算力：GPU→CUDA→Tegra→Drive PX；马斯克押硬件预埋+软件解锁：传感器→影子模式→OTA
- 结论：2015 年两人把赌注押在同一块地基的两面
- density 字数约 210 / 图0 / 留白约 20%
- anti_pattern 禁均分卡片

### P07 章节页 02 同台·美沙论坛 2025
- type section / role transition / rhythm transition / layout 章节大字(a)
- visual saudi_forum.png + 超大"02"
- anti_pattern 禁正文段落

### P08 三人同台
- type content / role supporting / rhythm valley / layout 左图右文(a)
- visual 复用 saudi_forum.png 占左 58%；右文三层：1 万亿美元投资 / AI 工厂 / 92 年联盟转向智能时代
- 结论：三个人从三个时间尺度，指向同一个瓶颈——电
- density 字数约 200 / 图1 / 留白约 20%
- anti_pattern 禁 50:50 等分

### P09 泡沫之问（三层账本）
- type content / role hero / rhythm peak / layout 金字塔/层级(j)
- 三层：① 摩尔定律到头 ② 数据处理换引擎(SQL/dataframe 几百亿美元) ③ 生成式/智能体 AI
- 巨型锚点"冰山"隐喻：外界看到的只是露出水面的一角
- density 字数约 200 / 图0 / 留白约 28%
- anti_pattern 禁等宽三栏

### P10 算力的物理边界
- type content / role supporting / rhythm valley / layout 数据展示(l) + 左图右文
- visual gpu_cluster.png 占左 55%；右侧巨型数字"1.95/2 吨"=机架冷却占比 97.5%
- 结论：地面方案撞墙，太空成为选项
- density 字数约 180 / 图1 / 留白约 22%
- anti_pattern 禁把数字塞进角落

### P11 太空里的 AI
- type content / role supporting / rhythm valley / layout 左图右文(a)
- visual space_datacenter.png 占左 58%；右侧：太空散热靠辐射 / 太阳能硬上限 / 马斯克：性价比远超地面
- 结论：当电力成为硬约束，算力开始向轨道迁移
- density 字数约 190 / 图1 / 留白约 22%
- anti_pattern 禁等分

### P12 AI 工厂与万物智能
- type content / role supporting / rhythm valley / layout 左图右文(a)
- visual ai_factory.png 占左 55%；右侧：炼油厂→AI 工厂 / 实时生成需就近部署 / AI 不止聊天，还有化学·蛋白·基因·机器人
- density 字数约 200 / 图1 / 留白约 20%
- anti_pattern 禁等分

### P13 章节页 03 回响
- type section / role transition / rhythm transition / layout 章节大字(a)
- 超大"03" + 一句：一个押算力，一个押软件，十年后谁都没输
- anti_pattern 禁正文段落

### P14 彼此眼中的对方（金句）
- type content / role hero / rhythm peak / layout 对比式(h) + 大引文
- 左（马斯克说黄仁勋）："Jensen's awesome" / "全世界只有一个人能建成 Colossus" / "我这辈子没见过建得这么快的东西"
- 右（黄仁勋说马斯克）："AI 会让马斯克更忙" / 邀请他每年回来看看 / "我可不会放开我的方向盘"(对话式玩笑归马斯克侧)
- density 字数约 230 / 图0 / 留白约 25%
- anti_pattern 禁等宽卡片、禁小字挤引文

### P15 放射科医生的反例（高潮·洞察）
- type content / role hero / rhythm peak / layout 巨型数字+洞察(a)
- 巨型"↑"与关键词"更多"：AI 化最高的放射科，医生不减反增
- 判断工具：别问岗位每天做什么，问它最终交付什么
- density 字数约 160 / 图0 / 留白约 35%
- anti_pattern 禁等宽卡片横排

### P16 结尾
- type ending / role hero / rhythm peak / layout 收束金句+落款(b)
- 大字："把不确定的问题，拆成确定的步骤" — 两位创新者共同的思维方式
- 落款：资料来源 · 马斯克全访谈文稿库（elon.qiaomu.ai）· 非官方整理
- anti_pattern 禁只写"谢谢"

## 三、节奏自查
- Hero 页：P1 P9 P14 P15 P16 = 5/16 ≈ 31%（合理）
- 过渡页：P4 P7 P13
- 连续 valley 检查：P10→P11→P12 三页 valley，用大图/巨型数字/多图变化打破（P10 数据+巨数、P11 太空图、P12 工厂图，锚点类型不同）
- 明暗节奏：深底为主，章节页用大图/大编号制造呼吸；P9 用纯深色块无图作对比呼吸
