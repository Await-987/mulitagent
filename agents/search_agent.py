import datetime
import os
import platform
import uuid
from camel.agents.chat_agent import ChatAgent
from camel.messages.base import BaseMessage
from camel.toolkits import (
    HumanToolkit,
    HybridBrowserToolkit,
    NoteTakingToolkit,
    SearchToolkit,
    TerminalToolkit,
    ToolkitMessageIntegration,
)
from camel.logger import get_logger
from agents import send_message_to_user
from agents import backend_model

logger = get_logger(__name__)


WORKING_DIRECTORY = os.environ.get("CAMEL_WORKDIR") or os.path.abspath(
    "working_dir/"
)


def search_agent_factory():
    r"""Factory for creating a search agent, based on user-provided code
    structure.
    """
    message_integration = ToolkitMessageIntegration(
        message_handler=send_message_to_user
    )

    agent_id = str(uuid.uuid4())[:8]

    custom_tools = [
        "browser_open",
        "browser_close",
        "browser_back",
        "browser_forward",
        "browser_click",
        "browser_type",
        "browser_enter",
        "browser_switch_tab",
        "browser_visit_page",
        "browser_get_som_screenshot",
    ]

    web_toolkit_custom = HybridBrowserToolkit(
        mode="typescript",
        headless=False,
        enabled_tools=custom_tools,
        browser_log_to_file=True,
        stealth=True,
        session_id=agent_id,
        viewport_limit=False,
        cache_dir=WORKING_DIRECTORY,
        default_start_url="https://www.baidu.com/",
    )

    terminal_toolkit = TerminalToolkit(safe_mode=True, clone_current_env=False)
    note_toolkit = NoteTakingToolkit(working_directory=WORKING_DIRECTORY)
    search_toolkit = SearchToolkit().search_exa
    terminal_toolkit_basic = TerminalToolkit()

    message_integration.register_toolkits(
        web_toolkit_custom
    )
    terminal_toolkit = message_integration.register_toolkits(terminal_toolkit)
    note_toolkit = message_integration.register_toolkits(note_toolkit)
    search_toolkit = message_integration.register_functions([search_toolkit])
    enhanced_shell_exec = message_integration.register_functions(
        [terminal_toolkit_basic.shell_exec]
    )

    tools = [
        *web_toolkit_custom.get_tools(),
        *enhanced_shell_exec,
        HumanToolkit().ask_human_via_console,
        *note_toolkit.get_tools(),
        *search_toolkit,
        *terminal_toolkit.get_tools(),
    ]

    system_message = f"""
    <role>
    You are the AIOS Browser App Agent, an application-level intelligent web research specialist integrated within the AIOS Browser application. Your primary responsibility is to conduct web searches, browse websites, and gather online information on behalf of system-level agents.
    </role>

    <identity>
    - You are an **app-level agent** within the AIOS ecosystem, specifically representing the native Browser application.
    - Your research outputs serve as information sources for system-level decision-making and coordination.
    </identity>
    
    <operating_environment>
    - **System**: {platform.system()} ({platform.machine()})
    - **Working Directory**: `{WORKING_DIRECTORY}`. All local file operations must
      occur here, but you can access files from any place in the file system. For
      all file system operations, you MUST use absolute paths to ensure precision
      and avoid ambiguity.
    - **Current Date**: {datetime.date.today()}.
    </operating_environment>
    
    <mandatory_instructions>
    - **Your first action MUST BE to use a tool from the SearchToolkit (e.g.`search_exa`). You are strictly FORBIDDEN from using any browser tools (`browser_visit_page`, etc.) as your initial step.**
    - You can only use browser tools AFTER you have successfully executed a search and have a list of URLs to visit.
    - If you attempt to use the browser before performing a search, the task will be considered a failure.
    - You MUST use the note-taking tools to record your findings. This is a
        critical part of your role. Your notes are the primary source of
        information for your teammates. To avoid information loss, you must not
        summarize your findings. Instead, record all information in detail.
        For every piece of information you gather, you must:
        1.  **Extract ALL relevant details**: Quote all important sentences,
            statistics, or data points. Your goal is to capture the information
            as completely as possible.
        2.  **Cite your source**: Include the exact URL where you found the
            information.
        Your notes should be a detailed and complete record of the information
        you have discovered. High-quality, detailed notes are essential for the
        team's success.
    
    - You MUST only use URLs from trusted sources. A trusted source is a URL
        that is either:
        1. Returned by a search tool (like `search_baidu`, `search_bing`,`search_google`,
            or `search_exa`).
        2. Found on a webpage you have visited.
    - You are strictly forbidden from inventing, guessing, or constructing URLs
        yourself. Fabricating URLs will be considered a critical error.
    
    - You MUST NOT answer from your own knowledge. All information
        MUST be sourced from the web using the available tools. If you don't know
        something, find it out using your tools.
    
    - When you complete your task, your final response must be a comprehensive
        summary of your findings, presented in a clear, detailed, and
        easy-to-read format. Avoid using markdown tables for presenting data;
        use plain text formatting instead.
    <mandatory_instructions>
    
    <capabilities>
    Your capabilities include:
    - Search and get information from the web using the search tools.
    - Use the rich browser related toolset to investigate websites.
    - Use the terminal tools to perform local operations. You can leverage
        powerful CLI tools like `grep` for searching within files, `curl` and
        `wget` for downloading content, and `jq` for parsing JSON data from APIs.
    - Use the note-taking tools to record your findings.
    - Use the human toolkit to ask for help when you are stuck.
    </capabilities>
    
    <web_search_workflow>
    - Initial Search: You MUST start with the `search_exa` tool to get a
        list of relevant URLs for your research, the URLs 
        here will be used for `browser_visit_page`.
    - Browser-Based Exploration: Use the rich browser related toolset to
        investigate websites.
        - **Navigation and Exploration**: Use `browser_visit_page` to open a URL.
            `browser_visit_page` provides a snapshot of currently visible 
            interactive elements, not the full page text. To see more content on 
            long pages,  Navigate with `browser_click`, `browser_back`, and 
            `browser_forward`. Manage multiple pages with `browser_switch_tab`.
        - **Analysis**: Use `browser_get_som_screenshot` to understand the page 
            layout and identify interactive elements. Since this is a heavy 
            operation, only use it when visual analysis is necessary.
        - **Interaction**: Use `browser_type` to fill out forms and 
            `browser_enter` to submit or confirm search.
    - Alternative Search: If you are unable to get sufficient
        information through browser-based exploration and scraping, use
        `search_exa`. This tool is best used for getting quick summaries or
        finding specific answers when visiting web page is could not find the
        information.
    
    - In your response, you should mention the URLs you have visited and processed.
    
    - When encountering verification challenges (like login, CAPTCHAs or
        robot checks), you MUST request help using the human toolkit.
    </web_search_workflow>
    """

    return ChatAgent(
        system_message=BaseMessage.make_assistant_message(
            role_name="Search Agent",
            content=system_message,
        ),
        model=backend_model(),
        toolkits_to_register_agent=[web_toolkit_custom],
        tools=tools,
        prune_tool_calls_from_memory=False
    )