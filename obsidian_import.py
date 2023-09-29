import os
import json
import uuid
from datetime import datetime
import re

def generate_token_id():
    """Generate a short random token ID."""
    return str(uuid.uuid4())[:8]

def obsidian_to_ideaflow_link_mapping(obsidian_folder_path):
    """Create a mapping between Obsidian note titles and IdeaFlow note_ids.

    Args:
        obsidian_folder_path (str): The file path of the Obsidian folder.

    Returns:
        dict: A dictionary mapping Obsidian note titles to IdeaFlow note_ids.
    """
    mapping = {}
    for root, _, files in os.walk(obsidian_folder_path):
        for filename in files:
            if filename.endswith('.md'):
                title = filename.replace('.md', '').replace('#', '')
                mapping[title] = generate_token_id()
    return mapping

# arg: line, a string of text
# returns: an array of dicts
def parse_by_word(line):
    elements = []
    # link, hashtag parsing is done word-by-word
    words = line.split()
    for i, word in enumerate(words):
        if re.match(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', word):  # URL links
            elements.append({"type": "link", "content": word, "slug": word})
        elif word.startswith('#'):
            elements.append({"type": "hashtag", "content": word})
        else:
            elements.append({"type": "text", "marks": [], "content": word})

        if i < len(words) - 1:
            elements.append({"type": "text", "marks": [], "content": ' '})
    return elements


# returns an array of dicts (or single dict if a list), as well as contenttype (list, paragraph)
def parse_line(line, mapping):
    """Parse a single line to extract its elements into IdeaFlow-compatible JSON."""
    elements = []
    content_type = "paragraph"

    # Bullet and checkbox parsing is done by line
    # Parse bullets
    if line.startswith('* '):
        stripped_line = line.lstrip()
        leading_spaces = len(line) - len(stripped_line)
        depth = leading_spaces // 4  # assuming each level of indentation is 4 spaces
        # print(f"Line: '{line}', Stripped: '{stripped_line}', Leading: {leading_spaces}, Depth: {depth}")  # Debug line

        remaining_text = line[2:]
        content = parse_by_word(remaining_text)  # text to parse further
        elements.append({
            "type": "listItem",
            "content": [
                {
                    "type": "paragraph",
                    "tokenId": generate_token_id(),
                    "content": content
                }
            ],
            "depth": depth
        })
        # print(f"Appending listItem with depth {depth}")  # Debug line

        return {"type": "list", "content": elements}, "list"
    # Parse checkboxes
    elif line.startswith('- [ ] ') or line.startswith('- [x] '):
        elements.append({"type": "checkbox", "isChecked": line.startswith('- [x] ')})
        content = parse_by_word(line[6:])  # text to parse further
        elements.extend(content)
    else:
        # Initialize patterns for regular expression matching
        obsidian_link_pattern = re.compile(r'\[\[(.*?)\]\]')
        obsidian_links = [(m.group(), m.start(), m.end()) for m in obsidian_link_pattern.finditer(line)]

        last_pos = 0  # Keep track of the last processed position

        # Iterate through Obsidian links and add adjacent plain text
        for link, start, end in obsidian_links:
            if start > last_pos:  # There is plain text before this link
                plain_text = line[last_pos:start]
                elements.extend(parse_by_word(plain_text))

            linked_note = link[2:-2]  # Remove [[ and ]]
            linked_note_id = mapping.get(linked_note, generate_token_id())
            elements.append({"type": "spaceship", "linkedNoteId": linked_note_id, "tokenId": generate_token_id()})

            last_pos = end  # Update last processed position

        # Append remaining plain text after the last link
        if last_pos < len(line):
            elements.extend(parse_by_word(line[last_pos:]))

    return elements, content_type


def convert_to_tokens(content, mapping):
    """Convert a note's content into IdeaFlow-compatible tokens."""
    paragraphs = content.split("\n")
    tokens = []
    for paragraph in paragraphs:
        if paragraph.strip():
            token_id = generate_token_id()
            elements, content_type = parse_line(paragraph, mapping)
            if content_type == "list":
                # keep list element high-level
                tokens.append(elements)
            else:
                # each line is wrapped in its own paragraph element
                tokens.append({
                    "type": "paragraph",
                    "tokenId": token_id,
                    "content": elements
                })
        else:
            tokens.append({
                "type": "paragraph",
                "tokenId": generate_token_id(),
                "content": []
            })

    return tokens

def obsidian_to_ideaflow(obsidian_folder_path):
    """Convert an Obsidian folder to an IdeaFlow JSON file."""
    ideaflow_notes = {}
    mapping = obsidian_to_ideaflow_link_mapping(obsidian_folder_path)

    for root, _, files in os.walk(obsidian_folder_path):
        for filename in files:
            if filename.endswith('.md'):
                full_path = os.path.join(root, filename)
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                title = filename.replace('.md', '').replace('#', '')
                note_id = mapping[title]  # Fetch the mapped IdeaFlow note_id
                tokens = convert_to_tokens(f"{title}\n{content}", mapping)

                timestamp = datetime.utcnow().isoformat() + "Z"

                note_data = {
                    "id": note_id,
                    "created_at": timestamp,
                    "deleted_at": None,
                    "inserted_at": timestamp.split('T')[0].replace('-', ''),
                    "position": "aC",
                    "tokens": tokens,
                    "read_all": False,
                    "updated_at": timestamp,
                    "position_in_pinned": None,
                    "folder_id": None,
                    "import_source": "Obsidian",
                    "import_batch": None,
                    "import_foreign_id": None
                }

                ideaflow_notes[note_id] = note_data

    output = {
        "version": "08212023",
        "notes": ideaflow_notes
    }

    with open('ideaflow_import.if.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    # obsidian_folder_path = 'C:\\Users\\Cody-DellXPS\\Documents\\Obsidian Vault'  # debug
    obsidian_folder_path = input("Enter the Obsidian vault filepath: ")
    if not os.path.exists(obsidian_folder_path):
        print("The provided filepath does not exist. Exiting.")
    else:
        obsidian_to_ideaflow(obsidian_folder_path)
        print("Ideaflow notes have been generated in 'ideaflow_import.if.json'.")
