import os, asyncio, datetime, re, pickle, random, textwrap, time, shutil
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from moviepy.editor import *
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from duckduckgo_search import DDGS
import google.generativeai as genai
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
import schedule

CHANNEL_NAME = "Future AI Toolkit"
PRIVACY = "private"
RESOLUTION = (1920, 1080)
FPS = 30
INTRO_DURATION = 3
OUTRO_DURATION = 8
DISCLAIMER = "Disclaimer: This video is for educational purposes only. Not financial advice."
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PROFILE_PIC = "assets/profile.png"

PEXELS_KEY = os.getenv("PEXELS_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]
CREDENTIALS_FILE = "client_secrets.json"
TOKEN_FILE = "token.pickle"
VIDEO_CATEGORY = "27"

TOPICS = [
    "Best Cash Back Credit Cards 2026 - Hidden Benefits Nobody Tells You",
    "Top 5 ETFs for Passive Income 2026 - Build Wealth While You Sleep",
    "Roth IRA Secrets 2026 - How to Retire Early Tax Free",
    "Chase Sapphire vs Amex Platinum 2026 - Which Card Wins",
    "How to Stack Credit Card Rewards Like a Pro in 2026",
    "I Bonds vs Treasury Bills 2026 - Where to Put Your Money",
    "Index Fund Investing for Beginners 2026 - Complete Guide",
]

# ================== ASSET GENERATION ==================
def get_profile_clip(size=(120,120)):
    if os.path.exists(PROFILE_PIC):
        img = Image.open(PROFILE_PIC).convert("RGBA").resize(size, Image.LANCZOS)
        mask = Image.new("L", size, 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, size[0], size[1]), fill=255)
        img.putalpha(mask)
        return ImageClip(np.array(img))
    else:
        initials = ''.join(word[0].upper() for word in CHANNEL_NAME.split()[:2])
        img = Image.new("RGBA", size, (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((2,2,size[0]-2,size[1]-2), fill=(50,50,50,255))
        font = ImageFont.truetype(FONT_BOLD, 50)
        draw.text((size[0]//2, size[1]//2), initials, fill="white", font=font, anchor="mm")
        return ImageClip(np.array(img))

def create_intro():
    profile = get_profile_clip((120,120)).set_position((40,40)).set_duration(INTRO_DURATION)
    txt = TextClip(CHANNEL_NAME, fontsize=80, font=FONT_BOLD, color='white',
                   stroke_color='black', stroke_width=3)
    txt = txt.set_position('center').set_duration(INTRO_DURATION).crossfadein(0.5).crossfadeout(0.5)
    bg = ColorClip(RESOLUTION, color=(10, 40, 30)).set_duration(INTRO_DURATION)
    intro = CompositeVideoClip([bg, txt, profile])
    intro.write_videofile("assets/intro.mp4", fps=FPS, logger=None)

def create_outro():
    profile = get_profile_clip((100,100)).set_position((RESOLUTION[0]//2 - 50, 300)).set_duration(OUTRO_DURATION)
    txt = TextClip("Subscribe for more!", fontsize=70, font=FONT_BOLD, color='white',
                   stroke_color='black', stroke_width=3)
    txt = txt.set_position(('center', 450)).set_duration(OUTRO_DURATION).crossfadein(0.5).crossfadeout(0.5)
    bg = ColorClip(RESOLUTION, color=(10, 40, 30)).set_duration(OUTRO_DURATION)
    outro = CompositeVideoClip([bg, txt, profile])
    outro.write_videofile("assets/outro.mp4", fps=FPS, logger=None)

def create_thumbnail_base():
    img = Image.new('RGB', (1280, 720), color=(20, 60, 40))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_BOLD, 50)
    draw.text((40, 40), CHANNEL_NAME, fill="gold", font=font, stroke_width=2, stroke_fill="black")
    img.save("assets/thumbnail_base.png")

def ensure_assets():
    os.makedirs("assets", exist_ok=True)
    if not os.path.exists("assets/intro.mp4"):
        create_intro()
    if not os.path.exists("assets/outro.mp4"):
        create_outro()
    if not os.path.exists("assets/thumbnail_base.png"):
        create_thumbnail_base()

# ================== THUMBNAIL ==================
def create_thumbnail(title, hook_text="", output_path="thumbnail.jpg"):
    base = Image.open("assets/thumbnail_base.png")
    draw = ImageDraw.Draw(base)
    font_large = ImageFont.truetype(FONT_BOLD, 65)
    font_small = ImageFont.truetype(FONT_BOLD, 45)
    if hook_text:
        lines = textwrap.wrap(hook_text[:80], width=22)
        y = 120
        for line in lines[:3]:
            draw.text((60, y), line, fill="white", font=font_large, stroke_width=2, stroke_fill="black")
            y += 80
    title_lines = textwrap.wrap(title[:100], width=28)
    y = 500
    for line in title_lines[:2]:
        draw.text((60, y), line, fill="yellow", font=font_small, stroke_width=2, stroke_fill="black")
        y += 60
    base.save(output_path)
    return output_path

# ================== WEB SEARCH ==================
def web_search(query, max_results=8):
    try:
        with DDGS() as ddgs:
            results = [r['body'] for r in ddgs.text(query, max_results=max_results)]
            return "\n".join(results)
    except Exception as e:
        print(f"Web search failed: {e}")
        return f"Finance tips for {query}."

# ================== SCRIPT GENERATION ==================
SCRIPT_PROMPT = '''You are a top US finance YouTuber creating a VIRAL video script.
Topic: "{topic}"
Research Facts: {facts}

Write a detailed 800-1000 word script. Use EXACTLY this structure with these EXACT labels:

HOOK: [Write a shocking stat or question that grabs attention in 2-3 sentences]

POINT 1: [First major point - write 3-4 sentences explaining clearly]
BROLL: [3 keywords for stock footage separated by commas]
TEXT: [One bold text overlay - max 8 words]

POINT 2: [Second major point - write 3-4 sentences]
BROLL: [3 keywords for stock footage]
TEXT: [One bold text overlay - max 8 words]

POINT 3: [Third major point - write 3-4 sentences]
BROLL: [3 keywords for stock footage]
TEXT: [One bold text overlay - max 8 words]

POINT 4: [Fourth major point - write 3-4 sentences]
BROLL: [3 keywords for stock footage]
TEXT: [One bold text overlay - max 8 words]

POINT 5: [Fifth major point - write 3-4 sentences]
BROLL: [3 keywords for stock footage]
TEXT: [One bold text overlay - max 8 words]

CONCLUSION: [Strong summary with CTA to subscribe - 3-4 sentences]

Rules:
- Total script must be 800-1000 words
- Use simple conversational American English
- Each point must have real actionable advice
- Hook must mention a specific number or stat
- End with "Disclaimer: This video is for educational purposes only. Not financial advice."
'''

def generate_script_gemini(topic, facts):
    models = ["gemini-2.0-flash", "gemini-1.5-flash-latest"]
    for model_name in models:
        for attempt in range(2):
            try:
                print(f"Trying Gemini {model_name}...")
                model = genai.GenerativeModel(model_name)
                prompt = SCRIPT_PROMPT.format(topic=topic, facts=facts[:2000])
                response = model.generate_content(prompt)
                print(f"✅ Gemini success: {model_name}")
                return response.text
            except Exception as e:
                err = str(e)
                if "429" in err or "ResourceExhausted" in err:
                    wait = 30 * (attempt + 1)
                    print(f"Gemini quota, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"Gemini error: {err[:80]}")
                    break
    return None

def generate_script_openrouter(topic, facts):
    if not OPENROUTER_KEY:
        return None
    models = [
        "mistralai/mistral-7b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "google/gemma-3-4b-it:free"
    ]
    for model in models:
        try:
            print(f"Trying OpenRouter {model}...")
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/mysteryhelper/tiger-pipeline"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": SCRIPT_PROMPT.format(topic=topic, facts=facts[:2000])}],
                    "max_tokens": 2000
                },
                timeout=60
            )
            result = resp.json()
            if 'choices' in result and result['choices']:
                print(f"✅ OpenRouter success: {model}")
                return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"OpenRouter {model} error: {e}")
            continue
    return None

def generate_script(topic, research_data):
    facts = web_search(f"latest {topic} tips guide USA 2026 finance")
    
    script = generate_script_gemini(topic, facts)
    if script:
        return script
    
    print("Gemini failed → trying OpenRouter...")
    script = generate_script_openrouter(topic, facts)
    if script:
        return script
    
    print("⚠️ All AI failed → basic fallback")
    points = [f.strip() for f in facts.split('\n') if len(f.strip()) > 60][:5]
    s = f"HOOK: Did you know most Americans are missing out on thousands of dollars every year? Today we reveal the truth about {topic}.\n\n"
    for i, p in enumerate(points, 1):
        s += f"POINT {i}: {p[:250]}\nBROLL: finance, money, investing\nTEXT: Key Tip #{i}\n\n"
    s += f"CONCLUSION: That covers everything you need to know about {topic}. Hit subscribe for daily finance tips that can change your life.\n\n{DISCLAIMER}"
    return s

# ================== PARSE SCRIPT ==================
def parse_script(script_text):
    parts = []
    lines = script_text.split('\n')
    current_point = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if re.match(r'^HOOK\s*:', line, re.I):
            text = line.split(':', 1)[1].strip() if ':' in line else ''
            if text:
                parts.append({"type": "hook", "text": text})
        
        elif re.match(r'^POINT\s*\d+\s*:', line, re.I):
            if current_point and current_point.get('text'):
                parts.append(current_point)
            text = line.split(':', 1)[1].strip() if ':' in line else ''
            current_point = {"type": "point", "text": text, "broll": [], "text_overlay": ""}
        
        elif re.match(r'^BROLL\s*:', line, re.I) and current_point is not None:
            kw = line.split(':', 1)[1].strip()
            current_point['broll'] = [k.strip() for k in kw.split(',') if k.strip()]
        
        elif re.match(r'^TEXT\s*:', line, re.I) and current_point is not None:
            current_point['text_overlay'] = line.split(':', 1)[1].strip()
        
        elif re.match(r'^CONCLUSION\s*:', line, re.I):
            if current_point and current_point.get('text'):
                parts.append(current_point)
                current_point = None
            text = line.split(':', 1)[1].strip() if ':' in line else ''
            if text:
                parts.append({"type": "conclusion", "text": text})
        
        else:
            # Multi-line text append
            if current_point is not None and line and not re.match(r'^(BROLL|TEXT|POINT|HOOK|CONCLUSION)\s*:', line, re.I):
                current_point['text'] = current_point.get('text', '') + ' ' + line
            elif parts and parts[-1]['type'] in ['hook', 'conclusion'] and line:
                parts[-1]['text'] = parts[-1].get('text', '') + ' ' + line
    
    if current_point and current_point.get('text'):
        parts.append(current_point)
    
    print(f"✅ Parsed {len(parts)} sections")
    return parts

# ================== SEO METADATA ==================
def generate_seo_metadata(narration, topic):
    prompt = f"""YouTube SEO expert. Create viral metadata for finance video.
Topic: {topic}
Script excerpt: {narration[:500]}

Output EXACTLY:
TITLE: [title with number + power word + 2026, under 60 chars]
DESCRIPTION: [2-3 sentences with keywords + CTA + disclaimer]
TAGS: tag1, tag2, tag3, tag4, tag5, tag6, tag7, tag8, tag9, tag10"""

    # Try Gemini
    if GEMINI_KEY:
        for model_name in ["gemini-2.0-flash", "gemini-1.5-flash-latest"]:
            try:
                model = genai.GenerativeModel(model_name)
                return model.generate_content(prompt).text
            except:
                continue
    
    # Try OpenRouter
    if OPENROUTER_KEY:
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
                json={"model": "mistralai/mistral-7b-instruct:free", "messages": [{"role": "user", "content": prompt}], "max_tokens": 300},
                timeout=30
            )
            result = resp.json()
            if 'choices' in result:
                return result['choices'][0]['message']['content']
        except:
            pass
    
    return f"TITLE: {topic[:55]} 2026\nDESCRIPTION: Discover the secrets of {topic}. Subscribe for more finance tips.\nTAGS: {topic}, finance, money, investing, 2026, credit cards, ETF, passive income, wealth, tips"

