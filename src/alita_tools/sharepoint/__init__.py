from typing import List
from langchain_community.agent_toolkits.base import BaseToolkit
from .api_wrapper import SharepointApiWrapper
from langchain_core.tools import BaseTool
from ..base.tool import BaseAction

name = "sharepoint"

def get_tools(tool):
    return SharepointToolkit().get_toolkit(
        site_url=tool['settings'].get('site_url', None),
        list_title=tool['settings'].get('list_title', None),
        client_id=tool['settings'].get('client_id', None),
        client_secret=tool['settings'].get('client_secret', None)
    )

class SharepointToolkit(BaseToolkit):

    tools: List[BaseTool] = []

    @classmethod
    def get_toolkit(cls, selected_tools: list[str] | None = None, **kwargs):
        if selected_tools is None:
            selected_tools = []
        sharepoint_api_wrapper = SharepointApiWrapper(**kwargs)
        available_tools = sharepoint_api_wrapper.get_available_tools()
        tools = []
        for tool in available_tools:
            if selected_tools:
                if tool["name"] not in selected_tools:
                    continue
            tools.append(BaseAction(
                api_wrapper=sharepoint_api_wrapper,
                name=tool["name"],
                description=tool["description"],
                args_schema=tool["args_schema"]
            ))
        return cls(tools=tools)

    def get_tools(self):
        return self.tools
