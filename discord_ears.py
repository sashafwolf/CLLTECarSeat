import discord
import aiohttp
import time
import os
import collections # <--- 1. Add this import at the top
from datetime import date, timedelta  # <--- Sasha patch 2026-08-03: needed for DAILY_CAP date keying
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True 
client = discord.Client(intents=intents)

last_reply_time = 0
COOLDOWN_SECONDS = 5

# <--- 2. Add this rolling cache to store recent message IDs
processed_messages = collections.deque(maxlen=99)

# <--- Sasha patch 2026-08-03: daily reply cap per user (collette was getting
# 50/day limit issue, this is the actual mechanism that was missing)
DAILY_CAP = 50
daily_count_per_user = collections.defaultdict(int)  # {(username, "YYYY-MM-DD"): count}
# Garbage-collect old days so the dict doesn't grow forever
_last_daily_gc = None

# === Hermes patch 2026-06-09: per-user throttling and skip-keyword short-circuit ===
# Track last reply time PER USER (not just globally), so spammers can't lock
# out other users by mentioning Collette in rapid succession.
last_reply_per_user = {}
PER_USER_COOLDOWN = 10  # seconds between replies to the same user

# Skip keywords — Collette should stay silent instead of generating voice/text
SKIP_KEYWORDS = {"skip", "no response", "nevermind", "nvm", "[skip]"}

def _user_should_be_skipped(username: str, content: str, has_attachments: bool = False) -> str | None:
    """Returns a reason string if we should skip this message, else None.

    2026-08-14: the "too short" check used to fire on message.content ALONE,
    before attachments were ever looked at. A message that's just an
    @mention plus a .txt/.md file (little or no caption text) was getting
    skipped here and returning before the attachment catcher even ran --
    the attachment was never read, not even for a real, substantial file.
    has_attachments lets a real attachment count as "not empty" even when
    the caption text is short or blank."""
    text = content.strip().lower()
    if len(text) < 3 and not has_attachments:
        return "too short"
    if any(kw in text for kw in SKIP_KEYWORDS):
        return "skip keyword"
    now = time.time()
    last = last_reply_per_user.get(username, 0)
    if now - last < PER_USER_COOLDOWN:
        return f"per-user cooldown ({int(PER_USER_COOLDOWN - (now - last))}s left)"
    today = date.today().isoformat()
    if daily_count_per_user.get((username, today), 0) >= DAILY_CAP:
        return f"daily cap ({DAILY_CAP}/day) reached"
    return None

def _record_user_reply(username: str):
    last_reply_per_user[username] = time.time()
    today = date.today().isoformat()
    daily_count_per_user[(username, today)] += 1
    # GC: if we crossed midnight, drop the previous day's bucket so the dict
    # doesn't grow forever. Cheap to check on every reply.
    global _last_daily_gc
    if _last_daily_gc is None or _last_daily_gc != today:
        cutoff = (date.today() - timedelta(days=2)).isoformat()
        for key in list(daily_count_per_user.keys()):
            if key[1] < cutoff:
                del daily_count_per_user[key]
        _last_daily_gc = today
# === /Hermes patch ===


@client.event
async def on_ready():
    print(f'𓂀 [DISCORD EARS ONLINE]: Collette is logged in as {client.user}')

