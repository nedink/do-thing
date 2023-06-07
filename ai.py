import os
import platform
import time
import openai
import argparse
import subprocess
from dotenv import load_dotenv

load_dotenv()

INPUT_LANGUAGE = os.getenv("INPUT_LANGUAGE") or "English"


def get_terminal_name():
    os_name = platform.system()
    if os_name == "Darwin":
        return "macOS terminal"
    elif os_name == "Windows":
        return "Windows Command Prompt"
    elif os_name == "Linux":
        return "Linux terminal"
    else:
        return "terminal"


TERMINAL_NAME = os.getenv("TERMINAL_NAME") or get_terminal_name()

SYSTEM_MESSAGE = f'You are an AI {INPUT_LANGUAGE}-to-command tool with the ability to take any imperative written in {INPUT_LANGUAGE} and generate a command to execute in the {TERMINAL_NAME} that would carry out this action automatically, be it opening programs, searching the web, parsing files, etc. Users will provide instructions or directives in their native language, {INPUT_LANGUAGE}, and you will return a command that can be subsequently run in {TERMINAL_NAME} (using the Python subprocess module, for instance). You may use popular, modern command line utilities/tools that may not come pre-installed on the OS as long as they are compatible with the system and could be installed by the user. If critiqued or given feedback, such as an error message or "i got [some error]" or "its saying [something]", generate a new command to resolve the issue for the user. As a last resort, if you really cannot answer or need to answer in natural language, return a command that prints your message to the user. Make sure that your response is ALWAYS in the form of a runnable command. Please note that your output will be passed directly into subprocess.run() and must be formatted in plain text to facilitate parsing.'

openai.api_key = os.getenv("OPENAI_API_KEY")

import concurrent.futures
import threading
import time

import random

def print_robot_animation(cancel_event):
    frames = ["🤖", "🤖💭", "🤖💭🐒", "🤖💭🐒🥁"]
    frame_index = 0

    while True:
        if cancel_event.is_set():
            return  # Cancel the animation if the event is set

        frame = frames[frame_index]
        print(frame)
        time.sleep(1)

        # Clear the previously printed line from the console
        print("\033[F\033[K", end="")

        frame_index = (frame_index + 1) % len(frames)


def get_completion(model, messages) -> str:
    cancel_event = threading.Event()

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Run the animation function in a separate thread
        animation_thread = executor.submit(print_robot_animation, cancel_event)

        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                n=1,
                temperature=0,
                stop=["\n"],
                max_tokens=1000,
            )
            result = response.choices[0].message.content.strip()
            return result
        finally:
            cancel_event.set()  # Set the cancel event to stop the animation
            animation_thread.result()  # Wait for the animation thread to complete


def save_history(user_message, ai_message, file_path) -> None:
    with open(file_path, "a") as file:
        file.write(f"\nuser: {user_message}\nassistant: {ai_message}")


def load_history(file_path) -> list:
    history = []
    if os.path.exists(file_path):
        with open(file_path, "r") as file:
            lines = file.readlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                role, content = line.split(": ", 1)
                history.append({"role": role.lower(), "content": content})
    return history


def prompt_and_execute(output, model, history, history_file, args):
    print(f"\nAI-generated command: {output}")
    execute_output = input("🧑‍💻 Run this command? (Y/n): ")
    if execute_output.lower() == "" or execute_output.lower() == "y":
        run_output(output, model, history, history_file, args)


def run_output(output, model, history, history_file, args) -> None:
    try:
        result = subprocess.run(
            output,
            shell=True,
            check=True,
            text=True,
            stderr=subprocess.PIPE,
        )
        if result.stderr:
            print("\n❌ " + result.stderr)
            time.sleep(1)
            error_message = f"result.stderr: {result.stderr}"
            history.append({"role": "user", "content": f"I got this: {error_message}"})

            retry = input("🔄 Find a fix? (Y/n/?): ")
            if retry.lower() == "" or retry.lower() == "y":
                ai_message = get_completion(model, history)
                history.append({"role": "assistant", "content": ai_message})
                if not args.disable_history:
                    save_history(error_message, ai_message, history_file)
                if args.run:
                    run_output(ai_message, model, history, history_file, args)
                else:
                    prompt_and_execute(ai_message, model, history, history_file, args)
            elif retry.lower() == "n":
                return
            else:
                history.append({"role": "user", "content": retry})
                ai_message = get_completion(model, history)
                history.append({"role": "assistant", "content": ai_message})
                if not args.disable_history:
                    save_history(error_message, ai_message, history_file)
                if args.run:
                    run_output(ai_message, model, history, history_file, args)
                else:
                    prompt_and_execute(ai_message, model, history, history_file, args)
        print("\n👍")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ subprocess.CalledProcessError: {e}")
        time.sleep(1)
        error_message = f"Error: {e}"
        history.append({"role": "user", "content": f"I got this: {error_message}"})

        retry = input("🔄 Find a fix? (Y/n/?): ")
        if retry.lower() == "" or retry.lower() == "y":
            ai_message = get_completion(model, history)
            history.append({"role": "assistant", "content": ai_message})
            if not args.disable_history:
                save_history(error_message, ai_message, history_file)
            if args.run:
                run_output(ai_message, model, history, history_file, args)
            else:
                prompt_and_execute(ai_message, model, history, history_file, args)
        elif retry.lower() == "n":
            return
        else:
            history.append({"role": "user", "content": retry})
            ai_message = get_completion(model, history)
            history.append({"role": "assistant", "content": ai_message})
            if not args.disable_history:
                save_history(error_message, ai_message, history_file)
            if args.run:
                run_output(ai_message, model, history, history_file, args)
            else:
                prompt_and_execute(ai_message, model, history, history_file, args)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("messages", nargs="*", help="user input message(s)")
    parser.add_argument(
        "-dh",
        "--disable-history",
        action="store_true",
        help="disable reading/writing to the history file",
    )
    parser.add_argument(
        "-r",
        "--run",
        action="store_false",
        help="whether to run the output directly (default true; include this flag to prompt before running)",
    )
    args = parser.parse_args()

    user_message = " ".join(args.messages)

    if not args.disable_history:
        history_file = "./mem.txt"
        history = load_history(history_file)
    else:
        history = []

    # Add system message to history
    history.insert(
        0,
        {
            "role": "system",
            "content": SYSTEM_MESSAGE.format(
                terminal_name=TERMINAL_NAME, input_lang=INPUT_LANGUAGE
            ),
        },
    )

    history.append({"role": "user", "content": user_message})

    model = "gpt-4"
    ai_message = get_completion(model, history)

    history.append({"role": "assistant", "content": ai_message})

    if not args.disable_history:
        save_history(user_message, ai_message, history_file)

    # Print the AI's message
    print("\n⚡️ " + ai_message)

    if args.run:
        run_output(ai_message, model, history, history_file, args)
    else:
        prompt_and_execute(ai_message, model, history, history_file, args)


if __name__ == "__main__":
    main()
