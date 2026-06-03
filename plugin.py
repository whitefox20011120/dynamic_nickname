"""
动态群名片插件
根据麦麦人设和当前时间，周期性自动更换群名片后缀。
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import random
import re
import time
from typing import Any, ClassVar

import aiohttp

from maibot_sdk import Command, Field, HookHandler, MaiBotPlugin, PluginConfigBase
from maibot_sdk.types import ErrorPolicy, HookMode, HookOrder


# ============================================================
# 配置模型
# ============================================================

class PluginSection(PluginConfigBase):
    """插件总开关。"""

    __ui_label__: ClassVar[str] = "插件开关"
    __ui_order__: ClassVar[int] = 0

    enabled: bool = Field(
        default=True,
        description="是否启用本插件。",
        json_schema_extra={
            "hint": "关闭后调度任务不会启动。",
            "label": "启用插件",
            "order": 0,
        },
    )
    config_version: str = Field(
        default="2.1.0",
        json_schema_extra={"disabled": True, "hidden": True, "label": "配置版本", "order": 99},
    )


class BotSection(PluginConfigBase):
    """Bot 身份信息。"""

    __ui_label__: ClassVar[str] = "Bot 身份"
    __ui_order__: ClassVar[int] = 1

    qq_account: str = Field(
        default="",
        description="Bot 的 QQ 号（必填）。",
        json_schema_extra={
            "hint": "必填。Bot 自己的 QQ 号，set_group_card 需要。",
            "label": "Bot QQ 号（必填）",
            "placeholder": "例如 114514",
            "order": 0,
            "required": True,
        },
    )
    nickname: str = Field(
        default="麦麦",
        description="Bot 昵称。",
        json_schema_extra={
            "hint": "用于 Prompt 中的自我称呼，留空则用『Bot』。",
            "label": "Bot 昵称",
            "placeholder": "麦麦",
            "order": 1,
        },
    )


class PersonalitySection(PluginConfigBase):
    """人格设定。"""

    __ui_label__: ClassVar[str] = "人格设定"
    __ui_order__: ClassVar[int] = 2

    personality: str = Field(
        default="是一个温柔的二次元爱好者",
        description="人格描述（建议第二人称）。",
        json_schema_extra={
            "hint": "用于生成日程和名片后缀的核心人设。",
            "label": "人设描述",
            "placeholder": "是一个在读女大学生……",
            "order": 0,
            "multiline": True,
        },
    )
    reply_style: str = Field(
        default="不要用AI腔，模仿真人对话风格",
        description="回复风格。",
        json_schema_extra={
            "hint": "辅助提示词，约束输出风格。",
            "label": "回复风格",
            "order": 1,
        },
    )


class NapcatSection(PluginConfigBase):
    """Napcat HTTP API 配置。"""

    __ui_label__: ClassVar[str] = "Napcat HTTP"
    __ui_order__: ClassVar[int] = 3

    address: str = Field(
        default="127.0.0.1",
        description="Napcat HTTP 地址。",
        json_schema_extra={
            "hint": "Napcat HTTP Server 的地址（不是 WebSocket！）",
            "label": "HTTP 地址",
            "placeholder": "127.0.0.1",
            "order": 0,
        },
    )
    port: int = Field(
        default=3002,
        description="Napcat HTTP 端口。",
        json_schema_extra={
            "hint": "在 Napcat 里新建 HTTP Server 后填这里的端口。",
            "label": "HTTP 端口",
            "order": 1,
            "step": 1,
        },
    )
    token: str = Field(
        default="",
        description="HTTP Server 的访问 token（如未设置则留空）。",
        json_schema_extra={
            "hint": "若 Napcat HTTP Server 设置了 token，则此处填写，否则留空。",
            "label": "HTTP Token",
            "placeholder": "可留空",
            "order": 2,
        },
    )


class SettingsSection(PluginConfigBase):
    """名片与群设置。"""

    __ui_label__: ClassVar[str] = "名片与群"
    __ui_order__: ClassVar[int] = 4

    target_group_id: list[str] = Field(
        default_factory=list,
        description="目标群号列表。",
        json_schema_extra={
            "hint": "在这些群里改 Bot 的群名片。",
            "label": "目标群号",
            "placeholder": "请输入群号",
            "order": 0,
            "required": True,
        },
    )
    bot_base_name: str = Field(
        default="",
        description="名片前缀；留空则用 bot.nickname。",
        json_schema_extra={
            "hint": "最终名片为 『前缀丨后缀』。留空则使用 Bot 昵称。",
            "label": "名片前缀",
            "placeholder": "留空使用 Bot 昵称",
            "order": 1,
        },
    )
    model_name: str = Field(
        default="utils",
        description="LLM 任务名（model_config.toml 里 [model_task_config.xxx] 的 xxx）。",
        json_schema_extra={
            "hint": "可选：utils / replyer / planner 等；留空走系统默认。",
            "label": "LLM 任务名",
            "placeholder": "utils",
            "order": 2,
        },
    )
    admin_list: list[str] = Field(
        default_factory=list,
        description="允许使用 /改名 命令的管理员 QQ。",
        json_schema_extra={
            "hint": "为空则任何人都能触发。",
            "label": "管理员 QQ",
            "placeholder": "请输入 QQ 号",
            "order": 3,
        },
    )


class ScheduleSection(PluginConfigBase):
    """自动调度。"""

    __ui_label__: ClassVar[str] = "调度"
    __ui_order__: ClassVar[int] = 5

    enabled: bool = Field(
        default=True,
        description="是否开启定时自动更换。",
        json_schema_extra={
            "hint": "关闭则只能用 /改名 手动触发。",
            "label": "启用定时调度",
            "order": 0,
        },
    )
    min_interval: int = Field(
        default=60,
        description="最小更换间隔（分钟）。",
        json_schema_extra={
            "hint": "下次改名等待时间的下限。",
            "label": "最小间隔（分钟）",
            "order": 1,
            "step": 1,
        },
    )
    max_interval: int = Field(
        default=180,
        description="最大更换间隔（分钟）。",
        json_schema_extra={
            "hint": "下次改名等待时间的上限。",
            "label": "最大间隔（分钟）",
            "order": 2,
            "step": 1,
        },
    )


class DynamicNicknameConfig(PluginConfigBase):
    plugin: PluginSection = Field(default_factory=PluginSection)
    bot: BotSection = Field(default_factory=BotSection)
    personality: PersonalitySection = Field(default_factory=PersonalitySection)
    napcat: NapcatSection = Field(default_factory=NapcatSection)
    settings: SettingsSection = Field(default_factory=SettingsSection)
    schedule: ScheduleSection = Field(default_factory=ScheduleSection)


# ============================================================
# 数据持久化
# ============================================================

DATA_FILE = os.path.join(os.path.dirname(__file__), "daily_schedule.json")


def _load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return {"schedules": [], "last_update_ts": 0}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "date" in data and "schedules" not in data:
            data["schedules"] = [{
                "date": data.pop("date"),
                "items": data.pop("items", []),
                "raw_content": data.pop("raw_content", ""),
            }]
        data.setdefault("schedules", [])
        return data
    except Exception:
        return {"schedules": [], "last_update_ts": 0}


def _save_data(data: dict) -> None:
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _update_schedule_history(new_item: dict) -> None:
    data = _load_data()
    schedules = [s for s in data.get("schedules", []) if s.get("date") != new_item["date"]]
    schedules.append(new_item)
    schedules.sort(key=lambda x: x.get("date", ""))
    data["schedules"] = schedules[-3:]
    _save_data(data)


def _get_latest_schedule(data: dict) -> tuple[str | None, list[str]]:
    schedules = data.get("schedules", [])
    if not schedules:
        return None, []
    latest = schedules[-1]
    return latest.get("date"), latest.get("items", [])


def _get_current_activity(items: list[str]) -> str:
    if not items:
        return "自由活动"
    now = datetime.datetime.now()
    cur_min = now.hour * 60 + now.minute
    parsed: list[tuple[int, str]] = []
    for item in items:
        parts = item.replace("：", ":").split(" ", 1)
        if len(parts) < 2:
            continue
        try:
            h, m = map(int, parts[0].split(":"))
            parsed.append((h * 60 + m, parts[1]))
        except Exception:
            continue
    parsed.sort(key=lambda x: x[0])
    activity = "休息/自由活动"
    for t_min, content in parsed:
        if cur_min >= t_min:
            activity = content
        else:
            break
    return activity


# ============================================================
# 主插件类
# ============================================================

class DynamicNicknamePlugin(MaiBotPlugin):
    """动态群名片插件。"""

    config_model = DynamicNicknameConfig

    def __init__(self) -> None:
        super().__init__()
        self._scheduler_task: asyncio.Task | None = None

    # ---------- 生命周期 ----------

    async def on_load(self) -> None:
        if not self.config.plugin.enabled:
            self.ctx.logger.info("动态群名片：插件未启用")
            return
        if self.config.schedule.enabled:
            self._scheduler_task = asyncio.create_task(self._scheduler_loop())
            self.ctx.logger.info("动态群名片：调度任务已启动")

    async def on_unload(self) -> None:
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

    async def on_config_update(self, scope: str, config_data: dict[str, object], version: str) -> None:
        del scope, config_data, version

    # ---------- LLM 调用封装 ----------

    async def _call_llm(self, prompt: str, temperature: float = 1.0, max_tokens: int = 8192) -> tuple[bool, str]:
        model_name = (self.config.settings.model_name or "").strip()
        try:
            kwargs: dict[str, Any] = {
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if model_name:
                kwargs["model"] = model_name
            result = await self.ctx.llm.generate(**kwargs)
        except Exception as e:
            self.ctx.logger.error(f"LLM 调用异常: {e}", exc_info=True)
            return False, ""
        if not isinstance(result, dict) or not result.get("success"):
            self.ctx.logger.warning(f"LLM 返回失败: {result}")
            return False, ""
        return True, str(result.get("response", "")).strip()

    # ---------- 日程生成 ----------

    async def _generate_daily_schedule(self) -> bool:
        today = datetime.date.today().isoformat()
        bot_name = self.config.bot.nickname or "Bot"
        personality = self.config.personality.personality

        history_ctx = ""
        history = _load_data().get("schedules", [])
        if history:
            history_ctx = "\n【过去几天的日程参考（请避免重复）】:\n"
            for sch in history:
                items_preview = " / ".join(sch.get("items", [])[:8])
                history_ctx += f"- {sch.get('date', '?')}: {items_preview}...\n"

        prompt = f"""
