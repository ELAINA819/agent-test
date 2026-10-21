import shutil
import json
import os
import sys
from openai import OpenAI
from pathlib import Path
import requests
from dotenv import load_dotenv
import subprocess
import readline

load_dotenv(Path(__file__).resolve().parent / ".env")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")



def copy_file(src, dst):
    shutil.copy2(src, dst)
    return True

def path_exists(path):
    return Path(path).exists()



def read_file(path):
    return Path(path).read_text(encoding='utf-8')

def write_file(path, content):
    Path(path).write_text(content, encoding='utf-8')




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


def run_command(command):

    if (
        not isinstance(command, list)
        or not command
        or not all (isinstance(item, str) for item in command)
    ):
        raise ValueError("command 必须是非空字符串列表")

    try:
        result = subprocess.run(
            command,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return {
            "success": result.returncode==0,
            "returncode": result.returncode,
            "stdout": result.stdout[-10000:],
            "stderr": result.stderr[-10000:],
        }
    except OSError as e:
        return {"success": False, "error": str(e)}



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
    # print(response.choices[0].message.content)
    # print("总 Token：", response.usage.total_tokens)
    content = response.choices[0].message.content
    # print("模型原始返回：", repr(content))
    #print("模型原始返回：", repr(content))
    return json.loads(content, strict=False)

agent_prompt = """
                返回结果为json，json中包含结果或工具调用，
                格式为{answer: 结果, tool: {tool_name:工具函数名, params:[a,b]}},
                两个字段必须有且只有一个为 null，另一个不能为 null，
                调用工具时，answer 必须为 null，格式示例：
                {"answer": null, "tool": {"tool_name": "run_command", "params": ["python", "--version"]}}
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
tool_prompt = """
我有以下工具：

1: path_exists(path)用来查询文件或者文件夹是否存在，参数为路径，返回结构为是否存在；

2: list_directory(path)用于列出对应路径文件夹下的子文件和子文件夹，参数为路径，返回值为文件和子文件夹名称组成的列表，例如 ["test.py", "images"]；

3: read_file(path)用来读取文件，参数为文件路径，返回值为文件内容；

4: write_file(path, content)用来写文件，会覆盖掉文件内容，参数为文件路径和要写入的内容；

5: copy_file(src, dst)用来复制文件，将文件从src复制到dst，返回结果为是否成功；

6: run_command(command)：在 AutoDL 服务器执行系统命令。
                此工具直接将整个 params 数组作为命令列表。
                params 第一项为程序名，后续项为参数，不使用嵌套列表。
                示例：
                {"answer": null, "tool": {"tool_name": "run_command", "params": ["python", "--version"]}}        
                返回 success、returncode、stdout、stderr，超时为30秒。
                不支持交互输入、持续运行程序，以及直接使用管道或重定向。

7: web_search(query)用于搜索互联网，参数为关键词字符串，返回最多5条结果，每条包含title、url、summary，results为空列表表示没有搜索结果，success为False表示搜索失败；

8: get_weather(city)：查询中国城市的当前天气,city 为城市名称字符串，例如“北京”“上海”，必要时使用拼音,返回匹配城市、省份、当地时间、气温、体感温度,湿度、降水量和风速。

9: save_chat_history(path)用于将当前聊天记录保存为json文件，参数为包含文件名的完整保存路径，聊天记录由程序自动提供，无需作为参数传入，文件已存在时会覆盖，返回值为保存结果和文件路径；

10: load_chat_history(path)用于读取JSON聊天记录并导入当前对话，参数为历史记录文件的完整路径，保留当前系统提示词，不清空已有对话，重复加载会产生重复消息，返回值为加载结果和导入的消息数量；

"""

def call_agent(prompt, messages):
    #skill_prompt = read_alltext(skill_dir)
    current_turn_start = len(messages)
    messages.append({"role" : "user", "content": prompt})

    for _ in range(10):
        try:
            result_json = call_openai_api(messages)
        except json.JSONDecodeError as e:
            print(f"模型返回的 JSON 格式错误：{e}")

            messages.append({
                "role": "user",
                "content": (
                    "上一条回复不是合法 JSON。"
                    "请重新返回合法 JSON，必须包含 answer 和 tool，"
                    "且恰好一个为 null。不要输出额外文字。"
                ),
            })
            continue
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

            # print(
            #     f"\n正在调用工具：{tool_name}\n" 
            #     f"参数：{json.dumps(params, ensure_ascii=False)}"
            # )
            
            if tool_name == "copy_file":
                tool_output = copy_file(params[0], params[1])
            elif tool_name == "path_exists":
                tool_output = path_exists(params[0])
            elif tool_name == "read_file":
                tool_output = read_file(params[0])
            elif tool_name == "write_file":
                tool_output = write_file(params[0], params[1])
            elif tool_name == "list_directory":
                tool_output = list_directory(params[0])
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
            elif tool_name == "run_command":
                tool_output = run_command(params)
        # print("工具执行结果：", tool_output)
        messages.append({"role": "assistant", "content":json.dumps(result_json, ensure_ascii=False)})
        messages.append({"role": "user", "content":"工具的执行结果是:" + str(tool_output)})


    return None


def main():
    messages = [{"role": "system","content": tool_prompt + agent_prompt,}]
    while True:
        prompt = input("你：").strip()
        try:
            prompt.encode("utf-8")
        except UnicodeEncodeError:
            print("输入含异常编码字符，请重新输入这一句话。")
            print("输入诊断：", ascii(prompt))
            continue

        if prompt == "退出":
            break

        if not prompt:
            continue

        answer = call_agent(prompt, messages)
        print("助手：", answer)


if __name__ == '__main__':
    main()