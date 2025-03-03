"""
3-Agent RAG system for robot personalization.
- Robot: is the highest-level robot agent which the user interacts with.
    It generates answers to handle user's requests, articulate, and update the rules and answers based on user feedback.
- RuleManager: is tasked with extracting structured information from a
    commercial lease document, and must present the terms in a specific nested JSON
    format. This agent generates questions corresponding to each field in the JSON
    format.
- DocAgent: This agent answers the questions generated by RuleManager,
    based on the household rule document it has access to via vecdb, using RAG.
Run like this:
```
chainlit run scenario2_mail_delivery.py
```
Edit the `model` argument in main() fn below to change the model.
If you set it to "", it will default to the GPT4-turbo model.
For more on setting up local LLMs with Langroid, see here:
https://langroid.github.io/langroid/tutorials/local-llm-setup/
"""
from langroid import ChatDocument
from rich import print
from pydantic import BaseModel
from typing import List, Any, Dict
import json
import os
import chainlit as cl
import langroid as lr
import langroid.language_models as lm
from langroid.mytypes import Entity
from langroid.agent.special.doc_chat_agent import DocChatAgent, DocChatAgentConfig
from langroid.parsing.parser import ParsingConfig
from langroid.agent.chat_agent import ChatAgent, ChatAgentConfig
from langroid.agent.task import Task
from langroid.agent.tool_message import ToolMessage
from langroid.utils.configuration import set_global, Settings
from langroid.utils.constants import NO_ANSWER, DONE, SEND_TO
from langroid.agent.callbacks.chainlit import add_instructions
from textwrap import dedent
from dotenv import load_dotenv

os.environ["TOKENIZERS_PARALLELISM"] = "false"


class RulesForAll(BaseModel):
    # Blaine: Dict[str, Any]
    # Susie: Dict[str, Any]
    # Ryan: Dict[str, Any]
    # Skyler: Dict[str, Any]
    Blaine: str
    Susie: str
    Ryan: str
    # Skyler: str


class RuleMessage(ToolMessage):
    """Tool/function to use to present details about household rules and schedules"""
    request: str = "rule_info"
    purpose: str = """
        Collect schedule and preference of every resident (Blaine, Susie, Ryan, and Skyler).
        """
    rules: RulesForAll
    result: str = ""

    def handle(self) -> str:
        return DONE + " " + json.dumps(self.dict(), indent=4)

    @classmethod
    def examples(cls) -> List["RuleMessage"]:
        return [
            cls(
                rules=RulesForAll(
                    # Blaine={"wakeup_time": "",
                    #        "routine": "",
                    #        "activity": "",
                    #        "appointment": "",
                    # },
                    # Susie={"wakeup_time": "",
                    #        "routine": "",
                    #        "activity": "",
                    #        "appointment": "",
                    # },
                    # Ryan={"wakeup_time": "",
                    #        "routine": "",
                    #        "activity": "",
                    #        "appointment": "",
                    # },
                    # Skyler={"wakeup_time": "",
                    #       "routine": "",
                    #       "activity": "",
                    #       "appointment": "",
                    #       }
                    Blaine="For breakfast, Blaine likes to have mixed fruits and green tea. She wants it prepared in the common room. For yoga class, Blaine wants the required materials to be left on her bed.",
                    Susie="Susie has weekly doctor checkups on Wednesday 10am. For doctor appointments, she asks to take her pink blanket and purple hat. On Monday, Wednesday, and Friday, Susie will have breakfast with others in the common room.",
                    Ryan="Ryan will wake up at 7 am every weekday. For breakfast, Ryan likes oatmeal, milk, and fruit.",
                    # Skyler="Skyler will wake up at 7 am every weekday. For breakfast, Ryan likes oatmeal, milk, and fruit."

                ),
                result="",
            ),
        ]


class RobotAgent(ChatAgent):
    def rule_info(self, msg: RuleMessage) -> str:
        # convert rules to NON-JSON so it doesn't look like a tool,
        rules_str = json.dumps(msg.rules.dict(), indent=4).replace('{', "[").replace('}', "]")
        return f"""{SEND_TO}LLM
        Below are the RULES you obtained from the RuleManager.
        Now ask the user what help they need, and respond keeping these RULES in mind.

        RULES: 
        {rules_str} 
        """


class RuleAgent(ChatAgent):
    def handle_message_fallback(
            self, msg: str | ChatDocument
    ) -> str | ChatDocument | None:
        """Nudge LLM when it fails to use rule_info correctly"""
        if self.has_tool_message_attempt(msg):
            return """
            You must use the "rule_info" tool to present the rules.
            You either forgot to use it, or you used it with the wrong format.
            Make sure all fields are filled out and pay attention to the 
            required types of the fields.
            """


