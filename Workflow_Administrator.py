# SPDX-FileCopyrightText: 2025 German Aerospace Center (DLR)
# SPDX-FileContributor: Tim Rosenbach <tim.rosenbach@dlr.de>
#
# SPDX-License-Identifier: MIT

from typing import List
import math

from pywinauto.controls.hwndwrapper import HwndWrapper
from pywinauto.mouse import click, right_click


class Component:
    name: str
    def __init__(self, name: str) -> None:
        self.name = name


class Workflow_Administrator:
    """Class to interact with the Workflow Editor of RCE
    
    Attributes:
    main_window (HwndWrapper): The main window of RCE
    components (List[Component]): List of components in the workflow

    Methods:
    add_to_workflow(path: str): Adds a component to the workflow
    left_click_component(number: int): Left clicks on a component in the workflow
    right_click_component(number: int): Right clicks on a component in the workflow
    get_position(number: int): Returns the position of the component in the workflow
    get_components_as_json(): Returns the components as a JSON object
    get_workflow_editor(): Returns the workflow editor window
    """
    main_window: HwndWrapper

    components: List[Component] = []

    def __init__(self, main_window: HwndWrapper) -> None:
        self.main_window = main_window


    def add_to_workflow(self, path: str) -> None:
        """Adds a component to the workflow

        Args:
            path (str): Path in TreeView of the palette to the component
        """
        palette = self.main_window.child_window(title="Palette", control_type="Pane")
        tree_view = palette.child_window(control_type="Tree")
        component = tree_view.get_item(path)
        position = self.get_position(len(self.components))
        component.click_input()
        click(coords=position)
        self.components.append(Component(component.texts()[0]))

    def left_click_component(self, number: int) -> None:
        """Left clicks on a component in the workflow
        
        Args:
            number (int): Index of the component in the workflow
        """
        position = self.get_position(number)
        click(coords=(position[0] + 5, position[1] + 5))
    
    def right_click_component(self, number: int) -> None:
        """Right clicks on a component in the workflow

        Args:
            number (int): Index of the component in the workflow
        """
        position = self.get_position(number)
        right_click(coords=(position[0] + 5, position[1] + 5))


    def get_position(self, number: int) -> tuple[int, int]:
        """Returns the position of the component in the workflow

        Args:
            number (int): Index of the component in the workflow

        Returns:
            Tuple[int, int]: Position of the component
        """
        rect = self.get_workflow_editor().rectangle()
        x = rect.left + 20 + ((100 * number) % (rect.right - rect.left - 40))
        y = rect.top + 20 + math.floor((100 * number) / (rect.right - rect.left - 40))*100
        if(y > rect.bottom - 20):
            raise Exception("no space on Workflow")
        
        return (x, y)
    
    def get_components_as_json(self) -> List[dict]:
        """Returns the components as a JSON object

        Returns:
            List[dict]: List of components as JSON objects
        """
        json = []
        for i, component in enumerate(self.components):
            json.append({
                "index": i,
                "name" : component.name
            })
        return json

    def get_workflow_editor(self) -> HwndWrapper:
        """Returns the workflow editor window

        Returns:
            HwndWrapper: The workflow editor window
        """
        return self.main_window.child_window(title="Test.wf", control_type="Pane")