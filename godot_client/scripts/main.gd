extends Node2D

const ApiClientScript = preload("res://scripts/api_client.gd")
const DialogueUIScript = preload("res://scripts/dialogue_ui.gd")
const NpcScript = preload("res://scripts/npc.gd")
const PlayerScript = preload("res://scripts/player.gd")
const WorldMapScript = preload("res://scripts/world_map.gd")

var api_client: ApiClient
var dialogue_ui: DialogueUI
var player: Player
var npcs: Array[TownNpc] = []
var backend_online := false


func _ready() -> void:
	_setup_input_actions()
	_create_world()
	_create_api_client()
	_create_player()
	_create_npcs()
	_create_ui()
	await _connect_backend()


func _setup_input_actions() -> void:
	_ensure_key_action("move_up", KEY_W)
	_ensure_key_action("move_down", KEY_S)
	_ensure_key_action("move_left", KEY_A)
	_ensure_key_action("move_right", KEY_D)
	_ensure_key_action("interact", KEY_E)


func _create_world() -> void:
	var world: WorldMap = WorldMapScript.new()
	world.name = "WorldMap"
	add_child(world)


func _create_api_client() -> void:
	api_client = ApiClientScript.new()
	api_client.name = "ApiClient"
	add_child(api_client)


func _create_player() -> void:
	player = PlayerScript.new()
	player.position = Vector2(480, 336)
	player.nearby_npc_changed.connect(_on_nearby_npc_changed)
	player.interaction_requested.connect(_on_interaction_requested)
	add_child(player)


func _create_npcs() -> void:
	for data in _npc_configs():
		var npc: TownNpc = NpcScript.new()
		npc.setup(data)
		npcs.append(npc)
		add_child(npc)


func _create_ui() -> void:
	dialogue_ui = DialogueUIScript.new()
	dialogue_ui.message_submitted.connect(_on_dialogue_message_submitted)
	dialogue_ui.closed.connect(_on_dialogue_closed)
	add_child(dialogue_ui)


func _connect_backend() -> void:
	dialogue_ui.add_system_message("正在连接 FastAPI 后端...")
	var health := await api_client.health()
	backend_online = health.get("ok", false)
	if not backend_online:
		dialogue_ui.add_system_message("后端未连接：请先运行 python -m aitown.api")
		return

	dialogue_ui.add_system_message("后端已连接，正在注册 NPC...")
	for npc in npcs:
		var result := await api_client.create_agent(npc.to_agent_payload())
		npc.backend_ready = result.get("ok", false)
		npc.queue_redraw()
		if npc.backend_ready:
			dialogue_ui.add_system_message(npc.npc_name + " 已接入后端。")
		else:
			dialogue_ui.add_system_message(npc.npc_name + " 接入失败：" + str(result.get("error", "未知错误")))


func _on_nearby_npc_changed(npc) -> void:
	if dialogue_ui.dialogue_panel.visible:
		return
	if npc == null:
		dialogue_ui.hide_hint()
	else:
		dialogue_ui.show_hint(npc)


func _on_interaction_requested(npc) -> void:
	player.can_move = false
	dialogue_ui.open_dialogue(npc)


func _on_dialogue_closed() -> void:
	if player != null:
		player.can_move = true
		dialogue_ui.show_hint(player.get_nearest_npc())


func _on_dialogue_message_submitted(npc, text: String) -> void:
	dialogue_ui.add_user_message(text)
	if not backend_online:
		dialogue_ui.add_system_message("后端还没连上。先在项目根目录运行：python -m aitown.api")
		return
	if not npc.backend_ready:
		dialogue_ui.add_system_message(npc.npc_name + " 还没有成功注册到后端。")
		return

	dialogue_ui.set_waiting(true)
	var result := await api_client.chat(npc.agent_id, text)
	dialogue_ui.set_waiting(false)

	if result.get("ok", false):
		var data: Dictionary = result.get("data", {})
		dialogue_ui.add_npc_message(data.get("agent_name", npc.npc_name), data.get("reply", ""))
	else:
		dialogue_ui.add_system_message("对话失败：" + str(result.get("error", "未知错误")))


func _ensure_key_action(action: StringName, keycode: int) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action)

	for event in InputMap.action_get_events(action):
		if event is InputEventKey and event.physical_keycode == keycode:
			return

	var key_event := InputEventKey.new()
	key_event.physical_keycode = keycode
	InputMap.action_add_event(action, key_event)


func _npc_configs() -> Array[Dictionary]:
	return [
		{
			"agent_id": "npc_xiao_ai",
			"npc_name": "小艾",
			"identity": "AI 小镇的咖啡店店员",
			"personality": "温和、细心、有点爱吐槽",
			"hobbies": "研究咖啡、观察来来往往的人、听玩家讲故事",
			"speaking_style": "口语化，回复简短，像熟人聊天",
			"relationship_to_user": "刚认识但很愿意帮忙的朋友",
			"background": "在小镇中心经营一家很小的咖啡摊。",
			"position": Vector2(336, 288),
			"body_color": Color("#e07a5f"),
			"hair_color": Color("#3b2f2f"),
		},
		{
			"agent_id": "npc_luo_yu",
			"npc_name": "洛雨",
			"identity": "AI 小镇的图书管理员",
			"personality": "安静、认真、偶尔会开冷笑话",
			"hobbies": "整理旧书、记录小镇传闻、看雨",
			"speaking_style": "慢一点、简短、带一点文学感",
			"relationship_to_user": "愿意和玩家交换情报的邻居",
			"background": "负责小镇北边的小图书馆。",
			"position": Vector2(640, 272),
			"body_color": Color("#6d597a"),
			"hair_color": Color("#22333b"),
		},
		{
			"agent_id": "npc_tang_dou",
			"npc_name": "糖豆",
			"identity": "AI 小镇的快递员",
			"personality": "活泼、直接、行动力强",
			"hobbies": "骑车送信、收集奇怪贴纸、打听小镇新闻",
			"speaking_style": "轻快，像朋友一样直接说重点",
			"relationship_to_user": "经常路过并愿意搭话的熟人",
			"background": "每天穿梭在小镇各处送包裹。",
			"position": Vector2(480, 424),
			"body_color": Color("#f2cc8f"),
			"hair_color": Color("#6f4e37"),
		},
	]
