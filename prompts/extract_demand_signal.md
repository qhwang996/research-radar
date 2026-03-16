你是一位安全研究分析专家。请从以下行业安全博客文章中提取需求信号。

需求信号指的是：工业界正在面对什么安全问题、现有解决方案有什么不足、为什么这个问题现在变得重要。

文章信息：
标题：{{title}}
来源：{{source_name}}
摘要/内容：{{content}}
标签：{{tags}}

请返回一个 JSON，不要加 Markdown 代码块，不要额外解释：

{
  "signal_type": "demand",
  "problem_described": "文章描述的核心安全问题（1-2 句话）",
  "affected_systems": ["受影响的系统或技术1", "系统2"],
  "current_solutions": "文章提到的现有解决方案（如果有，1-2 句话；没有就写'未提及'）",
  "solution_gaps": ["现有方案的不足或缺口1", "缺口2"],
  "urgency_indicators": ["为什么这个问题现在重要1", "原因2"],
  "related_academic_topics": ["相关的学术研究主题1", "主题2", "主题3"]
}

要求：
- problem_described 必须具体，不要泛泛而谈
- solution_gaps 对后续空白检测最重要，尽量具体指出现有方案做不到什么
- related_academic_topics 列出 3-5 个，使用学术领域的规范术语（如 fuzzing、program analysis、vulnerability detection）
- affected_systems 列出 1-3 个
- 如果文章信息有限，基于标题做合理推断，在 solution_gaps 中注明信息不足
- 使用中文
