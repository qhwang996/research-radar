# Summarize Artifact Prompt

你正在为一个安全研究信息收敛系统补全 artifact 的 Phase 1 增强字段。

请只返回 JSON，不要输出 Markdown、解释或额外文字。格式必须严格如下：

{
  "summary_l1": "一句话摘要",
  "tags": ["tag-one", "tag-two", "tag-three"]
}

要求：
- `summary_l1` 必须是一句中文或英文都可的简洁摘要，不超过 160 个字符
- `tags` 返回 3-5 个简短标签，使用小写英文短语，空格改为连字符
- 标签优先体现：研究问题、攻击面、技术方法、系统组件、安全方向
- 不要输出泛化标签，如 `research`、`paper`、`security`
- 如果输入信息有限，也必须尽量给出最有区分度的摘要和标签

{{artifact_context}}
