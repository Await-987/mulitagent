from camel.toolkits.base import BaseToolkit, FunctionTool
from typing import List
from camel.toolkits import SearchToolkit
from loguru import logger
from dotenv import load_dotenv


class SearchAPPToolkit(BaseToolkit):
    """
    Toolkit for the AIOS search app.
    """
    def __init__(self):
        super().__init__()
        load_dotenv()
        self.search_toolkit = SearchToolkit()

    def search_tool(
            self,
            query: str,
            number_of_result_pages: int = 1,
    ) -> List:
        r"""Use Exa search API to perform intelligent web search and return
        page contents. Each result contains the full text of a webpage, so
        the total output can be very long. Keep ``number_of_result_pages``
        small to avoid overwhelming context.

        Args:
            query (str): The search query string.
            number_of_result_pages (int): The number of result pages to
                retrieve. Each page already contains the full text of a
                website, so the combined output can be very large. Default
                is 1; use 2–3 only when one result is clearly insufficient.
                (default: :obj:`1`)

        Returns:
            List[Result]: A list of Exa Result objects. Each object contains
            metadata fields (``url``, ``title``, ``author``, ``published_date``)
            and a ``text`` field with the full extracted page content.
        """
        logger.info(f"Search app is searching with query: {query}")
        search_result = self.search_toolkit.search_exa(
            query=query,
            text=True,
            number_of_result_pages=int(number_of_result_pages),
        )
        if isinstance(search_result, dict):
            error_msg = search_result.get("error", "Unknown error")
            logger.error(f"Search failed for query '{query}': {error_msg}")
            return [f"Search failed: {error_msg}"]
        logger.info(f"Search toolkit searched {int(number_of_result_pages)} results.")
        return search_result.results

    def get_tools(self) -> List[FunctionTool]:
        return [
            FunctionTool(self.search_tool)
        ]