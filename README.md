# OCR Markdown 文本比对工具

这个项目提供了一个面向 OCR 结果校验的 Python 脚本 [textdiff_ocr.py](textdiff_ocr.py)。

它解决的核心问题是：

- 把两份 Markdown 文本先清洗成适合比较的纯文本。
- 在字符级别统计 OCR 的缺字、多字、错字。
- 计算基于参考文本长度的准确率。
- 输出一份可直接打开的单文件 HTML 报告，方便人工复核。

项目当前已经包含若干样例输入和输出：

- 输入样例位于 [md_summary](md_summary)
- 输出报告位于 [reports](reports)

## 1. 适用场景

这个脚本适合以下场景：

- 比较人工整理的参考 Markdown 与 OCR 提取后的 Markdown。
- 复核 OCR 在中英文混排文本中的字符识别质量。
- 保留 Markdown 原始资料，同时在比较时忽略标题、链接、强调、代码块等语法噪声。
- 生成便于汇报、归档、分享的 HTML 差异报告。

如果你的目标是更复杂的版面分析、段落对齐、句子级重排、图片区域识别，这个脚本不是为那些任务设计的。

## 2. 脚本做了什么

脚本的处理流程可以概括为 5 步：

1. 读取两份 Markdown 文件。
2. 去除 Markdown 语法，尽量保留可读文本内容。
3. 对文本做归一化处理，减少纯格式差异带来的误判。
4. 使用 Python 标准库 difflib.SequenceMatcher 进行字符级 diff。
5. 统计结果并导出 HTML 报告。

对应的核心函数如下：

