import argparse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List

import openai
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerMonitor,
    CrawlerRunConfig,
    DisplayMode,
    LLMConfig,
    MemoryAdaptiveDispatcher,
)
from crawl4ai.chunking_strategy import *
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from dotenv import load_dotenv
from pydantic import BaseModel, Field

def create_directory_if_not_exists(path):
    Path(path).mkdir(parents=True, exist_ok=True)

def map_extracted_data_to_steps(module):
    extracted_items = module.get("extracted_data", [])
    matched_indices = set()

    for step in module.get("execution_steps", []):
        matched_data = []
        for idx, data in enumerate(extracted_items):
            if data.get("step_name") == step.get("step"):
                matched_data.append({
                    "type": data["type"],
                    "request_description": data["request_description"],
                    "identifier_type": data["identifier_type"],
                    "identifier_tracking": data["identifier_tracking"]
                })
                matched_indices.add(idx)
        if matched_data:
            step["extracted_data"] = matched_data

    if len(matched_indices) == len(extracted_items):
        module.pop("extracted_data", None)

    return module

load_dotenv()

test_case_file = os.getenv("TEST_CASE")

exampleFolder = Path('TestCaseExamples')

newFolder = Path('TestCases')


def load_config():
    config_path = Path(__file__).resolve().parent / "config.properties"
    config = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()
    return config


def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate E2E tests with configurable LLM providers")
    parser.add_argument(
        "--provider",
        choices=["openai", "ollama"],
        help="LLM provider to use. Overrides environment variables and config.properties.",
    )
    parser.add_argument(
        "--api-key",
        help="API key for the selected provider. Overrides environment variables and config.properties.",
    )
    parser.add_argument(
        "--api-base",
        help="Base URL for the selected provider. Overrides environment variables and config.properties.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Name of the model to query (default Ollama: qwen2.5vl:32b; default OpenAI: gpt-4o-mini).",
    )
    return parser.parse_args()


def build_llm_settings(args=None):
    args = args or argparse.Namespace()
    config = load_config()
    provider = (getattr(args, "provider", None) or os.getenv("LLM_PROVIDER") or config.get("llmProvider") or "ollama").lower()

    if provider == "ollama":
        api_key = getattr(args, "api_key", None) or os.getenv("OLLAMA_API_KEY") or config.get("ollamaApiKey")
        if not api_key:
            raise RuntimeError(
                "Missing Ollama API key. Set the OLLAMA_API_KEY environment variable or "
                "provide ollamaApiKey in config.properties."
            )

        api_base = getattr(args, "api_base", None) or os.getenv("OLLAMA_API_BASE") or config.get("ollamaApiBase") or "https://suz-ai01.eisgroup.com/ollama/api/generate"
        model = getattr(args, "model", None) or os.getenv("OLLAMA_MODEL") or config.get("ollamaModel") or "qwen2.5vl:32b"
        client = openai.OpenAI(api_key=api_key, base_url=api_base)
        llm_provider = f"ollama/{model}"
    else:
        api_key = getattr(args, "api_key", None) or os.getenv("OPENAI_API_KEY") or config.get("openaiApiKey")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER is 'openai'.")
        api_base = getattr(args, "api_base", None) or os.getenv("OPENAI_BASE_URL") or config.get("openaiBaseUrl") or None
        model = getattr(args, "model", None) or os.getenv("OPENAI_MODEL") or config.get("openaiModel") or "gpt-4o-mini"
        client = openai.OpenAI(api_key=api_key, base_url=api_base)
        llm_provider = f"openai/{model}"

    return {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "client": client,
        "llm_provider": llm_provider,
    }


