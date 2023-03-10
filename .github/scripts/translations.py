import pathlib
import json
import xml.etree.ElementTree as ET
import os
import copy
import requests

from xml.dom import minidom

# Env Args
GITHUB_WORKSPACE = os.environ.get('GITHUB_WORKSPACE')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# Parsing Args
XML_ATTR_TRANSLATABLE = "translatable"
XML_ATTR_NAME = "name"

# Associative Array which is the source of our languages
qualifier_language = {
    "pl": "Polish",
    "en-rGB": "British English",
    "uk": "Ukrainian",
}

# Iterate through each source strings.xml file so the case where
source_paths = pathlib.Path(GITHUB_WORKSPACE).glob('**/src/*/res/values/strings.xml')

print("Starting Translations Script!")
print("-------------------------------")

for source_path in source_paths:
    # Generate a map of source strings
    print("Parsing " + str(source_path))
    source_tree = ET.parse(source_path)
    source_strings = dict()

    # For each source strings.xml, we first need to make a map of the strings.
    for child in source_tree.getroot():
        # Let's ignore the strings that are marked with translatable=false
        if child.attrib.get(XML_ATTR_TRANSLATABLE) == "false":
            print(f"⚠️ Ignoring {child.attrib.get(XML_ATTR_NAME)} because it wasn't marked as translatable")
            continue
        source_strings[child.attrib.get(XML_ATTR_NAME)] = child

    print("-------------------------------")

    # Next, we check to see if each language exists
    res_directory = source_path.parent.parent
    for qualifier in qualifier_language.keys():
        qualified_values_folder_name = 'values-{qualifier}'.format(qualifier=qualifier)
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
        qualified_strings_to_add = list()
        if len(qualified_strings_needed) != 0:
            # First we need our prompt, which will fetch a response for each language.
            prompt = "Translate each of these phrases, excluding punctuation unless present, into " + \
                     qualifier_language[qualifier]
            for qualified_string_needed_key in qualified_strings_needed:
                prompt += "\n" + qualified_strings_needed[qualified_string_needed_key].text

            url = "https://api.openai.com/v1/completions"
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": "Bearer " + OPENAI_API_KEY,
            }
            data = {
                "model": "text-davinci-003",
                "prompt": prompt,
                "temperature": 0,
                "max_tokens": 60,
                "top_p": 1,
                "frequency_penalty": 0.5,
                "presence_penalty": 0,
            }
            print(f"...Fetching {len(qualified_strings_needed)} {qualifier_language[qualifier]} translation(s)")
            json_response = requests.post(url, headers=headers, json=data)
            response_text = json_response.json()["choices"][0]["text"]
            response_strings = response_text.replace('\n\n', "").split('\n')
            filtered_response_strings = list(filter(lambda string: len(string) > 0, response_strings))

            # The count isn't the best way of doing this, but sometimes life is like that.
            if len(filtered_response_strings) != len(qualified_strings_needed):
                print(
                    "...Stopping translations for {qualifier}, OpenAI response returned {oai_count} item(s) but we "
                    "expected {local_count}".format(
                        qualifier=qualifier,
                        oai_count=len(filtered_response_strings),
                        local_count=len(qualified_strings_needed)
                    ))
                continue

            index = 0
            for qualified_string_needed_key in qualified_strings_needed:
                qualified_string_needed = qualified_strings_needed[qualified_string_needed_key]
                qualified_string_copy = copy.deepcopy(qualified_string_needed)
                qualified_string_copy.text = filtered_response_strings[index]
                print(
                    f"...Adding {qualified_strings_needed[qualified_string_needed_key].text} -> {qualified_string_copy.text}")
                qualified_strings_to_add.append(qualified_string_copy)
                index += 1

        # Now lets move onto modifying the XML file.
        if len(qualified_strings_remove) > 0 or len(qualified_strings_needed) > 0:
            qualified_strings_tree = ET.parse(qualified_strings_file_path)
            qualified_strings_root = qualified_strings_tree.getroot()

            # First lets remove the elements we dont need
            for qualified_string_to_remove in qualified_strings_remove:
                for qualified_string in qualified_strings_root:
                    if qualified_string.attrib.get(XML_ATTR_NAME) == qualified_string_to_remove:
                        qualified_strings_root.remove(qualified_string)

            # Next lets add the elements we do want
            for qualified_string in qualified_strings_to_add:
                qualified_strings_root.append(qualified_string)

            # Lastly, we write the changes to the file
            print(f"...Writing changes to {str(qualified_strings_file_path)}")
            qualified_strings_tree.write(
                qualified_strings_file_path,
                encoding="utf-8",
                xml_declaration="utf-8",
                method="xml"
            )
        print(f"...Translations for {qualifier_language[qualifier]} completed")
        print("-------------------------------")
    print("Translation Script Complete!")
