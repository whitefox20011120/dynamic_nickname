# 动态群名片插件 (Dynamic Nickname)

> 根据麦麦人设和当前时间，周期性自动更换群名片后缀
> 有问题请去插件仓库提issue

## ✨ 功能特性

- 🤖 **人设驱动**：基于自定义人格设定，由 LLM 生成符合性格的状态后缀
- 📅 **每日日程**：每天自动用 LLM 规划一份 6:00–24:00 的活动安排，名片会根据当前时间所对应的活动来生成
- 🔄 **周期更换**：在设定的最小/最大间隔之间随机刷新，自然不机械
- 💬 **手动命令**：支持 `/改名` 或 `/update_card` 即时刷新
- 🛡️ **管理员白名单**：可限制只有指定 QQ 才能触发手动命令

## ⚙️ 配置说明

| 分组 | 字段 | 说明 |
|------|------|------|
| **插件开关** | `enabled` | 总开关，关闭后调度任务不会启动 |
| **Bot 身份** | `qq_account` | **必填**，Bot 自己的 QQ 号，`set_group_card` 需要 |
|              | `nickname`   | Bot 昵称，用于 Prompt 中自称 |
| **人格设定** | `personality` | 直接把 bot_config.toml 的内容粘过来 |
|              | `reply_style` | 直接把 bot_config.toml 的内容粘过来 |
| **Napcat HTTP** | `address` | Napcat HTTP Server 地址，默认 `127.0.0.1` |
|              | `port`     | Napcat HTTP Server 端口，默认 `3002` |
|              | `token`    | 若 HTTP Server 设置了访问 token 则填写 |
| **名片与群** | `target_group_id` | **必填**，要改名的群号列表 |
|              | `bot_base_name`   | 名片前缀（留空则用 Bot 昵称） |
|              | `model_name`      | LLM 任务名（如 `utils` / `replyer`） |
|              | `admin_list`      | 允许使用 `/改名` 的 QQ 白名单（留空则任何人都能用） |
| **调度** | `enabled`         | 是否启用定时自动更换 |
|              | `min_interval`    | 最小更换间隔（分钟），默认 60 |
|              | `max_interval`    | 最大更换间隔（分钟），默认 180 |

### Napcat 配置提示

> 必须在 Napcat 里启用 **HTTP Server**（不是 WebSocket！），并把端口填到插件配置里。

## 💬 使用命令

| 命令 | 作用 |
|------|------|
| `/改名` | 立即刷新一次群名片 |
| `/update_card` | 同上，英文别名 |

> 若配置了 `admin_list`，则仅白名单 QQ 可触发；否则任何人都能用。

## 📂 数据文件

插件会在自己目录下生成：

- `daily_schedule.json`：存储最近 3 天的日程及上次更新时间戳

可以手动删除以重置状态。

## 🧪 名片效果示例

假设：
- `bot_base_name = "麦麦"`
- 人设：「温柔的二次元爱好者」
- 当前时间：22:30，日程显示「看番」

那么生成的群名片可能是：

```
麦麦丨摸鱼看新番
麦麦丨补完这一集
麦麦丨深夜冒泡
```

## 📜 License

MIT