def write_internal_execution_plan(feature_path: str, refined_data_path: str, output_dir: str, log_path: Path):
    with open(refined_data_path, "r", encoding="utf-8") as f:
        test_case = json.load(f)

    lines = [
        f"Feature file: {feature_path}",
        f"Refined data: {refined_data_path}",
        "Execution outline:",
    ]

    for module_idx, module in enumerate(test_case.get("modules", []), start=1):
        lines.append(f"Module {module_idx}: {module.get('url', '')}")
        lines.append(f"Purpose: {module.get('purpose', '')}")
        for step_idx, step in enumerate(module.get("execution_steps", []), start=1):
            lines.append(f"  {step_idx}. {step.get('step', '')}")
            for element in step.get("extracted_data", []):
                lines.append(
                    "    - Element: "
                    f"{element.get('type', '')} | {element.get('request_description', '')} | "
                    f"{element.get('identifier_type', '')}: {element.get('identifier_tracking', '')}"
                )

    log_path = Path(log_path)
    create_directory_if_not_exists(log_path.parent)
    log_path.write_text("\n".join(lines), encoding="utf-8")

    summary_path = Path(output_dir) / "execution_summary.json"
    summary_payload = {
        "feature_path": feature_path,
        "refined_data_path": refined_data_path,
        "modules": len(test_case.get("modules", [])),
        "steps": sum(len(m.get("execution_steps", [])) for m in test_case.get("modules", [])),
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2, ensure_ascii=False), encoding="utf-8")

class ExtractedElement(BaseModel):
    type: str = Field(
        ..., 
        description="Specifies the HTML element type. Example: 'input', 'button', 'select', etc."
    )
    request_description: str = Field(
        ..., 
        description="A detailed explanation of what the element asks from the user. Example: 'Enter your First Name'."
    )
    identifier_type: str = Field(
        ..., 
        description="The method used to locate the HTML element. Preferably 'XPath', but can be ID, name, or other unique identifiers."
    )
    identifier_tracking: str = Field(
        ..., 
        description="The exact path or unique identifier to locate the HTML element. For XPath, ensure it's the full and correct path. Example: '//*[@id=\"root\"]/div/div[2]/div/form/input[2]'."
    )
    step_name: str = Field(
        ..., 
        description="Indicates which test case step utilizes this element during execution"
    )

class ExecutionStepModel(BaseModel):
    step: str = Field(
        ..., 
        description="A description of the user action or verification performed on this page."
    )
    extracted_data: List[ExtractedElement] = Field(
        default_factory=list,
        description="List of HTML elements involved in this step. Can be empty if not applicable."
    )

class ModuleModel(BaseModel):
    url: str = Field(
        ..., 
        description="The specific URL where this portion of the test case is executed. Must include protocol (e.g., 'https://')."
    )
    purpose: str = Field(
        ..., 
        description="A brief and clear description of the main objective for this URL in the test case."
    )
    execution_steps: List[ExecutionStepModel] = Field(
        ..., 
        description="A list of step objects that detail user actions and extracted elements on this page."
    )

class TestCaseModel(BaseModel):
    testCase: str = Field(
        ..., 
        description="Test Case Name"
    )
    modules: List[ModuleModel] = Field(
        ..., 
        description="A list of modules representing separate URLs involved in the test case."
    )

