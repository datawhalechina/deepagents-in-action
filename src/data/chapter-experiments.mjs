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
    '从最小 create_deep_agent 项目识别 Runtime、Framework 与 Harness 的边界。',
  ),
  'ch02-quickstart': experiment(
    'deepagents/default',
    '修改系统提示词和自定义工具，跑通第一个可工作的 Deep Agent。',
  ),
  'ch03-virtual-filesystem': experiment(
    'deepagents/content-builder',
    '利用现成 FilesystemBackend 观察内容、中间结果和 Skills 如何落盘。',
  ),
  'ch04-task-planning': experiment(
    'deepagents/research',
    '通过 Todo 面板直接观察 write_todos 的计划生成与状态变化。',
  ),
  'ch05-subagents': experiment(
    'deepagents/research',
    '观察主 Agent 将搜索委派给 research-agent，并比较两侧上下文。',
  ),
  'ch06-async-subagents': experiment(
    'deepagents/research',
    '从同步研究应用开始，按本章将 researcher 拆成独立 graph 并接入 AsyncSubAgent。',
  ),
  'ch07-skills': experiment(
    'deepagents/content-builder',
    '使用内置 blog-post 与 social-media Skills 观察匹配和渐进式加载。',
  ),
  'ch08-long-term-memory': experiment(
    'deepagents/content-builder',
    '从内容应用开始，按本章加入 CompositeBackend、StoreBackend 和运行时 namespace。',
  ),
  'ch09-human-in-the-loop': experiment(
    'deepagents/mcp',
    '从 MCP 应用开始，按本章为有副作用的工具配置 interrupt_on。',
  ),
  'ch10-sandboxes': experiment(
    'deepagents/sandbox',
    '选择 Daytona 或 LangSmith Sandbox，观察隔离执行、文件读写与清理。',
  ),
  'ch11-filesystem-permissions': experiment(
    'deepagents/content-builder',
    '从真实内容目录开始，按本章加入 FilesystemPermission 并划分访问边界。',
  ),
  'ch12-mcp': experiment(
    'deepagents/mcp',
    '开箱验证 stdio/HTTP Server、工具发现、稳定前缀与名称冲突。',
  ),
  'ch13-grading-rubrics': experiment(
    'langchain/rubric',
    '先运行无需模型密钥的 Guided Demo，再观察 Evidence 与 Acceptance Gate。',
  ),
  'ch14-streaming': experiment(
    'deepagents/research',
    '用现成研究子 Agent 观察主 Agent、researcher、工具调用和最终输出的实时事件。',
  ),
};
