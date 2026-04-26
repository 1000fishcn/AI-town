extends StaticBody2D

class_name TownNpc

@export var agent_id := "npc_001"
@export var npc_name := "小艾"
@export var identity := "小镇居民"
@export var personality := "温和、好奇"
@export var hobbies := "聊天、观察小镇"
@export var speaking_style := "口语化，回复简短"
@export var relationship_to_user := "朋友"
@export var background := "住在 AI 小镇"
@export var body_color := Color("#e07a5f")
@export var hair_color := Color("#3b2f2f")

var backend_ready := false


func _ready() -> void:
	add_to_group("npc")
	z_index = 8
	_add_collision()


func setup(data: Dictionary) -> void:
	agent_id = data.get("agent_id", agent_id)
	npc_name = data.get("npc_name", npc_name)
	identity = data.get("identity", identity)
	personality = data.get("personality", personality)
	hobbies = data.get("hobbies", hobbies)
	speaking_style = data.get("speaking_style", speaking_style)
	relationship_to_user = data.get("relationship_to_user", relationship_to_user)
	background = data.get("background", background)
	body_color = data.get("body_color", body_color)
	hair_color = data.get("hair_color", hair_color)
	position = data.get("position", position)
	name = agent_id


func to_agent_payload() -> Dictionary:
	return {
		"agent_id": agent_id,
		"name": npc_name,
		"identity": identity,
		"personality": personality,
		"hobbies": hobbies,
		"speaking_style": speaking_style,
		"relationship_to_user": relationship_to_user,
		"background": background,
		"short_memory_rounds": 10,
		"memory_top_k": 6,
	}


func _draw() -> void:
	# NPC 也先用矩形画像素小人，颜色区分角色。
	draw_rect(Rect2(Vector2(-7, -20), Vector2(14, 10)), Color("#f0c8a0"))
	draw_rect(Rect2(Vector2(-8, -23), Vector2(16, 7)), hair_color)
	draw_rect(Rect2(Vector2(-9, -10), Vector2(18, 18)), body_color)
	draw_rect(Rect2(Vector2(-12, -7), Vector2(3, 12)), Color("#f0c8a0"))
	draw_rect(Rect2(Vector2(9, -7), Vector2(3, 12)), Color("#f0c8a0"))
	draw_rect(Rect2(Vector2(-8, 8), Vector2(6, 8)), Color("#2d3142"))
	draw_rect(Rect2(Vector2(2, 8), Vector2(6, 8)), Color("#2d3142"))
	draw_rect(Rect2(Vector2(-4, -16), Vector2(2, 2)), Color("#1f1f1f"))
	draw_rect(Rect2(Vector2(3, -16), Vector2(2, 2)), Color("#1f1f1f"))

	if backend_ready:
		draw_rect(Rect2(Vector2(9, -29), Vector2(4, 4)), Color("#5dd86d"))
	else:
		draw_rect(Rect2(Vector2(9, -29), Vector2(4, 4)), Color("#f2c14e"))


func _add_collision() -> void:
	var shape := RectangleShape2D.new()
	shape.size = Vector2(18, 16)

	var collision := CollisionShape2D.new()
	collision.position = Vector2(0, 8)
	collision.shape = shape
	add_child(collision)
