#!/usr/bin/env python

# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""

NOTE: This module requires the additional dependency `pyaudio`. To install
using pip:

    pip install pyaudio

Optional arguments -s, --source and -t, --target can be used to set source and target languages.

Example usages:

    python recognize.py
        (both source and target default to "en-US")

    python recognize.py -t es-ES
        (source defaults to English, target set to Spanish)
"""

# [START import_libraries]
from __future__ import division

import re
import sys

from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
import pyaudio, threading, argparse
from six.moves import queue
# [END import_libraries]

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms

SRC_LANG = 'en-US'
INTERP_LANG = 'en-US'

class recognizeThread(threading.Thread):
    def __init__(self, threadID, name, language, rate, chunk, mic):
        threading.Thread.__init__(self)
        self._threadID=threadID
        self._name=name
        self._language=language
        self._rate=rate
        self._chunk=chunk
        self._mic=mic

    def run(self):
        print("Listening to {}...".format(self._name))
        client = speech.SpeechClient()
        config = types.RecognitionConfig(
            encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self._rate,
            language_code=self._language)
        streaming_config = types.StreamingRecognitionConfig(
            config=config,
            interim_results=True)

        with MicrophoneStream(self._rate, self._chunk, self._mic) as stream:
            audio_generator = stream.generator()
            requests = (types.StreamingRecognizeRequest(audio_content=content) 
                for content in audio_generator)

            responses = client.streaming_recognize(streaming_config, requests)

            # Now, put the transcription responses to use.
            listen_print_loop(responses, self._name)


class MicrophoneStream(object):
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, rate, chunk, mic):
        self._rate = rate
        self._chunk = chunk
        self._mic = mic

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1, rate=self._rate,
            input=True, frames_per_buffer=self._chunk,
            input_device_index=self._mic,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)
# [END audio_stream]


def listen_print_loop(responses, name):
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.
    """
    num_chars_printed = 0
    for response in responses:
        if not response.results:
            continue

        # The `results` list is consecutive. For streaming, we only care about
        # the first result being considered, since once it's `is_final`, it
        # moves on to considering the next utterance.
        result = response.results[0]
        if not result.alternatives:
            continue

        # Display the transcription of the top alternative.
        transcript = result.alternatives[0].transcript

        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        #
        # If the previous result was longer than this one, we need to print
        # some extra spaces to overwrite the previous result
        overwrite_chars = ' ' * (num_chars_printed - len(transcript))

        if not result.is_final:
            sys.stdout.write(name + ': ' + transcript + overwrite_chars + '\r')
            sys.stdout.flush()

            num_chars_printed = len(transcript)

        else:
            print(name + ': ' + transcript + overwrite_chars)

            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            if re.search(r'\b(exit|quit)\b', transcript, re.I):
                print('Exiting..')
                break

            num_chars_printed = 0


def main():
    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    # language_code = 'en-US'  # a BCP-47 language tag

    parser = argparse.ArgumentParser()
    parser.add_argument('-s','--source', help='Source language (defaults to "en-US")', required=False)
    parser.add_argument('-t','--target', help='Target language (defaults to "en-US")', required=False)
    args = vars(parser.parse_args())

    src_lang = SRC_LANG
    interp_lang = INTERP_LANG

    if args['source']:
        src_lang = args['source']

    if args['target']:
        interp_lang = args['target']

    device_indices = []
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    print("Detecting input devices...")
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            device_indices.append(i)
            print("Input Device ID {} - {}".format(i, p.get_device_info_by_host_api_device_index(0, i).get('name'))) 

    print(device_indices)
    src_thread_name = "SOURCE"
    interp_thread_name = "INTERP"

    src_mic = device_indices[0]
    interp_mic = device_indices[1]

    # threadID, name, language, rate, chunk, mic
    src_thread = recognizeThread(1, src_thread_name, src_lang, RATE, CHUNK, src_mic)
    interp_thread = recognizeThread(2, interp_thread_name, interp_lang, RATE, CHUNK, interp_mic)

    src_thread.start()
    interp_thread.start()

    src_thread.join()
    interp_thread.join()


if __name__ == '__main__':
    main()