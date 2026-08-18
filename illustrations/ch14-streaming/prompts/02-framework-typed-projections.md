---
illustration_id: 02
type: framework
style: sketch-notes
palette: macaron
references:
  - ref_id: 01
    filename: 01-ref-course-style.png
    usage: style
---

Use case: scientific-educational
Asset type: 16:9 course chapter illustration for a Chinese technical tutorial
Primary request: Draw a precise but friendly field map of Deep Agents v3 Typed Projection, showing scope and lazy nested projections.

TITLE — render exactly once at the top:
“v3 Typed Projection：按层级观察运行”

STRUCTURE — hierarchical framework, top to bottom:

TOP NODE:
- One large pale blue rounded box labeled exactly “stream”
- Directly beneath it, five small projection tabs in one row, with these exact labels:
  “messages”  “tool_calls”  “values”  “subagents”  “output”
- Use simple icons: chat bubble, wrench, snapshot sheet, branching robot, result document.

FOCUS BRANCH:
- Make the “subagents” tab slightly larger and connect it downward with a bold hand-drawn arrow labeled exactly “发现一次委派”
- Middle large lavender rounded box titled exactly “subagent handle”
- Inside this box show three compact identity/status tags with exact text:
  “name：显示角色”
  “path：路由键”
  “status：生命周期”

NESTED PROJECTIONS:
- From the subagent handle, branch to five smaller pastel cards in one row with exact labels:
  “messages”  “tool_calls”  “values”  “subagents”  “output”
- Draw the branches as initially dotted, then solid near the cards, with one centered annotation exactly “访问时才打开”
- Use the same icons as the corresponding top-level projections to make the scope relationship visually obvious.

SCOPE CALLOUTS:
- Near the top row, a small outline note says exactly “coordinator 范围”
- Near the lower row, a small outline note says exactly “当前子 Agent 范围”
- On the right, a compact warning note with two same-name researcher cards says exactly “同名 Agent 用 path 区分”

BOTTOM TAKEAWAY — render exactly once:
“Projection 有自己的作用域；name 用来显示，path 用来定位。”

STYLE:
- Match the supplied course reference only for visual style: warm cream paper, subtle paper grain, black hand-drawn lines with slight wobble, softly painted pastel fills, rounded boxes, clear connector arrows, simple line icons, generous white space.
- Diagram only, no realistic humans, no screenshots, no glossy UI, no gradients, no 3D.
- All visible text must be exactly from the quoted strings above. Do not invent other labels. Preserve API identifiers in lowercase with underscores exactly.
- Keep text large and legible. Favor clean grouping over decoration.

COLORS:
- Warm cream background (#F5F0E8); black ink (#1A1A1A); light blue (#A8D8EA) for stream; lavender (#D5C6E0) for subagent; mint (#B5E5CF) and peach (#FFD5C2) for nested cards; coral (#E8655A) only for the path warning accent.
- Color values and color names are rendering guidance only — do NOT display color names, hex codes, or palette labels as visible text.

Clean composition with generous white space. Simple background. Main elements centered by content needs.
ASPECT: 16:9 landscape, designed to remain readable at 1600×900, balanced technical detail.
