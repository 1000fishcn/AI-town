# 任务

你会收到用户想创建的智能体数量，以及每个智能体的原始描述。请把这些描述整理成可以填充 `persona_chat_prompt.md` 的 JSON。

# 严格规则

- 只能抽取用户描述中明确出现的信息，不能自己补设定。
- 没有明确提到的字段必须填空字符串 `""`。
- 不要把推测、常识、联想写进 JSON。
- 如果某个智能体没有名字，`name` 也填空字符串，不要自己起名。
- 输出的智能体数量必须等于 `{agent_count}`。
- 只输出 JSON，不要 Markdown，不要解释。

# 需要填充的字段

- `name`：名字。
- `identity`：身份。
- `personality`：性格。
- `hobbies`：爱好。
- `speaking_style`：说话风格。
- `relationship_to_user`：和用户的关系。
- `background`：重要背景。

# 用户输入

智能体数量：{agent_count}

智能体描述：
{agent_descriptions}

# 输出格式

{
  "agents": [
    {
      "name": "",
      "identity": "",
      "personality": "",
      "hobbies": "",
      "speaking_style": "",
      "relationship_to_user": "",
      "background": ""
    }
  ]
}