def parse_seo_output(seo_text):
    title = desc = ""
    tags = []
    desc_lines = []
    mode = None
    for line in seo_text.split('\n'):
        if line.startswith("TITLE:"):
            title = line[6:].strip()
        elif line.startswith("DESCRIPTION:"):
            mode = "desc"
            desc_lines.append(line[12:].strip())
        elif line.startswith("TAGS:"):
            if mode == "desc":
                desc = " ".join(desc_lines)
                mode = None
            tags = [t.strip() for t in line[5:].split(",")]
        elif mode == "desc":
            desc_lines.append(line.strip())
    if mode == "desc":
        desc = " ".join(desc_lines)
    return title, desc, tags

# ================== TTS ==================
async def generate_tts(text, voice="en-US-ChristopherNeural", output="temp_audio.mp3"):
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output)
        print(f"✅ TTS generated: {output}")
        return output
    except Exception as e:
        print(f"❌ TTS failed: {e}")
        word_count = len(text.split())
        duration = max(30, word_count / 2.5)
        clip = AudioClip(lambda t: [0, 0], duration=duration, fps=44100)
        clip.write_audiofile(output, logger=None)
        return output

# ================== STOCK FOOTAGE ==================
def download_stock_clips_pexels(keywords, output_dir="temp_broll"):
    os.makedirs(output_dir, exist_ok=True)
    if not PEXELS_KEY:
        return []
    headers = {"Authorization": PEXELS_KEY}
    clips = []
    for kw in keywords:
        try:
            resp = requests.get(
                f"https://api.pexels.com/videos/search?query={kw}&per_page=3&size=large",
                headers=headers, timeout=15
            )
            if resp.status_code != 200:
                continue
            for video in resp.json().get('videos', []):
                for file in video['video_files']:
                    if file.get('width', 0) >= 1280:
                        url = file['link']
                        fname = f"{output_dir}/{kw.replace(' ', '_')}.mp4"
                        if not os.path.exists(fname):
                            r = requests.get(url, timeout=60)
                            with open(fname, 'wb') as f:
                                f.write(r.content)
                        clips.append(fname)
                        break
        except Exception as e:
            print(f"Pexels error for {kw}: {e}")
    return clips