你现在是{bot_name}。
【核心人设】{personality}
【任务】请为自己规划今天（{today}）的日程表。

{history_ctx}

【要求】
1. 只列出从早上6:00到晚上24:00之间的关键活动。
2. 严格遵循格式：每行 `时间 事项`，例如 `6:00 起床吃早餐`。
3. 事项要符合人设。
4. 结合历史记录，安排一些不同的活动或细节。
5. 不要任何开场白或结束语，只输出日程列表。
6. 时间用24小时制。
""".strip()

        self.ctx.logger.info(f"动态群名片：生成 {today} 日程...")
        success, content = await self._call_llm(prompt, temperature=1.2, max_tokens=4096)
        if not success or not content:
            return False

        items = [
            line.strip() for line in content.split("\n")
            if line.strip() and any(c.isdigit() for c in line)
        ]
        if not items:
            return False

        _update_schedule_history({"date": today, "items": items, "raw_content": content})
        self.ctx.logger.info(f"动态群名片：日程已更新，共 {len(items)} 项")
        return True

    # ---------- 名片后缀生成 ----------

    async def _generate_suffix(self) -> str:
        bot_name = self.config.bot.nickname or "Bot"
        personality = self.config.personality.personality
        now = datetime.datetime.now().strftime("%H:%M")
        today = datetime.date.today().isoformat()

        data = _load_data()
        latest_date, latest_items = _get_latest_schedule(data)
        items = latest_items if latest_date == today else []

        current_activity = _get_current_activity(items) if items else "思考今天要干什么"

        prompt = f"""
