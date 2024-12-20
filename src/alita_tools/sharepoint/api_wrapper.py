import logging
import os
from traceback import format_exc
import json
from typing import List, Optional, Any, Dict
from langchain_core.tools import ToolException
from langchain_core.pydantic_v1 import root_validator, BaseModel
from pydantic import create_model
from pydantic.fields import FieldInfo

from .utils import read_docx_from_bytes

logger = logging.getLogger(__name__)

NoInput = create_model(
    "NoInput"
)

SharepointReadList = create_model(
    "SharepointSearchModel",
    list_title=(str, FieldInfo(description="Name of a Sharepoint list to be read."))
)

SharepointGetAllFiles = create_model(
    "SharepointGetAllFilesModel",
    limit_files=(int, FieldInfo(description="Limit (maximum number) of files to be returned. Can be called with synonyms, such as First, Top, etc., or can be reflected just by a number for example Top 10 files'. Use default value if not specified in a query WITH NO EXTRA CONFIRMATION FROM A USER"))
)

SharepointGetAllFilesInFolder = create_model(
    "SharepointGetAllFilesInFolder",
    folder_name=(str, FieldInfo(description="Folder name to get list of the files.")),
    limit_files=(int, FieldInfo(description="Limit (maximum number) of files to be returned. Can be called with synonyms, such as First, Top, etc., or can be reflected just by a number for example Top 10 files'. Use default value if not specified in a query WITH NO EXTRA CONFIRMATION FROM A USER")),
)

SharepointReadDocument = create_model(
    "SharepointReadDocument",
    path=(str, FieldInfo(description="Contains the server-relative path of the  for reading."))
)

class SharepointApiWrapper(BaseModel):
    site_url: str
    client_id: str
    client_secret: str
    root_folder: Optional[str]

    @root_validator()
    def validate_toolkit(cls, values):

        try:
            from office365.runtime.auth.authentication_context import AuthenticationContext
            from office365.sharepoint.client_context import ClientContext
        except ImportError:
            raise ImportError(
                "`office365` package not found, please run "
               "`pip install office365` and `pip install office365-rest-python-client`"
            )

        site_url = values['site_url']
        root_folder = values.get('root_folder')
        client_id = values.get('client_id')
        client_secret = values.get('client_secret')

        values['client'] = None
        try:
            ctx_auth = AuthenticationContext(site_url)
            if ctx_auth.acquire_token_for_app(client_id, client_secret):
                values['client'] = ClientContext(site_url, ctx_auth)
            else:
                logging.error("Failed to authenticate with SharePoint.")
        except Exception as e:
                logging.error(f"Failed to authenticate with SharePoint: {str(e)}")
        return values


    def read_list(self, list_title):
        """ Reads a specified List in sharepoint site """
        try:
            target_list = self.client.web.lists.get_by_title(list_title)
            self.client.load(target_list)
            self.client.execute_query()
            items = target_list.items.get().top(1000).execute_query()
            logging.info("{0} items from sharepoint loaded successfully.".format(len(items)))
            result = []
            for item in items:
                result.append(item.properties)
            return result
        except Exception as e:
            logging.error(f"Failed to load items from sharepoint: {e}")


    def get_all_files(self, limit_files=10):
        """Lists files from SharePoint in a root folder (folder_name) if provided; otherwise lists from the main library called Documents, limited by limit_files (default is 10)."""
        try:
            result = []

            if self.root_folder:
                doc_lib = self.client.web.lists.get_by_title(self.root_folder)
            else:
                doc_lib = self.client.web.lists.get_by_title('Documents')
            self.client.load(doc_lib).execute_query()
            items = doc_lib.items.get().top(limit_files).execute_query()

            for item in items:
                if item.file_system_object_type == 0:  # FileSystemObjectType.File
                    file = item.file
                    self.client.load(file).execute_query()
                    temp_props = {
                        'Name': file.properties['Name'],
                        'Path': file.properties['ServerRelativeUrl'],
                        'Created': file.properties['TimeCreated'],
                        'Modified': file.properties['TimeLastModified'],
                        'Link': file.properties['LinkingUrl']
                        }
                    result.append(temp_props)
            return result
        except Exception as e:
            logging.error(f"Failed to load files from SharePoint: {e}")
            return []

    def get_all_files_in_folder(self, folder_name, limit_files=10):
        """ Lists all files from sharepoint in a specific folder, , limited by limit_files (default is 10)."""
        try:
            result = []

            target_folder_url = "Shared Documents/" + folder_name
            root_folder = self.client.web.get_folder_by_server_relative_path(target_folder_url)
            files = root_folder.get_files(True).execute_query()

            for file in files:
                if len(result) >= limit_files:
                    break
                temp_props = {'Name': file.properties['Name'],
                              'Path': file.properties['ServerRelativeUrl'],
                              'Created': file.properties['TimeCreated'],
                              'Modified': file.properties['TimeLastModified'],
                              'Link': file.properties['LinkingUrl']
                              }
                result.append(temp_props)
            return result
        except Exception as e:
            logging.error(f"Failed to load files from sharepoint: {e}")
            return []

    def read_file(self, path):
        """ Reads file located at the specified server-relative path """
        file = self.client.web.get_file_by_server_relative_path(path)
        self.client.load(file)
        self.client.execute_query()

        file_content = file.read()
        self.client.execute_query()

        if file.name.endswith('.txt'):
            try:
                file_content_str = file_content.decode('utf-8')
                print(file_content_str)
            except Exception as e:
                print(f"Error decoding file content: {e}")
        elif file.name.endswith('.docx'):
            file_content_str = read_docx_from_bytes(file_content)
        else:
            return "Not supported type of files entered. Supported types are TXT and DOCX only at the moment"
        return file_content_str

    def get_available_tools(self):
        return [
            {
                "name": "read_list",
                "description": self.read_list.__doc__,
                "args_schema": SharepointReadList,
                "ref": self.read_list
            },
            {
                "name": "get_all_files",
                "description": self.get_all_files.__doc__,
                "args_schema": SharepointGetAllFiles,
                "ref": self.get_all_files
            },
            {
                "name": "get_all_files_in_folder",
                "description": self.get_all_files_in_folder.__doc__,
                "args_schema": SharepointGetAllFilesInFolder,
                "ref": self.get_all_files_in_folder
            },
            {
                "name": "read_document",
                "description": self.read_file.__doc__,
                "args_schema": SharepointReadDocument,
                "ref": self.read_file
            }
        ]

    def run(self, mode: str, *args: Any, **kwargs: Any):
        for tool in self.get_available_tools():
            if tool["name"] == mode:
                return tool["ref"](*args, **kwargs)
        else:
            raise ValueError(f"Unknown mode: {mode}")
