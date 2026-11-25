上传接口按内容类型判断文件种类，参数里多一个引号就把类型解析成了空：主类型没有转成小写，大小写变体被当成不同种类；参数名保留原大小写，按小写查找失败；引号内的分号被切分，带分号的参数值被截断；反斜杠转义没有处理，转义引号提前结束取值；未闭合引号不报错，值被截到最后；重复参数保留最后一个，与保留第一个的约定相反；等号后为空的参数被丢弃，键会丢失；续行参数没有按序号拼接，分片参数只保留第一段；默认字符集对所有类型返回同一值；批量解析复用参数表，第二条沿用第一条的参数。engine/mime/parse.py 是核心，tests/mime/test_parse.py 15个红。要修的是：按上面的顺序把 10 个缺陷逐个修掉。

# sec-mime-param

这是一个围绕 MIME Content-Type 参数解析的 Bugfix 练习。题目故意把容易忽略的参数语法边角约定集中在 8 个函数里；初始状态没有任何实现，15 条测试全部因 NotImplementedError 失败。

## 运行方式

在仓库根目录执行：

    python -m pytest tests -q

初始输出必须恰好是：

    15 failed

这 15 条失败必须全部由 NotImplementedError 引起，不能出现收集错误、导入错误、跳过、通过或 xfail。运行只需要 Python 3 和 pytest，不需要安装任何第三方依赖，也不需要联网。

## 字段

| 字段 | 内容 |
| --- | --- |
| 安全 | 漏洞检测与攻防 |
| 类型 | Bugfix |
| 语言与测试 | Python 3, pytest |
| 依赖 | 无外部依赖 |

## 目录与 engine 嵌套布局

    sec-mime-param/
      README.md
      conftest.py
      engine/
        __init__.py
        mime/
          __init__.py
          parse.py
      tests/
        mime/
          test_parse.py

engine 是包，mime 是 engine 的子包，唯一实现文件固定在 engine/mime/parse.py。不要把它改成仓库根目录下的 parse.py，也不要把 tests 移出 tests/mime。conftest.py 只负责把仓库根加入 sys.path，保证 pytest 在仓库根运行时可以导入 engine.mime.parse。

## 不可修改

tests/mime/test_parse.py 是唯一验收标准，不可修改、不可删除、不可跳过、不可弱化断言。不要通过改测试期望、加 fixture 替换被测函数、改 conftest 的导入路径等方式让测试变绿。也不要引入 mock 或第三方库来绕过解析逻辑。实现必须留在 engine/mime/parse.py。

## 唯一实现文件与 8 个桩

engine/mime/parse.py 是唯一实现文件，恰好有 8 个桩，当前全部 raise NotImplementedError。

1. split_type(text) -> str：取出主类型，全小写，允许前导空白。
2. tokenize_params(text) -> list：按分号切分参数，引号内的分号不切。
3. unquote_value(value) -> str：去引号并处理反斜杠转义，未闭合引号报错。
4. parse_params(tokens) -> dict：参数名小写，重复参数按约定保留第一个。
5. parse_continutation(tokens) -> dict：续行参数按序号拼接，缺号报错。函数名的拼写就是 parse_continutation，不要改成 parse_continuation。
6. default_charset(media_type, policy) -> str：按策略给默认字符集，未知类型报错。
7. validate(text) -> list[str]：问题列表，包含空类型、非法字符、未闭合引号。
8. mime_batch(texts, policy) -> dict：批量解析，各条独立。

## 接口契约

以下契约与 tests/mime/test_parse.py 的断言一致。

split_type(text)：text 是完整 Content-Type 头值。返回第一个分号前的媒体类型，去掉首尾空白并转小写。允许前导空白；例如两个空格加 Text/HTML 加空格再加分号，返回 text/html。空输入返回空字符串。

tokenize_params(text)：text 是完整头值。按分号切分，但双引号内的分号不切；第一个分号前是媒体类型，不放进返回值；每个 token 去掉首尾空白；空片段丢弃。返回值只包含参数 token，例如 boundary="a;b" 和 charset=utf-8。

unquote_value(value)：value 是等号后的原始值。若以双引号开始，必须以未转义的双引号结束，去掉外层引号，并把反斜杠转义还原：反斜杠加双引号还原为双引号，两个连续反斜杠还原为一个反斜杠。未闭合引号抛 ValueError。未加引号的值原样返回，首尾空白由调用方处理。

parse_params(tokens)：tokens 来自 tokenize_params。每个 token 按第一个等号拆成名字和值；名字去空白并转小写；值用 unquote_value 处理；重复名字保留第一次出现的值，后出现的同名参数忽略；等号后为空时保留空字符串，不能丢键。没有等号的 token 抛 ValueError。返回普通 dict。

