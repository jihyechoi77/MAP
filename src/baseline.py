"""
Absolute bare-bones way to set up a simple chatbot using all default settings,
using a Langroid Task + callbacks.

After setting up the virtual env as in README,
and you have your OpenAI API Key in the .env file, run like this:

chainlit run examples/chainlit/chat_basic_chainlit.py
"""
import langroid as lr
import chainlit as cl
import langroid.language_models as lm
from langroid.agent.callbacks.chainlit import add_instructions
from langroid.utils.logging import setup_colored_logging
import logging


from textwrap import dedent

from dotenv import load_dotenv

logger = logging.getLogger(__name__)
setup_colored_logging()

@cl.on_chat_start
async def on_chat_start():
    await add_instructions(
        title="Hello! I am your personal robot, capable of assisting household chores!",
        content=dedent(
            """
            Enter `x` or `q` to quit at any point.
            """
        ),
    )

    load_dotenv()

    # lm_config = lm.OpenAIGPTConfig(chat_model="ollama/mistral")
    lm_config = lm.AzureConfig(
        chat_model=lm.OpenAIChatModel.GPT4_TURBO,
        chat_context_length=10000,
        max_output_tokens=2048,
        temperature=0,
        timeout=100,
    )

    sys_msg = f"""
        You are a helpful assistant.
        You should first start by welcoming me (the User) and wait for my input
        
        """
    config = lr.ChatAgentConfig(llm=lm_config,
                                system_message=sys_msg)
    agent = lr.ChatAgent(config)
    task = lr.Task(agent, interactive=True)

    # msg = "Help me with some questions"
    lr.ChainlitTaskCallbacks(task)
    # await task.run_async(msg)
    await task.run_async()