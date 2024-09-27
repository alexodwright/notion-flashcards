# retrieve credentials
from creds import NOTION_API_KEY as NOTION_TOKEN, GOOGLEAI_API_TOKEN, ROOT_BLOCK_ID

# imports
import notion_client
from notion2md.exporter.block import StringExporter
from pprint import pprint
import os
import json
import google.generativeai as genai
from genanki import Note, Deck, Model, Package
import random
import shutil
import sqlite3
import datetime
import zipfile

def create_db_con_cur(database_path):
  ''' Create the connection and cursor to the database. '''
  connection = sqlite3.connect(database_path)
  cursor = connection.cursor()
  return connection, cursor

def read_deck_from_file(filename, subject):
  ''' Reads in a previously made deck and extracts each flashcard. '''
  with zipfile.ZipFile(filename, "r") as zipf:
    zipf.extractall(f"unzipped/{subject}")
  deck_conn, deck_cur = create_db_con_cur(f"unzipped/{subject}/collection.anki2")
  res = deck_cur.execute("select * from notes").fetchall()
  deck_conn.close()
  shutil.rmtree(f"unzipped/{subject}")
  os.rmdir("unzipped")
  return res

def check_deletions(subject) -> None:
  ''' Checks if the user has deleted a flashcard file, if so,
   delete all the database entries relating to that subject.'''
  if 'flashcards' in os.listdir(os.getcwd()):
    subject_found = (f'{subject}.apkg' in os.listdir(f"{os.getcwd()}/flashcards"))
    if subject_found is False:
      query = '''
              DELETE
              FROM flashcards
              WHERE subject = ?
              '''
      cursor.execute(query, (subject, ))
      connection.commit()

def regenerate_cards(d, i) -> None:
  ''' Regenerates cards of a certain range from a question and answer read in from a file.

      To be used in conjunction with read_deck_from_file.  
  '''
  for x, data in enumerate(d):
    if x in range((i*3), ((i+1)*3)):
      data = data[6].split("\x1f")
      model = Model(
        x+1,
        'FlashCard Model',
        fields=[
          {'name': 'Question'},
          {'name': 'Answer'},
        ],
        templates=[
          {
            'name': f'Card {d}',
            'qfmt': '<h1 style="color: #0a7d62; text-align: center; font-weight: bold;">{{Question}}</h1>',
            'afmt': '{{FrontSide}}<hr id="answer"><p style="font-size: 1.5rem">{{Answer}}</p>',
          },
        ])

      note = Note(
          model,
          fields=[data[0], data[1]]
      )
      deck.add_note(note)

  
def create_flashcard(lecture, update, subject) -> None:
  ''' Creates a flashcard given a lecture represented in markdown, whether to update the database if the last_edited_time
      is newer, and the subject of this flashcard.
  '''
  # get the id of the lecture page
  lect_id = lecture['id']

  # convert to markdown
  md = StringExporter(block_id=lect_id, output_path=f"flashcards/{lect_id}").export()
  md = md.replace("```", "")

  # invoke gemini
  model = genai.GenerativeModel("gemini-1.5-flash")
  response = model.generate_content(f"Turn the following markdown into exactly 3 flashcard style objects formatted into strict, valid json with 'question' as the key and the generated question as the value, have 'answer' as the second key, and the generated answer as the value. Escape any neccessary characters that would cause an error:  {md}")
  data = response.text

  # remove the unwanted chars
  data = data.strip("```").strip("json").replace("\\n", " ")
  data = json.loads(fr"{data}")
  
  # for each question and answer create a flashcard with the question on the front and the answer on the back
  for d, text in enumerate(data):
      model = Model(
      d+1,
      'FlashCard Model',
      fields=[
        {'name': 'Question'},
        {'name': 'Answer'},
      ],
      templates=[
        {
          'name': f'Card {d}',
          'qfmt': '<h1 style="color: #0a7d62; text-align: center; font-weight: bold;">{{Question}}</h1>',
          'afmt': '{{FrontSide}}<hr id="answer"><p style="font-size: 1.5rem">{{Answer}}</p>',
        },
      ])
      
      note = Note(
          model,
          fields=[text['question'], text['answer']]
      )
      deck.add_note(note)
      
      # add flashcard to database
      flashcard_to_db(lecture, subject, update=update)

def flashcard_to_db(lecture, subject, update: bool = False) -> None:
  '''
  Given a flashcard and its subject update or insert its db entry depending on the value of the update argument.
  '''
  # get the current time
  # account for gmt +1 (Dublin Time)
  time_offset = datetime.timezone(datetime.timedelta(hours=1))
  curr_time = datetime.datetime.now(time_offset).isoformat()
  if update is False:
    query = '''
            INSERT INTO flashcards (time_created, page_id, subject)
            VALUES (?, ?, ?) 
            '''
    cursor.execute(query, (curr_time, lecture['id'], subject))
  else:
    query = '''
            UPDATE flashcards
            SET time_created = ?
            WHERE page_id = ?
            '''
    cursor.execute(query, (curr_time, lecture['id']))
  connection.commit()

