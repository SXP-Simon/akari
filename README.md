# Akari Discord Bot 框架

Akari 是一个基于 [discord-py](https://github.com/Rapptz/discord.py) 和 Google Gemini API 的可扩展 Discord 机器人框架，支持插件和自定义命令开发。

---

## 快速开始

### 方式一：本地运行

#### 1. 安装 uv（如未安装）

```bash
pip install uv
```

#### 2. 克隆项目并安装依赖

```bash
git clone <仓库地址>
cd akari
# 建议不需要体验meme生成的删除meme相关的plugin后进行安装
uv venv
source .venv/bin/activate # linux
.venv/Scripts/activate # win
uv pip install -e .
```

#### 3. 配置环境变量

在项目根目录下创建 `.env` 文件，内容如下：

```env
# Google Gemini API Key（https://makersuite.google.com/ 获取）
GOOGLE_AI_KEY=你的APIKEY

# Discord Bot Token（https://discord.com/developers/applications 获取）
DISCORD_BOT_TOKEN=你的TOKEN
```

#### 4. 运行机器人

```bash
uv run akari
```

### 方式二：Docker 运行

#### 1. 克隆项目

```bash
git clone <仓库地址>
cd akari
```

#### 2. 构建并启动

**不包含 meme 功能（默认）：**
```bash
# 构建镜像
docker build -t akari-bot .

# 运行容器
docker run -d \
  --name akari-bot \
  --restart unless-stopped \
  -e DISCORD_BOT_TOKEN=你的令牌 \
  -e GOOGLE_AI_KEY=你的API密钥 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  akari-bot
```

**包含 meme 功能：**
```bash
# 构建镜像
docker build --build-arg INCLUDE_MEME=true -t akari-bot .

# 运行容器
docker run -d \
  --name akari-bot \
  --restart unless-stopped \
  -e DISCORD_BOT_TOKEN=你的令牌 \
  -e GOOGLE_AI_KEY=你的API密钥 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  akari-bot
```

详细说明请参考 [DOCKER.md](DOCKER.md)

---

## 目录结构说明

```
akari/
├── akari/                    # 主程序目录
│   ├── __init__.py
│   ├── __main__.py           # 启动入口（可直接 python -m akari 启动）
│   ├── main.py               # 启动入口
│   ├── config/               # 配置与环境变量
│   │   └── settings.py
│   ├── bot/                  # Bot 主体与命令
│   │   ├── core/             # 核心功能（bot对象、事件、装饰器、模型等）
│   │   │   ├── bot.py
│   │   │   ├── events.py
│   │   │   ├── decorators.py
│   │   │   ├── commands.py
│   │   │   ├── models.py
│   │   │   └── __init__.py
│   │   ├── commands/         # 命令扩展
│   │   │   ├── general.py
│   │   │   ├── utility.py
│   │   │   └── __init__.py
│   │   ├── services/         # 服务层（AI、基础服务等）
│   │   │   ├── ai_service.py
│   │   │   ├── base.py
│   │   │   └── __init__.py
│   │   ├── utils/            # 工具函数（Embed、错误处理等）
│   │   │   ├── embeds.py
│   │   │   ├── error_handler.py
│   │   │   ├── formatters.py
│   │   │   └── __init__.py
│   │   └── __init__.py
│   ├── plugins/              # 插件目录
│   │   ├── admin/            # 管理员插件
│   │   │   ├── decorators.py
│   │   │   ├── manager.py
│   │   │   ├── models.py
│   │   │   ├── plugin.py
│   │   │   └── __init__.py
│   │   ├── galgame/          # Galgame 插件
│   │   │   ├── cache.py
│   │   │   ├── exceptions.py
│   │   │   ├── models.py
│   │   │   ├── plugin.py
│   │   │   ├── utils.py
│   │   │   └── __init__.py
│   │   ├── meme/             # Meme 生成器插件
│   │   │   ├── manager.py
│   │   │   ├── models.py
│   │   │   ├── plugin.py
│   │   │   ├── utils.py
│   │   │   └── __init__.py
│   │   ├── baoyan_plugin.py  # 保研信息查询插件
│   │   ├── openweaponscase_plugin.py  # CS开箱模拟插件
│   │   ├── restart_plugin.py # 重启插件
│   │   ├── rss_plugin.py     # RSS订阅插件
│   │   ├── wiki_plugin.py    # Wiki查询插件
│   │   └── __init__.py
│   └── __init__.py
├── data/                     # 运行数据与配置
│   ├── admin/
│   │   └── admin_config.json
│   ├── baoyan/
│   ├── galgame/
│   │   ├── cache/
│   │   │   ├── images/
│   │   │   └── temp/
│   │   ├── config.json
│   │   └── README.md
│   ├── meme/
│   │   └── meme_templates.md
│   ├── openweaponscase/
│   │   ├── cases.json
│   │   └── open_history.json
│   └── rss/
│       ├── rss_config.json
│       └── rss_data.json
├── logs/                     # 日志文件目录
├── pyproject.toml            # 项目配置与依赖
├── Dockerfile                # Docker 构建文件
├── DOCKER.md                 # Docker 部署指南
├── README.md
├── LICENSE
└── .env                      # 环境变量（需自行创建）
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

所有插件建议放在 `akari/plugins/` 目录下。简单插件需实现 `setup(bot)` 方法，并通过 `@bot.register_command` 注册命令。
复杂插件建议使用Cog命令组方法统一注册。

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
只需新建 Python 文件并实现命令函数，参考已有的 `general.py`、`utility.py` 等。

### 管理员插件
请获取信任者的 Discord ID 填入 `data/admin/admin_config.json`，首次使用建议将自己的 ID 填写到超级管理员中

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
遇到字体问题请到[meme-generator](https://github.com/MemeCrafters/meme-generator)的Issue部分查找解决办法。

### cs开箱模拟插件
正常安装机器人框架即可使用

### rss订阅插件
正常安装机器人框架即可使用

---

## 常见问题

- **依赖安装失败**：可以换源。
- **Token/Key 未设置**：请检查 `.env` 文件内容。
- **命令未生效**：请确认插件已正确注册，命令格式正确。
- **Docker 构建失败**：请检查网络连接，必要时使用 `--no-cache` 参数重新构建。

---

## 贡献与扩展

欢迎提交 PR 或 issue，完善文档和功能！

---

如需进一步帮助，请查阅源码或联系维护者。

