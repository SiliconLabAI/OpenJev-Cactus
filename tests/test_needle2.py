%%writefile /kaggle/working/test_needle2.py
import needle

@needle.tool
def get_weather(city: str):
    """Get the current weather for a city."""
    return {"city": city, "temp_c": 27, "sky": "clear"}

agent = needle.Needle(tools=[get_weather])
result = agent.run("what's it like in Lagos right now?")
print(result["results"])
# [{'city': 'Lagos', 'temp_c': 27, 'sky': 'clear'}]