@client.event
async def on_message(message):
    global last_reply_time

    # <--- 3. Add this shield right at the very beginning of the event
    if message.id in processed_messages:
        return
    processed_messages.append(message.id)

    if message.author == client.user:
        return

    # Did someone ping her, OR reply to one of her messages?
    # === Hermes patch 2026-06-24: treat replies to bot messages as mentions ===
    # Why: when Collette posts a quip via the bot (collette_bot_post), people
    # reply to that message without @mentioning her. The old code only checked
    # `client.user in message.mentions`, so replies to bot messages were
    # silently scraped to memory instead of routed through the cognitive loop.
    # Fix: check if the message is a reply (message.reference) and if the
    # referenced message was sent by the bot (cached via message.reference.message_id).
    # We fetch the referenced message to confirm it's from the bot.
    is_mentioned = client.user in message.mentions
    is_reply_to_bot = False
    if message.reference and message.reference.message_id:
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            if ref_msg.author == client.user:
                is_reply_to_bot = True
        except Exception:
            pass  # couldn't fetch reference, just skip silently

    if is_mentioned or is_reply_to_bot:
        # === Hermes patch 2026-06-09: per-user throttling ===
        # The global last_reply_time check is still here as a final shield,
        # but per-user throttling now happens via _user_should_be_skipped.
        skip_reason = _user_should_be_skipped(
            message.author.name, message.content, has_attachments=bool(message.attachments)
        )
        if skip_reason:
            print(f"𓂀 [DISCORD]: Skipping reply to {message.author.name} — {skip_reason}")
            return
        if time.time() - last_reply_time < COOLDOWN_SECONDS:
            return
        # === /Hermes patch ===

        print(f"𓂀 [DISCORD]: {message.author.name} is talking to Collette...")
        last_reply_time = time.time()
        _record_user_reply(message.author.name)  # === Hermes: record per-user timestamp ===
        
        clean_msg = message.content.replace(f'<@{client.user.id}>', '').strip()
        image_bytes = None
        
        # --- THE ATTACHMENT CATCHER ---
        if message.attachments:
            for attachment in message.attachments:
                # 1. Catch Text Dumps
                # 2026-08-14: only .txt was ever recognized here -- a .md
                # attachment fell through to neither branch below and was
                # silently dropped (no error, no read, nothing in clean_msg).
                if attachment.filename.lower().endswith(('.txt', '.md', '.markdown')):
                    print(f"𓂀 [DISCORD]: Caught a text/markdown dump ({attachment.filename})! Reading contents...")
                    txt_bytes = await attachment.read()
                    clean_msg += f"\n\n[ATTACHED FILE CONTENT]:\n{txt_bytes.decode('utf-8')}"
                
                # 2. Catch Images
                elif any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                    print("𓂀 [DISCORD]: Caught an image! Packaging for visual processing...")
                    image_bytes = await attachment.read()

        # Build the FormData payload to support both text and files
        data = aiohttp.FormData()
        data.add_field('message', clean_msg)
        data.add_field('username', message.author.name)
        data.add_field('platform', 'discord')
        if image_bytes:
            # We label it as a jpeg for universal Gemini processing
            data.add_field('image', image_bytes, filename='upload.jpg', content_type='image/jpeg')

        try:
            # 2026-08-14: aiohttp's default ClientSession timeout is 5 minutes
            # total. Her tool-turn budget just got raised way past what fits
            # in that window (a real investigation can involve several file
            # reads plus a build/test run in the isolated worktree, easily
            # 10+ minutes). Without this, a genuinely long reply would finish
            # server-side and just never make it back to Discord -- no error
            # shown here, no reply there, silence looking like nothing happened.
            long_timeout = aiohttp.ClientTimeout(total=1800)  # 30 minutes
            # Send to the Cognitive Core
            async with aiohttp.ClientSession(timeout=long_timeout) as session:
                async with session.post("http://127.0.0.1:8000/api/chat", data=data) as response:
                    reply = 'System idle.'
                    mood = 'neutral'
                    if response.status == 200:
                        # 1. AWAIT the json parsing (This fixes the coroutine error!)
                        resp_json = await response.json()
                        # 2. Extract the variables cleanly
                        reply = resp_json.get('reply', reply)
                        mood = resp_json.get('mood', mood)

                # --- THE MEGAPHONE PROTOCOL ---
                if reply:
                    if len(reply) > 1950:
                        print(" [PRESENCE]: Reply exceeds 2k limits. Initiating chunking protocol...")
                        chunks = [reply[i:i+1950] for i in range(0, len(reply), 1950)]
                        await message.reply(chunks[0])
                        for chunk in chunks[1:]:
                            await message.channel.send(chunk)
                    else:
                        await message.reply(reply)

                # 3. Tell Piper to generate the voice file
                try:
                    await session.post("http://127.0.0.1:8000/api/voice", json={"text": reply, "emotion": mood})
                except Exception:
                    pass
        except Exception as e:
            print(f"𓂀 [DISCORD ERROR]: Cognitive Core disconnected or failed: {e}")
            
    else:
        # Passive memory scraper
        payload = {"message": message.content.strip(), "username": message.author.name, "platform": "discord"}
        if not payload["message"]: return
        try:
            async with aiohttp.ClientSession() as session:
                await session.post("http://127.0.0.1:8000/api/memory", json=payload)
        except:
            pass

client.run(os.getenv('DISCORD_BOT_TOKEN'))