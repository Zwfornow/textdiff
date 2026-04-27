---
name: textdiff
description: "为 OCR 文本比对生成或修改 Python 脚本。Use when: Markdown 文本提取、去除 Markdown 语法和空白、纯文本 diff、OCR 准确率计算、HTML 高亮差异报告、SequenceMatcher opcode 分析、argparse 命令行工具。"
argument-hint: "描述 OCR 文本比对需求、输入输出格式、准确率口径或 HTML 报告样式"
user-invocable: true
---

# TextDiff

## 何时使用

- 需要编写或修改 OCR 文本比对脚本。
- 需要把 Markdown 文档清洗成纯文本后再进行字符级比对。
- 需要计算错误字符数、准确率或 CER 风格指标。
- 需要输出单文件 HTML 差异报告，并高亮缺字、多字、错字。
- 需要把一次性脚本整理成带 argparse 的可复用命令行工具。

## 默认技术约束

- 优先使用 Python 标准库，尤其是 re、argparse、difflib、html、pathlib、typing。
- 采用模块化实现，至少包含四个独立函数：读取并去除MD格式、文本预处理、核心Diff计算、生成HTML报告。
- 关键函数提供 Type Hints 与 Docstrings。
- 优先使用 difflib.SequenceMatcher 获取 equal、replace、delete、insert opcodes。
- 准确率默认按 `(1 - 错误字符数 / 参考文本总字数) * 100%` 计算；若改用 CER，要说明原因。
- HTML 报告必须为单文件并使用内联 CSS，不依赖外部前端框架。

## Markdown 预处理原则

- 对 Markdown 输入，先去除标题、强调、链接、图片、代码块、行内代码等语法。
- 清洗所有多余空白字符，包括空格、制表符、换行，得到稳定纯文本。
- 纯文本生成后直接进入 diff 阶段，默认不再做中文、日文或中日文混合的额外字符过滤。
- 这样可以避免 Markdown 原始空白和换行干扰后续比对结果。

## 工作步骤

1. 确认输入文件格式、输出 HTML 路径以及准确率口径。
2. 实现或重构读取逻辑，先将 Markdown 转换为纯文本。
3. 实现文本预处理，确保最终进入 diff 的字符串不受语法、空白、换行干扰。
4. 使用 SequenceMatcher opcodes 统计 replace、delete、insert 对应的错误字符数。
5. 生成单文件 HTML 报告，至少区分以下三类高亮：
   - 缺字：红色背景或删除线。
   - 多字：绿色背景。
   - 错字：黄色背景，并同时显示原字和错字。
6. 使用 argparse 暴露必要参数，并在可行时运行最小样例验证。

## 输出要求

- 默认给出可直接运行的 Python 代码，而不是只有思路。
- 如果用户提供已有脚本，应优先做最小化修改。
- 在说明里明确写出 Markdown 清洗策略、错误计数方式和 HTML 标记规则。
- 如存在歧义，先采用合理默认值，并标明哪些参数可以继续配置。