- [read_and_strip_markdown](textdiff_ocr.py#L74)：读取并清理 Markdown。
- [preprocess_text](textdiff_ocr.py#L95)：进行宽度、标点、大小写和空白归一化。
- [compute_diff](textdiff_ocr.py#L110)：生成 diff opcode 并统计错误数。
- [generate_html_report](textdiff_ocr.py#L180)：生成完整 HTML 报告。
- [main](textdiff_ocr.py#L307)：串联整个执行流程。

## 3. 环境要求

- Python 3.10+，推荐使用项目中的虚拟环境。
- 仅依赖 Python 标准库，不需要额外安装第三方包。

如果你要重新创建环境，可以在项目目录下执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -V
```

## 4. 目录说明

当前工作区结构大致如下：

```text
ocr_diff/
├── textdiff_ocr.py          # 主脚本
├── README.md                # 使用说明与学习文档
├── md_summary/              # 输入样例
│   ├── left_mac.md
│   ├── left_my.md
│   ├── left_my2.txt
│   ├── left_my3.md
│   ├── left_my4.md
│   ├── right_mac.md
│   ├── right_my.md
│   └── right_my4.md
└── reports/                 # HTML 报告输出目录
    ├── left_diff_report.html
    ├── left_diff_report2.html
    ├── left_diff_report3.html
    ├── left_diff_report4.html
    ├── right_diff_report.html
    └── right_diff_report4.html
```

## 5. 输入与输出

### 输入

脚本接收两个文件：

- reference：参考文本，作为正确答案。
- ocr：OCR 输出文本，作为待评估对象。

默认按 Markdown 处理，所以它最适合 `.md` 文件。只要文件内容是 UTF-8 编码的文本，即使后缀不同，也可以读取。

### 输出

脚本会输出两类结果：

1. 终端摘要

会打印：

- 参考文本总字数
- 错误字符数
- 缺字数
- 多字数
- 错字数
- 准确率
- HTML 报告路径

2. HTML 报告

报告包含：

- 准确率和错误统计卡片
- 参考文本与 OCR 文本的高亮对照
- 差异明细表

高亮规则如下：

- 缺字：红色背景，出现在参考文本一侧。
- 多字：绿色背景，出现在 OCR 文本一侧。
- 错字：黄色背景，两侧都会高亮。

## 6. 预处理规则

为了让比较更接近 OCR 质量本身，而不是 Markdown 写法差异，脚本会先做文本清洗。

### 6.1 Markdown 清洗

默认会处理这些内容：

- 代码块：去掉包围代码块的 Markdown 语法。
- 行内代码：去掉反引号。
- 图片：保留 alt 文本，去掉图片地址。
- 链接：保留链接文字，去掉 URL。
- 自动链接：保留链接内容。
- 标题标记：去掉 `#`。
- 引用标记：去掉 `>`。
- 列表标记：去掉 `-`、`*`、`1.` 之类的标记。
- 强调标记：去掉 `**`、`__`、`*`、`_`。
- HTML 标签：去掉标签本身。

### 6.2 归一化

Markdown 清洗后，脚本还会进行以下归一化：

- Unicode 宽度归一化：统一全角和半角字符。
- 常见标点归一化：例如把 `（ ）［ ］【 】` 等映射到更统一的形式。
- 大小写归一化：默认不区分大小写，内部会做 casefold。
- 空白归一化：移除空格、换行、制表符等所有空白字符。

这意味着默认比较的是“压缩后的纯文本字符序列”。如果你需要更严格的对比，可以关闭部分归一化选项。

## 7. 准确率口径

当前脚本使用的准确率定义是：

$$
准确率 = \left(1 - \frac{错误字符数}{参考文本总字数}\right) \times 100\%
$$

其中：

- 错误字符数 = 缺字数 + 多字数 + 错字数
- 缺字数来自 delete opcode
- 多字数来自 insert opcode
- 错字数来自 replace opcode

对于 replace，脚本按参考片段和 OCR 片段长度的较大值计数：

$$
replace\_count = \max(参考片段长度, OCR片段长度)
$$

这样做的原因是：OCR 错误在实际场景里不一定是一对一字符替换，可能表现为一段字符被误识别成另一段长度不同的内容。

### 边界情况

- 如果参考文本长度为 0 且 OCR 也没有错误，则准确率为 100%。
- 如果参考文本长度为 0 但 OCR 产生了字符，则准确率为 0%。

## 8. 命令行用法

基本命令：

```bash
python textdiff_ocr.py 参考文件 OCR文件 -o 输出报告.html
```

例如，基于当前项目里的样例：

```bash
python textdiff_ocr.py md_summary/right_mac.md md_summary/right_my4.md -o reports/right_diff_report4.html
```

如果你已经切换到样例文件所在目录并采用相对路径，也可以像当前终端记录那样运行：

```bash
python textdiff_ocr.py right_mac.md right_my4.md -o reports/right_diff_report4.html
```

前提是当前工作目录与文件路径保持一致。

### 可选参数

`--case-sensitive`

- 开启后区分大小写。
- 默认关闭，即 `A` 和 `a` 不会被视为差异。

`--no-normalize-width`

- 关闭全角/半角统一。
- 适合你想显式检查宽度差异时使用。

`--no-normalize-punctuation`

- 关闭常见括号和标点统一。
- 适合你想保留中英文标点差异时使用。

## 9. 复现步骤

如果你后续想完整复现一次结果，可以按下面流程执行。

### 方式一：直接复现现有样例

1. 进入项目目录。
2. 激活虚拟环境，如果你在用项目里的 `.venv`。
3. 执行样例命令。
4. 用浏览器打开生成的 HTML。

命令示例：

```bash
cd /Users/zw/internship/python-use/ocr_diff
source .venv/bin/activate
python textdiff_ocr.py md_summary/right_mac.md md_summary/right_my4.md -o reports/right_diff_report4.html
open reports/right_diff_report4.html
```

### 方式二：替换成你自己的 OCR 结果

1. 准备一份参考 Markdown。
2. 准备一份 OCR 输出 Markdown。
3. 指定输出 HTML 路径。
4. 运行脚本并查看报告。

示例：

```bash
python textdiff_ocr.py path/to/reference.md path/to/ocr.md -o reports/custom_report.html
```

## 10. 如何阅读 HTML 报告

建议按这个顺序阅读：

1. 先看顶部统计卡片，快速判断整体误差水平。
2. 再看左右对照区域，确认差异是由缺字、多字还是替换造成。
3. 最后看差异明细表，定位具体字符区间和问题内容。

如果你在分析某类 OCR 系统的稳定性，建议把多次实验报告都保存下来，便于横向比较不同模型、不同图片质量或不同预处理策略下的结果。

## 11. 代码学习路径

如果你是为了学习这个脚本，建议按下面顺序阅读源码：

1. 从 [main](textdiff_ocr.py#L307) 开始，看整体执行顺序。
2. 再看 [parse_args](textdiff_ocr.py#L278)，理解脚本支持哪些控制参数。
3. 阅读 [read_and_strip_markdown](textdiff_ocr.py#L74) 和 [preprocess_text](textdiff_ocr.py#L95)，理解“先清洗再比较”的思路。
4. 阅读 [compute_diff](textdiff_ocr.py#L110)，理解错误计数是如何从 opcode 推出来的。
5. 最后看 [generate_html_report](textdiff_ocr.py#L180)，理解报告页面如何拼装。

## 12. 设计取舍

这个脚本采用了几个明确的设计选择：

- 只用标准库：便于迁移、复现和长期维护。
- 先去 Markdown 再比较：避免语法噪声淹没 OCR 本身的问题。
- 去掉空白再比较：适合 OCR 纯文本准确率分析，但不适合版面保真分析。
- 用 SequenceMatcher：实现简单、解释性强，便于学习和调试。
- 输出单文件 HTML：方便直接打开和归档。

这些选择让脚本更偏向“实用分析工具”，而不是“通用文本评测框架”。

## 13. 常见问题

### 为什么生成的文本没有空格和换行？

因为脚本默认会移除所有空白字符，以避免 Markdown 排版差异影响 OCR 对比结果。

### 为什么有些标点差异没有算错？

因为默认开启了常见标点归一化和全角半角归一化。你可以通过命令行参数关闭这些选项。

### 为什么 replace 不是按参考文本长度计数？

因为 OCR 错误可能把一个字符识别成多个字符，或者把多个字符识别成一个字符。按两侧较大值计数更稳妥。

### 可以直接比较 txt 吗？

可以。只要是 UTF-8 文本并且路径正确，脚本都能读取。只是它的预处理逻辑是按照 Markdown 语法设计的。

## 14. 后续可扩展方向

如果你后面要继续扩展这个项目，可以考虑：

- 增加导出 JSON 结果，便于批处理统计。
- 增加批量比对目录的能力。
- 增加字符错误率 CER、词错误率 WER 等更多指标。
- 在 HTML 报告中加入源文件名、实验参数和时间戳。
- 增加是否保留空白字符的开关。
- 增加更细粒度的 Markdown 清洗策略配置。

## 15. 当前已验证命令

本工作区里已经成功运行过类似下面的命令，并生成 HTML 报告：

```bash
python textdiff_ocr.py right_mac.md right_my4.md -o reports/right_diff_report4.html
```

如果你后续复现时使用的是 [md_summary](md_summary) 目录中的文件，建议显式写出完整相对路径，这样更不容易因为工作目录变化而失败。
