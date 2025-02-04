<!--
# SPDX-FileCopyrightText: 2025 German Aerospace Center (DLR)
# SPDX-FileContributor: Tim Rosenbach <tim.rosenbach@dlr.de>
#
# SPDX-License-Identifier: CC-BY-NC-ND-4.0
-->

# GERALLT - GUI Executor for RCEs Automated LLM Testing

## Requirements

```bash
pip install -r requirements.txt
```

## Setup

Download RCE from their [website](https://rcenvironment.de/) and set it up.

Edit [config.cfg](config.cfg) by adding following information:
| Parameter | Description |
|---|---|
| ``openai_api_key`` | Path to RCE |
| ``ollama_server_ip`` | OpenAI API Key (if you are using ChatGPT models) |
| ``rce_path`` | IP to the Ollama server (if you are using local LLMs like Llama) |

## Settings

Following Paramters can be changed in the [config.cfg](config.cfg) file:

| Parameter | Description | Example |
|---|---|---|
| ``controller_model`` | the LLM that performs actions on the GUI of RCE | gpt-4o-2024-08-06 |
| ``evaluator_model`` | the LLM that evaluates the GUI for Problems | gpt-4o-2024-08-06 |
| ``icon_description_model`` | LLM that gives a textual description of the icons on the GUI | gpt-4o-2024-08-06 |
| ``max_saved_actions`` | maximum number of actions that are saved | 20 |
| ``max_actions`` | maximum number of actions that are being performed | 200 |
| ``step_by_step`` | if true, requires user input for performing any number of actions | true |
| ``test_only_tool_integration`` | if true, only tests the Tool Integration Wizard of RCE (For testing all of RCE not all capabilities for the controler Agent are implemented) | true |


## Results

After running [automated_gui_testing.py](automated_gui_testing.py) the results can be found in the ``./temp/`` folder.

## Licenses

Please see the file [LICENSE.md](LICENSE.md) for further information about how the content is licensed.