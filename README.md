Python 日常工作助手（AutoDL 版）

使用 Python 调用 DeepSeek，支持多轮对话、文件增删读写、文件查找、网络搜索、当前天气查询，以及手动保存和加载聊天记录。

运行环境：Python 3.11，AutoDL Linux。程序本身不需要 GPU，需要联网。

安装和运行：
在项目目录打开终端，执行以下命令。已有 autodl-agent 环境时跳过创建步骤。

source "$(conda info --base)/etc/profile.d/conda.sh"
conda create -n autodl-agent python=3.11 -y
conda activate autodl-agent
python -m pip install -r requirements.txt
cp .env.example .env

编辑 .env，填写自己的密钥：
DEEPSEEK_API_KEY=你的密钥

启动程序：
python agent.py

使用示例：
现在几点了？
查询北京当前天气。
搜索 Python 官方教程，并提供链接。
在 /root/autodl-tmp/agent_test_data 下创建 hello.py，打印 hello world。
把聊天记录保存到 /root/autodl-tmp/agent_test_data/history.json。

输入“退出”结束。每次问题在一行内提交，聊天记录不会自动保存。

注意：
.env 与 agent.py 放在同一目录，不要上传真实密钥。
文件操作针对服务器，相对路径以启动程序时所在目录为起点，建议使用完整路径。
覆盖写入会替换原内容；删除文件夹会递归删除全部内容，不进入回收站。
当前版本没有运行生成代码的工具，出现格式错误或工具异常时可能退出。
