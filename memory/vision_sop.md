# Vision API SOP

## ⚠️ 前置规则（必须遵守）

1. **先枚举窗口**：调用 vision 前必须先用 `pygetwindow` 枚举窗口标题，确认目标窗口存在且已激活到前台。窗口不存在就不要截图。
2. **🚫 禁止全屏截图**：必须先 `win32gui.GetWindowRect` 获取目标窗口坐标，再 `ImageGrab.grab(bbox=...)` 截窗口区域。能截局部（如标题栏）就不截整窗口，能截窗口就绝不全屏。全屏截图在任何场景下都不允许。
3. **能不用 vision 就不用**：如果窗口标题/本地 OCR（`ocr_utils.py`）能获取所需信息，就不要调用 vision API，省 token 且更可靠。Vision 是最后手段。

## 快速用法

### 函数签名

```python
ask_vision(
    image_input,
    prompt: str | None = None,
    timeout: int = 60,
    max_pixels: int = 1_440_000,
    backend: str = 'modelscope',   # 'modelscope'(免费) / 'claude' / 'openai'
    model: str | None = None,      # 仅modelscope后端可指定模型ID
) -> str
```

### 示例

```python
from vision_api import ask_vision

# 默认 ModelScope 免费后端（Qwen3-VL-8B-Instruct）
result = ask_vision("image.png", prompt="描述图片内容")

# 指定更大模型
result = ask_vision("image.png", "描述图片", model="Qwen/Qwen3-VL-235B-A22B-Instruct")

# 回退到付费 Claude 后端
result = ask_vision("image.png", "描述图片", backend="claude")
```

返回 `str`：成功为模型回复，失败为 `Error: ...`。

## 核心参数

- `image_input`: 文件路径(str/Path) 或 PIL Image 对象
- `prompt`: 提示词（默认：详细描述这张图片的内容）
- `max_pixels`: 最大像素数（默认1440000，超则自动缩放）
- `timeout`: 超时秒数（默认60）
- `backend`: `modelscope`(默认免费) / `claude` / `openai`
- `model`: ModelScope 模型ID，默认 `Qwen/Qwen3-VL-8B-Instruct`

## 故障排除

| 问题                    | 解决方案                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------ |
| 导入失败                | 检查 `mykey.py` 文件是否存在（仅检查存在性，不读取内容）                           |
| 超时                    | 提高 timeout 或降低 max_pixels                                                       |
| 格式错误                | 确保使用 PIL 支持的格式（PNG/JPG/GIF等）                                             |
| ModelScope Token 未配置 | 在 `mykey.py` 加 `modelscope_token = 'ms-xxx'` 或设环境变量 `MODELSCOPE_TOKEN` |

## 关键风险与坑点 (L3 Caveats)

- **无重试机制**: `vision_api.py` 内部未实现 API 错误重试（如 503、超时）。在自动化流程中使用时，**必须在上层代码手动实现重试逻辑**（建议指数退避），否则偶发网络波动会导致任务直接崩溃中断。
- **Claude后端 Config**: 使用 `xxx-xxx--xxx`。失效时改 `vision_api.py` 中的 `cfg = mk.xxx`。
- **ModelScope 免费限制**: API-Inference 为免费公共服务，高峰期可能排队或限速，非关键任务优先用。

## ModelScope 免费后端集成流程

### §1 获取访问令牌

1. 登录 https://modelscope.cn → 右上角头像 → 访问控制 → 访问令牌
2. 页面: `https://modelscope.cn/my/myaccesstoken`
3. 复制 `ms-` 开头的 token
4. 存入 `mykey.py`: `modelscope_token = 'ms-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'`
   - 或设环境变量: `export MODELSCOPE_TOKEN='ms-...'`

### §2 浏览可用免费模型

- 入口: https://modelscope.cn/models?filter=inference_type&page=1&tabKey=task&tasks=hotTask:image-text-to-text&type=tasks
- 所有带「API Inference」标签的模型均可免费调用
- 已验证可用模型:
  - `Qwen/Qwen3-VL-8B-Instruct`（默认，轻量快速）
  - `Qwen/Qwen3-VL-235B-A22B-Instruct`（大模型，质量更高）

### §3 API 调用格式（OpenAI 兼容）

```python
import requests
resp = requests.post(
    'https://api-inference.modelscope.cn/v1/chat/completions',
    headers={'Authorization': 'Bearer <TOKEN>', 'Content-Type': 'application/json'},
    json={
        'model': 'Qwen/Qwen3-VL-8B-Instruct',
        'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': '描述图片'},
            {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,<B64>'}}
        ]}],
        'max_tokens': 1024
    }, timeout=60)
result = resp.json()['choices'][0]['message']['content']
```

- 支持 URL 图片: `{'url': 'https://xxx.jpg'}` 替代 base64
- base_url: `https://api-inference.modelscope.cn/v1`

### §4 集成到 vision_api.py 的修改步骤

1. **备份原文件**
2. 新增 `_get_modelscope_token()`: 优先从 `mykey.py` 读 `modelscope_token`，备选环境变量 `MODELSCOPE_TOKEN`
3. 新增 `_call_modelscope(b64, prompt, timeout, model)`: POST 到 ModelScope API（OpenAI兼容格式）
4. 修改 `ask_vision()`: 新增 `backend='modelscope'`(默认) 和 `model=None` 参数，路由到 `_call_modelscope`
5. 文件位置: `~/Documents/vision_api.py`

---

更新: 2025-07-18 | 修复oai_config导入+返回值统一str
更新: 2026-02-18 | 默认后端改为Claude原生API | SOP精简(删废话/水段/合并示例)
更新: 2026-07 | 修复config(原claude_config8不存在)→改为claude_config141
更新: 2026-04-20 | 新增ModelScope免费后端(Qwen3-VL-8B)为默认 | 新增backend/model参数 | 集成流程SOP