# ================== VIDEO ASSEMBLY ==================
def build_video(parsed_script, audio_path, broll_clips, output="final_video.mp4"):
    intro = VideoFileClip("assets/intro.mp4").resize(RESOLUTION)
    outro = VideoFileClip("assets/outro.mp4").resize(RESOLUTION)
    voice = AudioFileClip(audio_path)
    total_audio_dur = voice.duration
    print(f"Audio duration: {total_audio_dur:.1f}s")

    available_clips = []
    for path in broll_clips:
        try:
            clip = VideoFileClip(path).without_audio().resize(RESOLUTION)
            available_clips.append(clip)
        except Exception as e:
            print(f"Clip error {path}: {e}")

    if not available_clips:
        bg = ColorClip(RESOLUTION, (20, 20, 40)).set_duration(total_audio_dur)
        available_clips = [bg]

    loop_parts = []
    acc_dur = 0
    while acc_dur < total_audio_dur:
        for cl in available_clips:
            loop_parts.append(cl)
            acc_dur += cl.duration
            if acc_dur >= total_audio_dur:
                break

    long_broll = concatenate_videoclips(loop_parts).subclip(0, total_audio_dur).resize(RESOLUTION)

    sections = [p for p in parsed_script if p['type'] in ['hook', 'point', 'conclusion']]
    total_chars = sum(len(p.get('text', '')) for p in sections) or 1
    time_pos = 0
    text_clips = []

    for part in sections:
        part_duration = (len(part.get('text', '')) / total_chars) * total_audio_dur
        overlay_text = part.get('text_overlay', '').strip()
        if overlay_text:
            try:
                overlay = TextClip(
                    overlay_text, fontsize=55, font=FONT_BOLD,
                    color='white', stroke_color='black', stroke_width=2,
                    method='caption', size=(1700, None)
                )
                overlay = overlay.set_position(('center', 0.82), relative=True)\
                                 .set_start(time_pos).set_duration(part_duration)\
                                 .crossfadein(0.3)
                text_clips.append(overlay)
            except Exception as e:
                print(f"Text overlay error: {e}")
        time_pos += part_duration

    content_video = CompositeVideoClip([long_broll] + text_clips).set_duration(total_audio_dur)
    final = concatenate_videoclips([intro, content_video, outro])
    audio_content = CompositeAudioClip([voice.set_start(INTRO_DURATION)])
    final = final.set_audio(audio_content)
    final.write_videofile(output, codec="libx264", audio_codec="aac", fps=FPS, logger=None)
    return output