def is_obsolete_flashcard(lecture) -> None:
  ''' Given a lecture, determine if its last_edited time is more recent than its flashcard creation time.

      If there is no flashcard report this.

      If it needs to be updated report this.

      If the flashcard is up to date report this.
  '''
  query = '''
          SELECT time_created
          FROM flashcards
          WHERE page_id = ?
          '''
  flashcard_time_created = cursor.execute(query, (lecture['id'], )).fetchone()
  if flashcard_time_created is not None:
    flashcard_time_created = datetime.datetime.fromisoformat(flashcard_time_created[0]).replace(tzinfo=None)
  
  # notion rounds the editing time to the nearest minute, so add a minute to make sure up to date
  notion_time = datetime.datetime.strptime(lecture['last_edited_time'], "%Y-%m-%dT%H:%M:%S.000Z") + datetime.timedelta(hours=1, minutes=1)

  if (flashcard_time_created is not None):
    if flashcard_time_created < notion_time:
      return "update"
    return "up to date"
  return "not found"

def print_db() -> None:
  ''' Print the contents of the flashcards table. '''
  query = '''
          SELECT *
          FROM flashcards
          '''
  flashcards = cursor.execute(query).fetchall()
  pprint(flashcards)

def clear_db() -> None:
  ''' Clear the contents of the flashcards table. '''
  query = "DELETE FROM flashcards WHERE 1=1"
  cursor.execute(query)
  connection.commit()

# initialize the notion client
notion = notion_client.Client(auth=NOTION_TOKEN)

# set the os notion key
os.environ["NOTION_TOKEN"] = NOTION_TOKEN

# set the google ai api key
genai.configure(api_key=GOOGLEAI_API_TOKEN)

# create deck_id
deck_id = random.randint(1,100)

def move_files() -> None:
  ''' For each of the subjects, if its file is not in the 'flashcards' directory, move it there. '''
  # if flashcards folder doesn't already exist, create it
  if 'flashcards' not in os.listdir(os.getcwd()):
    os.mkdir(os.getcwd() + "/flashcards")
  # move all the files to the 'flashcards' folder
  for subject in subject_page_ids:
    if f"{subject}.apkg" in os.listdir(os.getcwd()):
      shutil.move(f"{subject}.apkg", f"flashcards/{subject}.apkg")

def create_subjects() -> dict:
  ''' Using the root notion_id create a dictionary of the subjects, with their name as the key and the block_id as the value. '''
  # access the root of the notion page
  root_block = notion.blocks.children.list(block_id=ROOT_BLOCK_ID)

  # get the subjects, assuming their the direct children of the root block
  subjects = root_block['results']

  # create a dict with the name of the subject and it's block id
  subject_page_ids = {subject['child_page']['title']: subject['id'] for subject in subjects}
  return subject_page_ids

if __name__=="__main__":

  connection, cursor = create_db_con_cur("database.db")

  # if the user deletes the flashcards folder
  if ('flashcards' not in os.listdir(os.getcwd())) or (os.listdir(f"{os.getcwd()}/flashcards") == []):
    clear_db()

  subject_page_ids = create_subjects()
  for subject in subject_page_ids:

    # check if the user has deleted this subject's file if it already existed, if so, delete all database entries
    check_deletions(subject)

    print(f"---------------Exporting {subject }---------------")

    # create a deck
    deck = Deck(deck_id, subject)

    # get the block id from the dict
    sub_id = subject_page_ids[subject]

    # get each lecture from that subject
    lectures = notion.blocks.children.list(block_id=sub_id)['results']

    has_updated = False
    a = None

    # pre check if there will be an update
    for i, lecture in enumerate(lectures):
      a = is_obsolete_flashcard(lecture)
      if a=="update" or a=="not found":
        has_updated = True
        break

    for i, lecture in enumerate(lectures):
      if is_obsolete_flashcard(lecture)=="update":
        create_flashcard(lecture, True, subject)
        print(f"Flashcard for {subject} {lecture['child_page']['title']} has been updated!")
      elif is_obsolete_flashcard(lecture)=="not found":
        create_flashcard(lecture, False, subject)
        print(f"Flashcard for {subject} {lecture['child_page']['title']} has been created!")
      else:
        print(f"Flashcard for {subject} {lecture['child_page']['title']} is up to date!")
        if has_updated is True:
          regenerate_cards(read_deck_from_file(f"flashcards/{subject}.apkg", subject,), i)    

    print()
    # create a package with the subject's deck
    if has_updated:
      Package(deck).write_to_file(f'{subject}.apkg')
      print(f"Finished creating Flashcards for {subject}!")

  # if there are new flashcards move the files
  move_files()
  if has_updated:
    print("Successfully created flashcards! Check the 'flashcards' folder.")
  connection.close()