@cl.on_chat_start
async def on_chat_start():
    await add_instructions(
        title="Hello! I am your personal robot, in charge of assistive care!",
        content=dedent(
            """
            Enter `x` or `q` to quit at any point.
            """
        ),
    )
    load_dotenv()
    set_global(
        Settings(
            debug=False,
            cache=True,  # disables cache lookup; set to True to use cache
        )
    )
    # llm_cfg = lm.OpenAIGPTConfig()
    llm_cfg = lm.AzureConfig(
        chat_model=lm.OpenAIChatModel.GPT4_TURBO,
        chat_context_length=16_000,  # adjust based on model
        temperature=0,
        timeout=45,
    )
    doc_agent = DocChatAgent(
        DocChatAgentConfig(
            llm=llm_cfg,
            n_neighbor_chunks=2,
            parsing=ParsingConfig(
                chunk_size=50,
                overlap=10,
                n_similar_docs=3,
                n_neighbor_ids=4,
            ),
            vecdb=lr.vector_store.LanceDBConfig(
                collection_name="scenario2_assistive_care",
                replace_collection=False,
                storage_path=".lancedb/data/",
                embedding=lr.embedding_models.SentenceTransformerEmbeddingsConfig(
                    model_type="sentence-transformer",
                    model_name="BAAI/bge-large-en-v1.5",
                ),
            ),
            cross_encoder_reranking_model="",
        )
    )
    doc_agent.vecdb.set_collection("scenario2_assistive_care", replace=False) #True)
    doc_agent.config.doc_paths = [
        "docs/scenario2_assistive.txt"
    ]
    doc_agent.ingest()
    doc_task = Task(
        doc_agent,
        name="DocAgent",
        done_if_no_response=[Entity.LLM],  # done if null response from LLM
        done_if_response=[Entity.LLM],  # done if non-null response from LLM
        # Don't us system_message here since it will override doc chat agent's
        # default system message
        # system_message="""You are a housekeeper in my house
        # who are aware of houehold rules of every houehold members.
        # Your job is to answer them CONCISELY in at most 30 sentences.
        # """,
    )
    rule_agent = RuleAgent(
        ChatAgentConfig(
            llm=llm_cfg,
            vecdb=None,
        )
    )
    rule_agent.enable_message(RuleMessage)
    rule_task = Task(
        rule_agent,
        name="RuleManager",
        interactive=False,  # set to True to slow it down (hit enter to progress)
        system_message=f"""
        You are an expert at understanding JSON function/tool specifications.
        When the user asks you to get information about certain resident's schedule and preference,
        you must collect all information so that you can fill in 
        all fields of the `rule_info` function/tool below. 
        You have to fill in the required fields in this `rule_info` function/tool, as shown in the example. 
        This is ONLY an EXAMPLE, and YOU CANNOT MAKE UP VALUES FOR THESE FIELDS.

        To fill in these fields, you must ASK DocAgent QUESTIONS about the preference and schedule,
        ONE BY ONE, and DocAgent will answer each question. 
        If DocAgent am unable to answer your question initially, try asking DocAgent 
        differently. If DocAgent is still unable to answer after 3 tries, fill in 
        {NO_ANSWER} for that field.
        Think step by step. 
        Phrase each question simply as "What is ...'s preference and schedule?",
        and do not explain yourself, or say any extraneous things. 
        When you receive the answer, then ask for the next field, and so on.
        """,
    )
    robot_agent = RobotAgent(
        ChatAgentConfig(
            llm=llm_cfg,
            vecdb=None,
        )
    )
    robot_agent.enable_message(lr.agent.tools.RecipientTool)
    # enable robot agent to HANDLE tool but NOT use it.
    robot_agent.enable_message(RuleMessage, use=False, handle=True)
    robot_task = Task(
        robot_agent,
        name="Robot",
        interactive=True,
        system_message=f"""
        You are a helpful assistive caretaking robot.

        FIRST OF ALL, you have to talk to RuleManager to collect schedules and preferences of residents.
        Make SURE to use the 'recipient_message' tool/function when asking the questions.
        You must keep this information in mind and give me (the User) personalized answers throughout the conversation.
        ONCE DONE, you don't need to talk to RuleManager anymore.

        Next, you should start conversation with me (the User) by welcoming me and 
        list some tasks you can do for me.
        I will give you delivery, and you should answer how you will address my request.
        MAKE SURE that NONE of your answers conflicts with ANY of the rules that you figured out in the first step.
        When assisting residents, if ANY resident has overlapping conflicts from their preferences and schedules with another resident, 
        serve them in ALPHABETICAL ORDER of the resident’s name. 
        Once you present your answer, the I may ask for the summary of relevant rules that you referred to. 
        Then you should provide the summary of relevant rules.
        
        We understand that you do not have physical capabilities of actually performing your suggestions,
        and it is okay to suggest actions that are not feasible for you to perform. 
        You don't need to mention that you can't physically perform the suggested tasks at any time.
        """,
    )
    robot_task.add_sub_task([rule_task])
    rule_task.add_sub_task([doc_task])
    # rule_task.add_sub_task([validator_task, doc_task])
    lr.ChainlitTaskCallbacks(robot_task)
    # must use run() instead of run_async() because DocChatAgent
    # does not have an async llm_response method
    await cl.make_async(robot_task.run)()
