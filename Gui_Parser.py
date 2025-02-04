# SPDX-FileCopyrightText: 2025 German Aerospace Center (DLR)
# SPDX-FileContributor: Tim Rosenbach <tim.rosenbach@dlr.de>
#
# SPDX-License-Identifier: MIT

import base64
import configparser
import shutil

from pywinauto.controls.hwndwrapper import HwndWrapper
from pywinauto.controls.uia_controls import ListItemWrapper
from pywinauto.controls.uia_controls import HeaderWrapper

from Agent import Agent
from Workflow_Administrator import Workflow_Administrator


config = configparser.ConfigParser()
config.read("config.cfg")
settings = config["settings"]

PATH_TO_ICON_PROMPT = "prompts\\icon_description_promt.txt"
PATH_TO_IMAGES = "temp\\images\\"


class GUI_Parser:
    """Class that can parse GUI elements into textual description.

    Attributes:
        workflow_administrator (Workflow_Administrator): Workflow administrator to get the workflow editor from.
        icon_agent (Agent): Agent to generate descriptions for icons.
        generated_Image_descriptions (list[dict]): List of generated image descriptions.

    Methods:
        create_gui_information(element: HwndWrapper) -> dict: Creates a dictionary with information about the GUI element.
        get_icon_description(icon_path: str) -> str: Gets a description for the icon at the given path.
    """
    generated_Image_descriptions = []

    def __init__(self, workflow_administrator: Workflow_Administrator) -> None:
        self.workflow_administrator = workflow_administrator
        self.icon_agent = Agent(settings["icon_description_model"])

    def _is_control_valid(self, window: HwndWrapper) -> bool:
        """Valid control elments are visible, enabled, have a control id, and have a non-zero size."""
        if(not window.is_visible()):
            return False
        if(not window.is_enabled()):
            return False
        if(window.control_id() == None):
            return False
        if window.friendly_class_name() in ("Header", "TitleBar", "TabItem", "ListItem", "HeaderItem"):
            return False
        rect = window.rectangle()
        if(rect.width() == 0 or rect.height() == 0):
            return False
        return True

    def create_gui_information(self, element: HwndWrapper) -> dict:
        """Creates a dictionary with information about the GUI element.
        
        Args:
            element (HwndWrapper): GUI element to get information from.
            
        Returns:
            dict: Dictionary with information about the GUI element.
        """
        if self._is_control_valid(element):
            rect = element.rectangle()
            element_info = {
                "class_name": element.friendly_class_name(),
                "control_type": type(element).__name__,
                "control_id": element.control_id(),
                "rectangle": ['L' + str(rect.left), 'T' + str(rect.top), 'R' + str(rect.right), 'B' + str(rect.bottom)],
            }

            if element.window_text() != '':
                element_info["text"] = element.window_text()

            match element.friendly_class_name():
                case "RadioButton":
                    state = element.is_selected()
                    if state == 0:
                        element_info["check_state"] = "unchecked"
                    elif state == 1:
                        element_info["check_state"] = "checked"
                    else:
                        element_info["check_state"] = "indeterminate"

                case "ListBox":
                    element_info["single_selection"] = (element.can_select_multiple() == True)
                    element_info["columns"] = []
                    element_info["items"] = []
                    for index, item in enumerate(element.get_items()):
                        if type(item) == ListItemWrapper:
                            text = item.texts()
                            if len(text) == 1:
                                text = text[0]
                            element_info["items"].append({
                                "index": index,
                                "text": text,
                                "selected": item.is_selected() == 1
                            })
                        elif type(item) == HeaderWrapper:
                            for header in item.children():
                                element_info["columns"].append(header.texts())
                    if element_info["columns"] == []:
                        element_info.pop("columns")

                case "ComboBox":
                    if element.class_name() == "ComboBox":
                        element.expand()
                        element_info["items"] = []
                        list = None
                        for child in element.children():
                            if child.friendly_class_name() == "ListBox":
                                list = child
                        for index, item in enumerate(list.get_items()):
                            if type(item) == ListItemWrapper:
                                text = item.texts()
                                if len(text) == 1:
                                    text = text[0]
                                element_info["items"].append({
                                    "index": index,
                                    "text": text,
                                    "selected": item.is_selected() == 1
                                })
                        element.collapse()
                    else:
                        print("Weird ComboBox")

                case "CheckBox":
                    check_state = element.get_toggle_state()
                    if check_state == 0:
                        element_info["check_state"] = "unchecked"
                    elif check_state == 1:
                        element_info["check_state"] = "checked"
                    else:
                        element_info["check_state"] = "indeterminate"

                case "Image":
                    element.capture_as_image().save(PATH_TO_IMAGES + "icon.png")
                    description = self.get_icon_description(PATH_TO_IMAGES + "icon.png")
                    element_info["image_description"] = description

                case "ListView":
                    element_info["columns"] = []
                    header_control = element.get_header_control()
                    for i in range(header_control.item_count()):
                        element_info["columns"].append(header_control.get_column_text(i))
                    
                    element_info["content"] = []
                    for row in range(element.item_count()):
                        row_info = []
                        for column in range(element.column_count()):
                            row_info.append(element.get_item(row, column).text())
                        element_info["content"].append(row_info)
                
                case "TabControl":
                    element_info["tabs"] = []
                    for i in range(element.tab_count()):
                        text = element.texts()[i]
                        if text != "":
                            element_info["tabs"].append(
                                {
                                    "index": i,
                                    "text": element.texts()[i],
                                    "selected": i == element.get_selected_tab()
                                }
                            )

                case "Edit":
                    element_info["content"] = element.get_value()
                    element_info["is_editable"] = element.is_editable()

                case "TreeView":
                    items = element.print_items()
                    lines = items.strip().splitlines()
                    result = []
                    current_parents = []

                    def process_line(line):
                        # Remove leading spaces to determine level of indentation
                        level = len(line) - len(line.lstrip())
                        text = line.strip()
                        return level, text
                    
                    for line in lines:
                        level, text = process_line(line)

                        current = {"text": text}
                        if len(current_parents) == level:
                            current_parents.append(current)
                        else:
                            if level == 0:
                                result.append(current_parents[0])
                                current_parents[0] = current
                            else:
                                if "children" not in current_parents[level-1]:
                                    current_parents[level-1]["children"] = [current_parents[level]]
                                else:
                                    current_parents[level-1]["children"].append(current_parents[level])
                                current_parents[level] = current
                    
                    for i in range(len(current_parents)-1, 0, -1):
                        if "children" not in current_parents[i-1]:
                            current_parents[i-1]["children"] = [current_parents[i]]
                        else:
                            current_parents[i-1]["children"].append(current_parents[i])
                        current_parents[i] = current
                    if len(current_parents) > 0:
                        result.append(current_parents[0])


                    element_info["items"] = result
                
            if element.control_id() == self.workflow_administrator.get_workflow_editor().control_id():
                element_info["workflow_components"] = self.workflow_administrator.get_components_as_json()

            element_info["sub_elements"] = []
            for child in element.children():
                child_info = self.create_gui_information(child)
                if child_info:
                    element_info["sub_elements"].append(child_info)
            
            if element_info["sub_elements"] == []:
                element_info.pop("sub_elements")

            return element_info
        else:
            if element.friendly_class_name() == "Dialog":
                for child in element.children():
                    if child.friendly_class_name() == "Dialog":
                        return self.create_gui_information(child)
            return {}
        

    def get_icon_description(self, icon_path: str) -> str:
        """Gets a description for the icon at the given path.

        Args:
            icon_path (str): Path to the icon image.

        Returns:
            str: Description of the icon.
        """
        with open(icon_path, "rb") as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode('utf-8')

        for image in self.generated_Image_descriptions:
            if image["image"] == image_base64:
                return image["description"]

        description = self.icon_agent.make_request(PATH_TO_ICON_PROMPT, jsonFormat=False, pathsToImages=[icon_path])

        self.generated_Image_descriptions.append({
            "image": image_base64,
            "description": description
        })

        shutil.copyfile(icon_path, PATH_TO_IMAGES + str(len(self.generated_Image_descriptions)) + "_icon.png")

        return description