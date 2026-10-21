import shutil
import json
import os
import sys
from openai import OpenAI
from pathlib import Path
from datetime import datetime
import requests
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")


def get_disk_size(path):
    total = shutil.disk_usage(path)
    return total[0]

def copy_file(src, dst):
    shutil.copy2(src, dst)
    return True

def path_exists(path):
    return Path(path).exists()

def create_folder(path):
    Path(path).mkdir(parents= True,exist_ok=True)

def create_file(path):
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.touch(exist_ok=True)

def read_file(path):
    return Path(path).read_text(encoding='utf-8')

def write_file(path, content):
    Path(path).write_text(content, encoding='utf-8')

def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def delete_file(path):
    Path(path).unlink()

def delete_folder(path):
    shutil.rmtree(Path(path))

def list_directory(path):
    results = []
    folders = Path(path)

    for item in folders.iterdir():
        info = {
            'name': item.name,
            'path': item.as_posix(),
            'is_dir': item.is_dir(),
        }
        results.append(info)

    return results

def get_file_info(path):
    file = Path(path)
    info = file.stat()

    return {
        "name": file.name,
        "path": file.resolve().as_posix(),
        "is_file": file.is_file(),
        "is_directory": file.is_dir(),
        "size_bytes": info.st_size if file.is_file() else None,
        "modified_time": datetime.fromtimestamp(
            info.st_mtime
        ).strftime("%Y-%m-%d %H:%M:%S"),
    }

def find_files(path, pattern):
    folder = Path(path)
    results = []

    for item in folder.rglob(pattern):
        if item.is_file():
            results.append(item.as_posix())

    return results

def web_search(query):

    try:
        response = requests.post(
            "https://api.deepseek.com/v1/tools/search",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            },
            json={
                "query": query.strip(),
                "count": 5,
                "need_content": False,
            },
            timeout=30,
        )
        response.raise_for_status()
        results = [
            {
                "title": item["title"],
                "url": item["url"],
                "summary": item.get("summary") or item.get("snippet", ""),
            }
            for item in response.json()["results"]
        ]
        return {"success": True, "results": results}

    except requests.RequestException as e:
        return {"success": False, "error": str(e)}

def save_chat_history(path, messages):
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)

    file.write_text(
        json.dumps(messages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return f"聊天记录已保存到：{file.resolve().as_posix()}"

def load_chat_history(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    history = []

    for message in data:
        if not isinstance(message, dict):
            raise ValueError("消息格式错误")

        role = message.get("role")
        content = message.get("content")

        if role == "system":
            continue

        history.append({"role": role, "content": content})

    return history

import requests


def get_weather(city):
    try:
        location_response = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={
                "name": city,
                "count": 1,
                "language": "zh",
                "countryCode": "CN",
            },
            timeout=20,
        )
        location_response.raise_for_status()

        locations = location_response.json().get("results", [])

        if not locations:
            return {
                "success": False,
                "error": "未找到城市，请换用城市名称或拼音",
            }

        location = locations[0]

        weather_response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "current": (
                    "temperature_2m,"
                    "apparent_temperature,"
                    "relative_humidity_2m,"
                    "precipitation,"
                    "wind_speed_10m"
                ),
                "timezone": "auto",
            },
            timeout=20,
        )
        weather_response.raise_for_status()

        data = weather_response.json()
        current = data["current"]

        return {
            "success": True,
            "city": location["name"],
            "province": location.get("admin1", ""),
            "country": location.get("country", ""),
            "time": current["time"],
            "timezone": data["timezone"],
            "temperature_c": current["temperature_2m"],
            "feels_like_c": current["apparent_temperature"],
            "humidity_percent": current["relative_humidity_2m"],
            "precipitation_mm": current["precipitation"],
            "wind_speed_kmh": current["wind_speed_10m"],
            "source": "Open-Meteo",
        }

    except (requests.RequestException, ValueError, KeyError) as e:
        return {
            "success": False,
            "error": str(e),
        }




def call_openai_api(messages):
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )

    response = client.chat.completions.create(
        model="deepseek-flash",
        messages=messages,
        stream=False,
        extra_body={"thinking": {"type": "disabled"}},
        response_format={"type": "json_object"},
    )
    print(response.choices[0].message.content)
    print("总 Token：", response.usage.total_tokens)
    content = response.choices[0].message.content
    #print("模型原始返回：", repr(content))
    return json.loads(content)

agent_prompt = """
                返回结果为json，json中包含结果或工具调用，
                格式为{answer: 结果, tool: {tool_name:工具函数名, params:[a,b]}},
                两个字段必须有且只有一个为 null，另一个不能为 null，
                调用工具时，answer 必须为 null，格式示例：
                {"answer": null, "tool": {"tool_name": "get_current_time", "params": []}}
                直接回答时，tool 必须为 null，格式示例：
                {"answer": "回答内容", "tool": null}；
                JSON 字符串中的换行必须使用\\n转义，
                双引号和反斜杠也必须正确转义，不得直接在字符串内部换行；
                当前运行环境为 AutoDL 的 Linux 系统，路径使用正斜杠 /，不使用 Windows 盘符，例如 /root/autodl-tmp/agent_test；
                写入前使用 path_exists 检查目标路径是否存在；
                文件不存在时直接写入创建,存在时覆盖写入；
                如果用户要求修改已有文件，必须先读取原内容，再修改并保存；
                你可以通过web_search获取实时信息，不得声称自己没有联网工具；
               """
