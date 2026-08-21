const templateSource = (template) =>
  `https://github.com/agentseek-ai/agentseek-templates/tree/main/templates/${template}`;

const experiment = (template, note) => ({
  template,
  note,
  command: `agentseek create ${template} --checkout main --no-input`,
  source: templateSource(template),
});

export const chapterExperiments = {
  'ch01-agent-harness': experiment(
    'deepagents/default',
    '从最小 Agent 项目辨清框架、运行时与 Harness。',
  ),
  'ch02-quickstart': experiment(
    'deepagents/default',
    '修改提示词和工具，跑通第一个 Deep Agent。',
  ),
  'ch03-virtual-filesystem': experiment(
    'deepagents/content-builder',
    '观察 FilesystemBackend 如何管理内容与中间结果。',
  ),
  'ch04-task-planning': experiment(
    'deepagents/research',
    '通过 Todo 面板观察计划生成与状态变化。',
  ),
  'ch05-subagents': experiment(
    'deepagents/research',
    '观察主 Agent 委派搜索并隔离上下文。',
  ),
  'ch06-async-subagents': experiment(
    'deepagents/research',
    '拆分 researcher，接入异步子 Agent。',
  ),
  'ch07-skills': experiment(
    'deepagents/content-builder',
    '运行内置 Skills，观察匹配与渐进式加载。',
  ),
  'ch08-long-term-memory': experiment(
    'deepagents/content-builder',
    '接入 CompositeBackend，验证跨会话记忆。',
  ),
  'ch09-human-in-the-loop': experiment(
    'deepagents/mcp',
    '为有副作用的 MCP 工具配置人工审批。',
  ),
  'ch10-sandboxes': experiment(
    'deepagents/sandbox',
    '选择沙箱后端，观察隔离执行与文件读写。',
  ),
  'ch11-filesystem-permissions': experiment(
    'deepagents/content-builder',
    '配置 FilesystemPermission，划分文件访问边界。',
  ),
  'ch12-mcp': experiment(
    'deepagents/mcp',
    '验证 MCP 工具发现、名称前缀与冲突处理。',
  ),
  'ch13-grading-rubrics': experiment(
    'langchain/rubric',
    '运行 Guided Demo，观察 Evidence 验收闭环。',
  ),
  'ch14-streaming': experiment(
    'deepagents/streaming',
    '运行 Streaming 模板，观察 Agent 与工具事件流。',
  ),
};
