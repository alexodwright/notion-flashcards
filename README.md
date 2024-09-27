# NOTION TO ANKI FLASHCARD APP - PYTHON, GOOGLE GEMINI, NOTION API

This is a python script that creates Anki flashcard files from your Notion notes! By using the Notion API and the Google Gemini AI 1.5 flash model, flashcards are created to help you study for your exams!
Before running, ensure you input your Notion Integration API Key, Google Gemini Studio Key and the Block ID of the root page of your Notion notes into the creds.py file. Assuming a notion page layout as follows:

```bash
├── ROOT BLOCK
   ├── Subject 1
   │   ├── Lecture 1
   │   ├── Lecture 2
   │   ├── Lecture 3
   ├── Subject 2
   │   ├── Lecture 1
   │   ├── Lecture 2
   │   ├── Lecture 3
   ├── Subject 
   │   ├── Lecture 1
   │   ├── Lecture 2
   │   ├── Lecture 3
```
