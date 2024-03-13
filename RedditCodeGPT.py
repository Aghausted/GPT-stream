from openai import OpenAI
import json
import os
from queue import Queue
import threading
from pydub import AudioSegment
from pydub.playback import play
import time


with open('api_key.json', 'r') as json_file:
    api_key_data = json.load(json_file)
    your_api_key = api_key_data['api_key']

client = OpenAI(api_key=your_api_key)


def play_audio(file_path):
    audio = AudioSegment.from_file(file_path)
    play(audio)

def generate_and_play_audio(message, response_number, playback_queue):

    response = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=message,
    )

    output_folder = "OutputAudio"
    os.makedirs(output_folder, exist_ok=True)

    audio_filename = f"Response{response_number}.mp3"
    output_path = os.path.join(output_folder, audio_filename)

    response.stream_to_file(output_path)

    # Add the audio file path to the queue
    playback_queue.put(output_path)

def audio_manager(playback_queue):
    # Initialize a variable to keep track of the current playing audio file
    current_audio_file = None

    while True:
        file_path = playback_queue.get()  # Wait for an item in the queue
        playback_queue.task_done()  # Signal that the task is complete

        # Wait for the previous audio playback to finish before starting a new one
        if current_audio_file is not None:
            current_audio_file.join()

        # Play the audio in a separate thread
        current_audio_file = threading.Thread(target=play_audio, args=(file_path,), daemon=True)
        current_audio_file.start()

        time.sleep(0.2)

def GenerateResponse(conversation_history):
    print("Creating Response\n")

    response = client.chat.completions.create(
        model="gpt-3.5-turbo-1106",
        messages=[
            {"role": "user", "content": conversation_history}
        ],
        temperature=0.8,
        stream=True,
    )
    
    i = 0
    response_number = 1
    processMessage = ""

    collected_chunks = []
    collected_messages = []

    # Use a queue to decouple chunk generation and audio playback
    playback_queue = Queue()

    # Start the audio manager thread
    threading.Thread(target=audio_manager, args=(playback_queue,), daemon=True).start()
    
    for chunk in response:
        collected_chunks.append(chunk) 
        chunk_message = chunk.choices[0].delta.content 
        if chunk_message is not None:
            collected_messages.append(chunk_message)

            if '.' in chunk_message:
                processMessage = processMessage + chunk_message
                print(processMessage)
                generate_and_play_audio(processMessage, response_number, playback_queue)
                response_number += 1

                processMessage = ""
            else:
                processMessage = processMessage + chunk_message

    # Outside the loop, print any remaining messages in processMessage
    if processMessage:
        print(processMessage)
        generate_and_play_audio(processMessage, response_number, playback_queue)

    # Wait for all audio playback to complete before continuing
    playback_queue.join()

    collected_messages = [m for m in collected_messages if m is not None]
    assistant_response = full_reply_content = ''.join([m for m in collected_messages])

    return assistant_response


userInput = input("Prompt: ")

GenerateResponse(userInput)