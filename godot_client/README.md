# AI Town Pixel Godot 客户端

这是一个 Godot 4 像素风小镇客户端，用来连接 `aitown.api` 后端。

## 启动顺序

1. 在项目根目录启动后端：

```powershell
python -m aitown.api
```

2. 打开 Godot 4，点击“导入”，选择：

```text
D:\python\aitown\godot_client\project.godot
```

3. 打开后点击右上角运行按钮，主场景是：

```text
res://scenes/Main.tscn
```

## 操作

- `WASD`：移动。
- `E`：靠近 NPC 后交互。
- `Enter`：发送对话。
- `Esc`：关闭对话框。

## 后端接口

客户端启动后会自动请求：

- `GET /health`：检查后端是否在线。
- `POST /agents`：把场景里的 NPC 注册到后端。
- `POST /chat`：把玩家输入发送给指定 NPC，并显示模型回复。

如果画面里提示“后端未连接”，先确认 `python -m aitown.api` 是否已经启动。