# ================== YOUTUBE UPLOAD ==================
def get_authenticated_service():
    credentials = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            credentials = pickle.load(token)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(credentials, token)
    return build('youtube', 'v3', credentials=credentials)

def upload_video(video_file, title, description, tags, thumbnail_file=None):
    youtube = get_authenticated_service()
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': VIDEO_CATEGORY
        },
        'status': {
            'privacyStatus': PRIVACY,
            'selfDeclaredMadeForKids': False,
        }
    }
    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    video_id = response['id']
    print(f"✅ Uploaded: https://youtu.be/{video_id}")
    if thumbnail_file and os.path.exists(thumbnail_file):
        youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumbnail_file)).execute()
    return video_id

# ================== MAIN PIPELINE ==================
async def create_and_upload_video(topic):
    print(f"\n🐯 TIGER starting: {topic}\n")

    print("📝 Generating script...")
    raw_script = generate_script(topic, {})
    parsed = parse_script(raw_script)
    
    if not parsed:
        print("❌ Parse failed!")
        return

    narration_parts = [p.get('text', '') for p in parsed if p['type'] in ['hook', 'point', 'conclusion']]
    full_narration = ' '.join(narration_parts) + ' ' + DISCLAIMER
    print(f"📊 Narration length: {len(full_narration.split())} words")

    print("🎯 Generating SEO metadata...")
    seo_raw = generate_seo_metadata(full_narration, topic)
    seo_title, seo_desc, seo_tags = parse_seo_output(seo_raw)
    
    if not seo_title:
        seo_title = f"{topic[:55]} 2026"
    if not seo_desc:
        seo_desc = f"Learn everything about {topic}. {DISCLAIMER}"
    if not seo_tags:
        seo_tags = ["finance", "money", "investing", "2026", "credit cards", "ETF", "wealth"]
    
    print(f"Title: {seo_title}")

    print("🎙️ Generating voiceover...")
    audio_file = await generate_tts(full_narration)

    broll_keywords = []
    for part in parsed:
        if part['type'] == 'point' and part.get('broll'):
            broll_keywords.extend(part['broll'])
    if not broll_keywords:
        broll_keywords = ["money", "finance", "investing", "credit card", "stock market"]
    broll_keywords = list(set(broll_keywords))[:6]

    print("🎬 Downloading stock clips...")
    clips = download_stock_clips_pexels(broll_keywords)
    print(f" Got {len(clips)} clips")

    print("🎞️ Assembling video...")
    video_path = "output_video.mp4"
    build_video(parsed, audio_file, clips, video_path)

    hook_line = next((p['text'] for p in parsed if p['type'] == 'hook'), "")
    print("🖼️ Creating thumbnail...")
    thumb_path = create_thumbnail(seo_title, hook_line[:80])

    print("📤 Uploading to YouTube...")
    upload_video(video_path, seo_title, seo_desc, seo_tags, thumb_path)

    if os.path.exists(audio_file):
        os.remove(audio_file)
    if os.path.exists("temp_broll"):
        shutil.rmtree("temp_broll")
    
    print("✅ Done!")

def run_daily_pipeline():
    ensure_assets()
    today_topic = TOPICS[datetime.date.today().weekday() % len(TOPICS)]
    print(f"Today's topic: {today_topic}")
    asyncio.run(create_and_upload_video(today_topic))

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--manual":
        print("🐯 TIGER manual run...")
        run_daily_pipeline()
    else:
        schedule.every().day.at("06:00").do(run_daily_pipeline)
        print("🐯 TIGER scheduler started. Runs daily at 6 AM.")
        while True:
            schedule.run_pending()
            time.sleep(60)
