# SPDX-FileCopyrightText: 2025 German Aerospace Center (DLR)
# SPDX-FileContributor: Tim Rosenbach <tim.rosenbach@dlr.de>
#
# SPDX-License-Identifier: MIT

import configparser
import json
import os
import shutil
import time

from pywinauto.application import Application
from pywinauto.controls.hwndwrapper import HwndWrapper
from pywinauto.controls.uia_controls import ButtonWrapper
from pywinauto.controls.uia_controls import TabControlWrapper
from pywinauto.controls.uia_controls import EditWrapper
from pywinauto.controls.uia_controls import ComboBoxWrapper
from pywinauto.controls.uia_controls import ListViewWrapper
from pywinauto.findwindows import ElementAmbiguousError
from pywinauto.findwindows import ElementNotFoundError
from pywinauto.mouse import move, press, release
from pywinauto.timings import TimeoutError

from Agent import Agent
from Gui_Parser import GUI_Parser
from Workflow_Administrator import Workflow_Administrator


config = configparser.ConfigParser()
config.read("config.cfg")
setup = config["setup"]
settings = config["settings"]

BACKEND = "uia"
PATH_TO_DOCUMENTATION = "rce_documentation\\"
PATH_TO_EVALUATION_PROMPT = "prompts\\evaluator_prompt.txt"
PATH_TO_CONTROLLER_PROPMPT = "prompts\\controller_prompt.txt"
PATH_TO_EVALUATION_REQUEST = "temp\\requests\\evaluation_request.txt"
PATH_TO_CONTROLLER_REQUEST = "temp\\requests\\controller_request.txt"

TASK = r"""
Act as a GUI-Tester for the software RCE.
Cover all pages of the Tool Integration Wizard.
Use as many different UI-Elements as possible.
"""


controller_agent = Agent(settings["controller_model"], None)
evaluator_agent = Agent(settings["evaluator_model"], None)

previous_actions = []


def start_or_connect_rce() -> Application:
    """Starts or connects to an existing instance of RCE.
    
    Returns:
        Application: The RCE application object.
    """
    try:
        app = Application(backend=BACKEND).connect(title_re="RCE*")
        print("RCE is already running. Connected to the existing instance.")
    except ElementNotFoundError:
        app = Application(backend=BACKEND).start(setup["rce_path"])
        app.connect(title_re="RCE*", timeout=50)
        print("RCE was not running. Started a new instance.")
    
    return app

def format_json(data: dict) -> str:
    """Formats a dictionary as a JSON string with an indentation of 4 spaces.
    
    Args:
        data (dict): The dictionary to be formatted.
    
    Returns:
        str: The formatted JSON string.
    """
    json_str = json.dumps(data, indent=4)
    json_lines = json_str.split("\n")
    formatted_lines = []
    
    i = 0
    while i < len(json_lines):
        line = json_lines[i]
        if line.strip().startswith('"rectangle": ['):
            combined_line = line
            while not line.strip().endswith('],') and not line.strip().endswith(']'):
                i += 1
                line = json_lines[i].strip()
                combined_line += ' ' + line
            formatted_lines.append(combined_line)
        else:
            formatted_lines.append(line)
        i += 1
    
    return "\n".join(formatted_lines)

def get_documentation(documentation_name: str) -> str:
    """Gets the documentation for the current task.
    
    Args:
        documentation_name (str): The name of the documentation file.

    Returns:
        str: The documentation for the current task.
    """
    with open(PATH_TO_DOCUMENTATION + documentation_name + ".txt", "r") as file:
        return file.read()

def write_controller_request(gui_info: dict, documentation_name:str) -> None:
    """Writes the controller request file with the given GUI information.
    
    Args:
        gui_info (dict): The GUI information to be written to the controller request file.
    """
    with open(PATH_TO_CONTROLLER_PROPMPT, "r") as prompt_file:
        prompt = prompt_file.read()
    if settings["test_only_tool_integration"]:
        formatted_prompt = prompt.format(TASK, "\nDocumentation: " + get_documentation(documentation_name), format_json(gui_info), format_json(previous_actions))    
    else:
        formatted_prompt = prompt.format(TASK, "", format_json(gui_info), format_json(previous_actions))
    with open(PATH_TO_CONTROLLER_REQUEST, "w") as file:
        file.write(formatted_prompt)

