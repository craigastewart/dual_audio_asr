# Dual Audio ASR using Google Cloud Speech API
An adaptation of Google's default ASR streaming module to receive and transcribe two simultaneous streams of audio input

# Requirements

This module requires the dependency 'pyaudio'. To install using pip:
  
  pip install pyaudio
  
Using this module also requires an existing Google Cloud Project and with the environment variable GOOGLE_APPLICATION_CREDENTIALS being set as described in the section 'Before you begin', here:

  https://cloud.google.com/speech-to-text/docs/quickstart-client-libraries
  
# Microphone Setup (Mac)

The module receives and transcribes audio input from two microphones connected to the same system.

On MacOSX this can be acheived using the internal built-in microphone (either using the built in mic or by connecting an external mic through the headphone jack) and an external USB microphone.

Ensure that the microphone is detected and enabled in Applications>Utilities>Audio MIDI Setup

NB: There are various free apps that allow an iPhone to be used as an external USB microphone for example:

  https://itunes.apple.com/us/app/microphone-free-vonbruno/id1070812067?mt=8
  
# Usage

Languages detected are defaulted to 'en-US' (English) although optionally these can be changed using the commandline arguments:

  -s, --source (Source Language)
  -t, --target (Target language)
  
NB: See https://cloud.google.com/speech-to-text/docs/languages for a list of supported language codes
  
Example usages:

  python recognize.py
    (Both source and target set to 'en-US')
    
  python recognize.py -t es-ES
    (English source and Spanish target)
    
  python recognize.py -s it-IT -t es-ES
    (Italian source and Spanish target)
    
The module can currently be exited by saying 'exit' or 'quit', although it should be noted that currently the command must be heard on both streams.
