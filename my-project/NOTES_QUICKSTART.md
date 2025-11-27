# Notes Feature - Quick Start Guide

## Prerequisites
- Application must be running
- User must be logged in
- Database initialized with new notes and reactions tables

## Step-by-Step Walkthrough

### Step 1: Access the Notes Page
1. Click the **"Notes"** link in the top navigation menu
2. You should see a page with:
   - "Write a Note" form at the top
   - A "Tips" sidebar on the right
   - Empty note feed (if first time)

### Step 2: Post Your First Note
1. In the "Write a Note" form, enter text like:
   ```
   Just learning Flask! Loving it so far.
   ```
2. Click **"Post Note"** button
3. You should see a success flash message: "Note posted!"
4. Your note appears in the feed with:
   - Your username
   - Timestamp
   - Your message content
   - 10 emoji reaction buttons (👍, ❤️, 😀, 😂, 🤔, 😢, 😡, 🎉, 🔥, ✨)
   - A reply input field

### Step 3: React with Emoji
1. On your note, click any emoji button (e.g., **👍**)
2. The emoji button will:
   - Turn blue (indicating you reacted)
   - Show a count: "👍 1"
3. Click the same emoji again to **remove your reaction**
   - Button returns to gray
   - Count disappears
4. Try reacting with multiple different emojis

### Step 4: Post a Reply
1. In the reply field under your note, type:
   ```
   Following up on what I just learned!
   ```
2. Click **"Reply"** button
3. You should see a success message: "Reply posted!"
4. Your reply appears indented under your note with:
   - Username and timestamp
   - Reply content
   - Its own emoji reaction buttons

### Step 5: React to Replies
1. On your reply, click an emoji button
2. The reaction is added just like on main notes
3. Click again to remove

### Step 6: Simulate Multiple Users
To test the full social features, you need at least 2 user accounts:

1. **User A** (currently logged in):
   - Already posted a note
   - Already reacted to it

2. **User B** (new account):
   - Open a new browser tab (or private/incognito window)
   - Go to `/register`
   - Create account with different username
   - Log in
   - Navigate to `/notes`
   - You should see **User A's note**
   - Click **👍** to react (reaction count will show "👍 2" because User A also reacted)
   - Post your own note

### Step 7: View Nested Conversation
1. Go back to User A's tab (or log back in as User A)
2. Refresh `/notes`
3. Your note now shows:
   - Your original note content
   - Your reply to your own note (indented)
   - User B's reactions to your note
   - User B's separate note in the feed

## Key Features to Test

### ✅ Post Creation
- [x] Can create new top-level notes
- [x] Note appears immediately
- [x] Author name shows correctly

### ✅ Replies
- [x] Can reply to any note
- [x] Replies appear indented
- [x] Reply shows correct author

### ✅ Emoji Reactions
- [x] Can react with any of 10 emojis
- [x] Reaction count updates
- [x] User's reactions highlighted in blue
- [x] Can toggle reaction on/off

### ✅ Multi-User Interaction
- [x] Other users see your notes
- [x] Other users can reply to your notes
- [x] Other users can react to your notes
- [x] Reaction counts include all users

### ✅ Data Persistence
- [x] Notes persist after logout/login
- [x] Reactions persist
- [x] Replies persist

## Database Queries You Can Run

If you want to inspect the database directly, use SQLite CLI:

```bash
# Open database
sqlite3 database.db

# View all notes (including replies)
SELECT id, user_id, parent_note_id, content, created_at FROM notes;

# View only top-level notes
SELECT id, user_id, content FROM notes WHERE parent_note_id IS NULL;

# View all reactions
SELECT note_id, user_id, emoji FROM reactions;

# Count reactions by emoji
SELECT emoji, COUNT(*) FROM reactions GROUP BY emoji;

# View a specific note with author info
SELECT n.id, u.username, n.content, n.created_at 
FROM notes n 
JOIN users u ON n.user_id = u.id 
WHERE n.id = 1;
```

## Expected Behavior

### Success Cases
- ✅ User can post note (1-500 chars)
- ✅ User can reply to note (1-500 chars)
- ✅ User can react with emoji (any 1-10 char string)
- ✅ Clicking emoji again removes reaction (toggle)
- ✅ Multiple users can interact with same note
- ✅ Reaction counts aggregate across all users

### Validation
- ❌ Can't post empty note (validation error shown)
- ❌ Can't post >500 char note (validation error shown)
- ❌ Can't access `/notes` without login (redirects to `/login`)
- ❌ Can't reply to non-existent note (error message shown)

## Common Issues & Solutions

### Issue: "Note not found" message
**Cause:** Trying to reply to deleted note or note ID doesn't exist
**Solution:** Refresh page; note may have been deleted

### Issue: Reaction not appearing
**Cause:** UNIQUE constraint - same emoji on same note by same user
**Solution:** Click existing emoji to remove, then add again

### Issue: Can't see other users' reactions
**Cause:** May have just reacted - refresh page
**Solution:** Refresh `/notes` to see latest reaction counts

## Next Steps / Enhancement Ideas

1. **Pagination**: Currently loads all notes on one page
2. **Emoji Picker**: Could add a proper emoji picker library
3. **@Mentions**: Could tag other users in notes
4. **Delete/Edit**: Users could edit/delete own notes
5. **Likes Counter**: Different from reactions
6. **Sort Options**: By newest, most reactions, etc.
7. **Search**: Find notes by content
8. **User Profiles**: Show user's notes history
