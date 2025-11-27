# Notes Feature Implementation

## Overview
Added a complete notes/comments system with nested replies and emoji reactions.

## Database Schema Changes

### New Tables Created:

**`notes` table:**
```sql
id (INTEGER PRIMARY KEY AUTOINCREMENT)
user_id (INTEGER, foreign key to users.id)
parent_note_id (INTEGER, NULL for top-level, references notes.id for replies)
content (TEXT, 1-500 chars)
created_at (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
```

**`reactions` table:**
```sql
id (INTEGER PRIMARY KEY AUTOINCREMENT)
note_id (INTEGER, foreign key to notes.id)
user_id (INTEGER, foreign key to users.id)
emoji (TEXT, 1-10 chars)
created_at (TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
UNIQUE(note_id, user_id, emoji) - prevents duplicate reactions per user/note
```

## Forms Added

1. **PostNoteForm** - Create top-level notes
   - `content`: StringField (1-500 chars)

2. **ReplyForm** - Reply to existing notes
   - `content`: StringField (1-500 chars)

3. **ReactForm** - Add emoji reactions
   - `emoji`: StringField (1-10 chars)

## Routes Added

### GET Routes:
- **`/notes`** - Display all notes with replies and reactions
  - Requires login (redirects to `/login` if not authenticated)
  - Loads top-level notes ordered by newest first
  - Loads replies for each note
  - Shows reaction counts and checks if current user has reacted
  - Returns `notes.html` template

### POST Routes:
- **`/notes/create`** - Post a new top-level note
  - Requires login
  - Validates content (1-500 chars)
  - Inserts into notes table with `parent_note_id = NULL`
  - Redirects to `/notes`

- **`/notes/<int:note_id>/reply`** - Post a reply to a note
  - Requires login
  - Validates content (1-500 chars)
  - Verifies parent note exists
  - Inserts into notes table with `parent_note_id = note_id`
  - Redirects to `/notes`

- **`/notes/<int:note_id>/react`** - Toggle emoji reaction on a note
  - Requires login
  - Accepts emoji from form data
  - If user already reacted with that emoji → deletes reaction (toggle)
  - If new reaction → inserts into reactions table
  - UNIQUE constraint prevents duplicates
  - Redirects to `/notes`

## Template Created

**`templates/notes.html`** - Main notes page
- Bootstrap 5.3.2 styling
- Two-column layout (main content + sidebar tips)
- Post form at top
- Each note displays:
  - Author username and timestamp
  - Note content
  - Existing reactions with counts (clickable to remove)
  - 10 emoji buttons for quick reactions (👍, ❤️, 😀, 😂, 🤔, 😢, 😡, 🎉, 🔥, ✨)
  - Reply form
  - Nested replies with their own reactions
- Reply cards are indented and styled differently
- Flash messages for user feedback

## UI Features

- **Emoji Reactions**: Click emoji button to add reaction, click existing reaction to remove it (toggle)
- **Nested Replies**: Replies are indented and visually distinguished from top-level notes
- **Real-time Reaction Counts**: Shows how many users reacted with each emoji
- **User Highlighting**: Reactions the current user made are highlighted in blue
- **Responsive Design**: Works on mobile and desktop

## How to Use

1. **Navigate to Notes**: Click "Notes" in the main navigation menu
2. **Post a Note**: Enter text in "Write a Note" form and click "Post Note"
3. **Reply to Note**: Enter text in the reply form under any note and click "Reply"
4. **React with Emoji**: Click any emoji button to add a reaction
5. **Remove Reaction**: Click an existing reaction you added to remove it

## Integration Points

- **Home Page**: Added "Notes" link to main navigation (`/notes`)
- **Authentication**: Uses existing session-based auth (requires login)
- **Database**: Uses existing `get_db_connection()` and SQLite with WAL mode
- **CSRF Protection**: Uses Flask-WTF for all forms

## Example Workflow

```
User A logs in → Clicks "Notes" → Posts: "Just learned Flask!"
User B logs in → Clicks "Notes" → Sees User A's note
User B → Clicks 👍 (reacts with thumbs up)
User B → Clicks reply field → Posts: "Me too!"
User C logs in → Sees User A's note with reply from User B
User C → Clicks ❤️ on User B's reply
User A → Sees their note has 2 reactions (👍 from B, ❤️ from C on the reply)
```

## Database Query Examples

```sql
-- Get all top-level notes with user info
SELECT n.id, n.user_id, n.content, n.created_at, u.username
FROM notes n
JOIN users u ON n.user_id = u.id
WHERE n.parent_note_id IS NULL
ORDER BY n.created_at DESC;

-- Get replies to a note
SELECT n.id, n.user_id, n.content, n.created_at, u.username
FROM notes n
JOIN users u ON n.user_id = u.id
WHERE n.parent_note_id = ?
ORDER BY n.created_at ASC;

-- Get reaction counts for a note
SELECT emoji, COUNT(*) as count
FROM reactions
WHERE note_id = ?
GROUP BY emoji
ORDER BY count DESC;
```

## Technical Details

- **Emoji Picker**: Currently hardcoded 10 emoji buttons; can be extended
- **Single Reaction Toggle**: Clicking same emoji twice removes reaction
- **No Nested Replies**: Replies are 2-level (note + reply only)
- **Concurrent Access**: Benefits from SQLite WAL mode for better concurrency
- **Performance**: Loads all notes on single page (can be optimized with pagination)
