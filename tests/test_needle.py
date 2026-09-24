import needle

tools = [{
    "name": "get_weather",
    "description": "Get the current weather for a city.",
    "parameters": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"]
    }
}]

agent = needle.Needle(tools=tools)
print(agent.complete("what's it like in Lagos right now?"))