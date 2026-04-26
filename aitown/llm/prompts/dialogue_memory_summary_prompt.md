# 任务

你会收到最近 {round_count} 轮对话。请做四件事：

1. 提取对话里出现的事务、人名，以及每个对象对应的关键词，尽量保留细节。
2. 总结这 {round_count} 轮对话发生了什么。
3. 生成一段可以塞进下一轮对话提示词的压缩上下文。
4. 选出适合进入长期记忆的内容。

# 输入

- 角色自我画像：{persona}
- 已有长期记忆：{existing_long_memory}
- 历史短期记忆总结：{short_memory_summary}
- 最近 {round_count} 轮对话：{dialogue_rounds}

# 长期记忆筛选标准

只保存对未来对话长期有帮助的信息，例如：

- 用户稳定的身份、职业、目标、偏好、爱好、习惯。
- 用户明确表达过的重要关系、长期计划、反复出现的需求。
- 用户对角色的称呼、互动偏好、边界或禁忌。
- 已经形成结果的事件，例如“用户决定以后每天晚上复盘 10 分钟”。

不要保存这些内容：

- 一次性的闲聊细节。
- 短暂情绪，除非它和长期状态、持续压力或重要事件有关。
- 模型自己的猜测。
- 没有证据支持的扩写。
- 敏感信息的原文细节；如果必须保存，只保留概括。

# 长期记忆结构

长期记忆按两级结构保存：

- 第一级：`owner_name`，记忆所属的人名，通常是当前 NPC 名字。
- 第二级：`section`，只能是以下三种：
- `self_profile`：职业、性格、爱好等自我画像。
- `npc_profile`：与其它人的关系、对其他人的看法、记忆等其它 NPC 画像。
- `user_profile`：对用户的看法、记忆等用户画像。

# 输出格式

只输出 JSON，不要 Markdown，不要解释。字段如下：

{
  "details": [
    {
      "name": "事务或人名",
      "type": "event|person|topic|object|other",
      "keywords": ["关键词1", "关键词2"],
      "detail": "保留关键细节的一句话"
    }
  ],
  "summary": "用 1 到 3 句话总结这 {round_count} 轮对话",
  "context_summary": "合并历史短期记忆总结和最新 {round_count} 轮对话后，给下一轮对话使用的压缩上下文",
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "long_term_memories": [
    {
      "owner_name": "记忆所属的人名，没有把握就留空",
      "section": "self_profile|npc_profile|user_profile",
      "target_name": "这条记忆涉及的对象，比如用户、某个 NPC、人名；没有就留空",
      "content": "可作为长期记忆保存的一句话",
      "keywords": ["关键词1", "关键词2"],
      "importance": 1,
      "evidence": "来自对话的简短依据",
      "confidence": 0.0
    }
  ],
  "discarded_notes": ["不保存但值得短期留意的信息"]
}

# 输出要求

- `importance` 使用 1 到 5，5 表示非常重要。
- `confidence` 使用 0 到 1。
- `long_term_memories` 最多 5 条；没有合适内容就输出空数组。
- `keywords` 控制在 3 到 8 个。
- `details` 里的人名、事务和关键词要尽量具体，避免细节丢失。
- `context_summary` 必须继承历史短期记忆总结里的重要信息，再吸收最新 {round_count} 轮对话的新信息。
- 所有内容使用中文。