def execute_action(action_dict: dict, active_window: HwndWrapper, workflow_administrator: Workflow_Administrator) -> dict:
    """Executes the given action on the given window.

    Args:
        action_dict (dict): The action to be executed.
        active_window (HwndWrapper): The window on which the action should be

    Returns:
        dict: The action dictionary with the status of the execution.
    """
    try:
        action = action_dict["action"]
        elements = action.split("(")
        action_name = elements[0]
        parameters = elements[1].split(")")[0].split(",")

        if not parameters[0].isdigit():
            if action_name == "add_component":
                workflow_administrator.add_to_workflow(path=parameters[0].replace("\"", "").replace("'", "").strip())
                action_dict["status"] = "executed"
            else:
                action_dict["status"] = "not executed"
                action_dict["error"] = "action or parameter do not match"
            
        else:
            match action_name:
                case "select_component":
                    workflow_administrator.left_click_component(int(parameters[0]))
                    action_dict["status"] = "executed"
                case "right_click_component":
                    workflow_administrator.right_click_component(int(parameters[0]))
                    action_dict["status"] = "executed"
                case _:
                    control_type = HwndWrapper
                    element = None
                    try:
                        control_type = type(active_window.window(control_id=int(parameters[0])).wrapper_object())
                        element = active_window.window(control_id=int(parameters[0]))
                    except ElementNotFoundError:
                        action_dict["status"] = "not executed"
                        action_dict["error"] = "Element with control_id " + parameters[0] + " does not exist"
                        return action_dict
                    except ElementAmbiguousError:
                        action_dict["status"] = "not executed"
                        action_dict["error"] = "There are multiple elements with control_id " + parameters[0]
                        return action_dict
                    
                    if not element.is_enabled():
                        action_dict["status"] = "not executed"
                        action_dict["error"] = "Element with control_id " + parameters[0] + " is not enabled"
                        return action_dict
                    
                    match action_name:
                        case "click":
                            if control_type == ButtonWrapper:
                                element.click()
                                action_dict["status"] = "executed"
                            else:
                                action_dict["status"] = "not executed"
                                action_dict["error"] = "Element with control_id " + parameters[0] + " is a " + control_type.__name__ + " which has no action " + action_name
                        case "write":
                            if control_type == EditWrapper:
                                if element.is_editable():
                                    text_input = parameters[1]
                                    for param in parameters[2:]:
                                        text_input += "," + param
                                    text_input = text_input.replace("\"", "").replace("'", "").strip()
                                    element.set_edit_text(text_input)
                                    action_dict["status"] = "executed"
                                else:
                                    action_dict["status"] = "not executed"
                                    action_dict["error"] = "Element with control_id " + parameters[0] + " is not editable"
                            else:
                                action_dict["status"] = "not executed"
                                action_dict["error"] = "Element with control_id " + parameters[0] + " is a " + control_type.__name__ + " which has no action " + action_name
                        case "select":
                            try:
                                if control_type == ComboBoxWrapper:
                                    element.expand()
                                    list_box = element.child_window(control_type="List")
                                    list_box.get_item(int(parameters[1])).click_input()
                                    element.collapse()
                                    action_dict["status"] = "executed"
                                elif control_type == TabControlWrapper:
                                    index = int(parameters[1])
                                    if index not in range(1, element.tab_count()):
                                        action_dict["status"] = "not executed"
                                        action_dict["error"] = "There is no tab with index " + str(index)
                                    else:
                                        element.child_window(title=element.texts()[int(parameters[1])]).click_input()
                                        action_dict["status"] = "executed"
                                elif control_type == ListViewWrapper:
                                    element.get_item(int(parameters[1])).select()
                                    action_dict["status"] = "executed"
                                else:
                                    action_dict["status"] = "not executed"
                                    action_dict["error"] = "Element with control_id " + parameters[0] + " is a " + control_type.__name__ + " which has no action " + action_name
                            except IndexError:
                                action_dict["status"] = "not executed"
                                action_dict["error"] = "Index " + parameters[1] + " is out of range"
                        case _:
                            action_dict["status"] = "not executed"
                            action_dict["error"] = "Element with control_id " + parameters[0] + " is a " + control_type.__name__ + " which has no action " + action_name
        return action_dict
    except Exception as e:
        action_dict["status"] = "not executed"
        action_dict["error"] = str(e)
        return action_dict

