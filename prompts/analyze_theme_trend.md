你是一位安全研究领域分析专家。请分析以下研究子领域的方法论演进和开放问题。

研究子领域：{{theme_name}}
描述：{{theme_description}}
关键词：{{theme_keywords}}
论文数量：{{paper_count}}

以下是该子领域中论文的研究问题和方法摘要：

{{paper_summaries}}

请返回一个 JSON，不要加 Markdown 代码块：

{
  "methodology_tags": ["该领域常用的研究方法1", "方法2", "方法3"],
  "open_questions": ["该领域尚待解决的关键问题1", "问题2", "问题3"],
  "methodology_evolution": "方法论演进的一句话总结"
}

要求：
- methodology_tags 列出 3-5 个该子领域的代表性研究方法
- open_questions 列出 2-4 个从多篇论文中归纳出的共性开放问题，尽量具体
- methodology_evolution 用 1-2 句话描述该领域方法论的演进趋势
- 使用中文