你现在是{bot_name}。
【核心人设】{personality}
【当前状态】
- 现在时间：{now}
- 你正在：**{current_activity}**

【任务】生成一个非常简短的"状态后缀"，会显示在群名片名字后面。
【要求】
1. 完全符合{bot_name}的语气和人设。
2. 结合正在做的事和时间。
3. 字数严格 ≤12 个字。
4. 只返回后缀内容，不含名字、不含标点。
""".strip()

        success, content = await self._call_llm(prompt, temperature=1.2, max_tokens=16000)
        if not success or not content:
            return random.choice(["发呆中", "信号接收中"])

        cleaned = content.replace('"', "").replace("“", "").replace("”", "").replace("\n", "").strip()
        return cleaned[:12] if len(cleaned) > 12 else cleaned

    # ---------- Napcat 调用 ----------

    async def _set_group_card(self, group_id: str, user_id: str, card: str) -> tuple[bool, str]:
        url = f"http://{self.config.napcat.address}:{self.config.napcat.port}/set_group_card"
        payload = {"group_id": group_id, "user_id": user_id, "card": card}
        headers: dict[str, str] = {}
        token = (self.config.napcat.token or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return False, f"HTTP {resp.status}"
                    result = await resp.json()
                    if result.get("status") != "ok":
                        return False, f"napcat 返回: {result.get('message', '未知')}"
                    return True, "ok"
        except Exception as e:
            return False, f"请求异常: {e}"

    # ---------- 执行改名 ----------

    async def _perform_change(self) -> tuple[bool, str]:
        target_groups = [str(g).strip() for g in self.config.settings.target_group_id if str(g).strip()]
        if not target_groups:
            return False, "未配置目标群号"

        bot_qq = (self.config.bot.qq_account or "").strip()
        if not bot_qq:
            return False, "未配置 Bot QQ 号 (bot.qq_account)"

        suffix = await self._generate_suffix()
        base_name = (self.config.settings.bot_base_name or self.config.bot.nickname or "Bot").strip()
        new_card = f"{base_name}丨{suffix}"

        ok_count = 0
        for gid in target_groups:
            success, msg = await self._set_group_card(gid, bot_qq, new_card)
            if success:
                ok_count += 1
            else:
                self.ctx.logger.warning(f"群[{gid}] 改名失败: {msg}")

        if ok_count > 0:
            data = _load_data()
            data["last_update_ts"] = time.time()
            _save_data(data)
            return True, f"已更新: {new_card} ({ok_count}/{len(target_groups)})"
        return False, "所有群改名均失败"

    # ---------- 调度循环 ----------

    async def _scheduler_loop(self) -> None:
        try:
            min_interval_sec = self.config.schedule.min_interval * 60
            data = _load_data()
            elapsed = time.time() - data.get("last_update_ts", 0)
            first_wait = max(10.0, min_interval_sec - elapsed + 5) if elapsed < min_interval_sec else 10.0
            self.ctx.logger.info(f"动态群名片：首次等待 {first_wait/60:.1f} 分钟")
            await asyncio.sleep(first_wait)

            while True:
                if not self.config.plugin.enabled:
                    await asyncio.sleep(60)
                    continue

                today = datetime.date.today().isoformat()
                latest_date, _ = _get_latest_schedule(_load_data())
                if latest_date != today:
                    self.ctx.logger.info("动态群名片：日期变更，刷新日程")
                    await self._generate_daily_schedule()
                    await asyncio.sleep(3)

                if self.config.settings.target_group_id:
                    success, msg = await self._perform_change()
                    self.ctx.logger.info(f"动态群名片：{msg}")
                else:
                    if random.random() < 0.1:
                        self.ctx.logger.warning("动态群名片：未配置目标群号")

                wait = random.uniform(
                    self.config.schedule.min_interval,
                    self.config.schedule.max_interval,
                ) * 60
                self.ctx.logger.info(f"动态群名片：下次将在 {wait/60:.1f} 分钟后执行")
                await asyncio.sleep(wait)

        except asyncio.CancelledError:
            self.ctx.logger.info("动态群名片：调度任务已取消")
            raise
        except Exception as e:
            self.ctx.logger.error(f"动态群名片：调度循环异常: {e}", exc_info=True)

    # ---------- 手动命令 ----------

    @Command(
        "update_nickname",
        description="立即根据人设刷新 Bot 群名片（/改名 或 /update_card）",
        pattern=r"^/(?:改名|update_card)$",
    )
    async def handle_manual_update(self, stream_id: str = "", **kwargs):
        admin_list = [str(x) for x in self.config.settings.admin_list]
        if admin_list:
            sender_id = ""
            for key in ("user_id", "sender_id"):
                v = kwargs.get(key)
                if v:
                    sender_id = str(v)
                    break
            if not sender_id:
                sender_info = kwargs.get("sender_info")
                if isinstance(sender_info, dict):
                    sender_id = str(sender_info.get("user_id", ""))
            if sender_id and sender_id not in admin_list:
                return True, "ignored_not_admin", True

        try:
            today = datetime.date.today().isoformat()
            latest_date, _ = _get_latest_schedule(_load_data())
            if latest_date != today:
                await self.ctx.send.text("新的一天，正在规划今日日程...", stream_id)
                await self._generate_daily_schedule()

            await self.ctx.send.text("正在构思新名片...", stream_id)
            success, msg = await self._perform_change()
            if success:
                await self.ctx.send.text(f"✅ {msg}", stream_id)
                return True, "改名成功", True
            await self.ctx.send.text(f"❌ 改名失败：{msg}", stream_id)
            return False, msg, True
        except Exception as e:
            self.ctx.logger.error(f"动态群名片：手动改名异常: {e}", exc_info=True)
            await self.ctx.send.text(f"❌ 异常：{e}", stream_id)
            return False, str(e), True


    # ---------- Hook：剥离自身名片后缀，避免污染聊天上下文 ----------

    @HookHandler(
        "chat.receive.before_process",
        name="strip_self_card_suffix",
        description="把入站消息中 @Bot 自身的『前缀丨状态』后缀剥掉，避免 LLM 把状态当用户原话",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
        error_policy=ErrorPolicy.SKIP,
    )
    async def strip_self_card_suffix(self, **kwargs: Any) -> dict[str, Any]:
        message = kwargs.get("message")
        if not isinstance(message, dict):
            return {"action": "continue"}

        bot_qq = (self.config.bot.qq_account or "").strip()
        if not bot_qq:
            return {"action": "continue"}

        base_name = (self.config.settings.bot_base_name or self.config.bot.nickname or "").strip()

        changed = False

        segments = message.get("raw_message")
        if isinstance(segments, list):
            for seg in segments:
                if not isinstance(seg, dict) or seg.get("type") != "at":
                    continue
                seg_data = seg.get("data")
                if not isinstance(seg_data, dict):
                    continue
                if str(seg_data.get("target_user_id", "")).strip() != bot_qq:
                    continue
                cardname = str(seg_data.get("target_user_cardname") or "")
                stripped = self._strip_suffix(cardname, base_name)
                if stripped != cardname:
                    seg_data["target_user_cardname"] = stripped or None
                    changed = True

        for text_key in ("processed_plain_text", "plain_text", "raw_text"):
            text_value = message.get(text_key)
            if not isinstance(text_value, str) or not text_value:
                continue
            cleaned = self._strip_suffix_in_text(text_value, base_name, bot_qq)
            if cleaned != text_value:
                message[text_key] = cleaned
                changed = True

        if not changed:
            return {"action": "continue"}

        modified = dict(kwargs)
        modified["message"] = message
        return {"action": "continue", "modified_kwargs": modified}

    @staticmethod
    def _strip_suffix(cardname: str, base_name: str) -> str:
        if not cardname:
            return cardname
        idx = cardname.find("丨")
        if idx < 0:
            return cardname
        prefix = cardname[:idx].strip()
        if base_name and prefix != base_name:
            return cardname
        return prefix or base_name

    _AT_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"@([^\s@丨]+)丨[^\s@]{1,16}",
    )

    def _strip_suffix_in_text(self, text: str, base_name: str, bot_qq: str) -> str:
        del bot_qq

        def _sub(match: re.Match[str]) -> str:
            prefix = match.group(1)
            if base_name and prefix != base_name:
                return match.group(0)
            return f"@{prefix}"

        return self._AT_PATTERN.sub(_sub, text)


def create_plugin() -> DynamicNicknamePlugin:
    return DynamicNicknamePlugin()