async def main():

    create_directory_if_not_exists(newFolder)

    args = parse_arguments()
    llm_settings = build_llm_settings(args)
    client = llm_settings["client"]
    chat_model = llm_settings["model"]

    async with AsyncWebCrawler() as crawler:

        for arquivo in exampleFolder.iterdir():
            if arquivo.is_file():
                with open(arquivo, 'r', encoding='utf-8') as file:
                    test_case = file.read()
                    newTestCaseFolder = newFolder / arquivo.stem
                    create_directory_if_not_exists(newTestCaseFolder)

                    completion_messages = [
                            {
                            "role": "system",
                            "content": (
                                f"""You are a highly skilled software test automation engineer. Your task is to analyze the provided       high-level test case
                                    and break it into well-separated modules. Each module must represent a unique web page, identified by its full URL.

                                    Test Case: {test_case}

                                    OBJECTIVE:
                                    - Break the test case into a list of modules.
                                    - Each module should group actions performed on a single page (same URL).
                                    - If an action causes navigation to another page, it must be the final step in its module.
                                    - The next module must start with the new URL.

                                    IMPORTANT RULES:
                                    - Do NOT omit any URLs. Every page transition must include its full URL.
                                    - Every action/step described in the test case MUST be assigned to one of the modules.
                                    - No steps should be left out or described outside of the modules.

                                    STRUCTURE PER MODULE:
                                    - url: full URL of the page, including 'https://'
                                    - purpose: short description of the page’s role in the test
                                    - execution_steps: list of steps (actions/verifications) as objects with:
                                        - step: string describing the user action
                                        - extracted_data: ALWAYS an empty list at this stage

                                    **IMPORTANT:**
                                    At this stage, `extracted_data` must be an empty list for all steps. It will be completed in a separate process.

                                    MODEL SCHEMA:
                                    TestCaseModel:
                                    testCase: str
                                    modules: List[ModuleModel]

                                    ModuleModel:
                                    url: str
                                    purpose: str
                                    execution_steps: List[ExecutionStepModel]

                                    ExecutionStepModel:
                                    step: str
                                    extracted_data: List (leave it empty for now)

                                    EXAMPLE:
                                    - If a step says 'Click Login', place that step in one module.
                                    - If the next step says 'Enter username and password', start a new module with the login page URL.

                                    INSTRUCTIONS:
                                    - Separate steps by page (URL)
                                    - A navigation action = boundary between modules
                                    - Use one module per page (i.e., per URL)
                                    - Do NOT omit or skip any URLs or steps
                                    - Return a clean JSON matching the schema above"""
                                )
                            }
                    ]

                    if llm_settings["provider"] == "openai":
                        completion = client.beta.chat.completions.parse(
                            model=chat_model,
                            messages=completion_messages,
                            response_format=TestCaseModel
                        )
                        refinedTestCase = completion.choices[0].message.parsed.model_dump_json(indent=2)
                    else:
                        completion = client.chat.completions.create(
                            model=chat_model,
                            messages=completion_messages,
                            response_format={"type": "json_object"}
                        )
                        refinedTestCase = TestCaseModel.model_validate_json(
                            completion.choices[0].message.content
                        ).model_dump_json(indent=2)

                    newRefinedTestCase = newTestCaseFolder / ("Refined"+arquivo.stem+".json")

                    with open(newRefinedTestCase, "w", encoding="utf-8") as f:
                        f.write(refinedTestCase)

                    test_case_example = json.loads(refinedTestCase)
                            
                    for i in range(1):

                        newTestCaseFolderAttempt = newTestCaseFolder / f"{i + 1}.{arquivo.stem}"
                        create_directory_if_not_exists(newTestCaseFolderAttempt)

                        newTestCaseFileAttemptExtractedData = newTestCaseFolderAttempt / "ExtractedData.json"

                        newTestCaseFileAttemptRefinedExtractedData = newTestCaseFolderAttempt / "RefinedExtractedData.json"
                        
                        test_case_json1 = json.loads(refinedTestCase)

                        test_case_json2 = json.loads(refinedTestCase)            

                        for n in range(len(test_case_example["modules"])):
                            # session_id = "Session_Id"
                            llm_strategy_1 = LLMExtractionStrategy(
                                llm_config=LLMConfig(
                                    provider=llm_settings["llm_provider"],
                                    api_token=llm_settings["api_key"]
                                ),
                                schema=ExtractedElement.model_json_schema(),
                                extraction_type="schema",
                                input_format="html",
                                extra_args={"temperature": 0.0},
                                instruction= f"""
                                                You are a QA test automation manager. Your task is to extract only the HTML elements required to execute the following module of a test case:

                                                {test_case_example["modules"][n]}

                                                Each `execution_step` in the module contains a `step` description. You must analyze the HTML of the corresponding page and extract the elements required to execute **that step**.

                                                ### Output Structure:
                                                For each Test Case, return a list of relevant elements to implement the structure example below:

                                                ```json
                                                    [
                                                        {{
                                                            "type": "input",
                                                            "request_description": "Field to enter the user's name",
                                                            "identifier_type": "XPath",
                                                            "identifier_tracking": "//*[@id='form']input[1]"
                                                            "step_name" : "Enter incorrect email address and password"
                                                        }},
                                                        {{
                                                            "type": "input",
                                                            "request_description": "Field to enter the user's email",
                                                            "identifier_type": "XPath",
                                                            "identifier_tracking": "//*[@id='form']input[2]"
                                                            "step_name" : "Enter incorrect email address and password"
                                                        }}
                                                    ]
                                                ...
                                                
                                                ### Important Notes:
                                                - Only include elements required to execute this test case successfully.
                                                - Return a clean, structured JSON array with the relevant elements only.

                                                Be precise, focused, and avoid redundancy."""
                            )
                            
                            dispatcher = MemoryAdaptiveDispatcher(
                                # max_session_permit=1, 
                            )

                            browser_cfg = BrowserConfig(headless=True)

                            crawl_config_1 = CrawlerRunConfig(
                                verbose=True,
                                word_count_threshold=1,
                                # session_id=session_id,
                                extraction_strategy=llm_strategy_1,
                                cache_mode=CacheMode.BYPASS
                            )

                            print("Pag ",n+1, ". Identifying relevant elements...")
                            result_1 = await crawler.arun_many(
                                urls=[test_case_json1["modules"][n]["url"]],
                                config=crawl_config_1,
                                dispatcher=dispatcher
                            )

                            for result in result_1:
                                if result.success:
                                    print("Usages llm1:............")
                                    print(llm_strategy_1.usages)
                                    test_case_json1["modules"][n]["extracted_data"] = json.loads(result.extracted_content)
                                    usage = llm_strategy_1.total_usage
                                    token_data = {
                                        "completion_tokens": usage.completion_tokens,
                                        "prompt_tokens": usage.prompt_tokens,
                                        "total_tokens": usage.total_tokens,
                                        "completion_tokens_details": usage.completion_tokens_details,
                                        "prompt_tokens_details": usage.prompt_tokens_details
                                    }
                                    test_case_json1["modules"][n]["token"] = token_data
                                    start_time = datetime.fromtimestamp(result.dispatch_result.start_time)
                                    end_time = datetime.fromtimestamp(result.dispatch_result.end_time)
                                    dispatcher_data = {
                                        "memory_usage_MB": result.dispatch_result.memory_usage,
                                        "peak_memory_MB": result.dispatch_result.peak_memory,
                                        "start_time": start_time.isoformat(),
                                        "end_time": end_time.isoformat(),
                                        "duration_seconds": (end_time - start_time).total_seconds()
                                    }
                                    test_case_json1["modules"][n]["dispatcher"] = dispatcher_data

                            test_case_json1["modules"][n] = map_extracted_data_to_steps(test_case_json1["modules"][n])

                            llm_strategy_2 = LLMExtractionStrategy(
                                llm_config=LLMConfig(
                                    provider=llm_settings["llm_provider"],
                                    api_token=llm_settings["api_key"]
                                ),
                                schema=ExtractedElement.model_json_schema(),
                                extraction_type="schema",
                                input_format="html",
                                instruction = f"""
                                                You are a highly skilled software tester specialized in end-to-end (E2E) automation testing.

                                                Your task is to **analyze and refine** a list of **already extracted JSON elements** from a test module.

                                                Important:
                                                - DO NOT add new elements unless absolutely necessary.
                                                - DO NOT remove existing ones unless absolutely necessary.
                                                - Your role is to ensure the **accuracy and reliability** of the **elements that have already been found**.

                                                Your focus:
                                                - Validate that each element’s `identifier_tracking` (XPath) correctly and uniquely identifies.
                                                - Make improvements **only when necessary** to correct or optimize the XPath (e.g., make it more robust or less fragile).
                                                - Double-check that the `type`, `request_description`, and `step_name` are correctly describing the element and consistent with its use.
                                                - Follow best practices for XPath and HTML element identification in automated tests.

                                                Here is the module with the extracted data to review and refine:
                                                {test_case_json1["modules"][n]}

                                                Return ONLY the improved list of JSON objects, preserving the structure. Each item must include:
                                                - "type"
                                                - "request_description"
                                                - "identifier_type"
                                                - "identifier_tracking"
                                                - "step_name"

                                                Output format:
                                                ```json
                                                    [
                                                        {{
                                                            "type": "input",
                                                            "request_description": "Field to enter the user's name",
                                                            "identifier_type": "XPath",
                                                            "identifier_tracking": "//*[@id='form'][1]"
                                                            "step_name" : "Enter incorrect email address and password"
                                                        }},
                                                        {{
                                                            "type": "input",
                                                            "request_description": "Field to enter the user's email",
                                                            "identifier_type": "XPath",
                                                            "identifier_tracking": "//*[@id='form'][2]"
                                                            "step_name" : "Enter incorrect email address and password"
                                                        }}
                                                    ]
                                                ...
                                                """
                            )

                            crawl_config_2 = CrawlerRunConfig(
                                verbose=True,
                                word_count_threshold=1,
                                # session_id=session_id,
                                extraction_strategy=llm_strategy_2,
                                cache_mode=CacheMode.BYPASS
                            )

                            print("Pag ",n+1, ". Refining extracted elements...")
                            result_2 = await crawler.arun_many(
                                urls=[test_case_json1["modules"][n]["url"]],
                                config=crawl_config_2,
                                dispatcher=dispatcher
                            )
                            
                            for result in result_2:
                                if result.success:
                                    print("Usages llm2:............")
                                    print(llm_strategy_2.usages)
                                    test_case_json2["modules"][n]["extracted_data"] = json.loads(result.extracted_content)
                                    usage = llm_strategy_2.total_usage
                                    token_data = {
                                        "completion_tokens": usage.completion_tokens,
                                        "prompt_tokens": usage.prompt_tokens,
                                        "total_tokens": usage.total_tokens,
                                        "completion_tokens_details": usage.completion_tokens_details,
                                        "prompt_tokens_details": usage.prompt_tokens_details
                                    }
                                    test_case_json2["modules"][n]["token"] = token_data
                                    start_time = datetime.fromtimestamp(result.dispatch_result.start_time)
                                    end_time = datetime.fromtimestamp(result.dispatch_result.end_time)
                                    dispatcher_data = {
                                        "memory_usage_MB": result.dispatch_result.memory_usage,
                                        "peak_memory_MB": result.dispatch_result.peak_memory,
                                        "start_time": start_time.isoformat(),
                                        "end_time": end_time.isoformat(),
                                        "duration_seconds": (end_time - start_time).total_seconds()
                                    }
                                    test_case_json2["modules"][n]["dispatcher"] = dispatcher_data


                            test_case_json2["modules"][n] = map_extracted_data_to_steps(test_case_json2["modules"][n])

                        with open(newTestCaseFileAttemptExtractedData, "w", encoding="utf-8") as f:
                            json.dump(test_case_json1, f, indent=4, ensure_ascii=False)

                        with open(newTestCaseFileAttemptRefinedExtractedData, "w", encoding="utf-8") as f:
                            json.dump(test_case_json2, f, indent=4, ensure_ascii=False)
                        
                        log_path = newTestCaseFolderAttempt / "execution_plan.log"
                        print("Writing internal execution outline...")
                        write_internal_execution_plan(
                            feature_path=str(arquivo.resolve()),
                            refined_data_path=str(newTestCaseFileAttemptRefinedExtractedData.resolve()),
                            output_dir=str(newTestCaseFolderAttempt.resolve()),
                            log_path=log_path,
                        )
                        print(f"Execution outline saved to {log_path}.")
    

if __name__ == "__main__":
    asyncio.run(main())
    