parse_continutation(tokens)：识别 name*0、name*1 这种带数字后缀的续行参数，按编号从小到大直接拼接值，返回基名到拼接结果的 dict。编号必须从 0 开始连续；缺号抛 ValueError；值按 unquote_value 处理。例如 subject*1=World 与 subject*0=Hello 拼接为 subject 对应 HelloWorld；只有 subject*0 和 subject*2 时抛 ValueError。

default_charset(media_type, policy)：policy 是媒体类型到字符集的精确映射；media_type 先转小写后查表；命中返回对应字符串；未命中抛 ValueError。不能对所有类型统一返回同一个值，也不能在 policy 之外偷偷使用全局回退值。

validate(text)：返回问题码列表，顺序不作要求。空媒体类型时列表包含 empty type；媒体类型或参数名含非法字符时列表包含 illegal character；存在未闭合双引号时列表包含 unclosed quote；完全合法时返回空列表。validate 本身不抛解析异常，问题通过列表返回。

mime_batch(texts, policy)：逐个完整解析每个头，返回以原始 text 为键的 dict。每个值包含 media_type、params、charset 三个键；params 精确等于 parse_params(tokenize_params(text))；charset 优先取参数里的 charset，没有时调用 default_charset；media_type 由 split_type 得到。每个条目必须使用独立的新 dict，不能复用上一批的参数表，也不能让不同条目共享可变状态。

## 15 个测试

10 条缺陷测试：

1. test_main_type_is_lowercased
2. test_parameter_names_are_lowercased
3. test_semicolon_inside_quotes_is_not_split
4. test_backslash_escaped_quote_is_decoded
5. test_unclosed_quote_is_reported
6. test_duplicate_parameter_keeps_first
7. test_empty_parameter_value_is_kept
8. test_continuation_segments_are_joined_and_gaps_rejected
9. test_default_charset_depends_on_media_type
10. test_batch_does_not_reuse_parameters_between_items

5 条补充测试：

1. test_standard_type_without_parameters
2. test_quoted_parameter_value_is_parsed
3. test_quoted_semicolon_is_preserved_in_parsed_value
4. test_duplicate_parameters_keep_first_in_full_parse
5. test_batch_matches_individual_parses

## 边角约定逐条

1. 类型大小写：主类型必须转小写。Text/HTML、text/HTML、TEXT/HTML 都归一到 text/html，不能因为大小写不同被判成不同种类。
2. 参数名大小写：参数名必须转小写后再查找。Charset、CHARSET、charset 是同一个参数，查找时不能保留原大小写。
3. 带引号值与分号：双引号包住的值可以包含分号、空格和等号。切分参数时只能认双引号之外的分号；引号内的分号必须留在值里。分号两侧空白要去掉，连续分号产生的空片段要丢弃。
4. 反斜杠转义：引号内的反斜杠是转义字符。反斜杠加双引号表示值里的双引号，不会提前结束引号；两个连续反斜杠表示一个反斜杠。实现不能把转义引号当成结束引号。
5. 未闭合引号：以双引号开始但找不到未转义结束引号时，unquote_value 必须抛 ValueError，validate 必须返回 unclosed quote；不能静默截到字符串末尾。
6. 参数重复：同名参数重复出现时保留第一个，后续同名参数忽略。比较名字前先转小写，因此 Charset 与 charset 也算重复。
7. 空参数值：等号后为空是合法值，必须保留为空字符串。不能因为值为空就把整个键丢掉。
8. 续行参数：name*0、name*1、name*2 按数字升序拼接。编号必须从 0 连续；缺号是错误，不能被当作不完整值静默保留。分片不能只保留第一段。
9. 字符集默认值：默认字符集由 media_type 和 policy 决定。不同类型可以映射不同字符集；policy 未覆盖的类型必须报错。不能统一返回一个常量。
10. 批量独立性：mime_batch 中每一条都从自己的 header 重新解析。第二条不能沿用第一条的参数表，也不能共享同一个 dict 引用；两条结果要分别等于各自单独解析的结果。
11. 非法字符：媒体类型和参数名只能使用合法 token 字符；空格、控制字符等非法字符要通过 validate 的 illegal character 问题码报告。分隔符两侧的空白是允许的，不属于非法字符。
12. 空类型：header 以分号开头或分号前为空时，split_type 返回空字符串，validate 返回 empty type；不能把空类型当成合法类型继续解析。

## 验收命令

修完 10 个缺陷后，测试应从 15 failed 变成 15 passed：

    python -m pytest tests -q

初始自检时只允许看到 15 failed，且每条失败堆栈中都是 NotImplementedError。

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 安全 |
| 子方向 | 漏洞检测与攻防 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |

