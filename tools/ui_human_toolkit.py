import sys
from typing import List, Optional

from camel.toolkits.base import BaseToolkit
from camel.toolkits.function_tool import FunctionTool
from camel.logger import get_logger

logger = get_logger(__name__)


class UIHumanToolkit(BaseToolkit):
    """Human interaction toolkit that routes questions through the phone UI.

    In web-server mode the question appears as an AI bubble in the 小艺 chat
    panel and execution blocks until the user submits a free-text reply via
    the input box.  In standalone mode it prints to the terminal and reads
    from stdin.
    """

    def __init__(self, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)

    def ask_human_via_console(self, question: str) -> str:
        r"""Show a question to the user as a chat bubble and wait for their
        free-text reply before continuing.  Use this tool to:
        - Clarify ambiguous intent or missing information.
        - Ask for a preference or constraint not in the soul profile.
        - Summarise the planned action and ask if the user wants to adjust.

        Args:
            question (str): The question to show the user.

        Returns:
            str: The user's free-text reply (web-UI mode) or the terminal
                 input (standalone mode).
        """

        try:
            from demo.os_view import ui_bridge as _bridge
            sid = _bridge.get_session_id()
            if sid:
                reply = _bridge.ask_user(question)
                logger.info("User reply via UI: %s", reply)
                return reply
        except ImportError:
            pass


        print(f"\nQuestion: {question}")
        logger.info("Question: %s", question)
        try:
            reply = input("Your reply: ")
        except (UnicodeDecodeError, EOFError):
            buf = getattr(sys.stdin, "buffer", None)
            if buf:
                raw = buf.readline().rstrip(b"\r\n")
                enc = getattr(sys.stdin, "encoding", None) or "utf-8"
                reply = raw.decode(enc, errors="replace")
            else:
                reply = "(no reply)"
        logger.info("User reply: %s", reply)
        return reply


    def get_tools(self) -> List[FunctionTool]:
        """Return the list of FunctionTool objects provided by this toolkit."""
        return [FunctionTool(self.ask_human_via_console)]
