# Akari Discord Bot 框架

Akari 是一个基于 [discord-py](https://github.com/Rapptz/discord.py) 和 Google Gemini API 的可扩展 Discord 机器人框架，支持插件和自定义命令开发。

---

## 快速开始

### 1. 安装 uv（如未安装）

```bash
pip install uv
```

### 2. 克隆项目并安装依赖

```bash
git clone <仓库地址>
cd akari
# 建议不需要体验meme生成的删除meme相关的plugin后进行安装
uv pip install -e .
```


### 3. 配置环境变量

在项目根目录下创建 `.env` 文件，内容如下：

```env
# Google Gemini API Key（https://makersuite.google.com/ 获取）
GOOGLE_AI_KEY=你的APIKEY

# Discord Bot Token（https://discord.com/developers/applications 获取）
DISCORD_BOT_TOKEN=你的TOKEN
```

### 4. 运行机器人

```bash
uv run akari
```


---

## 目录结构说明

```
akari/
├── akari/
│   ├── main.py           # 启动入口
│   ├── config/           # 配置与环境变量
│   │   └── settings.py
│   ├── bot/              # Bot 主体与命令
│   │   ├── bot.py
│   │   ├── utils.py      # discord.Embed相关
│   │   └── commands/
│   ├── plugins/          # 插件目录
│   │   └── gemini_plugin.py
│   └── __init__.py
├── pyproject.toml        # 项目配置与依赖
├── README.md
└── .env                  # 环境变量（需自行创建）
```

---

## 依赖管理

如需添加依赖，推荐使用 uv：

```bash
uv add 包名
```
例如：
```bash
uv add discord-py google-generativeai python-dotenv psutil
```
依赖会自动写入 `pyproject.toml`。

---

## 插件开发指南

所有插件建议放在 `akari/plugins/` 目录下。插件需实现 `setup(bot)` 方法，并通过 `@bot.register_command` 注册命令。

**示例：`akari/plugins/gemini_plugin.py`**
```python
import asyncio
from akari.config.settings import Settings
import google.generativeai as genai
from akari.bot.commands import command

def setup(bot):
    genai.configure(api_key=Settings.GOOGLE_AI_KEY)
    ai_model = genai.GenerativeModel(model_name="gemini-1.5-flash")

    @bot.register_command
    @command(name="askai", description="向Gemini AI提问（插件版）")
    async def askai(ctx, *, question: str):
        async with ctx.typing():
            try:
                full_prompt = f"{Settings.BOT_PERSONA}\n用户: {question}"
                response = await asyncio.to_thread(
                    ai_model.generate_content,
                    full_prompt
                )
                await ctx.reply(response.text)
            except Exception as e:
                await ctx.reply(f"Gemini插件出错: {str(e)}")
```

---

## 命令扩展开发

自定义命令建议放在 `akari/bot/commands/` 目录下。  
只需新建 Python 文件并实现命令函数，参考已有的 `aicmd.py`、`utilcmd.py` 等。

### 保研信息查询插件
正常安装机器人框架即可使用

### meme生成器
需下载图片资源
```bash
uv add meme_generator
#激活虚拟环境安装资源
source .venv/bin/activate # linux
.venv/Scripts/activate # win
meme download
```

### cs开箱模拟插件
正常安装机器人框架即可使用

---

## 常见问题

- **依赖安装失败**：请务必使用国内 PyPI 镜像源。
- **Token/Key 未设置**：请检查 `.env` 文件内容。
- **命令未生效**：请确认插件已正确注册，命令格式正确。

---

## 贡献与扩展

欢迎提交 PR 或 issue，完善文档和功能！

---

如需进一步帮助，请查阅源码或联系维护者。

