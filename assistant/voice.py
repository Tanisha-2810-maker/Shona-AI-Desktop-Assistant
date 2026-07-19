import speech_recognition as sr
import pyttsx3


engine = pyttsx3.init()
engine.setProperty("rate", 170)


def speak(text):
    print("Assistant:", text)
    engine.say(text)
    engine.runAndWait()


def listen(on_ready=None):
    recognizer = sr.Recognizer()

    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 1.2
    recognizer.phrase_threshold = 0.3

    try:
        with sr.Microphone() as source:
            print("Adjusting for background noise...")

            recognizer.adjust_for_ambient_noise(
                source,
                duration=1.2,
            )

            # Tell the UI that calibration is complete.
            if on_ready:
                on_ready()

            print("Listening... Speak now.")

            try:
                audio = recognizer.listen(
                    source,
                    timeout=5,
                    phrase_time_limit=10,
                )

            except sr.WaitTimeoutError:
                print("No speech detected.")
                return ""

        command = recognizer.recognize_google(
            audio,
            language="en-IN",
        )

        command = command.lower().strip()

        print("You:", command)

        return command

    except sr.UnknownValueError:
        print("Could not understand the audio.")
        return ""

    except sr.RequestError as error:
        print(f"Speech recognition service error: {error}")
        return ""

    except Exception as error:
        print(f"Microphone error: {error}")
        return ""