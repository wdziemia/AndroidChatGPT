import argparse
import pathlib
import json
import xml.etree.ElementTree as ET
import os
import copy
import requests
import re
import pydoc

from xml.dom import minidom
from itertools import islice

# if you don't want to import the dependencies and don't plan to use google translate
# comment out the following line
from google.cloud import translate


# Parsing Args
XML_ATTR_TRANSLATABLE = "translatable"
XML_ATTR_NAME = "name"

# Associative Array which is the source of our languages
qualifier_language = {
#     "pl": "Polish",
#     "en-rGB": "British English",
    "ar": "Arabic",
    "bg": "Bulgarian",
    "bn": "Bengali",
    "ca": "Catalan",
    "cs": "Czech",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "es": "Spanish",
    "fi": "Finnish",
    "fa": "Persian",
    "fr": "French",
    "hi": "Hindi",
    "hr": "Croatian",
    "id": "Indonesian",
    "it": "Italian",
    "iw": "Hebrew",
    "ja": "Japanese",
    "ko": "Korean",
    "nb": "Norwegian Bokmål",
    "nl": "Dutch",
    "pl": "Polish",
    "pt-rBR" : "Brazilian Portuguese",
    "pt-rPT": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sv": "Swedish",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "zh": "Chinese"
}

class Translator:
    """
        Class Translator 
        This is the base class for OpenAI and Google Translator with common methods. 
    """

    def fetch(self, strings_needed, language, language_code):
        """
            fetch is implemented by OpenAI and Google Translator class.

            :param strings_needed: The strings to be fetched
            :param language: The language name for the langauge to fetch
            :param language_code: The language code for the langauge to fetch
        """
        pass

    def try_chunk(self, strings_needed, language, language_code):
        """
            try_chunk tries to fetch a chunk of strings for one language.
            It'll divide the chunk in two if its chunk fails.

            btw, for OpenAI we often have to divide the chunk.
            with Google Translation, it never happens.

            :param strings_needed: The strings to be fetched
            :param language: The language name for the langauge to fetch
            :param language_code: The language code for the langauge to fetch
            :return: the list of strings fetched

        """
        response_strings = translator.fetch(strings_needed, language, language_code)

        filtered_response_strings = list(filter(lambda string: len(string) > 0, response_strings))
        if len(filtered_response_strings) != len(strings_needed):
            if len(strings_needed) > 1:
                in1 = dict(list(strings_needed.items())[len(strings_needed)//2:])
                in2 = dict(list(strings_needed.items())[:len(strings_needed)//2])
                out1 = self.try_chunk(in1, language, language_code)
                out2 = self.try_chunk(in2, language, language_code)
                return out1 + out2
            else:
                return filtered_response_strings
        else:
            self.insert_strings(filtered_response_strings, strings_needed)
            return filtered_response_strings


    def insert_strings(self, strings_to_add, strings_needed):
        """
            insert_strings inserts a set of strings 

            :param strings_to_add: The strings we fetched, that'll be inserted.
            :param strings_needed: The strings that were needed
            :return: returns nothing
        """

        index = 0
        qualified_strings_to_add = list()

        for qualified_string_needed_key in strings_needed:
            qualified_string_needed = strings_needed[qualified_string_needed_key]
            qualified_string_copy = copy.deepcopy(qualified_string_needed)
            qualified_string_copy.text = strings_to_add[index].replace('\'', r'\'').replace("...", "&#8230:")

            if not config['quiet']:
                print(
                    f"...Adding {qualified_strings_needed[qualified_string_needed_key].text} -> {qualified_string_copy.text}")
            qualified_strings_to_add.append(qualified_string_copy)
            index += 1

        # Now lets move onto modifying the XML file.
        if len(strings_needed) > 0:
            qualified_strings_tree = ET.parse(qualified_strings_file_path)
            qualified_strings_root = qualified_strings_tree.getroot()

            # Next lets add the elements we do want
            for qualified_string in qualified_strings_to_add:
                qualified_strings_root.append(qualified_string)

            # Lastly, we write the changes to the file
            if not config['quiet']:
                print(f"...Writing changes to {str(qualified_strings_file_path)}")
            qualified_strings_tree.write(
                qualified_strings_file_path,
                encoding="utf-8",
                xml_declaration="utf-8",
                method="xml"
            )

class GoogleTranslate (Translator):
    """
        Class GoogleTranslate implement Translator::fetch to fetch translations from Google Translation
    """

    def __init__(self, project_id) -> None:
        """
        Construct a new 'GoogleTranslate' object.

        :project_id: The project id of Google Cloud project
        :return: returns nothing
        """
        super().__init__()
        self.project_id = project_id
        self.client = translate.TranslationServiceClient()
        location = "global"
        self.parent = f"projects/{PROJECT_ID}/locations/{location}"


    def fetch(self, strings_needed, language, language_code):

        request_strings = list(map(lambda x: x.text, strings_needed.values()))
        request={
                    "parent": self.parent,
                    "contents": request_strings,
                    "mime_type": "text/plain",
                    "source_language_code": "en-US",
                    "target_language_code": language_code.replace("-r", "-"),  # pt-rBR -> pt-BR
                }
    #    print(f"request={request}")
        response = self.client.translate_text(
            request=request
        )

    #     print(f"response={response}")
        return map(lambda x: x.translated_text, response.translations)

class OpenAITranslator (Translator):
    """
        Class OpenAITranslator implement Translator::fetch to fetch translations from OpenAI (ChatGPT)
    """

    def __init__(self, api_key) -> None:
        super().__init__()
        self.url = "https://api.openai.com/v1/completions"
        self.headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": "Bearer " + api_key,
        }

    def fetch(self, strings_needed, language, language_code):
            # First we need our prompt, which will fetch a response for each language.
        prompt = "Translate each of these phrases, excluding punctuation unless present, into " + \
                language + "\n" +  "\n".join([x.text for x in strings_needed.values()])        

        data = {
            "model": "text-davinci-003",
            "prompt": prompt,
            "temperature": 0,
            "max_tokens": 1024,
            "top_p": 1,
            "frequency_penalty": 0.5,
            "presence_penalty": 0,
        }

        if not config['quiet']:
            print(f"...Fetching {len(strings_needed)} {language} translation(s)")
        json_response = requests.post(self.url, headers=self.headers, json=data)
        response_text = json_response.json()["choices"][0]["text"]
        response_strings = response_text.replace('\n\n', "").split('\n')
        return response_strings

    
def chunks(data, SIZE=10000):
   it = iter(data)
   for i in range(0, len(data), SIZE):
      yield {k:data[k] for k in islice(it, SIZE)}


parser = argparse.ArgumentParser(description="Android String Translator",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-r", "--root", help="root directory of the android app, or library")
parser.add_argument("-q", "--quiet", action="store_true", help="decrease verbosity")
parser.add_argument("-O", "--openai-key", help="OpenAI Key")
parser.add_argument("-p", "--project_id", help="The Project Id for Google Translate")
parser.add_argument("-g", "--google-translate", action="store_true", help="use Google Translate instead of OpenAI")
args = parser.parse_args()
config = vars(args)

rootDir = config['root'] if config['root'] != None else os.environ.get('GITHUB_WORKSPACE')
if config['google_translate']:
    PROJECT_ID = config['project_id'] if config['project_id'] != None else os.environ.get('GOOGLE_PROJECT_ID')
else:
    OPENAI_API_KEY = config['openai_key'] if config['openai_key'] != None else os.environ.get('OPENAI_API_KEY')

translator = GoogleTranslate(PROJECT_ID) if config['google_translate'] else OpenAITranslator(OPENAI_API_KEY)
# Iterate through each source strings.xml file so the case where
source_paths = pathlib.Path(rootDir).glob('**/src/*/res/values/strings.xml')

if not config['quiet']:
    print("Starting Translations Script!")
    print("-------------------------------")

for source_path in source_paths:
    # Generate a map of source strings
    if not config['quiet']:
        print("Parsing " + str(source_path))
    source_tree = ET.parse(source_path)
    source_strings = dict()

    # For each source strings.xml, we first need to make a map of the strings.
    for child in source_tree.getroot():
        # Let's ignore the strings that are marked with translatable=false
        if child.attrib.get(XML_ATTR_TRANSLATABLE) == "false":
            if not config['quiet']:
                print(f"⚠️ Ignoring {child.attrib.get(XML_ATTR_NAME)} because it wasn't marked as translatable")
            continue
        source_strings[child.attrib.get(XML_ATTR_NAME)] = child

    if not config['quiet']:
        print("-------------------------------")

    # Next, we check to see if each language exists
    res_directory = source_path.parent.parent
    for qualifier in qualifier_language.keys():
        qualified_values_folder_name = f"values-{qualifier}"
        qualified_values_folder_path = os.path.join(res_directory, qualified_values_folder_name)
        qualified_values_folder_exists = os.path.exists(qualified_values_folder_path)
        qualified_strings_file_path = os.path.join(qualified_values_folder_path, "strings.xml")
        qualified_strings_file_exists = os.path.exists(qualified_strings_file_path)

        # Next make a list of the strings we need and ones we can remove. If the strings file doesn't exist then we will
        # proceed to creating the file
        qualified_strings_remove = list()
        qualified_strings_needed = dict()
        qualified_strings_needed.update(source_strings)
        if qualified_strings_file_exists:
            strings_tree = ET.parse(qualified_strings_file_path)
            for qualified_string in strings_tree.getroot():
                # Let's ignore the strings that are marked with translatable=false
                if qualified_string.attrib.get(XML_ATTR_TRANSLATABLE) == "false":
                    if not config['quiet']:
                        print(f"...⚠️ Ignoring values-{qualifier}/{child.attrib.get(XML_ATTR_NAME)} because it wasn't marked as translatable")
                    continue

                # Now we check to see if this qualified file has the translation
                qualified_string_key = qualified_string.attrib.get(XML_ATTR_NAME)
                if qualified_string_key in qualified_strings_needed:
                    # If it does, remove it from the ones we need
                    qualified_strings_needed.pop(qualified_string_key)
                else:
                    # If it doesn't, then the source-strings.xml is not in-sync with the qualfied-strings.xml, so we
                    # let's keep track of that and remove the translation.
                    qualified_strings_remove.append(qualified_string_key)
        else:
            # Create the dir if needed
            if not qualified_values_folder_exists:
                os.mkdir(qualified_values_folder_path, 0o777)
            new_strings_file = open(qualified_strings_file_path, 'w')
            new_strings_file.write("<resources></resources>")
            new_strings_file.close()

        # It's time to request from OpenAI and get our translations!
        filtered_response_strings = list()
        if len(qualified_strings_needed) != 0:
            for chunk in chunks(qualified_strings_needed, 16):
                translator.try_chunk(chunk, qualifier_language[qualifier], qualifier)

        # First lets remove the elements we don't need
        qualified_strings_tree = ET.parse(qualified_strings_file_path)
        qualified_strings_root = qualified_strings_tree.getroot()

        for qualified_string_to_remove in qualified_strings_remove:
            for qualified_string in qualified_strings_root:
                if qualified_string.attrib.get(XML_ATTR_NAME) == qualified_string_to_remove:
                    qualified_strings_root.remove(qualified_string)

        if not config['quiet']:
            print(f"...Translations for {qualifier_language[qualifier]} completed")
            print("-------------------------------")
    if not config['quiet']:
        print("Translation Script Complete!")