def evaluate_gui(path_to_previous_state: str, path_to_current_state: str) -> None:
    """Evaluates the GUI change between the previous and the current state.
    
    Args:
        path_to_previous_state (str): The path to the screenshot of the previous state.
        path_to_current_state (str): The path to the screenshot of the current state.
    """
    with open(PATH_TO_EVALUATION_PROMPT, "r") as prompt_file:
        prompt = prompt_file.read()
    formatted_prompt = prompt.format(previous_actions[-1]["explanation"])
    with open(PATH_TO_EVALUATION_REQUEST, "w") as file:
        file.write(formatted_prompt)

    evaluation = evaluator_agent.make_request(PATH_TO_EVALUATION_REQUEST, jsonFormat=True, pathsToImages=[path_to_previous_state, path_to_current_state])
    print("Evaluation:")
    print(evaluation)

    json_output = json.loads(evaluation)
    if json_output["state"] == "problem":
        with open("./temp/evaluation.txt", "a") as evaluation_file:
            evaluation_file.write(path_to_current_state + "\n")
            evaluation_file.write(evaluation)
            evaluation_file.write("\n\n")

def get_manuel_action() -> str:
    """Gets the manual action from the user.
    
    Returns:
        str: The manual action.
    """
    user_input = input("Please enter a string: ")
    return user_input

def create_temp_folders() -> None:
    """Creates the temporary folders for the GUI states, requests, and images."""
    if os.path.exists("./temp"):
        shutil.rmtree("./temp")
    os.makedirs("./temp")
    os.makedirs("./temp/gui_states")
    os.makedirs("./temp/requests")
    os.makedirs("./temp/images")


def main() -> None:
    rce = start_or_connect_rce()
    rce_window = rce.window(title_re="RCE*")
    rce_window.wait("ready", timeout=30)

    create_temp_folders()

    workflow_administrator = Workflow_Administrator(rce_window)
    gui_parser = GUI_Parser(workflow_administrator)

    if bool(settings["test_only_tool_integration"]):
        try:
            tool_integration_wizard = rce_window.child_window(title="Integrate a Tool as a Workflow Component")
            tool_integration_wizard.wait("ready", timeout=5)
        except TimeoutError:
            rce_window.menu_select("integration -> Integrate Tool...")
            tool_integration_wizard = rce_window.child_window(title="Integrate a Tool as a Workflow Component")
            tool_integration_wizard.wait("ready", timeout=30)
        title_id = tool_integration_wizard.child_window(title="Choose Tool Configuration").control_id()
        main_window = tool_integration_wizard
    else:
        main_window = rce_window


    next_steps = 0
    is_manual = False

    i = 0

    while i < int(settings["max_actions"]):
        if next_steps > 0 or not bool(settings["step_by_step"]):
            next_steps -= 1
            i += 1
         
            time.sleep(0.1) # wait for the GUI to update, otherwise the screenshot will sometimes be blurred
            path_to_screenshot = f"./temp/gui_states/screenshot_{i}.png"
            main_window.capture_as_image().save(path_to_screenshot)
 
            gui_info = gui_parser.create_gui_information(main_window)   

            if i > 1 and previous_actions[-1]["status"] == "executed":
                previous_path = f"./temp/gui_states/screenshot_{i - 1}.png"
                evaluate_gui(previous_path, path_to_screenshot)

            if settings["test_only_tool_integration"]:
                write_controller_request(gui_info, tool_integration_wizard.child_window(control_id=title_id).window_text().strip())
            else:
                write_controller_request(gui_info, "")

            if is_manual:
                output = get_manuel_action()
            else:
                output = controller_agent.make_request(PATH_TO_CONTROLLER_REQUEST, jsonFormat=True, pathsToImages=[path_to_screenshot])

            try:
                json_output = json.loads(output)
                if isinstance(json_output, dict):
                    action = json_output
                    action = execute_action(action, main_window, workflow_administrator)
                    previous_actions.append(action)
                    print(f"Action {i}:")
                    print(json.dumps(action, indent=2))
                else:
                    for action in json_output:
                        action = execute_action(action, main_window, workflow_administrator)
                        previous_actions.append(action)
                        print(f"Action {i}:")
                        print(json.dumps(action, indent=2))

                while len(previous_actions) > int(settings["max_saved_actions"]):
                    previous_actions.pop(0)
                
            except json.JSONDecodeError as e:
                print("Fehler bei der JSON-Dekodierung:", e)

        else:
            steps = input("How many steps should the LLM do: ")
            if steps == "m":
                is_manual = True
                next_steps = 1
            else:
                is_manual = False
                next_steps = int(steps)

main()