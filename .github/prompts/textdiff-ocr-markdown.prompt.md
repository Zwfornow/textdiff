---
name: TextDiff OCR Markdown Diff
description: "使用 TextDiff 生成或修改 OCR Markdown 文本比对脚本。适用于去除 Markdown 语法与空白、计算准确率、输出 HTML 差异报告。"
argument-hint: "描述输入文件、输出 HTML、准确率口径或希望修改的脚本"
agent: TextDiff
---

请使用 TextDiff 完成一个 OCR 文本比对任务，默认遵守以下要求：

- 输入可以是 Markdown 或纯文本文件。
- 如果输入是 Markdown，先用正则表达式去除 Markdown 语法，并去除空格、制表符、换行等多余空白，得到纯文本后再进行比对。
- 不要在 Markdown 预处理阶段默认按中文、日文或中日文字符集进行额外过滤，除非我明确要求。
- 采用模块化 Python 设计，至少包含四个函数：读取并去除MD格式、文本预处理、核心Diff计算、生成HTML报告。
- 优先使用 difflib.SequenceMatcher 进行字符级 diff，并基于参考文本总字数与错误字符数计算准确率。
- 生成单文件 HTML 报告，使用内联 CSS 标记缺字、多字、错字。
- 使用 argparse 暴露必要命令行参数。

如果我提供的是已有脚本，请直接在现有实现上最小化修改；如果我只给需求，请生成可运行的完整 Python 脚本。
