#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""默认训练课的内容数据。前端和 AI 共用同一份事实源。

系统提示词的构造在 src/prompts/teacher.py；本课的教学须知不在这里，
由同名内置教程 functional-communication-starter.html 的 manifest 声明
（前端上报 course_id，服务端据此读回），见 docs/material-protocol.md 第 3 节。

右侧默认展示的是那份自包含课件；这里的 lessons 只在课件加载失败时作为降级展示，
所以站点与课件保持一致，能力与教学规则一律不在这里登记。
"""

DEMO_COURSE = {
    'id': 'functional-communication-starter',
    'title': '把想法说出来（语言障碍恢复）',
    'subtitle': '功能性沟通与语言训练 · 自闭症 / 语言障碍',
    'description': '从选择喜欢的东西开始，练请求、拒绝、求助、轮流，最后练开口说。',
    'principles': [
        '不强迫对视，不把安静或回避当作不配合',
        '手势、点选、图片和口语都是有效沟通',
        '一次只给一个短提示，先留出 5 秒等待',
        '提示由少到多：等待、指认、示范，到顶就交还给照护者',
        '先回应表达的意图，再自然扩展一个词；近似发音不纠正',
    ],
    'lessons': [
        {
            'id': 'choose',
            'eyebrow': '第 1 站 · 我来选择',
            'title': '你想玩什么？',
            'instruction': '点一个你喜欢的。指一指、点一下，或者说出来，都可以。这一站要选三回。',
            'coach_note': '带着练：把选择权真的交出去，孩子点完就兑现或演一下，不要求重复发音。',
            'goal': '用任意方式在三个选项中表达偏好，连续完成 3 个回合',
            'prompt': '你想要哪一个？',
            'options': [
                {'id': 'bubbles', 'emoji': '🫧', 'label': '泡泡', 'spoken': '泡泡'},
                {'id': 'car', 'emoji': '🚗', 'label': '小车', 'spoken': '小车'},
                {'id': 'music', 'emoji': '🎵', 'label': '音乐', 'spoken': '音乐'},
            ],
        },
        {
            'id': 'request',
            'eyebrow': '第 2 站 · 我会请求',
            'title': '把愿望变成一句话',
            'instruction': '按顺序点词卡，拼出「我要 + 一样东西」。只说得出一个词，也完全可以。',
            'coach_note': '带着练：先示范半个「要 ——」，等他接上；他只说一个词就替他补成整句再兑现。',
            'goal': '从单词扩展到「我要 + 物品」，换两样东西各拼一句',
            'prompt': '拼出「我要泡泡」',
            'tokens': ['我', '要', '泡泡', '小车', '音乐'],
            'options': [
                {'id': 'want-bubbles', 'emoji': '🫧', 'label': '我要泡泡', 'spoken': '我要泡泡'},
                {'id': 'again', 'emoji': '🔁', 'label': '再来一次', 'spoken': '再来一次'},
            ],
        },
        {
            'id': 'boundaries',
            'eyebrow': '第 3 站 · 我的意思很重要',
            'title': '说「不」也很有用',
            'instruction': '老师拿出一个很大声的鼓。你可以说不要，也可以说停一下、帮帮我。',
            'coach_note': '带着练：孩子说「不要」请真的停下来。让「不」有实际效果，他才愿意继续开口。',
            'goal': '练习拒绝、暂停与主动求助，并让表达立刻产生结果',
            'prompt': '你现在想说什么？',
            'options': [
                {'id': 'no', 'emoji': '✋', 'label': '不要', 'spoken': '不要'},
                {'id': 'pause', 'emoji': '⏸️', 'label': '停一下', 'spoken': '停一下'},
                {'id': 'help', 'emoji': '🤝', 'label': '帮帮我', 'spoken': '帮帮我'},
            ],
        },
        {
            'id': 'turn-taking',
            'eyebrow': '第 4 站 · 一起玩',
            'title': '轮到谁了？',
            'instruction': '吹泡泡要有来有往。看一看现在轮到谁，再点对应的那句。',
            'coach_note': '带着练：轮流只做两三回合，趁孩子还有兴趣时收尾。',
            'goal': '在共同活动中使用「轮到我 / 轮到你 / 还要吗」',
            'prompt': '刚才老师吹了泡泡，现在轮到谁？',
            'options': [
                {'id': 'my-turn', 'emoji': '🙋', 'label': '轮到我', 'spoken': '轮到我'},
                {'id': 'your-turn', 'emoji': '🫵', 'label': '轮到你', 'spoken': '轮到你'},
                {'id': 'ask-more', 'emoji': '🔁', 'label': '还要吗', 'spoken': '还要吗'},
            ],
        },
        {
            'id': 'speak-out',
            'eyebrow': '第 5 站 · 我来说一说',
            'title': '把这句话讲给老师听',
            'instruction': '先听老师读一遍，再点左下角的麦克风自己说。说不清楚也没关系。',
            'coach_note': '带着练：这一站才要求开口。近似音也算成功，先强化意图再塑型；不肯说就退回点选。',
            'goal': '对目标短语主动发声或口语表达，接受近似发音',
            'prompt': '挑一句，说给老师听：我要泡泡',
            'options': [
                {'id': 'say-want', 'emoji': '🫧', 'label': '我要泡泡', 'spoken': '我要泡泡'},
                {'id': 'say-again', 'emoji': '🔁', 'label': '再来一次', 'spoken': '再来一次'},
                {'id': 'say-help', 'emoji': '🤝', 'label': '帮帮我', 'spoken': '帮帮我'},
            ],
        },
    ],
}
