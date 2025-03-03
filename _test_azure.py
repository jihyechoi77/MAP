import langroid as lr
import langroid.language_models as lm

lm_config = lm.AzureConfig()
agent_config = lr.ChatAgentConfig(llm=lm_config)
agent = lr.ChatAgent(agent_config)
task = lr.Task(agent, system_message="You are a helpful assistant")
task.run()