tool_prompt =  """
                我有几个tool
               1: get_disk_size(path)用来获取磁盘大小，参数path是磁盘路径，返回磁盘总容量；
               2: copy_file(src, dst)用来复制文件，将文件从src复制到dst，返回结果为是否成功；
               3: create_folder(path)用来创建文件夹，参数为文件夹的路径；"
               4: create_file(path)用来创建文件，参数为文件的路径；"
               5: path_exists(path)用来查询文件或者文件夹是否存在，参数为路径，返回结构为是否存在；
               6: read_file(path)用来读取文件，参数为文件路径，返回值为文件内容；
               7: write_file(path, content)用来写文件，会覆盖掉文件内容，参数为文件路径和要写入的内容；
               8: get_current_time()用来查看系统当前时间，无参数，返回值为系统当前时间；
               9: delete_file(path)用于删除文件，参数为文件路径；
               10: delete_folder(path)用于删除文件夹，参数为文件夹路径；
               11: list_directory(path)用于列出对应路径文件夹下的子文件和子文件夹，参数为路径，返回值为文件和子文件夹名称组成的列表，例如 ["test.py", "images"]；
               12: get_file_info(path)用于获取对应文件信息，参数为路径，返回值为名称、完整路径、类型、文件大小和修改时间；
               13: find_files(path, pattern)在指定目录及其所有子目录中查找文件，参数为路径和文件名，文件名可以是完整文件名，也可以带通配符，返回值为匹配文件的路径列表，没有匹配结果时返回空列表；
               14: web_search(query)用于搜索互联网，参数为关键词字符串，返回最多5条结果，每条包含title、url、summary，results为空列表表示没有搜索结果，success为False表示搜索失败；
               15: save_chat_history(path)用于将当前聊天记录保存为json文件，参数为包含文件名的完整保存路径，聊天记录由程序自动提供，无需作为参数传入，文件已存在时会覆盖，返回值为保存结果和文件路径；
               16: load_chat_history(path)用于读取JSON聊天记录并导入当前对话，参数为历史记录文件的完整路径，保留当前系统提示词，不清空已有对话，重复加载会产生重复消息，返回值为加载结果和导入的消息数量；
               17: get_weather(city)：查询中国城市的当前天气,city 为城市名称字符串，例如“北京”“上海”，必要时使用拼音,返回匹配城市、省份、当地时间、气温、体感温度,湿度、降水量和风速。
               """

def call_agent(prompt, messages):
    #skill_prompt = read_alltext(skill_dir)
    current_turn_start = len(messages)
    messages.append({"role" : "user", "content": prompt})

    for _ in range(10):
        result_json = call_openai_api(messages)
        valid = (
            isinstance(result_json, dict)
            and "answer" in result_json
            and "tool" in result_json
            and (result_json["answer"] is None)
            != (result_json["tool"] is None)
        )
        if not valid:
            messages.append({
                "role": "assistant",
                "content": json.dumps(result_json, ensure_ascii=False),
            })
            messages.append({
                "role": "user",
                "content": (
                    "返回格式错误。必须同时包含 answer 和 tool，"
                    "其中恰好一个为 null，另一个不能为 null。"
                    "请重新返回 JSON。"
                ),
            })
            continue

        if result_json.get("answer") is not None:
            messages.append({"role": "assistant", "content": json.dumps(result_json, ensure_ascii=False)})
            return result_json["answer"]
        else:
            tool_name = result_json["tool"]["tool_name"]
            params = result_json["tool"]["params"]
            if tool_name == "copy_file":
                tool_output = copy_file(params[0], params[1])
            elif tool_name == "get_disk_size":
                tool_output = get_disk_size(params[0])
            elif tool_name == "create_folder":
                tool_output = create_folder(params[0])
            elif tool_name == "create_file":
                tool_output = create_file(params[0])
            elif tool_name == "path_exists":
                tool_output = path_exists(params[0])
            elif tool_name == "read_file":
                tool_output = read_file(params[0])
            elif tool_name == "write_file":
                tool_output = write_file(params[0], params[1])
            elif tool_name == "get_current_time":
                tool_output = get_current_time()
            elif tool_name == "delete_file":
                tool_output = delete_file(params[0])
            elif tool_name == "delete_folder":
                tool_output = delete_folder(params[0])
            elif tool_name == "list_directory":
                tool_output = list_directory(params[0])
            elif tool_name == "get_file_info":
                tool_output = get_file_info(params[0])
            elif tool_name == "find_files":
                tool_output = find_files(params[0], params[1])
            elif tool_name == "web_search":
                tool_output = web_search(params[0])
            elif tool_name == "save_chat_history":
                tool_output = save_chat_history(params[0], messages)
            elif tool_name == "load_chat_history":
                history = load_chat_history(params[0])
                messages[current_turn_start:current_turn_start] = history
                tool_output = f"已加载 {len(history)} 条历史消息"
            elif tool_name == "get_weather":
                tool_output = get_weather(params[0])

        messages.append({"role": "assistant", "content":json.dumps(result_json, ensure_ascii=False)})
        messages.append({"role": "user", "content":"工具的执行结果是:" + str(tool_output)})


    return None


def main():
    messages = [{"role": "system","content": tool_prompt + agent_prompt,}]
    while True:
        prompt = input("你：").strip()

        if prompt == "退出":
            break

        if not prompt:
            continue

        answer = call_agent(prompt, messages)
        print("助手：", answer)


if __name__ == '__main__':
    main()