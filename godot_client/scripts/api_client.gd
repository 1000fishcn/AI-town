extends Node

class_name ApiClient

@export var base_url := "http://127.0.0.1:8000"


func health() -> Dictionary:
	return await request_json("/health", HTTPClient.METHOD_GET)


func create_agent(payload: Dictionary) -> Dictionary:
	return await request_json("/agents", HTTPClient.METHOD_POST, payload)


func chat(agent_id: String, user_message: String) -> Dictionary:
	return await request_json(
		"/chat",
		HTTPClient.METHOD_POST,
		{
			"agent_id": agent_id,
			"user_message": user_message,
		}
	)


func request_json(path: String, method: int, payload: Dictionary = {}) -> Dictionary:
	var http := HTTPRequest.new()
	add_child(http)

	var headers := PackedStringArray(["Content-Type: application/json"])
	var body := ""
	if not payload.is_empty():
		body = JSON.stringify(payload)

	var error := http.request(base_url + path, headers, method, body)
	if error != OK:
		http.queue_free()
		return {
			"ok": false,
			"status": 0,
			"error": "请求没有发出去，错误码：" + str(error),
			"data": {},
		}

	var result = await http.request_completed
	http.queue_free()

	var request_result: int = result[0]
	var status: int = result[1]
	var response_body: PackedByteArray = result[3]
	var text := response_body.get_string_from_utf8()
	var data = {}
	if not text.is_empty():
		var parsed = JSON.parse_string(text)
		data = parsed if typeof(parsed) == TYPE_DICTIONARY else {"raw": text}

	if request_result != HTTPRequest.RESULT_SUCCESS:
		return {
			"ok": false,
			"status": status,
			"error": "网络请求失败，错误码：" + str(request_result),
			"data": data,
		}

	if status < 200 or status >= 300:
		return {
			"ok": false,
			"status": status,
			"error": str(data.get("detail", "后端返回错误")),
			"data": data,
		}

	return {
		"ok": true,
		"status": status,
		"error": "",
		"data": data,
	}
